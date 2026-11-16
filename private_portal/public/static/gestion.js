'use strict';

async function gestionPage(content){
 const {rows,buckets}=await api('/gestion');
 const sorted=rows.sort((a,b)=>b.date.localeCompare(a.date)||a.supplier.localeCompare(b.supplier,'es'));
 content.innerHTML=`<h1>Gestión</h1><p>Contabilidad de Miribilla BTT Elkartea · CIF G95613758</p>
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
 ${select('Asignado a','gestionBucket',[['','Todos'],['pending','Pendientes de asignar'],...Object.entries(buckets)])}
 <label>Mes<input id="gestionMonth" type="month"></label><a class="button" id="gestionExport" href="/api/gestion/export">Exportar contabilidad consolidada</a></div>
 <div id="gestionTotals"></div><div id="gestionRows"></div>`;
 const search=content.querySelector('#gestionSearch');
 const bucket=content.querySelector('[name="gestionBucket"]');
 const month=content.querySelector('#gestionMonth');
 const list=content.querySelector('#gestionRows');
 const toCents=value=>Math.round(Number(value||0)*100);
 const summary=(items,getAmount)=>['Gasto','Ingreso'].map(direction=>
  `${direction==='Gasto'?'Gastos':'Ingresos'} ${euros(items.filter(item=>item.direction===direction).reduce((sum,item)=>sum+getAmount(item),0))}`
 ).join(' · ');
 function render(){
  content.querySelector('#gestionExport').href='/api/gestion/export'+(month.value?'?month='+encodeURIComponent(month.value):'');
  const query=search.value.trim().toLocaleLowerCase('es');
  const pending=row=>!Object.keys(row.allocations).length;
  const matches=sorted.filter(row=>
   (!month.value||row.date.startsWith(month.value))&&
   (!bucket.value||(bucket.value==='pending'?pending(row):row.allocations[bucket.value]>0))&&
   [row.supplier,row.reference,row.concept].join(' ').toLocaleLowerCase('es').includes(query));
  const amount=row=>buckets[bucket.value]?row.allocations[bucket.value]:row.amount;
  content.querySelector('#gestionTotals').innerHTML=`<p><strong>${matches.length} apuntes · ${summary(matches,amount)}</strong></p>`;
  list.innerHTML=matches.map(row=>{
   const allocations=Object.entries(row.allocations).map(([key,value])=>`${esc(buckets[key])} ${euros(value)}`).join(' · ');
   const source=buckets[row.team]||'Buzón de facturas';
   return `<details class="card">
    <summary>${esc(row.date||'Sin fecha')} · ${esc(row.supplier||row.concept||'Apunte')} · ${euros(row.amount)}</summary>
    <p>${esc([row.direction,source,row.reference,row.concept,row.status].filter(Boolean).join(' · '))}</p>
    ${row.base||row.tax?`<p>Base ${euros(row.base)} · IVA ${euros(row.tax)}</p>`:''}
    <p>${allocations||'Pendiente de asignar'}</p>
    ${row.files.map((id,index)=>`<a class="button" href="/api/gestion/file/${encodeURIComponent(id)}">Descargar original ${row.files.length>1?index+1:''}</a>`).join('')}
    ${row.amount>0?`<form id="gestion-split-${esc(row.id)}"><h3>Reparto interno (€)</h3>
     <div class="grid">${Object.entries(buckets).map(([key,label])=>
       `<label>${esc(label)}<input name="${key}" type="number" min="0" step="0.01" value="${row.allocations[key]?row.allocations[key]/100:''}"></label>`).join('')}</div>
     <button type="submit">Guardar reparto</button></form>`:''}
   </details>`;
  }).join('')||'<p>No hay apuntes con estos filtros.</p>';
  for(const row of matches)bindForm('gestion-split-'+row.id,async(_,data)=>{
   const amounts=Object.fromEntries(Object.keys(buckets).map(key=>[key,toCents(data[key])]).filter(([,value])=>value));
   if(Object.values(amounts).reduce((a,b)=>a+b,0)!==row.amount)throw Error('El reparto debe sumar '+euros(row.amount)+'.');
   await api('/gestion/'+encodeURIComponent(row.id)+'/allocation','POST',{amounts});
   row.allocations=amounts;
   render();
   message('Reparto guardado.');
  });
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
