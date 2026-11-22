import {verifyPdf} from '/vendor/verify.mjs?v=b80c1f90f872';
self.onmessage=({data})=>{try{self.postMessage(verifyPdf(data));}catch{self.postMessage({status:'unsupported'});}};
