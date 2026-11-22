import forge from 'node-forge';

// Preserve the original issuer Name DER, including UTF-8 and RDN grouping.
// Rebuilding parsed forge attributes double-encodes non-ASCII UTF8String values.
export function certificateIssuer(cert){
 const tbs=forge.pki.certificateToAsn1(cert).value[0].value;
 const hasVersion=tbs[0].tagClass===128&&tbs[0].type===0;
 return tbs[hasVersion?3:2];
}
