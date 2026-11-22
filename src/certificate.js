import {certificateIssuer} from './x509.js';
import forge from 'node-forge';
import {Buffer} from 'buffer';
import {SignPdf, Signer} from '@signpdf/signpdf';
import {pdflibAddPlaceholder} from '@signpdf/placeholder-pdf-lib';
import {PDFDocument} from 'pdf-lib';
function fail(code){throw Error(code);}
function checkCertificate(cert){const now=new Date();if(now<cert.validity.notBefore||now>cert.validity.notAfter)fail('CERT_EXPIRED');const usage=cert.getExtension('keyUsage');if(usage&&!usage.digitalSignature&&!usage.nonRepudiation)fail('CERT_USAGE');if(cert.getExtension('basicConstraints')?.cA)fail('CERT_CA');}
export function readCertificate(bytes,password){
 let p12;try{p12=forge.pkcs12.pkcs12FromAsn1(forge.asn1.fromDer(forge.util.createBuffer(bytes)),true,password);}catch{fail('CERT_OPEN');}
 const keys=[...(p12.getBags({bagType:forge.pki.oids.pkcs8ShroudedKeyBag})[forge.pki.oids.pkcs8ShroudedKeyBag]||[]),...(p12.getBags({bagType:forge.pki.oids.keyBag})[forge.pki.oids.keyBag]||[])];
 if(keys.length!==1||!keys[0].key?.n)fail('CERT_RSA');const key=keys[0].key;if(key.n.bitLength()<2048)fail('CERT_WEAK');
 const certs=(p12.getBags({bagType:forge.pki.oids.certBag})[forge.pki.oids.certBag]||[]).map(b=>b.cert).filter(Boolean);
 const matching=certs.filter(c=>c.publicKey.n?.equals(key.n)&&c.publicKey.e?.equals(key.e));if(matching.length!==1)fail('CERT_MATCH');const certificate=matching[0];checkCertificate(certificate);
 const label=a=>a?.valueTagClass===12?forge.util.decodeUtf8(a.value):a?.value;
 const field=(name)=>certificate[name].attributes.map(a=>`${a.shortName||a.name||a.type}=${label(a)}`).join(', ');
 return {key,certificate,certs,info:{subject:field('subject'),issuer:field('issuer'),name:label(certificate.subject.getField('CN'))||field('subject'),from:certificate.validity.notBefore.toISOString(),until:certificate.validity.notAfter.toISOString(),fingerprint:forge.md.sha256.create().update(forge.asn1.toDer(forge.pki.certificateToAsn1(certificate)).getBytes()).digest().toHex()}};
}
class LocalSigner extends Signer{
 constructor(identity){super();this.identity=identity;}
 async sign(pdf,when){const {key,certificate,certs}=this.identity;checkCertificate(certificate);const p7=forge.pkcs7.createSignedData();p7.content=forge.util.createBuffer(pdf.toString('binary'));certs.forEach(c=>p7.addCertificate(c));p7.addSigner({key,certificate,digestAlgorithm:forge.pki.oids.sha256,authenticatedAttributes:[{type:forge.pki.oids.contentType,value:forge.pki.oids.data},{type:forge.pki.oids.signingTime,value:when},{type:forge.pki.oids.messageDigest}]});p7.sign({detached:true});const asn=p7.toAsn1();asn.value[1].value[0].value.at(-1).value[0].value[1].value[0]=certificateIssuer(certificate);return Buffer.from(forge.asn1.toDer(asn).getBytes(),'binary');}
}
export async function signPdf(bytes,identity){checkCertificate(identity.certificate);const doc=await PDFDocument.load(bytes);const when=new Date();const size=Math.max(32768,identity.certs.reduce((n,c)=>n+forge.asn1.toDer(forge.pki.certificateToAsn1(c)).length(),0)*4+8192);pdflibAddPlaceholder({pdfDoc:doc,reason:'Signed with the certificate holder’s own certificate',contactInfo:'',name:identity.info.name,location:'',signingTime:when,signatureLength:size,appName:'BSign'});const prepared=await doc.save({useObjectStreams:false});return new Uint8Array(await new SignPdf().sign(Buffer.from(prepared),new LocalSigner(identity),when));}
