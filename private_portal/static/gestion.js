'use strict';

async function gestionPage(content,runOCR=true){
 const {rows,buckets,mailAccounts}=await api('/gestion');
 const sorted=rows.sort((a,b)=>b.date.localeCompare(a.date)||a.supplier.localeCompare(b.supplier,'es'));
 content.innerHTML=`<h1>Gestión</h1><p>Contabilidad de Miribilla BTT Elkartea · CIF G95613758</p>
 <details class="card"><summary>Conectar Gmail</summary>
 <p>Configura un proyecto de Google Apps Script en cada cuenta y autoriza una vez la lectura de Gmail. El conector busca candidatos de Miribilla y carga el PDF para revisión.</p>
 <ol><li>Copia el <a href="/static/gestion-gmail.txt" target="_blank" rel="noopener">código del conector</a> en un <a href="https://script.google.com/home/projects/create" target="_blank" rel="noopener">proyecto de Apps Script</a> del buzón correspondiente. En Configuración, muestra <code>appsscript.json</code> y pega el <a href="/static/gestion-gmail-manifest.txt" target="_blank" rel="noopener">manifiesto de solo lectura</a> en ese archivo.</li>
 <li>En Configuración del proyecto → Propiedades de la secuencia de comandos, añade <code>GESTION_MAILBOX</code> con el correo y <code>GESTION_KEY</code> con la clave generada aquí.</li>
 <li>Ejecuta <code>conectarGestion</code> y autoriza el acceso en Google. El proyecto consultará el correo cada hora.</li></ol>
 <form id="gestionMailKey">${select('Buzón','account',mailAccounts)}<button type="submit">Generar clave de conexión</button></form>
 <div id="gestionMailKeyResult"></div></details>
 <details class="card"><summary>Añadir factura al buzón</summary>
 <form id="gestionInvoice"><div class="grid">
  <label>PDF original<input name="file" type="file" accept="application/pdf,.pdf" required></label>
  <label>Fecha de factura<input name="date" type="date" required></label>
  <label>Proveedor<input name="supplier" maxlength="180" required></label>
  <label>NIF del proveedor<input name="taxId" maxlength="40"></label>
  <label>Número de factura<input name="reference" maxlength="120" required></label>
  <label>Concepto<input name="concept" maxlength="250"></label>
  ${[['base','Base imponible (€)'],['tax','IVA (€)'],['amount','Total (€)']].map(([key,label])=>
    `<label>${label}<input name="${key}" type="number" min="0" step="0.01" ${key==='amount'?'required':''}></label>`).join('')}
 </div><button type="submit" class="primary">Guardar factura pendiente</button></form></details>
 <div class="toolbar"><label>Buscar<input id="gestionSearch" type="search" placeholder="Proveedor, número o concepto"></label>
 ${select('Asignado a','gestionBucket',[['','Todos'],['review','Pendientes de revisar'],['pending','Pendientes de asignar'],...Object.entries(buckets)])}
 <label>Mes<input id="gestionMonth" type="month"></label><a class="button" id="gestionExport" href="/api/gestion/export">Exportar contabilidad consolidada</a></div>
 <div class="toolbar"><button type="button" id="gestionRunOCR" class="primary">Leer facturas pendientes con OCR</button></div>
 <p id="gestionOCRStatus" role="status" aria-live="polite"></p>
 <div id="gestionTotals"></div><div id="gestionRows"></div>`;
 const search=content.querySelector('#gestionSearch');
 const bucket=content.querySelector('[name="gestionBucket"]');
 const month=content.querySelector('#gestionMonth');
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
   (!month.value||row.date.startsWith(month.value))&&
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
   </details>`;
  }).join('')||'<p>No hay apuntes con estos filtros.</p>';
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
 search.oninput=render;
 bucket.onchange=month.onchange=render;
 bindForm('gestionInvoice',async(form)=>{
  const payload=new FormData(form);
  for(const key of ['base','tax','amount'])payload.set(key,toCents(payload.get(key)));
  const result=await api('/gestion/invoices','POST',payload);
  await gestionPage(content);
  message(result.duplicate?'La factura ya está registrada.':'Factura original guardada, pendiente de asignar.');
 });
 render();
 const pendingOCR=sorted.filter(row=>row.needsReview&&row.files.length&&(row.needsOCR||!row.amount));
 const button=content.querySelector('#gestionRunOCR');
 const status=content.querySelector('#gestionOCRStatus');
 button.disabled=!pendingOCR.length;
 status.textContent=pendingOCR.length?`${pendingOCR.length} PDF pendientes de lectura.`:'No hay PDF pendientes de lectura.';
 async function run(){
  button.disabled=true;
  const result=await prepareGestionOCR(pendingOCR,status);
  if(!status.isConnected||!result)return;
  const previousMonth=month.value;
  const previousSearch=search.value;
  if(result.prepared||result.partial){
   await gestionPage(content,false);
   const nextMonth=content.querySelector('#gestionMonth');
   const nextSearch=content.querySelector('#gestionSearch');
   const nextBucket=content.querySelector('[name="gestionBucket"]');
   nextMonth.value=previousMonth;
   nextSearch.value=previousSearch;
   nextBucket.value='review';
   nextBucket.onchange();
  }else{
   button.disabled=false;
  }
  content.querySelector('#gestionOCRStatus').textContent=
   `${result.prepared} borradores preparados.${result.partial?' '+result.partial+' con datos parciales guardados.':''}${result.failed?' '+result.failed+' PDF sin datos reconocibles.':''}`;
 }
 button.onclick=()=>run().catch(error=>{if(status.isConnected){status.textContent=error.message;button.disabled=false;}});
 if(runOCR&&pendingOCR.some(row=>row.needsOCR))void button.onclick();
}

async function prepareGestionOCR(rows,status){
 let prepared=0;
 let failed=0;
 let partial=0;
 for(const row of rows){
  if(!status.isConnected)return;
  const progress=`Leyendo PDF ${prepared+failed+partial+1} de ${rows.length}`;
  status.textContent=progress;
  try{
   const response=await fetch('/api/gestion/file/'+encodeURIComponent(row.files[0]),{cache:'no-store'});
   if(!response.ok)throw Error('PDF no disponible');
   const file=new File([await response.blob()],'factura.pdf',{type:'application/pdf'});
   const result=await InvoiceOCR.read(file,step=>{if(status.isConnected)status.textContent=progress+' · '+step;},{cancelled:false});
   if(!status.isConnected)return;
   const data=InvoiceOCR.parse(result.text);
   const hasAmount=Number.isFinite(data.amount)&&data.amount>0;
   if(!result.text.trim()||(!hasAmount&&!data.reference&&!data.date&&!data.taxId&&!data.counterparty))throw Error('PDF sin datos reconocibles');
   const draft={date:data.date||row.date||'',counterparty:(data.counterparty||row.supplier||'').slice(0,180),
     reference:data.reference||row.reference||'',taxId:data.taxId||row.taxId||'',concept:data.concept||row.concept||''};
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
