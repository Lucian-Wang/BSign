const $=id=>document.getElementById(id);
let lang=localStorage.getItem('bsign-language')||'en',csrf='',user=null,rows=[];
let verification=null,selectedPdf=null;
const t=(en,zh)=>lang==='zh'?zh:en;
function translate(){document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-en]').forEach(e=>e.textContent=e.dataset[lang]||e.dataset.en);$('lang').textContent=lang==='zh'?'EN':'中文';localStorage.setItem('bsign-language',lang);if($('list'))render();if($('verify')&&typeof renderVerification==='function')renderVerification();}
async function api(path,method='GET',body){const r=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body?JSON.stringify(body):undefined});if(!r.ok){const q=await r.json();throw Error(q.detail||'Request failed');}return r.json();}
$('lang').onclick=async()=>{lang=lang==='zh'?'en':'zh';translate();if(user)try{await api('/preferences','PATCH',{language:lang});}catch{}};
function el(tag,text,cls){const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;}
translate();
if($('create')){
 $('new-certificate').onclick=()=>{$('error').textContent='';$('create-dialog').showModal();$('name').focus();};$('close-create').onclick=()=>{$('create-dialog').close();$('create').reset();};$('create-dialog').addEventListener('close',()=>{$('create').reset();});
 try{const q=await api('/me');user=q.user;csrf=q.csrf;if(user.language)lang=user.language;translate();if(user.role!=='user')throw Error(t('Administrators manage users only.','管理员仅管理用户，不能访问证书。'));$('manage').hidden=false;$('session').textContent=user.email;rows=await api('/certificates');render();}catch(e){$('session').textContent=t('Please sign in with a user account in the workspace. ','请先在工作台登录普通用户账号。 ')+e.message;}
 $('create').onsubmit=async e=>{e.preventDefault();$('error').textContent='';if($('password').value!==$('confirm').value){$('error').textContent=t('Passwords do not match.','两次密码不一致。');return;}$('generate').disabled=true;try{await api('/certificates','POST',{name:$('name').value,password:$('password').value,acknowledge:$('ack').checked});$('create').reset();rows=await api('/certificates');render();$('create-dialog').close();$('certificate-feedback').textContent=t('Certificate created. Download a backup and keep your password safe.','证书已生成。建议下载备份，并妥善保存密码。');}catch(e){$('error').textContent=e.message;}finally{$('generate').disabled=false;}};
}
function render(){const list=$('list');list.replaceChildren();if(!rows.length){const empty=el('div','','cert-empty');empty.append(el('span','◇','cert-icon'),el('h3',t('Your first certificate starts here','创建你的第一张证书')),el('p',t('Create a certificate, then select it when exporting a PDF.','点击“新建证书”，生成后即可在导出 PDF 时使用。')));list.append(empty);return;}for(const row of rows){const card=el('article','','certificate-card');const top=el('div','','cert-card-top'),title=el('div');title.append(el('h3',row.name),el('p',row.source==='bsign-ca'?t('BSign Community private CA · Identity not verified','BSign Community 私有 CA · 未验证身份'):row.source==='imported'?t('Imported certificate','自行导入证书'):t('Legacy self-signed · Identity not verified','旧版自签名 · 未验证身份'),'cert-type'));const expired=row.expires*1000<Date.now();top.append(el('span','◇','cert-icon'),title,el('span',expired?t('Expired','已过期'):t('Active','有效期内'),'cert-state'+(expired?' expired':'')));const meta=el('div','','cert-meta');for(const [label,value] of [[t('Created','创建日期'),row.created],[t('Valid until','有效期至'),row.expires]]){const cell=el('div');cell.append(el('span',label),el('strong',new Date(value*1000).toLocaleDateString()));meta.append(cell);}card.append(top,meta,el('p','SHA-256  '+row.fingerprint,'fingerprint'));const actions=el('div','','actions');const download=el('a',t('Download P12','下载 P12 证书'),'secondary');download.href='/api/certificates/'+row.id+'/download';download.download='BSign-'+row.id+'.p12';const del=el('button',t('Delete','删除'),'danger');del.onclick=async()=>{if(!confirm(t('Delete this encrypted server copy? Downloaded copies and existing PDF signatures remain usable. This does not revoke the certificate.','删除服务器中的加密副本？已下载的证书及已有 PDF 签名仍然有效，此操作不等于撤销证书。')))return;del.disabled=true;try{await api('/certificates/'+row.id,'DELETE');rows=await api('/certificates');render();}catch(e){$('certificate-feedback').textContent=e.message;del.disabled=false;}};actions.append(download,del);card.append(actions);list.append(card);}}

function renderVerification(){
 const box=$('result');if(!box||!verification)return;
 const {result,expected,error,busy}=verification;
 const match=result?.status==='intact'&&(!expected||expected===result.fingerprint);
 const messages={unsigned:[t('No digital signature found','未发现数字签名'),t('Integrity cannot be confirmed for this document.','无法确认这份文件在签署后是否被修改。')],unsupported:[t('Signature not supported','暂不支持此签名'),t('This signature structure or algorithm cannot be checked here.','暂不支持此签名结构或算法，无法得出完整性结论。')],invalid:[t('Verification failed','验证失败'),t('The signature or signed data does not match. The file may have been altered or damaged.','签名或所签内容不匹配，文件可能已被修改或损坏。')],modified:[t('Additional data found','发现签署后追加的数据'),t('The signature does not cover the entire current PDF. Integrity cannot be confirmed.','签名未覆盖当前整份 PDF，无法确认当前文件未被修改。')]};
 let title,description;
 if(busy){title=t('Checking your PDF…','正在验证 PDF…');description=t('Processing locally in your browser.','正在浏览器内检查，请稍候。');}
 else if(error){title=t('Unable to verify','暂时无法验证');description=error==='file'?t('Choose a PDF up to 100 MB.','请选择不超过 100 MB 的 PDF。'):error==='fingerprint'?t('Enter a valid 64-digit SHA-256 fingerprint.','请输入有效的 64 位 SHA-256 指纹。'):t('Unable to complete verification. No integrity conclusion can be made.','未能完成验证，无法得出完整性结论。');}
 else if(result.status==='intact'){title=match?t('Integrity verified','完整性验证通过'):t('Certificate fingerprint mismatch','证书指纹不匹配');description=match?t('The signature covers the entire PDF. The signed data has not changed.','签名覆盖整份 PDF，所签内容未被修改。'):t('The signature is internally valid, but the certificate is not the one you expected.','文件内部签名校验通过，但使用的并非你指定的证书。');}
 else [title,description]=messages[result.status]||messages.unsupported;
 box.hidden=false;box.className='trust-card result verification-result '+(match?'success':'warning');box.replaceChildren();
 const banner=el('div','','result-banner'),heading=el('div');heading.append(el('h2',title),el('p',description));banner.append(el('span',busy?'…':match?'✓':'!','result-symbol'),heading);box.append(banner);
 if(result?.status!=='intact')return;
 const body=el('div','','result-body'),statuses=el('div','','result-status-grid');
 for(const [label,value] of [[t('Signer identity','签署人身份'),t('Not verified','未验证')],[t('Known fingerprint','已知指纹核对'),expected?(match?t('Matched','一致'):t('Does not match','不一致')):t('Not provided','未提供')]]){const cell=el('div','','result-status');cell.append(el('span',label),el('strong',value));statuses.append(cell);}
 const meta=el('dl','','result-meta');for(const [label,value,cls] of [[t('Certificate subject · Self-declared','证书主体 · 自行声明'),result.subject,''],[t('Certificate validity','证书有效期'),result.from.slice(0,10)+' — '+result.until.slice(0,10),''],['SHA-256',result.fingerprint,'fingerprint']]){const row=el('div');row.append(el('dt',label),el('dd',value,cls));meta.append(row);}
 body.append(statuses,meta,el('p',t('Certificate trust, revocation and trusted timestamps have not been checked.','未验证证书信任、吊销状态或可信时间戳。')+(!expected?' '+t('Without an independent fingerprint, replacement and re-signing cannot be ruled out.','未提供独立取得的已知指纹，不能排除文件被替换后重新签署。'):''),'result-footnote'));box.append(body);
}
if($('verify')){
 const choose=file=>{selectedPdf=file;verification=null;$('result').hidden=true;$('picked-file').hidden=!file;$('picked-file').textContent=file?file.name+' · '+(file.size/1024/1024).toFixed(2)+' MB':'';};
 $('pdf').onchange=()=>choose($('pdf').files[0]);
 const drop=$('pdf-drop');drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('drag-over');});drop.addEventListener('dragleave',()=>drop.classList.remove('drag-over'));drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('drag-over');if(!$('verify').disabled){$('pdf').value='';choose(e.dataTransfer.files[0]);}});
 $('expected').addEventListener('input',()=>{verification=null;$('result').hidden=true;});
 $('verify').onclick=async()=>{
 const file=selectedPdf,expected=$('expected').value.replace(/[\s:]/g,'').toLowerCase();
 if(!file||file.size>100*1024*1024||!file.name.toLowerCase().endsWith('.pdf')){verification={error:'file'};renderVerification();return;}
 if(expected&&!/^[a-f0-9]{64}$/.test(expected)){verification={error:'fingerprint'};renderVerification();return;}
 $('verify').disabled=true;$('pdf').disabled=true;$('expected').disabled=true;verification={busy:true};renderVerification();let worker;
 try{worker=new Worker('/verify-worker.js?v=97a4498710ff',{type:'module'});const bytes=await file.arrayBuffer();const result=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('timeout')),60000);worker.onmessage=e=>{clearTimeout(timeout);resolve(e.data);};worker.onerror=()=>{clearTimeout(timeout);reject(Error('worker'));};worker.postMessage(bytes,[bytes]);});verification={result,expected};}
 catch{verification={error:'failed'};}
 finally{worker?.terminate();$('verify').disabled=false;$('pdf').disabled=false;$('expected').disabled=false;renderVerification();}
 };
}

if($('import-form')){
 $('import-certificate').onclick=()=>{$('import-error').textContent='';$('import-dialog').showModal();};
 $('close-import').onclick=()=>$('import-dialog').close();$('import-dialog').addEventListener('close',()=>$('import-form').reset());
 $('import-form').onsubmit=async e=>{e.preventDefault();const file=$('import-file').files[0];if(!file||file.size>2*1024*1024){$('import-error').textContent=t('Choose a P12/PFX file up to 2 MB.','请选择不超过 2 MB 的 P12/PFX 文件。');return;}$('import-submit').disabled=true;$('close-import').disabled=true;$('import-error').textContent='';try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));await api('/certificates/import','POST',{name:$('import-name').value.trim(),password:$('import-password').value,file:btoa(binary)});rows=await api('/certificates');render();$('import-dialog').close();$('certificate-feedback').textContent=t('Certificate imported. You can now select it when exporting a PDF.','证书已导入，可在导出 PDF 时选择使用。');}catch(e){$('import-error').textContent=t('Import failed. Check your file and password. ','导入失败，请检查文件和密码。 ')+e.message;}finally{$('import-password').value='';$('import-submit').disabled=false;$('close-import').disabled=false;}};
}
