'use strict';
// Files are read locally. Only explicit form confirmation writes fields to CONTA.
window.InvoiceOCR=(()=>{
 const CDN='https://cdn.jsdelivr.net/npm/';
 let scriptPromise;
 function library(){if(window.Tesseract)return Promise.resolve(window.Tesseract);if(!scriptPromise)scriptPromise=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=CDN+'tesseract.js@7.0.0/dist/tesseract.min.js';s.crossOrigin='anonymous';s.onload=()=>window.Tesseract?resolve(window.Tesseract):reject(Error('No se pudo iniciar el lector OCR'));s.onerror=()=>{scriptPromise=null;reject(Error('No se pudo descargar el lector. Revisa la conexión.'));};document.head.appendChild(s);});return scriptPromise;}
 function number(v){let s=String(v||'').replace(/[^\d.,-]/g,'');if(!s)return NaN;const c=s.lastIndexOf(','),d=s.lastIndexOf('.');if(c>=0&&d>=0)s=c>d?s.replace(/\./g,'').replace(',','.'):s.replace(/,/g,'');else if(c>=0)s=s.replace(',','.');else if(/\.\d{3}$/.test(s))s=s.replace(/\./g,'');return Number(s);}
 function date(v){const iso=String(v).match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);let result;if(iso)result=iso[0];else{const m=String(v).match(/\b(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d{2}|\d{2})\b/);if(!m)return '';result=(m[3].length===2?'20'+m[3]:m[3])+'-'+m[2].padStart(2,'0')+'-'+m[1].padStart(2,'0');}const d=new Date(result+'T00:00:00Z');return !Number.isNaN(d.valueOf())&&d.toISOString().slice(0,10)===result?result:'';}
 function moneyValues(line){
  const text=line.replace(/\b\d{1,3}(?:[.,]\d+)?\s*%/g,' ').replace(/(\d)\s*([,.])\s*(\d)/g,'$1$2$3');
  const tokens=text.matchAll(/(?<![\d.,])(-?(?:\d{1,3}(?:[., ]\d{3})+|\d+)[,.]\d{2})(?![\d.,])|(?<![\d.,])(-?\d+)\s*(?:€|EUR\b)/gi);
  return [...tokens].map(match=>number(match[1]||match[2])).filter(Number.isFinite);
 }
 const totalLabels=[
  /\b(?:total\s+(?:de\s+(?:la\s+)?)?(?:factura|documento|con\s+iva|iva\s+incluido|euros?|eur)|importe\s+total|grand\s+total)\b/i,
  /\btotal\b(?!\s+(?:iva|igic|base|descuento|impuestos|retenci[oó]n|sin\s+iva|ahorro|art[ií]culos?|unidades|efectivo|tarjeta|a\s+pagar|pendiente)\b)/i,
  /\b(?:total\s+a\s+pagar|importe\s+a\s+pagar|a\s+pagar|amount\s+due)\b/i
 ];
 const baseLabel=/\b(?:base\s+(?:imponible|iva|igic|sujeta)|subtotal|importe\s+neto|total\s+sin\s+iva)\b/i;
 const taxLabel=/\b(?:cuota\s+(?:de\s+)?(?:iva|igic)|importe\s+iva|iva\s+repercutido|total\s+iva|iva(?=\s*[:=]|\s+\d{1,2}\s*%))\b/i;
 function labeled(lines,pattern,{integer=false,first=false,ignore=()=>false}={}){
  const nextAmount=/^(?:€\s*)?-?[\d., ]+(?:\s*(?:€|EUR))?$/i;
  for(let i=lines.length-1;i>=0;i--){
   const line=lines[i],match=line.match(pattern);
   if(!match||ignore(line))continue;
   const rest=line.slice(match.index+match[0].length).trim();
   const values=moneyValues(rest);
   if(values.length)return first?values[0]:values.at(-1);
   const prefix=line.slice(0,match.index).trim();
   if(nextAmount.test(prefix)){
    const before=moneyValues(prefix);
    if(before.length===1)return before[0];
   }
   if(integer&&/^[:=\s-]*\d{1,6}$/.test(rest))return number(rest.replace(/^[:=\s-]+/,''));
   if(/^[\s:=(€EUR)]*$/i.test(rest)&&nextAmount.test(lines[i+1]||'')){
    const valuesBelow=moneyValues(lines[i+1]);
    if(valuesBelow.length===1)return valuesBelow[0];
   }
  }
  return NaN;
 }
 function invoiceAmounts(lines){
  const ignored=line=>/\b(?:subtotal|base\s+total|total\s+(?:sin\s+iva|descuento|ahorro|art[ií]culos?|unidades|puntos)|cambio|entregado|a\s+cuenta)\b/i.test(line);
  let total=NaN;
  for(const label of totalLabels){
   total=labeled(lines,label,{integer:true,ignore:ignored});
   if(Number.isFinite(total))break;
  }
  let base=labeled(lines,baseLabel,{first:true}),tax=labeled(lines,taxLabel,{first:true});
  const rateRows=lines.filter(line=>/\bIVA\s*\d{1,2}\s*%?\s*\(\s*base\b/i.test(line))
   .map(line=>line.match(/\bIVA\s*\d{1,2}\s*%?\s*\(\s*base\s*([^)]*)\)(.*)/i))
   .filter(Boolean).map(match=>[moneyValues(match[1])[0],moneyValues(match[2])[0],Number(match[0].match(/IVA\s*(\d+)/i)[1])])
   .filter(row=>row.every(Number.isFinite));
  if(rateRows.length){
   if(!Number.isFinite(base))base=Math.round(rateRows.reduce((sum,row)=>sum+row[0],0)*100)/100;
   const declaredTax=rateRows.reduce((sum,[net,value,rate])=>{
    const cents=Math.round(net*rate);
    // A missing decimal separator is only corrected when the rate confirms it.
    return sum+(Number.isInteger(value)&&value===cents?value/100:value);
   },0);
   if(!Number.isFinite(tax))tax=Math.round(declaredTax*100)/100;
  }
  const header=lines.findIndex(line=>/\bbase\s+imponible\b/i.test(line)&&/\b(?:cuota|iva|igic)\b/i.test(line)&&moneyValues(line).length===0);
  if(header>=0){
   const columns=lines[header];
   const table=[];
   for(const line of lines.slice(header+1)){
    const values=moneyValues(line);
    if(!/^\s*[\d€+-]/.test(line)||values.length<2)break;
    table.push(values);
   }
   if(table.length){
    const baseFirst=columns.search(/\bbase\s+imponible\b/i)<columns.search(/\b(?:cuota|iva|igic)\b/i)||/\b(?:cuota|importe)\s+(?:de\s+)?iva\b/i.test(columns);
    // Most summaries list base, percentage (removed above), tax, and optional gross.
    if(baseFirst){
     base=table.reduce((sum,row)=>sum+row[0],0);
     tax=table.reduce((sum,row)=>sum+row[1],0);
    }
   }
  }
  const amount=Number.isFinite(total)?total:Number.isFinite(base)&&Number.isFinite(tax)?Math.round((base+tax)*100)/100:NaN;
  return {amount,baseAmount:base,taxAmount:tax};
 }
 function parse(raw){const text=String(raw||'').replace(/\r/g,'\n').replace(/\u00a0/g,' '),lines=text.split(/\n+/).map(x=>x.replace(/\s+/g,' ').trim()).filter(Boolean),find=rx=>lines.find(x=>rx.test(x))||'';
 const heading=lines.findIndex(line=>/\bFACTU\s*RA\b/i.test(line)&&!/\btotal\b/i.test(line));
 const standaloneRef=heading>=0?lines.slice(heading,heading+8).join('\n').match(/\bn[úu]mero\s*[:#]\s*([A-Z0-9][A-Z0-9_./-]{2,31})/i):null;
 const reference=standaloneRef?.[1]||(text.match(/(?:n[úu]mero\s+(?:de\s+)?factura|factura\s*(?:n[.º°oúu]*|#|no\.?|número)?|n[.º°oúu]*\s*factura)\s*[:#-]?\s*([A-Z0-9][A-Z0-9_./-]{2,31})/i)||[])[1]||'';
 const dated=find(/fecha\s*(?:de\s*)?(?:emisi[oó]n|factura|expedici[oó]n|[:=])/i),when=date(dated)||date(text);
 const taxId=(text.match(/\bTBAI-([A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z])-/i)||[])[1]||(text.match(/\b(?:NIF|CIF|VAT(?:\s*ID)?)\s*[:.\-]?\s*([A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]|[A-Z]{2}\d{8,12})\b/i)||[])[1]||'';
 let vendor=find(/^(?:emisor|proveedor|raz[oó]n\s+social|empresa)\s*[:=-]/i).replace(/^(?:emisor|proveedor|raz[oó]n\s+social|empresa)\s*[:=-]\s*/i,'');if(!vendor){
  const company=lines.slice(0,12).map(line=>line.replace(/\s+[5§]\s*\.\s*[1lI]\.?$/,' S.L.')).find(line=>/\b(?:S\.?\s*[LA]\.?|S\.?\s*L\.?\s*U\.?)$/i.test(line)&&/[a-záéíóú]{3}/i.test(line));
  vendor=company||lines.slice(0,12).find(line=>/^hotel\s+[a-záéíóú]{3,}/i.test(line))||'';
 }if(!vendor)vendor=lines.slice(0,8).find(x=>x.length>4&&x.length<90&&!/^(FACTURA|TICKET|NOTA|FECHA|NIF|CIF|IVA|N[º°]|TOTAL|CLIENTE|DIRECCI[OÓ]N|TEL|WWW|HTTP|ESPAÑA|\d|BASE|PRESUPUESTO)/i.test(x)&&!/@/.test(x))||'';
 let concept=find(/^(?:concepto|descripci[oó]n|detalle|servicio)\s*[:=-]\s*\S/i).replace(/^(?:concepto|descripci[oó]n|detalle|servicio)\s*[:=-]\s*/i,'');if(!concept&&vendor)concept='Factura de '+vendor;
 const joined=(vendor+' '+concept+' '+text.slice(0,1000)).toLowerCase();let category='Otros';if(/hotel|alojamiento|habitaci[oó]n|hospedaje/.test(joined))category='Alojamiento';else if(/supermercado|mercadona|eroski|carrefour|lidl|aldi\b/.test(joined))category='Supermercado';else if(/restaurante|desayuno|comida|cena|men[uú]|manutenci[oó]n/.test(joined))category='Manutención';else if(/gasolina|combustible|gasoil|repostaje/.test(joined))category='Gasolina';else if(/peaje/.test(joined))category='Transporte';else if(/maillot|culote|ropa|sudadera/.test(joined))category='Ropa';else if(/bicicleta|material|casco/.test(joined))category='Material';else if(/inscripci[oó]n/.test(joined))category='Inscripciones';
 return {date:when,...invoiceAmounts(lines),counterparty:vendor.slice(0,200),reference:reference.slice(0,100),taxId,concept:concept.slice(0,200),category};}
 function spatialText(tsv){
  const words=String(tsv||'').split('\n').slice(1).flatMap(line=>{
   const parts=line.split('\t');
   if(parts[0]!=='5'||!parts[11]?.trim())return [];
   const [left,top,,height]=parts.slice(6,10).map(Number);
   return [{left,center:top+height/2,height,text:parts[11].trim()}];
  }).sort((a,b)=>a.center-b.center);
  const rows=[];
  for(const word of words){
   const row=rows.at(-1);
   if(row&&Math.abs(word.center-row.center)<=Math.max(5,Math.min(row.height,word.height)*0.55))row.words.push(word);
   else rows.push({center:word.center,height:word.height,words:[word]});
  }
  return rows.map(row=>row.words.sort((a,b)=>a.left-b.left).map(word=>word.text).join(' ')).join('\n');
 }
 async function read(file,progress=()=>{},control={}){if(!file)throw Error('Selecciona una factura');if(file.size>4*1024*1024)throw Error('Máximo 4 MB por original.');let worker=null,pdf=null;
 const check=()=>{if(control.cancelled)throw Error('Lectura cancelada');};
 async function ocr(source){check();const t=await library();if(!worker){progress('Preparando lector en español… La primera carga puede tardar.');worker=await t.createWorker('spa',1,{workerPath:CDN+'tesseract.js@7.0.0/dist/worker.min.js',corePath:CDN+'tesseract.js-core@7.0.0',langPath:CDN+'@tesseract.js-data/spa@1.0.0/4.0.0',workerBlobURL:true,gzip:true,logger:m=>{if(m.status==='recognizing text')progress('Leyendo texto: '+Math.round((m.progress||0)*100)+' %');}});control.worker=worker;}check();const r=await worker.recognize(source,{}, {text:true,tsv:true});check();
 const layout=spatialText(r.data.tsv);
 return layout||r.data.text||'';}
 try{check();if(/^image\//.test(file.type)||/\.(png|jpe?g|webp)$/i.test(file.name)){progress('Leyendo fotografía en este dispositivo…');const text=await ocr(file);return {text,method:'OCR de imagen',pages:1};}
 if(file.type==='application/pdf'||/\.pdf$/i.test(file.name)){progress('Abriendo PDF en este dispositivo…');const lib=await import(CDN+'pdfjs-dist@6.5.438/build/pdf.mjs');lib.GlobalWorkerOptions.workerSrc=CDN+'pdfjs-dist@6.5.438/build/pdf.worker.mjs';check();pdf=await lib.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false,disableFontFace:true,useSystemFonts:true}).promise;const texts=[],limit=Math.min(pdf.numPages,8);let scanned=false;
 for(let i=1;i<=limit;i++){check();progress('Leyendo página '+i+' de '+limit);const pg=await pdf.getPage(i),tc=await pg.getTextContent(),lines=new Map();for(const t of tc.items){if(!t.str?.trim())continue;const y=Math.round((t.transform?.[5]||0)/3),x=t.transform?.[4]||0;if(!lines.has(y))lines.set(y,[]);lines.get(y).push({x,str:t.str});}let piece=[...lines].sort((a,b)=>b[0]-a[0]).map(([,items])=>items.sort((a,b)=>a.x-b.x).map(x=>x.str).join(' ')).join('\n');const sparse=piece.replace(/\s/g,'').length<35;if(sparse||(i===limit&&!Number.isFinite(parse([...texts,piece].join('\n')).amount))){scanned=true;progress('PDF escaneado · OCR de página '+i);const normal=pg.getViewport({scale:1}),viewport=pg.getViewport({scale:Math.min(3,1979/normal.width,3000/normal.height)}),canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);try{await pg.render({canvasContext:canvas.getContext('2d'),viewport}).promise;const scannedText=await ocr(canvas);if(sparse||Number.isFinite(parse(scannedText).amount))piece=scannedText;}finally{canvas.width=canvas.height=0;}}texts.push(piece);pg.cleanup();}return {text:texts.join('\n'),method:scanned?'PDF con OCR':'Texto del PDF',pages:limit,truncated:pdf.numPages>limit};}
 throw Error('Selecciona una foto JPG/PNG/WEBP o un PDF.');}finally{if(worker){try{await worker.terminate();}catch{}}if(pdf){try{await pdf.destroy();}catch{}}control.worker=null;}}
 return {number,date,parse,read,spatialText};
})();
function addInvoiceOCR(c,ctx){const form=document.getElementById('moduleForm');if(!form)return;const box=document.createElement('section');box.className='card invoice-ocr';box.innerHTML='<h2>Subir ticket o factura</h2><div class="toolbar"><button type="button" class="primary" id="takeInvoicePhoto">Hacer foto y registrar</button><button type="button" id="pickInvoiceFile">Adjuntar factura o foto</button></div><input id="invoiceCamera" type="file" accept="image/*" capture="environment" hidden><input id="invoiceFile" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" hidden><div class="toolbar"><button type="button" id="readInvoice" class="primary">Leer factura</button><button type="button" id="cancelInvoice" hidden>Cancelar lectura</button></div><p id="invoiceProgress" role="status" aria-live="polite"></p><div id="invoiceDetected"></div><small>La lectura se hace en tu navegador. Al guardar se adjunta el archivo seleccionado. Las fotos de cámara que superen el límite o usen otro formato se preparan en JPG. Solo Dirección podrá descargarlo. Máximo 4 MB y 8 páginas por lectura.</small>';document.getElementById('moduleEditor').before(box);let current=null;
 const camera=box.querySelector('#invoiceCamera'),picker=box.querySelector('#invoiceFile');
 box.querySelector('#takeInvoicePhoto').onclick=()=>camera.click();
 box.querySelector('#pickInvoiceFile').onclick=()=>picker.click();
 let selection=0;
 const chooseOriginal=async e=>{
  const attempt=++selection;
  let file=e.target.files[0];
  e.target.value='';
  if(!file)return;
  if(e.target===camera&&(file.size>4*1024*1024||!/^image\/(jpeg|png|webp)$/.test(file.type))){
   try{
    const bitmap=await createImageBitmap(file);
    const canvas=document.createElement('canvas');
    const scale=Math.min(1,2000/Math.max(bitmap.width,bitmap.height));
    canvas.width=Math.max(1,Math.round(bitmap.width*scale));
    canvas.height=Math.max(1,Math.round(bitmap.height*scale));
    try{
     canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);
     const jpeg=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.86));
     if(!jpeg)throw Error('JPEG no disponible');
     file=new File([jpeg],'foto-ticket.jpg',{type:'image/jpeg'});
    }finally{bitmap.close();}
   }catch{
    if(attempt===selection)message('No se pudo preparar la foto. Adjunta una imagen JPG o PNG de hasta 4 MB.');
    return;
   }
  }
  if(attempt!==selection||!box.isConnected)return;
  if(file.size>4*1024*1024){message('El archivo debe ocupar como máximo 4 MB.');return;}
  if(current)current.cancelled=true;
  form.invoiceOriginal=file;
  delete form.dataset.ocrReview;
  form.querySelector('#invoiceReview')?.remove();
  box.querySelector('#invoiceDetected').textContent='';
  box.querySelector('#invoiceProgress').textContent='Archivo seleccionado: '+file.name+'. Indica el importe y guarda, o pulsa Leer factura para probar el OCR.';
  document.getElementById('moduleEditor').hidden=false;
  form.elements.amount.scrollIntoView?.({block:'nearest'});
 };
 camera.onchange=picker.onchange=chooseOriginal;
 document.getElementById('cancelInvoice').onclick=async()=>{if(current){current.cancelled=true;if(current.worker){try{await current.worker.terminate();}catch{}}document.getElementById('invoiceProgress').textContent='Lectura cancelada.';}};
 document.getElementById('readInvoice').onclick=async()=>{const button=document.getElementById('readInvoice'),cancel=document.getElementById('cancelInvoice'),status=document.getElementById('invoiceProgress'),file=form.invoiceOriginal;if(!file){message('Selecciona una factura o fotografía.');return;}const control={cancelled:false};current=control;button.disabled=true;cancel.hidden=false;message('');try{const result=await InvoiceOCR.read(file,text=>{if(box.isConnected&&!control.cancelled)status.textContent=text;},control);if(control.cancelled||!box.isConnected)return;const fields=InvoiceOCR.parse(result.text);if(!result.text.trim())throw Error('No se ha detectado texto. Prueba una foto más nítida o completa los campos manualmente.');document.getElementById('moduleEditor').hidden=false;
 const mappings=['date','counterparty','reference','taxId','concept','category'];for(const key of mappings){if(fields[key]&&form.elements[key])form.elements[key].value=fields[key];}for(const key of ['amount','baseAmount','taxAmount']){if(Number.isFinite(fields[key])&&fields[key]>=0&&form.elements[key])form.elements[key].value=fields[key].toFixed(2);}form.elements.direction.value='Gasto';form.elements.status.value='Pendiente';const matches=ctx.fixedEvent?[ctx.fixedEvent]:ctx.events.filter(e=>e.date&&fields.date&&fields.date>=e.date&&fields.date<=(e.endDate||e.date)&&e.status!=='Cancelada');if(matches.length===1)form.elements.event.value=matches[0].id;else form.elements.event.value='';form.dataset.ocrReview='true';let review=document.getElementById('invoiceReview');if(!review){review=document.createElement('label');review.id='invoiceReview';review.className='checkline note';review.innerHTML='<input type="checkbox" name="ocrReviewed"> He revisado proveedor, fecha, factura, importes y actividad antes de guardar.';form.querySelector('button[type=submit]').before(review);}form.elements.ocrReviewed.checked=false;
 status.textContent=result.method+' · '+result.pages+' página(s). '+(result.truncated?'Solo se han leído las primeras 8 páginas. ':'')+'Datos propuestos: revísalos antes de guardar.';const panel=document.getElementById('invoiceDetected');panel.innerHTML='<p class="note">'+(Number.isFinite(fields.amount)?'Total propuesto: '+esc(fields.amount.toFixed(2))+' €':'No se ha detectado un total fiable: introduce el importe manualmente.')+'<br>Base imponible: '+(Number.isFinite(fields.baseAmount)?esc(fields.baseAmount.toFixed(2))+' €':'por revisar')+' · IVA: '+(Number.isFinite(fields.taxAmount)?esc(fields.taxAmount.toFixed(2))+' €':'por revisar')+'<br>'+esc(matches.length===1?(ctx.fixedEvent?'Actividad vinculada: ':'Actividad propuesta: ')+matches[0].name:matches.length>1?'Varias actividades coinciden con la fecha: elige una.':'Sin actividad coincidente: se propone gasto general.')+'</p><details><summary>Ver texto detectado</summary><pre id="invoiceRawText"></pre></details>';document.getElementById('invoiceRawText').textContent=result.text;
 }catch(e){if(box.isConnected&&!control.cancelled)message('No se pudo leer la factura: '+e.message);}finally{button.disabled=false;cancel.hidden=true;if(current===control)current=null;}};}
