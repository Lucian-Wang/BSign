// Rendering geometry only. Original uploaded/encrypted bytes are never replaced.
// Include every nontransparent pixel; do not threshold faint ink or remove white.
export function visibleArtwork(image) {
  const canvas=document.createElement('canvas');
  canvas.width=image.width;canvas.height=image.height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  ctx.drawImage(image,0,0);
  const {width:w,height:h}=canvas,pixels=ctx.getImageData(0,0,w,h);
  let left=w,top=h,right=-1,bottom=-1;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    if(pixels.data[(y*w+x)*4+3]!==0){
      left=Math.min(left,x);right=Math.max(right,x);
      top=Math.min(top,y);bottom=Math.max(bottom,y);
    }
  }
  if(right<0 || (left===0&&top===0&&right===w-1&&bottom===h-1))return null;
  const result=document.createElement('canvas');
  result.width=right-left+1;result.height=bottom-top+1;
  // No resampling: pixel values remain identical to the original source region.
  result.getContext('2d').putImageData(ctx.getImageData(left,top,result.width,result.height),0,0);
  canvas.width=canvas.height=0;
  return result;
}
