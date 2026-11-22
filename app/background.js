import {visibleArtwork} from '/artwork.js';

// Estimate a flat paper colour from opaque pixels along all four edges.
export function paperColour(pixels,w,h){
 const samples=[[],[],[]];
 const add=(x,y)=>{const i=(y*w+x)*4;if(pixels[i+3]<240)return;for(let c=0;c<3;c++)samples[c].push(pixels[i+c]);};
 for(let n=0;n<40;n++){const x=Math.round(n*(w-1)/39),y=Math.round(n*(h-1)/39);add(x,0);add(x,h-1);add(0,y);add(w-1,y);}
 return samples.map(a=>a.length?a.sort((a,b)=>a-b)[Math.floor(a.length/2)]:255);
}
// Unmatte the selected flat background while retaining the existing alpha channel.
export function removeMatte(data,colour,strength=8){
 const out=new Uint8ClampedArray(data.length),cut=Math.max(0,Math.min(60,strength))/255;
 for(let i=0;i<data.length;i+=4){
  if(!data[i+3])continue;
  let coverage=0;
  for(let c=0;c<3;c++){const b=colour[c],v=data[i+c];coverage=Math.max(coverage,v<b?(b-v)/Math.max(1,b):(v-b)/Math.max(1,255-b));}
  const a=Math.max(0,(coverage-cut)/(1-cut));
  if(a===0)continue;
  for(let c=0;c<3;c++)out[i+c]=Math.max(0,Math.min(255,(data[i+c]-colour[c]*(1-a))/a));
  out[i+3]=Math.round(data[i+3]*a);
 }
 return out;
}
export function backgroundEditor(preview,t,onChange){
 const box=document.createElement('section');box.className='background-editor';
 const enable=document.createElement('input');enable.type='checkbox';enable.className='background-enable';
 const label=document.createElement('label');label.className='checkbox';const title=document.createElement('span');label.append(enable,title);
 const fields=document.createElement('div');fields.className='background-fields';
 const colour=document.createElement('input');colour.type='color';colour.className='background-colour';
 const strength=document.createElement('input');strength.type='range';strength.min=0;strength.max=60;strength.value=8;strength.className='background-strength';
 const colourLabel=document.createElement('label'),strengthLabel=document.createElement('label'),colourText=document.createElement('span'),strengthText=document.createElement('span');colourLabel.append(colourText,colour);strengthLabel.append(strengthText,strength);fields.append(colourLabel,strengthLabel);
 const reset=document.createElement('button');reset.type='button';reset.className='secondary background-reset';
 const hint=document.createElement('p');hint.className='hint';box.append(label,fields,reset,hint);preview.parentElement.after(box);
 let source=null,originalUrl='',pixels=null,initialColour='';
 function render(){
  colour.disabled=strength.disabled=!enable.checked;reset.disabled=!enable.checked;
  let canvas=source,url=originalUrl,changed=false;
  if(enable.checked){canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;const ctx=canvas.getContext('2d'),data=ctx.createImageData(canvas.width,canvas.height),rgb=colour.value.match(/[a-f\d]{2}/gi).map(v=>parseInt(v,16));data.data.set(removeMatte(pixels.data,rgb,Number(strength.value)));ctx.putImageData(data,0,0);url=canvas.toDataURL('image/png');changed=true;}
  const cropped=visibleArtwork(canvas)||canvas;preview.src=cropped.toDataURL('image/png');onChange({url,changed,width:cropped.width,height:cropped.height});
 }
 enable.onchange=render;colour.oninput=render;strength.oninput=render;reset.onclick=()=>{enable.checked=false;colour.value=initialColour;strength.value=8;render();};
 return {set(image,url){source=document.createElement('canvas');source.width=image.width;source.height=image.height;const ctx=source.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);pixels=ctx.getImageData(0,0,source.width,source.height);originalUrl=url;initialColour='#'+paperColour(pixels.data,source.width,source.height).map(v=>v.toString(16).padStart(2,'0')).join('');colour.value=initialColour;enable.checked=false;strength.value=8;colour.disabled=strength.disabled=reset.disabled=true;title.textContent=t('Remove background','去除底色');colourText.textContent=t('Background colour','底色颜色');strengthText.textContent=t('Removal strength','去除强度');reset.textContent=t('Restore original','恢复原图');hint.textContent=t('Preview before saving. For flat backgrounds; stronger removal may fade light strokes. Restore is available before saving.','适用于纯色背景，保存前请核对笔迹。强度越高，浅色笔迹也可能变淡；保存前可恢复原图。');}};
}
