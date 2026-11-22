// Image conversion stays in the browser. Word uses the isolated temporary endpoint.
export async function documentBytes(file,{csrf,notice,t}){
 const ext=file.name.split('.').pop().toLowerCase();
 if(ext==='pdf')return new Uint8Array(await file.arrayBuffer());
 if(['doc','docx'].includes(ext)){
  if(file.size>8*1024*1024)throw Error(t('Use a Word file below 8 MB.','Word 文件不能超过 8 MB。'));
  notice('Converting Word on the server. Temporary files are deleted after conversion…','正在服务器临时转换 Word，转换完成后立即清理临时文件…');
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),85000);
  try{
   const response=await fetch('/api/convert-word',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-CSRF-Token':csrf,'X-Word-Format':ext},credentials:'same-origin',body:file,signal:controller.signal});
   if(!response.ok){let code='WORD_CONVERT';try{code=(await response.json()).detail;}catch{}const messages={WORD_BUSY:['The converter is busy. Please try again shortly.','转换服务正在处理其他文件，请稍后重试。'],WORD_LIMIT:['Word exceeds the conversion size limit.','Word 文件过大或解压后内容过多，请拆分后重试。'],WORD_INVALID:['This is not a valid DOC or DOCX file.','文件不是有效的 DOC 或 DOCX 文档。'],WORD_MACRO:['Use a Word document without macros.','请使用不包含宏的 Word 文档。'],WORD_TIMEOUT:['Conversion timed out. Try a smaller file.','转换超时，请拆分文档后重试。'],WORD_UNAVAILABLE:['Word conversion is temporarily unavailable.','Word 转换服务暂不可用，请稍后重试。'],WORD_CONVERT:['Could not convert Word. Check that it is not encrypted or damaged.','Word 转换失败，请确认文件没有密码保护且未损坏。']};const pair=messages[code];throw Error(pair?t(...pair):response.status===401?t('Sign in again to convert Word.','请重新登录后转换 Word。'):t('Conversion failed. Please try again later.','转换失败，请稍后重试。'));}
   return new Uint8Array(await response.arrayBuffer());
  }catch(e){if(e.name==='AbortError')throw Error(t('Conversion timed out. Please retry.','转换超时，请稍后重试。'));throw e;}finally{clearTimeout(timer);}
 }
 if(!['jpg','jpeg','png'].includes(ext))throw Error(t('Choose PDF, DOC, DOCX, JPG or PNG.','请选择 PDF、DOC、DOCX、JPG 或 PNG 文件。'));
 if(file.size>20*1024*1024)throw Error(t('Use an image below 20 MB.','图片不能超过 20 MB。'));
 notice('Converting the image to A4 PDF on your device…','正在本机将图片转换为 A4 PDF，图片不会上传…');
 let image;
 try{image=await createImageBitmap(file);}catch{throw Error(t('The image could not be opened.','图片无法打开，请检查文件是否损坏。'));}
 try{
  if(image.width*image.height>40000000)throw Error(t('Use an image below 40 megapixels.','请选择不超过 4000 万像素的图片。'));
  const landscape=image.width>image.height,mm=landscape?[297,210]:[210,297],c=document.createElement('canvas');c.width=Math.round(mm[0]/25.4*300);c.height=Math.round(mm[1]/25.4*300);
  const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);const scale=Math.min(c.width/image.width,c.height/image.height),w=image.width*scale,h=image.height*scale;ctx.drawImage(image,(c.width-w)/2,(c.height-h)/2,w,h);
  const blob=await new Promise(resolve=>c.toBlob(resolve,'image/png'));c.width=c.height=0;const pdf=await PDFLib.PDFDocument.create(),png=await pdf.embedPng(await blob.arrayBuffer()),size=mm.map(x=>x*72/25.4);pdf.addPage(size).drawImage(png,{x:0,y:0,width:size[0],height:size[1]});return await pdf.save();
 }finally{image.close();}
}
