// Adapt the functional workspace to the reviewed inspector layout.
export function initWorkspaceUI(){
 const $=id=>document.getElementById(id), scroll=document.querySelector('.side-scroll');
 const section=(className)=>{const el=document.createElement('section');el.className='ins-section '+className;return el;};
 const company=section('company-section'),library=section('library-section');
 const companyHeading=$('company').previousElementSibling,libraryHeading=document.querySelector('.space-top');
 const actions=document.querySelector('.seal-actions'),note=document.querySelector('.small-note');
 company.append(companyHeading,$('company'));library.append(libraryHeading,$('library'),actions,$('image-input'),note);
 const property=document.querySelector('.property-box');property.id='selection-panel';property.hidden=true;
 const heading=document.createElement('div');heading.className='selection-heading';heading.innerHTML='<span data-en="CURRENT MARK" data-zh="当前签章">CURRENT MARK</span><button id="deselect-mark" type="button" class="quiet" aria-label="Deselect / 取消选中">×</button>';property.prepend(heading);
 const preview=document.createElement('img');preview.id='selection-image';preview.alt='';const card=document.createElement('div');card.className='selected-card';$('selected-info').before(card);card.append(preview,$('selected-info'));const fixed=document.createElement('p');fixed.id='fixed-mark-size';$('angle').closest('label').before(fixed);
 const angleOutput=document.createElement('output');angleOutput.id='angle-value';$('angle').before(angleOutput);
 const placementHeading=$('place').previousElementSibling;placementHeading.remove();
 library.append($('place'));const row=$('remove-mark').parentElement;row.prepend($('copy-all'));
 const random=$('random').closest('label');library.append(random);
 function disclosure(id,en,zh){const d=document.createElement('details');d.className='ins-disclosure';d.id=id;const sum=document.createElement('summary');sum.innerHTML='<span data-en="'+en+'" data-zh="'+zh+'">'+en+'</span><span aria-hidden="true">⌄</span>';d.append(sum);return d;}
 const seam=disclosure('seam-settings','Across-page seal','骑缝章');seam.append(document.querySelector('.seam-box'));
 const cert=disclosure('certificate-settings','Digital certificate · optional','数字证书 · 可选');cert.append($('certificate-enabled').closest('label'),$('export-certificate'));
 scroll.replaceChildren(company,library,property,seam,cert);
 const fills=()=>document.querySelectorAll('#workspace input[type=range]').forEach(el=>{const min=Number(el.min)||0,max=Number(el.max)||100;el.style.setProperty('--fill',((Number(el.value)-min)/(max-min)*100)+'%');});
 document.querySelectorAll('#workspace input[type=range]').forEach(el=>el.addEventListener('input',()=>{fills();$('angle-value').textContent=$('angle').value+'°';}));
 return selected=>{property.hidden=!selected;$('fixed-mark-size').hidden=!selected||['signature','text','date'].includes(selected.kind);if(selected){$('fixed-mark-size').textContent=Number(selected.w.toFixed(1))+' × '+Number(selected.h.toFixed(1))+' mm';$('selection-image').src=selected.url;$('angle-value').textContent=$('angle').value+'°';}fills();};
}

