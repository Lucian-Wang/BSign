import {backgroundEditor} from '/background.js?v=a3f24e80e245';
import {visibleArtwork} from '/artwork.js?v=1ae9f03b646e';
const $=id=>document.getElementById(id),t=(en,zh)=>lang==='zh'?zh:en;
let lang=localStorage.getItem('bsign-language')||'en',user=null,csrf='',spaces=[],current='',rows=[],editingSpace=false,pending=null,generation=0,loading=false;
const urls=new Set();
function node(tag,text='',cls=''){const e=document.createElement(tag);e.textContent=text;e.className=cls;return e;}
function message(en,zh){$('feedback').textContent=t(en,zh||en);}
function translate(){document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-en]').forEach(e=>e.textContent=e.dataset[lang]||e.dataset.en);$('lang').textContent=lang==='zh'?'EN':'中文';localStorage.setItem('bsign-language',lang);renderSpaces();renderSeals();}
async function api(path,method='GET',body){const r=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body?JSON.stringify(body):undefined});if(!r.ok){const q=await r.json();throw Error(q.detail||t('Request failed.','操作失败。'));}return r.json();}
function changed(){localStorage.setItem('bsign-library-changed',JSON.stringify({user:user.id,time:Date.now()}));}
function clearUrls(){for(const url of urls)URL.revokeObjectURL(url);urls.clear();}
function kindName(kind){return kind==='round'?t('Round seal','圆章'):kind==='square'?t('Square seal','方章'):t('Signature','签名');}
function renderSpaces(){const box=$('spaces');box.replaceChildren();for(const item of spaces){const b=node('button',item.name,'space-button'+(current===item.id?' active':''));b.setAttribute('aria-pressed',String(current===item.id));b.onclick=()=>selectSpace(item.id);box.append(b);}if(!spaces.length)box.append(node('p',t('Create a company or project to get started.','新建企业或项目，开始整理印章。'),'hint'));$('space-title').textContent=spaces.find(s=>s.id===current)?.name||t('Your seal library','你的印章库');$('space-count').textContent=t('COMPANY / PROJECT','企业 / 项目');for(const id of ['edit-space','use-space','upload-seal','draw-signature'])$(id).disabled=!current||loading;}
function renderSeals(){const box=$('seal-grid');box.replaceChildren();clearUrls();const version=++generation;const search=$('search').value.toLowerCase();const items=rows.filter(r=>r.name.toLowerCase().includes(search));if(loading||!items.length){const empty=node('div','','seal-empty');empty.append(node('h3',loading?t('Loading…','正在加载…'):!current?t('Give your seals a home','先为印章建立一个分组'):search?t('No matching seals','没有找到匹配的印章'):t('Your library starts here','这里还没有印章')),node('p',loading?'':!current?t('Create a company or project on the left.','点击左侧“新建”，创建企业或项目。'):t('Import a seal image or write a signature.','可导入印章图片，也可以手写签名。')));box.append(empty);return;}
 for(const r of items){const card=node('article','','managed-seal'),preview=node('div','','managed-image'),img=node('img');img.alt=r.name;preview.append(img);fetch('/api/stamps/'+r.id+'/image',{credentials:'same-origin'}).then(async res=>{if(!res.ok)throw Error();const blob=await res.blob();if(version!==generation)return;const url=URL.createObjectURL(blob);urls.add(url);const source=await image(url);if(version!==generation)return;const trimmed=visibleArtwork(source);img.src=trimmed?trimmed.toDataURL('image/png'):url;}).catch(()=>{if(version===generation)preview.replaceChildren(node('small',t('Image unavailable','图样暂不可用')));});const info=node('div','','managed-seal-info');info.append(node('h3',r.name),node('small',kindName(r.kind)+' · '+r.width+' × '+r.height+' mm'));const actions=node('div','','actions'),edit=node('button',t('Edit','编辑'),'secondary'),download=node('a',t('Download','下载'),'quiet'),remove=node('button',t('Delete','删除'),'danger');edit.onclick=()=>openSeal(r).catch(e=>message(e.message));download.href='/api/stamps/'+r.id+'/image';download.download=r.name+'.png';remove.onclick=async()=>{if(!confirm(t('Delete this saved seal? Existing PDF placements are not removed.','删除此印章？已放在 PDF 上的签章不会被移除。')))return;remove.disabled=true;try{await api('/stamps/'+r.id,'DELETE');changed();await selectSpace(current);message('Seal deleted.','印章已删除。');}catch(e){message(e.message);remove.disabled=false;}};actions.append(edit,download,remove);info.append(actions);card.append(preview,info);box.append(card);}
}
async function loadSpaces(prefer=current){spaces=await api('/companies');current=spaces.some(s=>s.id===prefer)?prefer:(spaces[0]?.id||'');await selectSpace(current);}
let requestSequence=0;
async function selectSpace(id){const seq=++requestSequence;current=id;rows=[];loading=true;$('search').value='';renderSpaces();renderSeals();try{const result=id?await api('/companies/'+id+'/stamps'):[];if(seq!==requestSequence)return;rows=result;}catch(e){if(seq===requestSequence)message(e.message);}finally{if(seq===requestSequence){loading=false;renderSpaces();renderSeals();}}}
$('lang').onclick=async()=>{lang=lang==='zh'?'en':'zh';translate();if(user)try{await api('/preferences','PATCH',{language:lang});}catch{}};
$('search').oninput=renderSeals;
function openSpace(edit){editingSpace=edit;$('space-name').value=edit?spaces.find(s=>s.id===current).name:'';$('delete-space').hidden=!edit;$('space-error').textContent='';$('space-dialog').showModal();$('space-name').focus();}
$('new-space').onclick=()=>openSpace(false);$('edit-space').onclick=()=>openSpace(true);
$('space-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const r=await api(editingSpace?'/companies/'+current:'/companies',editingSpace?'PATCH':'POST',{name:$('space-name').value.trim()});changed();$('space-dialog').close();await loadSpaces(r.id||current);}catch(e){$('space-error').textContent=e.message;}finally{b.disabled=false;}};
$('delete-space').onclick=async()=>{if(!confirm(t('Delete this company/project and ALL of its saved seals? This cannot be undone.','删除此企业 / 项目及其中全部印章？此操作不可撤销。')))return;$('delete-space').disabled=true;try{await api('/companies/'+current,'DELETE');changed();$('space-dialog').close();await loadSpaces('');}catch(e){$('space-error').textContent=e.message;}finally{$('delete-space').disabled=false;}};
$('use-space').onclick=()=>{localStorage.setItem('bsign-space-'+user.id,current);window.open('/','_blank','noopener');};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
function image(url){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error(t('Unable to read image.','无法读取图片。')));im.src=url;});}
const background=backgroundEditor($('seal-preview'),t,result=>{pending.image=result.url;pending.imageChanged=result.changed;pending.ratio=result.height/result.width;dimensions();});
async function openSeal(record){let original=record.image;if(!original){const response=await fetch('/api/stamps/'+record.id+'/image',{credentials:'same-origin'});if(!response.ok)throw Error(t('Seal unavailable.','印章不可用。'));original=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);response.blob().then(b=>reader.readAsDataURL(b));});}const im=await image(original);if(im.width*im.height>16000000)throw Error(t('Use an image below 16 megapixels.','请选择不超过 1600 万像素的图片。'));const cropped=visibleArtwork(im)||im;pending={...record,image:original,company:current,ratio:record.id?record.height/record.width:cropped.height/cropped.width};$('editor-space').textContent=spaces.find(s=>s.id===current)?.name||'';$('editor-title').textContent=record.id?t('Edit seal','编辑印章'):t('Add to your library','保存到印章库');$('seal-preview').src=cropped.toDataURL?cropped.toDataURL('image/png'):original;$('seal-name').value=record.name;$('seal-kind').value=record.kind;$('seal-kind').disabled=!!record.id;$('seal-width').value=record.width||42;$('seal-height').value=record.height||42;$('seal-error').textContent='';dimensions();background.set(im,original);$('seal-dialog').showModal();}
function dimensions(){const kind=$('seal-kind').value,w=Number($('seal-width').value);$('seal-height').readOnly=true;$('seal-height').value=(kind==='signature'?w*pending.ratio:w).toFixed(1);}
$('seal-width').oninput=dimensions;$('seal-kind').onchange=()=>{if($('seal-kind').value==='square')$('seal-width').value=20;if($('seal-kind').value==='signature')$('seal-width').value=35;dimensions();};document.querySelectorAll('[data-size]').forEach(b=>b.onclick=()=>{$('seal-width').value=b.dataset.size;dimensions();});
$('upload-seal').onclick=()=>$('seal-file').click();$('seal-file').onchange=async()=>{const file=$('seal-file').files[0];$('seal-file').value='';if(!file)return;try{if(file.size>5*1024*1024)throw Error(t('Use an image up to 5 MB.','请选择不超过 5 MB 的图片。'));if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error(t('Use PNG, JPEG or WebP.','请选择 PNG、JPEG 或 WebP 图片。'));const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});await openSeal({name:file.name.replace(/\.[^.]+$/,''),kind:'round',width:42,image:data});}catch(e){message(e.message);}};
$('seal-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const q={name:$('seal-name').value.trim(),kind:$('seal-kind').value,width:Number($('seal-width').value),height:Number($('seal-height').value)};if(!pending.id||pending.imageChanged)q.image=pending.image.split(',')[1];await api(pending.id?'/stamps/'+pending.id:'/companies/'+pending.company+'/stamps',pending.id?'PATCH':'POST',q);changed();$('seal-dialog').close();await selectSpace(current);message('Saved. Ready to use in the signing workspace.','已保存，可在签章工作台中使用。');}catch(e){$('seal-error').textContent=e.message;}finally{b.disabled=false;}};
const canvas=$('signature-canvas'),ctx=canvas.getContext('2d');let drawing=false,ink=false;
function clearDrawing(){ctx.clearRect(0,0,canvas.width,canvas.height);ink=false;}
$('draw-signature').onclick=()=>{clearDrawing();$('draw-dialog').showModal();};$('clear-drawing').onclick=clearDrawing;
function point(e){const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*canvas.width/r.width,(e.clientY-r.top)*canvas.height/r.height];}
canvas.onpointerdown=e=>{e.preventDefault();drawing=true;ink=true;canvas.setPointerCapture(e.pointerId);ctx.strokeStyle='#18343a';ctx.fillStyle='#18343a';ctx.lineWidth=4;ctx.lineCap='round';ctx.lineJoin='round';const [x,y]=point(e);ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);ctx.fill();ctx.beginPath();ctx.moveTo(x,y);};canvas.onpointermove=e=>{if(drawing){ctx.lineTo(...point(e));ctx.stroke();}};canvas.onpointerup=canvas.onpointercancel=()=>drawing=false;
$('use-drawing').onclick=async()=>{if(!ink)return;try{const cropped=visibleArtwork(canvas)||canvas;$('draw-dialog').close();await openSeal({name:t('Handwritten signature','手写签名'),kind:'signature',width:35,image:canvas.toDataURL('image/png')});}catch(e){message(e.message);}};
translate();
try{const q=await api('/me');user=q.user;csrf=q.csrf;if(user.role!=='user')throw Error(t('Administrators manage users only.','管理员仅管理用户，不能访问印章。'));if(user.language)lang=user.language;translate();$('session').textContent=user.email;$('seals-manage').hidden=false;await loadSpaces(localStorage.getItem('bsign-space-'+user.id)||'');}catch(e){$('session').textContent=t('Sign in with a user account in the workspace.','请先在签章工作台登录普通用户账号。');message(e.message);}
window.addEventListener('beforeunload',clearUrls);

// Phone signatures are reviewed before being saved to the selected library.
let phoneSession=null,phoneTimer=null,phoneGeneration=0;
async function stopPhone(){const old=phoneSession;phoneSession=null;++phoneGeneration;clearTimeout(phoneTimer);if(old)try{await api('/phone-sign/'+old.id,'DELETE');}catch{}}
async function beginPhone(){
 $('phone-sign').disabled=true;$('phone-renew').disabled=true;
 const company=current;await stopPhone();const generation=phoneGeneration;
 if(!$('phone-dialog').open)$('phone-dialog').showModal();
 $('phone-qr').removeAttribute('src');$('phone-status').textContent=t('Creating QR code…','正在生成二维码…');
 try{
  const q=await api('/phone-sign','POST',{language:lang});
  if(generation!==phoneGeneration){await api('/phone-sign/'+q.id,'DELETE');return;}
  phoneSession={...q,company};$('phone-qr').src=q.qr;$('phone-status').textContent=t('Waiting for your signature…','等待手机签名…');
  phoneTimer=setTimeout(()=>pollPhone(generation),1500);
 }catch(e){if(generation===phoneGeneration)$('phone-status').textContent=e.message;}finally{$('phone-sign').disabled=false;$('phone-renew').disabled=false;}
}
async function pollPhone(generation){
 if(generation!==phoneGeneration||!phoneSession)return;const session=phoneSession;
 if(Date.now()>=session.expires*1000){$('phone-status').textContent=t('QR code expired. Generate a new one.','二维码已过期，请重新生成。');await stopPhone();return;}
 try{
  const q=await api('/phone-sign/'+session.id);
  if(generation!==phoneGeneration)return;
  if(q.ready){
   const data='data:image/png;base64,'+q.image;await image(data);
   if(generation!==phoneGeneration)return;
   if(current!==session.company){$('phone-status').textContent=t('Company changed. Generate a new QR code.','企业已切换，请重新生成二维码。');await stopPhone();return;}
   await stopPhone();$('phone-dialog').close();$('draw-dialog').close();
   await openSeal({name:user.name||t('Handwritten signature','手写签名'),kind:'signature',width:35,image:data});
   message('Signature received. Review and save it to your library.','已收到手机签名，请核对后保存到印章库。');return;
  }
 }catch(e){if(generation!==phoneGeneration)return;$('phone-status').textContent=t('Connection interrupted or link unavailable. Retry or generate a new QR code.','连接中断或链接已失效，可稍后重试或重新生成二维码。');}
 if(generation===phoneGeneration)phoneTimer=setTimeout(()=>pollPhone(generation),2000);
}
$('phone-sign').onclick=beginPhone;$('phone-renew').onclick=beginPhone;
$('phone-dialog').addEventListener('close',()=>stopPhone());
window.addEventListener('pagehide',()=>{clearTimeout(phoneTimer);if(phoneSession)fetch('/api/phone-sign/'+phoneSession.id,{method:'DELETE',credentials:'same-origin',headers:{'X-CSRF-Token':csrf},keepalive:true}).catch(()=>{});});
