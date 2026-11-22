import {readFileSync,writeFileSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
const hash=file=>createHash('sha256').update(readFileSync(`app/${file}`)).digest('hex').slice(0,12);
// Dependencies first, then modules that refer to them, then HTML entry points.
const modules=['certificate-worker.js','verify-worker.js','certificate-session.js','seals.js','trust.js','app.js'];
for(const file of [...modules,...readdirSync('app').filter(f=>f.endsWith('.html'))]){
 let text=readFileSync(`app/${file}`,'utf8');
 text=text.replace(/(["'])\/((?:vendor\/)?[a-zA-Z0-9_.-]+\.(?:css|m?js))(?:\?[^"']*)?\1/g,(all,q,asset)=>`${q}/${asset}?v=${hash(asset)}${q}`);
 writeFileSync(`app/${file}`,text);
}
console.log('Versioned local assets.');
