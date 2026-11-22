// Mobile keeps the document on screen; existing tools move into a native modal sheet.
export function initMobileWorkspace({canPlace,place,pageSize,editText,nudge}) {
 const $=id=>document.getElementById(id), root=$('workspace'), media=matchMedia('(max-width:760px), (max-width:950px) and (max-height:500px), (hover:none) and (pointer:coarse) and (max-width:1100px)');
 const label=(en,zh)=>`<span data-en="${en}" data-zh="${zh}">${en}</span>`;
 const dock=document.createElement('nav');dock.id='mobile-dock';dock.setAttribute('aria-label','Document tools / 文档工具');
 dock.innerHTML=[['pages','▤','Pages','页面'],['add','＋','Add','添加'],['adjust','☷','Adjust','调整'],['export','↓','Export','导出']].map(([id,icon,en,zh])=>`<button type="button" id="mobile-${id}"><b aria-hidden="true">${icon}</b>${label(en,zh)}</button>`).join('');root.append(dock);
 const sheet=document.createElement('dialog');sheet.id='mobile-sheet';sheet.setAttribute('aria-labelledby','mobile-sheet-title');sheet.innerHTML=`<div class="mobile-sheet-heading"><strong id="mobile-sheet-title"></strong><button type="button" id="mobile-sheet-close" aria-label="Close / 关闭">×</button></div><div id="mobile-sheet-content"></div>`;root.append(sheet);
 const instruction=document.createElement('div');instruction.id='mobile-placement';instruction.hidden=true;instruction.innerHTML=label('Tap the document to place your item','轻点文档上的目标位置放置')+`<button type="button" id="mobile-placement-cancel">${label('Cancel','取消')}</button>`;root.append(instruction);
 const edit=document.createElement('button');edit.id='mobile-edit-text';edit.type='button';edit.innerHTML=label('Edit text','编辑文字');$('selection-panel').append(edit);edit.onclick=editText;
 const nudges=document.createElement('div');nudges.id='mobile-nudges';nudges.innerHTML=`<span>${label('Move · 1 mm','微调位置 · 1 毫米')}</span>`+[['←',-1,0],['↑',0,-1],['↓',0,1],['→',1,0]].map(([s,x,y])=>`<button type="button" data-x="${x}" data-y="${y}" aria-label="${s} 1 mm">${s}</button>`).join('');$('selection-panel').append(nudges);nudges.onclick=e=>{const b=e.target.closest('button');if(b)nudge(Number(b.dataset.x),Number(b.dataset.y));};
 const menu=document.createElement('button');menu.id='mobile-menu';menu.type='button';menu.innerHTML=label('Menu','菜单');menu.setAttribute('aria-expanded','false');document.querySelector('.app-header').append(menu);menu.onclick=()=>{const open=document.querySelector('.app-header').classList.toggle('mobile-menu-open');menu.setAttribute('aria-expanded',String(open));};
 let moved=null,anchor=null,returnFocus=null,armed=false;
 const cancel=()=>{armed=false;instruction.hidden=true;root.classList.remove('mobile-placing');};
 function restore(){if(moved&&anchor){anchor.replaceWith(moved);moved=null;anchor=null;}root.removeAttribute('data-mobile-sheet');if(returnFocus?.isConnected)returnFocus.focus();}
 function close(){if(sheet.open)sheet.close();restore();}
 sheet.addEventListener('close',()=>{if(!sheet.open)restore();});$('mobile-sheet-close').onclick=close;
 sheet.addEventListener('click',e=>{if(e.target===sheet)close();});
 function open(kind){if(!media.matches)return;cancel();close();returnFocus=document.activeElement;root.dataset.mobileSheet=kind;
  const titles={pages:['Pages','页面预览'],add:['Add to document','添加到文档'],adjust:['Adjust mark','调整签章'],export:['Export PDF','导出 PDF']};const [en,zh]=titles[kind];const title=$('mobile-sheet-title');title.dataset.en=en;title.dataset.zh=zh;title.textContent=document.documentElement.lang==='zh-CN'?zh:en;
  moved=document.querySelector(kind==='pages'?'.thumbnail-panel':'.tools-panel');anchor=document.createComment('mobile panel');moved.before(anchor);$('mobile-sheet-content').append(moved);sheet.showModal();$('mobile-sheet-close').focus();
  if(kind==='export')$('certificate-settings').open=true;
 }
 for(const kind of ['pages','add','adjust','export'])$('mobile-'+kind).onclick=()=>open(kind);
 root.addEventListener('click',e=>{if(sheet.open&&e.target.closest('.page-thumb'))close();});
 $('export').addEventListener('click',()=>{if(media.matches)close();},true);
 $('mobile-placement-cancel').onclick=cancel;
 let start=null;
 $('stage').addEventListener('pointerdown',e=>{if(armed)start={x:e.clientX,y:e.clientY};});
 $('stage').addEventListener('pointercancel',()=>start=null);
 $('stage').addEventListener('pointerup',e=>{if(!armed||!start||Math.hypot(e.clientX-start.x,e.clientY-start.y)>10)return;start=null;if(!canPlace())return;const rect=$('stage').getBoundingClientRect(),size=pageSize();cancel();place({x:(e.clientX-rect.left)*size.w/rect.width,y:(e.clientY-rect.top)*size.h/rect.height});});
 const note=document.querySelector('.small-note'),originalNote={en:note.dataset.en,zh:note.dataset.zh};
 function responsive(){document.body.classList.toggle('mobile-workspace',media.matches&&!root.hidden);if(!media.matches){close();cancel();}note.dataset.en=media.matches?'Select an item, then tap the document to place it.':originalNote.en;note.dataset.zh=media.matches?'选择签章后，轻点文档上的目标位置放置。':originalNote.zh;note.textContent=note.dataset[document.documentElement.lang==='zh-CN'?'zh':'en'];document.querySelector('.app-header').classList.remove('mobile-menu-open');menu.setAttribute('aria-expanded','false');}
 media.addEventListener('change',responsive);new MutationObserver(responsive).observe(root,{attributes:true,attributeFilter:['hidden']});responsive();
 return {cancel,pick(){if(!media.matches||!canPlace())return false;close();armed=true;instruction.hidden=false;root.classList.add('mobile-placing');return true;},sync({ready,selected,busy}){for(const id of ['pages','add','export'])$('mobile-'+id).disabled=!ready;$('mobile-adjust').disabled=!ready;edit.hidden=selected?.kind!=='text';nudges.hidden=!selected;dock.inert=busy;if(busy)cancel();}};
}
