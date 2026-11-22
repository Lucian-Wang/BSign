import {build} from 'esbuild';
import {copyFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {dirname,join} from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
process.chdir(root);
await build({absWorkingDir:root,entryPoints:['src/certificate.js'],outfile:'app/vendor/certificate.mjs',bundle:true,format:'esm',platform:'browser',minify:true,inject:['src/buffer-shim.js'],legalComments:'linked'});
copyFileSync(join(dirname(createRequire(import.meta.url).resolve('node-forge/package.json')),'LICENSE'),'app/vendor/node-forge-LICENSE');

await build({absWorkingDir:root,entryPoints:['src/verify.js'],outfile:'app/vendor/verify.mjs',bundle:true,format:'esm',platform:'browser',minify:true,legalComments:'linked'});
