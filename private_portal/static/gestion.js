'use strict';

function gestionInvoiceForm(){
 return `<details class="card" id="gestionIntake"><summary>Escanear o subir factura · ${esc(teamName(me.team))}</summary>
 <form id="gestionInvoice"><div class="toolbar">
 <button type="button" class="primary" id="gestionScan">Escanear con cámara</button>
 <button type="button" id="gestionRead">Leer con OCR</button></div>
 <p id="gestionIntakeStatus" role="status" aria-live="polite"></p><div class="grid">
 <label>Factura o justificante · PDF, JPG, PNG o WEBP<input name="file" type="file" accept="application/pdf,image/jpeg,image/png,image/webp"></label>
 <label>Concepto del gasto<input name="concept" maxlength="250" placeholder="Ej. gasolina para la Copa de España"></label>
 <label>Fecha de factura<input name="date" type="date"></label>
 <label>Proveedor<input name="supplier" maxlength="180"></label>
 <label>NIF del proveedor<input name="taxId" maxlength="40"></label>
 <label>Número de factura<input name="reference" maxlength="120"></label>
 ${[['base','Base imponible (€)'],['tax','IVA (€)'],['amount','Total (€)']].map(([name,label])=>
  `<label>${label}<input name="${name}" type="number" min="0" step="0.01"></label>`).join('')}
 </div><button type="submit" class="primary">Enviar a Gestión para revisión</button></form></details>`;
}

function bindGestionIntake(content){
 const form=content.querySelector('#gestionInvoice');
 const status=content.querySelector('#gestionIntakeStatus');
 const scan=content.querySelector('#gestionScan');
 const read=content.querySelector('#gestionRead');
 let original=null;
 const attach=file=>{
  original=file;
  if(file)status.textContent='Adjuntado · '+file.name;
 };
 form.elements.file.onchange=()=>attach(form.elements.file.files[0]);
 scan.onclick=async()=>{
  scan.disabled=true;
  try{
   const file=await scanDocumentWithCamera();
   if(file&&form.isConnected){form.elements.file.value='';attach(file);}
  }catch(error){status.textContent=error.message;}
  finally{scan.disabled=false;}
 };
 read.onclick=async()=>{
  if(!original){status.textContent='Escanea o adjunta la factura primero.';return;}
  const file=original;
  read.disabled=true;
  try{
   const result=await InvoiceOCR.read(file,step=>{if(original===file)status.textContent=step;},{cancelled:false});
   if(original!==file||!form.isConnected)return;
   const data=InvoiceOCR.parse(result.text);
   for(const [field,key] of Object.entries({date:'date',supplier:'counterparty',taxId:'taxId',reference:'reference',concept:'concept',base:'baseAmount',tax:'taxAmount',amount:'amount'})){
    const value=data[key];
    if(!form.elements[field].value&&(typeof value==='string'&&value||Number.isFinite(value))){
     form.elements[field].value=typeof value==='number'?value.toFixed(2):value;
    }
   }
   status.textContent='Revisa los datos leídos antes de enviar.';
  }catch(error){status.textContent=error.message;}
  finally{read.disabled=false;}
 };
 bindForm(form.id,async()=>{
  if(!original)throw Error('Escanea o adjunta la factura primero.');
  const payload=new FormData(form);
  payload.set('file',original);
  for(const key of ['base','tax','amount'])payload.set(key,Math.round(Number(payload.get(key)||0)*100));
  const result=await api('/gestion/invoices','POST',payload);
  if(!content.isConnected)return;
  await gestionPage(content,false);
  message(result.duplicate?'La factura ya está registrada.':'Factura enviada a Gestión y pendiente de revisar.');
 });
 return attach;
}

async function gestionPage(content,runOCR=true,scan=null){
 const {rows,archived,buckets,mailAccounts}=await api('/gestion');
 const sorted=rows.sort((a,b)=>b.date.localeCompare(a.date)||a.supplier.localeCompare(b.supplier,'es'));
 if(!me.canManageGestion){
  content.innerHTML=`<h1>Gestión · ${esc(teamName(me.team))}</h1>
  ${gestionInvoiceForm()}<h2>Registros del equipo</h2>
  ${sorted.map(row=>`<article class="card"><strong>${esc(row.supplier||row.concept||'Factura')}</strong>
   <p>${esc([row.date,row.concept,row.status].filter(Boolean).join(' · '))} · ${row.amount?euros(row.amount):'Importe pendiente'}</p>
   ${row.files.map(id=>`<a class="button" href="/api/gestion/file/${encodeURIComponent(id)}">Descargar original</a>`).join('')}
  </article>`).join('')||'<p>Todavía no hay registros.</p>'}`;
  const attach=bindGestionIntake(content);
  if(scan){attach(scan);content.querySelector('#gestionIntake').open=true;}
  return;
 }
 content.innerHTML=`<h1>Gestión</h1><p>Contabilidad de Miribilla BTT Elkartea · CIF G95613758</p>
 <details class="card"><summary>Conectar Gmail</summary>
 <p>Configura un proyecto de Google Apps Script en cada cuenta y autoriza una vez la lectura de Gmail. El conector busca candidatos de Miribilla y carga el PDF para revisión.</p>
 <ol><li>Copia el <a href="/static/gestion-gmail.txt" target="_blank" rel="noopener">código del conector</a> en un <a href="https://script.google.com/home/projects/create" target="_blank" rel="noopener">proyecto de Apps Script</a> del buzón correspondiente. En Configuración, muestra <code>appsscript.json</code> y pega el <a href="/static/gestion-gmail-manifest.txt" target="_blank" rel="noopener">manifiesto de solo lectura</a> en ese archivo.</li>
 <li>En Configuración del proyecto → Propiedades de la secuencia de comandos, añade <code>GESTION_MAILBOX</code> con el correo y <code>GESTION_KEY</code> con la clave generada aquí.</li>
 <li>Ejecuta <code>conectarGestion</code> y autoriza el acceso en Google. El proyecto consultará el correo cada hora.</li></ol>
 <form id="gestionMailKey">${select('Buzón','account',mailAccounts)}<button type="submit">Generar clave de conexión</button></form>
 <div id="gestionMailKeyResult"></div></details>
 ${gestionInvoiceForm()}
 <div class="toolbar"><label>Buscar<input id="gestionSearch" type="search" placeholder="Proveedor, número o concepto"></label>
 ${select('Equipo de origen','gestionOrigin',[['','Todos'],...Object.entries(buckets).filter(([key])=>key!=='common'),['gestion','Buzón de facturas']])}
 ${select('Asignado a','gestionBucket',[['','Todos'],['review','Pendientes de revisar'],['pending','Pendientes de asignar'],...Object.entries(buckets)])}
 <label>Mes<input id="gestionMonth" type="month"></label><a class="button" id="gestionExport" href="/api/gestion/export">Exportar contabilidad consolidada</a></div>
 <div class="toolbar"><button type="button" id="gestionRunOCR" class="primary">Leer facturas pendientes con OCR</button></div>
 <p id="gestionOCRStatus" role="status" aria-live="polite"></p>
 <div id="gestionTotals"></div><div id="gestionRows"></div>
 <details class="card"><summary>Asientos borrados (${archived.length})</summary>
 ${archived.map(row=>`<p>${esc(row.date||'Sin fecha')} · ${esc(row.supplier||row.concept||'Apunte')} · ${euros(row.amount)}
 <button type="button" data-gestion-restore="${esc(row.id)}">Recuperar asiento</button></p>`).join('')||'<p>No hay asientos borrados.</p>'}
 </details>`;
 const search=content.querySelector('#gestionSearch');
 const bucket=content.querySelector('[name="gestionBucket"]');
 const month=content.querySelector('#gestionMonth');
 const origin=content.querySelector('[name="gestionOrigin"]');
 const list=content.querySelector('#gestionRows');
 const toCents=value=>Math.round(Number(value||0)*100);
 const fields=[
  ['date','Fecha','date'],['counterparty','Proveedor','text'],['reference','Número de factura','text'],
  ['taxId','NIF del proveedor','text'],['concept','Concepto','text'],
  ['baseAmount','Base imponible (€)','number'],['taxAmount','IVA (€)','number'],['amount','Total (€)','number']
 ];
 const toEntry=(data,approved)=>Object.fromEntries([
  ...fields.map(([name,,type])=>[name,type==='number'?toCents(data[name]):data[name]||'']),
  ['approved',approved]
 ]);
 function reviewForm(row){
  const values={...row,counterparty:row.supplier,baseAmount:row.base,taxAmount:row.tax};
  return `<form id="gestion-review-${esc(row.id)}"><h3>Revisar asiento</h3><div class="grid">
   ${fields.map(([name,label,type])=>`<label>${label}<input name="${name}" type="${type}"
    ${type==='number'?'min="0" step="0.01"':''} value="${esc(type==='number'?(values[name]?values[name]/100:''):values[name]||'')}"></label>`).join('')}
   </div><button type="submit">Confirmar asiento revisado</button></form>`;
 }
 bindForm('gestionMailKey',async(_,data)=>{
  if(!confirm('Generar una clave nueva sustituye la anterior de este buzón. ¿Continuar?'))return;
  const result=await api('/gestion/mail-key','POST',data);
  content.querySelector('#gestionMailKeyResult').innerHTML=`<label>Clave para el proyecto de Gmail<input readonly value="${esc(result.key)}"></label>`;
 });
 const summary=(items,getAmount)=>['Gasto','Ingreso'].map(direction=>
  `${direction==='Gasto'?'Gastos':'Ingresos'} ${euros(items.filter(item=>item.direction===direction).reduce((sum,item)=>sum+getAmount(item),0))}`
 ).join(' · ');
 function render(){
  content.querySelector('#gestionExport').href='/api/gestion/export'+(month.value?'?month='+encodeURIComponent(month.value):'');
  const query=search.value.trim().toLocaleLowerCase('es');
  const pending=row=>!Object.keys(row.allocations).length;
  const matches=sorted.filter(row=>
   (!month.value||row.date.startsWith(month.value))&&(!origin.value||row.team===origin.value)&&
   (!bucket.value||(bucket.value==='review'?row.needsReview:bucket.value==='pending'?pending(row):row.allocations[bucket.value]>0))&&
   [row.supplier,row.reference,row.concept].join(' ').toLocaleLowerCase('es').includes(query));
  const amount=row=>buckets[bucket.value]?row.allocations[bucket.value]:row.amount;
  content.querySelector('#gestionTotals').innerHTML=`<p><strong>${matches.length} apuntes · ${summary(matches.filter(row=>!row.needsReview),amount)}</strong></p>`;
  list.innerHTML=matches.map(row=>{
   const allocations=Object.entries(row.allocations).map(([key,value])=>`${esc(buckets[key])} ${euros(value)}`).join(' · ');
   const source=buckets[row.team]||'Buzón de facturas';
   return `<details class="card">
    <summary>${esc(row.date||'Sin fecha')} · ${esc(row.supplier||row.concept||'Apunte')} · ${euros(row.amount)}</summary>
    <p>${esc([row.direction,source,row.reference,row.concept,row.status].filter(Boolean).join(' · '))}</p>
    ${row.base||row.tax?`<p>Base ${euros(row.base)} · IVA ${euros(row.tax)}</p>`:''}
    <p>${allocations||'Pendiente de asignar'}</p>
    ${row.files.map((id,index)=>`<a class="button" href="/api/gestion/file/${encodeURIComponent(id)}">Descargar original ${row.files.length>1?index+1:''}</a>`).join('')}
    ${row.needsReview?`<p>${row.needsOCR?'Pendiente de lectura OCR':row.amount>0?'Borrador pendiente de revisar':'Importe pendiente de revisar'}</p>${reviewForm(row)}`:''}
   ${row.amount>0&&!row.needsReview?`<form id="gestion-split-${esc(row.id)}"><h3>Reparto interno (€)</h3>
     <div class="grid">${Object.entries(buckets).map(([key,label])=>
       `<label>${esc(label)}<input name="${key}" type="number" min="0" step="0.01" value="${row.allocations[key]?row.allocations[key]/100:''}"></label>`).join('')}</div>
     <button type="submit">Guardar reparto</button></form>`:''}
   <button type="button" data-gestion-archive="${esc(row.id)}">Borrar asiento</button>
   </details>`;
  }).join('')||'<p>No hay apuntes con estos filtros.</p>';
  for(const action of list.querySelectorAll('[data-gestion-archive]')){
   action.onclick=()=>changeArchive(action,action.dataset.gestionArchive,false);
  }
  for(const row of matches){
   bindForm('gestion-review-'+row.id,async(_,data)=>{
    await api('/gestion/'+encodeURIComponent(row.id)+'/review','POST',toEntry(data,true));
    await gestionPage(content);
    message('Asiento revisado. Ya puedes repartirlo y exportarlo.');
   });
   bindForm('gestion-split-'+row.id,async(_,data)=>{
   const amounts=Object.fromEntries(Object.keys(buckets).map(key=>[key,toCents(data[key])]).filter(([,value])=>value));
   if(Object.values(amounts).reduce((a,b)=>a+b,0)!==row.amount)throw Error('El reparto debe sumar '+euros(row.amount)+'.');
   await api('/gestion/'+encodeURIComponent(row.id)+'/allocation','POST',{amounts});
   row.allocations=amounts;
   render();
   message('Reparto guardado.');
   });
  }
 }
 async function changeArchive(button,id,restore){
  if(!restore&&!confirm('¿Borrar este asiento de Gestión y de los informes? Podrás recuperarlo desde Asientos borrados.'))return;
  button.disabled=true;
  try{
   await api('/gestion/'+encodeURIComponent(id)+(restore?'/restore':'/archive'),'POST',{});
   if(!content.isConnected)return;
   await gestionPage(content,false);
   message(restore?'Asiento recuperado.':'Asiento borrado. Puedes recuperarlo en Asientos borrados.');
  }catch(error){message(error.message);button.disabled=false;}
 }
 for(const action of content.querySelectorAll('[data-gestion-restore]')){
  action.onclick=()=>changeArchive(action,action.dataset.gestionRestore,true);
 }
 search.oninput=render;
 bucket.onchange=month.onchange=origin.onchange=render;
 const attach=bindGestionIntake(content);
 if(scan){attach(scan);content.querySelector('#gestionIntake').open=true;}
 render();
 const pendingOCR=sorted.filter(row=>row.needsReview&&row.files.length&&(row.needsOCR||!row.amount));
 const button=content.querySelector('#gestionRunOCR');
 const status=content.querySelector('#gestionOCRStatus');
 button.disabled=!pendingOCR.length;
 status.textContent=pendingOCR.length?`${pendingOCR.length} archivos pendientes de lectura.`:'No hay archivos pendientes de lectura.';
 async function run(){
  button.disabled=true;
  const result=await prepareGestionOCR(pendingOCR,status);
  if(!status.isConnected||!result)return;
  const previousMonth=month.value;
  const previousSearch=search.value;
  const previousOrigin=origin.value;
  if((result.prepared||result.partial)&&!content.querySelector('#gestionIntake').open){
   await gestionPage(content,false);
   const nextMonth=content.querySelector('#gestionMonth');
   const nextSearch=content.querySelector('#gestionSearch');
   const nextBucket=content.querySelector('[name="gestionBucket"]');
   nextMonth.value=previousMonth;
   nextSearch.value=previousSearch;
   content.querySelector('[name="gestionOrigin"]').value=previousOrigin;
   nextBucket.value='review';
   nextBucket.onchange();
  }else{
   button.disabled=false;
  }
  content.querySelector('#gestionOCRStatus').textContent=
   `${result.prepared} borradores preparados.${result.partial?' '+result.partial+' con datos parciales guardados.':''}${result.failed?' '+result.failed+' archivos sin datos reconocibles.':''}`;
 }
 button.onclick=()=>run().catch(error=>{if(status.isConnected){status.textContent=error.message;button.disabled=false;}});
 if(runOCR&&!scan&&pendingOCR.some(row=>row.needsOCR))void button.onclick();
}

async function prepareGestionOCR(rows,status){
 let prepared=0;
 let failed=0;
 let partial=0;
 for(const row of rows){
  if(!status.isConnected)return;
  const progress=`Leyendo factura ${prepared+failed+partial+1} de ${rows.length}`;
  status.textContent=progress;
  try{
   const url='/gestion/file/'+encodeURIComponent(row.files[0]);
   const embedded=await api(url+'?text=1').catch(()=>({text:''}));
   let source=embedded.text||'';
   let data=InvoiceOCR.parse(source);
   if(!Number.isFinite(data.amount)||data.amount<=0){
    const response=await fetch('/api'+url,{cache:'no-store'});
    if(!response.ok)throw Error('PDF no disponible');
    const blob=await response.blob();
    const file=new File([blob],blob.type==='application/pdf'?'factura.pdf':'factura',{type:blob.type});
    const result=await InvoiceOCR.read(file,step=>{if(status.isConnected)status.textContent=progress+' · '+step;},{cancelled:false});
    const alternative=InvoiceOCR.parse(result.text);
    source=source+'\n'+result.text;
    data=Object.fromEntries(Object.keys(alternative).map(key=>[
     key,typeof alternative[key]==='number'?(Number.isFinite(data[key])?data[key]:alternative[key]):data[key]||alternative[key]
    ]));
   }
   if(!status.isConnected)return;
   const hasAmount=Number.isFinite(data.amount)&&data.amount>0;
   if(!source.trim()||(!hasAmount&&!data.reference&&!data.date&&!data.taxId&&!data.counterparty))throw Error('PDF sin datos reconocibles');
   const draft={date:data.date||row.date||'',counterparty:(data.counterparty||row.supplier||'').slice(0,180),
     reference:data.reference||row.reference||'',taxId:data.taxId||row.taxId||'',concept:row.concept||data.concept||''};
   for(const key of ['baseAmount','taxAmount','amount'])draft[key]=Number.isFinite(data[key])?Math.max(0,Math.round(data[key]*100)):({baseAmount:row.base,taxAmount:row.tax,amount:row.amount})[key]||0;
   await api('/gestion/'+encodeURIComponent(row.id)+'/review','POST',draft);
   if(hasAmount)prepared++;else partial++;
  }catch{failed++;}
 }
 return {prepared,failed,partial};
}

async function teamAccountingPage(content){
 await featureViews.conta(content);
 if(window.DemoPortal?.active)return;
 const {rows}=await api('/gestion/team');
 if(!rows.length)return;
 const panel=document.createElement('details');
 panel.className='card';
 panel.innerHTML=`<summary>Imputaciones internas de Gestión · ${rows.length}</summary>
  <p>Importes asignados a ${esc(teamName(me.team))} en el reparto interno. Si un apunte del equipo figura también en esta tabla, el importe imputado sustituye al original para el control interno.</p>
  <div class="scroll"><table><thead><tr><th>Fecha</th><th>Proveedor</th><th>Factura o concepto</th><th>Movimiento</th><th>Importe imputado</th></tr></thead>
   <tbody>${rows.map(row=>`<tr><td>${esc(row.date)}</td><td>${esc(row.supplier)}</td><td>${esc([row.reference,row.concept].filter(Boolean).join(' · '))}</td><td>${esc(row.direction)}</td><td>${euros(row.amount)}</td></tr>`).join('')}</tbody>
  </table></div>`;
 content.prepend(panel);
}
