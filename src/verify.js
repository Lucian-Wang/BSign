import {certificateIssuer} from './x509.js';
import forge from 'node-forge';
const oid=n=>forge.asn1.derToOid(n.value);
const der=n=>forge.asn1.toDer(n).getBytes();
// Deliberately limited to one detached RSA/SHA-256 signature covering the entire file.
// Unsupported structures must never be reported as verified.
export function verifyPdf(bytes){
 const text=forge.util.createBuffer(bytes).getBytes();
 const hits=[...text.matchAll(/\/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]/g)];
 if(!hits.length)return {status:'unsigned'};
 if(hits.length!==1)return {status:'unsupported'};
 try{
  const [a,b,c,d]=hits[0].slice(1).map(Number);
  if(![a,b,c,d].every(Number.isSafeInteger)||a!==0||b<=0||c<=b||d<0||c+d>text.length)return {status:'invalid'};
  if(c+d!==text.length)return {status:'modified'};
  const gap=text.slice(b,c);
  if(!/^<[0-9a-fA-F]+>$/.test(gap)||! /\/Contents\s*$/.test(text.slice(Math.max(0,b-100),b)))return {status:'unsupported'};
  const hex=gap.slice(1,-1);if(hex.length%2)return {status:'invalid'};
  const buffer=forge.util.createBuffer(forge.util.hexToBytes(hex));
  const asn=forge.asn1.fromDer(buffer,{strict:true,parseAllBytes:false});if(!/^\x00*$/.test(buffer.getBytes()))return {status:'invalid'};
  if(oid(asn.value[0])!==forge.pki.oids.signedData)return {status:'unsupported'};
  const data=asn.value[1].value[0],signers=data.value.at(-1);
  if(signers.type!==17||signers.value.length!==1)return {status:'unsupported'};
  const info=signers.value[0].value;
  if(oid(info[2].value[0])!==forge.pki.oids.sha256||info[3].tagClass!==128||info[3].type!==0||oid(info[4].value[0])!==forge.pki.oids.rsaEncryption)return {status:'unsupported'};
  const encap=data.value[2];if(oid(encap.value[0])!==forge.pki.oids.data||encap.value.length!==1)return {status:'unsupported'};
  const msg=forge.pkcs7.messageFromAsn1(asn);
  const sid=info[1];if(sid.type!==16)return {status:'unsupported'};
  const certs=msg.certificates.filter(cert=>der(certificateIssuer(cert))===der(sid.value[0])&&cert.serialNumber.replace(/^00/,'')===forge.util.bytesToHex(sid.value[1].value).replace(/^00/,''));
  if(certs.length!==1||!certs[0].publicKey.n)return {status:'unsupported'};
  const cert=certs[0],attrs=info[3].value;
  const digests=attrs.filter(x=>oid(x.value[0])===forge.pki.oids.messageDigest);
  const types=attrs.filter(x=>oid(x.value[0])===forge.pki.oids.contentType);
  if(digests.length!==1||types.length!==1||types[0].value[1].value.length!==1||oid(types[0].value[1].value[0])!==forge.pki.oids.data||digests[0].value[1].value.length!==1)return {status:'unsupported'};
  const hash=forge.md.sha256.create().update(text.slice(0,b)).update(text.slice(c,c+d)).digest().getBytes();
  if(hash!==digests[0].value[1].value[0].value)return {status:'invalid'};
  const signed=forge.asn1.create(0,17,true,attrs);
  const md=forge.md.sha256.create().update(der(signed));
  if(!cert.publicKey.verify(md.digest().getBytes(),info[5].value))return {status:'invalid'};
  const fingerprint=forge.md.sha256.create().update(der(forge.pki.certificateToAsn1(cert))).digest().toHex();
  return {status:'intact',fingerprint,subject:cert.subject.attributes.map(a=>`${a.shortName||a.name}=${a.valueTagClass===12?forge.util.decodeUtf8(a.value):a.value}`).join(', '),from:cert.validity.notBefore.toISOString(),until:cert.validity.notAfter.toISOString()};
 }catch{return {status:'unsupported'};}
}
