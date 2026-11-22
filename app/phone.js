import {visibleArtwork} from '/artwork.js';
const $=id=>document.getElementById(id),params=new URLSearchParams(location.hash.slice(1)),token=params.get('token');
let lang=params.get('lang')==='zh'?'zh':'en',valid=false,sending=false,submitted=false,writing=false,ink=false,expires=0;
const t=(en,zh)=>lang==='zh'?zh:en;
function translate(){document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-en]').forEach(e=>e.textContent=e.dataset[lang]);$('language').textContent=lang==='zh'?'EN':'中文';if(submitted)done();}
$('language').onclick=()=>{lang=lang==='en'?'zh':'en';translate();};translate();
const canvas=$('signature'),pen=canvas.getContext('2d');
function point(e){const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*canvas.width/r.width,y:(e.clientY-r.top)*canvas.height/r.height};}
function controls(){$('send').disabled=!valid||!ink||sending;$('clear').disabled=sending;}
canvas.onpointerdown=e=>{if(!valid||sending||writing)return;e.preventDefault();writing=true;ink=true;canvas.setPointerCapture(e.pointerId);const p=point(e);pen.strokeStyle=$('ink').value;pen.fillStyle=pen.strokeStyle;pen.lineWidth=Number($('pen').value)*2;pen.lineCap='round';pen.lineJoin='round';pen.beginPath();pen.arc(p.x,p.y,pen.lineWidth/2,0,Math.PI*2);pen.fill();pen.beginPath();pen.moveTo(p.x,p.y);controls();};
canvas.onpointermove=e=>{if(!writing)return;const p=point(e);pen.lineTo(p.x,p.y);pen.stroke();};canvas.onpointerup=canvas.onpointercancel=()=>writing=false;
$('clear').onclick=()=>{pen.clearRect(0,0,canvas.width,canvas.height);ink=false;controls();};
async function request(path,data){const r=await fetch('/api/phone-sign/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,...data})});if(!r.ok)throw Object.assign(Error('request failed'),{status:r.status});return r.json();}
function done(){submitted=true;valid=false;$('signing').hidden=true;$('status').className='';$('status').textContent=t('Signature sent. Return to your computer to review and place it. You can close this page.','签名已提交，请回到电脑核对并放置签名。可以关闭此页面。');}
function error(e){$('status').className='error';$('status').textContent=e.status===410?t('This link has expired or was cancelled. Generate a new QR code on your computer.','链接已过期或已取消，请在电脑上重新生成二维码。'):t('Unable to connect. Check your connection and try again.','暂时无法连接，请检查网络后重试。');if(e.status===410){valid=false;controls();}}
$('send').onclick=async()=>{if(!valid||sending)return;const trimmed=visibleArtwork(canvas);if(!trimmed)return;sending=true;controls();$('status').textContent=t('Sending…','正在回传…');try{await request('submit',{image:trimmed.toDataURL('image/png').split(',')[1]});done();}catch(e){error(e);}finally{sending=false;controls();}};
async function init(){if(!token){error({status:410});return;}try{const q=await request('status',{});expires=q.expires;if(q.submitted){done();return;}valid=true;controls();$('status').textContent=t('Ready. Write your signature above.','已连接，请在上方手写签名。');}catch(e){error(e);if(e.status!==410)setTimeout(init,3000);}}
setInterval(()=>{if(valid&&expires&&Date.now()>=expires*1000)error({status:410});},1000);init();
