'use strict';
const moduleLabels={staff:'Técnicos',vehicle:'Vehículos',travel:'Viajes, hoteles e inscripciones',result:'Resultados',days:'Días de actividad',entry:'CONTA · Ingresos y gastos',budget:'Presupuesto',bank:'Banco y conciliación',charge:'Liquidaciones por corredor',license:'Licencias',sport:'Material y medidas',post:'Publicaciones'};
const moduleSpecs={
 staff:[['name','Nombre'],['function','Función'],['city','Población'],['phone','Teléfono'],['user','Usuario técnico','person?'],['notes','Observaciones','textarea']],
 vehicle:[['name','Vehículo'],['plate','Matrícula'],['seats','Plazas','integer'],['driver','Conductor habitual'],['notes','Observaciones','textarea']],
 travel:[['event','Actividad','event'],['manager','Responsable general'],['registrationDeadline','Plazo de inscripción','date'],['registrationStatus','Estado inscripción',['Pendiente','Solicitada','Confirmada']],['registrationReference','Referencia inscripción'],['hotel','Hotel'],['hotelAddress','Dirección hotel'],['hotelPhone','Teléfono hotel'],['booking','Referencia de reserva'],['departureBilbao','Salida Bilbao'],['departureZaragoza','Salida Zaragoza'],['meeting','Punto y hora de encuentro'],['staff','Personal asignado','staff[]'],['vehicles','Vehículos asignados','vehicle[]'],['rooming','Distribución de habitaciones','textarea'],['routeUrl','Enlace al recorrido','url'],['scheduleUrl','Enlace horarios','url'],['plan','Planning y notas','textarea']],
 result:[['event','Carrera','event'],['rider','Corredor','runner'],['place','Puesto','integer'],['days','Días de competición','integer'],['discipline','Disciplina',['Carretera','Ciclocrós','XCO','Pista']],['notes','Valoración técnica','textarea']],
 days:[['event','Actividad','event'],['person','Persona','person'],['days','Días realizados','integer'],['function','Función'],['notes','Observaciones','textarea']],
 entry:[['date','Fecha','date'],['event','Actividad (opcional)','event?'],['direction','Movimiento',['Gasto','Ingreso']],['category','Categoría',['Inscripciones','Alojamiento','Gasolina','Supermercado','Manutención','Transporte','Material','Ropa','Patrocinio','Aportación clubes','Otros']],['budget','Partida presupuestaria','budget?'],['concept','Concepto'],['counterparty','Proveedor / pagador'],['reference','Referencia factura'],['taxId','NIF/CIF proveedor'],['baseAmount','Base imponible (€)','money'],['taxAmount','IVA (€)','money'],['amount','Importe (€)','money'],['status','Estado',['Pendiente','Pagado','Cobrado']],['notes','Notas','textarea']],
 budget:[['category','Partida'],['amount','Presupuesto (€)','money'],['notes','Notas','textarea']],
 bank:[['date','Fecha','date'],['direction','Movimiento',['Ingreso','Gasto']],['concept','Concepto'],['reference','Referencia'],['amount','Importe (€)','money'],['matched','Conciliado con apunte CONTA','entry?']],
 charge:[['event','Actividad','event?'],['rider','Corredor','runner'],['concept','Concepto'],['amount','Importe (€)','money'],['status','Estado',['Pendiente','Pagado','Anulado']],['notes','Observaciones','textarea']],
 license:[['rider','Corredor','runner'],['number','Número de licencia'],['status','Estado',['No aportada','Pendiente de revisión','Verificada','Caducada']],['expiration','Caducidad','date'],['notes','Observaciones','textarea']],
 sport:[['rider','Corredor','runner'],['bike','Bicicleta · marca y modelo'],['bikeSize','Talla bicicleta'],['helmet','Talla casco'],['pedals','Pedales'],['saddleHeight','Altura sillín (mm)','integer'],['saddleToBar','Distancia sillín–manillar (mm)','integer'],['coach','Preparador'],['club','Club de procedencia'],['notes','Notas deportivas','textarea']]
};
const featureViews={shop:shopPage,dashboard:dashboardPage,calls:callsPage,planning:c=>modulePage(c,'travel'),resources:resourcesPage,licenses:c=>modulePage(c,'license'),equipment:c=>modulePage(c,'sport'),results:c=>modulePage(c,'result'),days:c=>modulePage(c,'days'),conta:c=>modulePage(c,'entry'),budgets:c=>modulePage(c,'budget'),bank:c=>modulePage(c,'bank'),charges:c=>modulePage(c,'charge'),publications:communicationPage,archive:archivePage};
const euros=n=>new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format((Number(n)||0)/100);
let moduleContext={};
async function dashboardPage(c){if(me.role!=='director'){c.innerHTML='<h1>Mi equipo</h1><p>Utiliza el menú para consultar tus actividades y tu ficha.</p>';return;}const s=await api('/summary');c.innerHTML=`<h1>Panel de Dirección</h1><div class="metricgrid">${[[s.riders,'Corredores activos'],[s.events,'Actividades'],[s.staff,'Técnicos'],[s.vehicles,'Vehículos'],[euros(s.income),'Ingresos registrados'],[euros(s.expenses),'Gastos registrados']].map(([v,label])=>`<div class="card"><small>${label}</small><strong class="metric">${v}</strong></div>`).join('')}</div><div class="grid">${[['calendar','Carreras y calendario','Crear actividades y recoger disponibilidad'],['calls','Convocatorias','Seleccionar disponibles y publicar'],['planning','Viajes y hoteles','Inscripción, salidas, personal y habitaciones'],['resources','Técnicos y vehículos','Dar de alta y asignar recursos'],['licenses','Licencias y plantilla','Estado de cada corredor'],['conta','CONTA','Facturas, presupuesto, banco y cobros'],['publications','Comunicación','Diseños colectivos e individuales'],['users','Usuarios','Crear invitaciones y gestionar permisos']].map(([id,title,desc])=>`<button class="tile" data-shortcut="${id}"><strong>${title}</strong><small>${desc}</small></button>`).join('')}</div>`;c.querySelectorAll('[data-shortcut]').forEach(b=>b.onclick=()=>navigate(b.dataset.shortcut));}
async function getContext(kind){const [events,riders]=await Promise.all([api('/events'),api('/roster')]);const ctx={events:events.events,riders:riders.riders,people:[],staff:[],vehicle:[],entry:[],budget:[]};if(['director','technician'].includes(me.role))ctx.people=(await api('/people')).people;if(kind==='travel'){if(me.role!=='runner'){ctx.staff=(await api('/modules/staff')).records;ctx.vehicle=(await api('/modules/vehicle')).records;}}if(kind==='entry')ctx.budget=(await api('/modules/budget')).records;if(kind==='bank')ctx.entry=(await api('/modules/entry')).records;return ctx;}
function fieldOptions(type,ctx){const optional=String(type).endsWith('?');let values=[];if(type.startsWith('event'))values=ctx.events.map(x=>[x.id,x.name]);else if(type.startsWith('runner'))values=ctx.riders.map(x=>[x.id,x.name]);else if(type.startsWith('person'))values=ctx.people.map(x=>[x.id,x.name+' · '+roles[x.role]]);else if(type==='entry?')values=ctx.entry.map(x=>[x.id,x.concept+' · '+euros(x.amount)]);else values=(ctx[type]||[]).map(x=>[x.id,x.name]);return optional?[['','Sin asignar'],...values]:values;}
function moduleInput([key,label,type='text'],data,ctx){let v=data[key]??'';if(type==='budget?'){
 const options=[['','Sin asignar'],...ctx.budget.map(part=>[part.id,part.category])];
 if(v&&!ctx.budget.some(part=>part.id===v))options.push([v,(data.budgetName||'Partida')+' (archivada)']);
 return select(label,key,options,v);
}if(Array.isArray(type))return select(label,key,type,v);if(type==='textarea')return `<label>${esc(label)}<textarea name="${key}" maxlength="2500" rows="3">${esc(v)}</textarea></label>`;if(String(type).endsWith('[]')){const opts=fieldOptions(type.slice(0,-2),ctx);return `<fieldset><legend>${esc(label)}</legend>${opts.length?opts.map(([id,name])=>`<label class="checkline"><input type="checkbox" name="${key}" value="${id}" ${(data[key]||[]).includes(id)?'checked':''}>${esc(name)}</label>`).join(''):'Sin recursos registrados'}</fieldset>`;}if(['event','event?','runner','person','person?','entry?'].includes(type))return select(label,key,fieldOptions(type,ctx),v);if(type==='money')return `<label>${esc(label)}<input name="${key}" type="number" step="0.01" min="0" value="${v===''&&['baseAmount','taxAmount','amount'].includes(key)&&data.direction!==undefined?'':(Number(v)||0)/100}" ${['baseAmount','taxAmount'].includes(key)?'':'required'}></label>`;if(type==='integer')return `<label>${esc(label)}<input name="${key}" type="number" min="0" step="1" value="${v||0}" required></label>`;return field(label,key,type==='url'?'url':type==='date'?'date':'text',v);}
function moduleValue(value,key,ctx,spec){if(value===undefined)return '';if(spec.find(x=>x[0]===key)?.[2]==='money')return euros(value);if(['event','rider','person','matched'].includes(key))return [...ctx.events,...ctx.riders,...ctx.people,...ctx.entry].find(x=>x.id===value)?.name||ctx.entry.find(x=>x.id===value)?.concept||value||'Sin asignar';if(Array.isArray(value))return value.map(id=>[...ctx.staff,...ctx.vehicle].find(x=>x.id===id)?.name||id).join(', ');return String(value);}
async function modulePage(c,kind,editing=null,event=null){
const [ctx,d]=await Promise.all([getContext(kind),api('/modules/'+kind+(event?'?event='+encodeURIComponent(event.id):''))]);
if(event)ctx.fixedEvent=event;
const redraw=(id=null)=>modulePage(c,kind,id,event);
const issuedStaff=new Map();
moduleContext=ctx;const spec=moduleSpecs[kind];let rows=d.records;if(kind==='license')rows.sort((a,b)=>(ctx.riders.find(r=>r.id===a.rider)?.name||'').localeCompare(ctx.riders.find(r=>r.id===b.rider)?.name||'','es'));const canEdit=me.role==='director';if(me.role==='communication'&&kind!=='post')throw Error('Sin permiso');const edit=editing?rows.find(x=>x.id===editing)||{}:kind==='entry'?{event:event?.id||'',direction:'Gasto',status:'Pendiente',category:'Otros'}:{};let subnav='';if(me.role==='director'&&!event&&['entry','budget','bank','charge'].includes(kind))subnav=`<div class="toolbar">${[['conta','Ingresos y gastos'],['budgets','Presupuesto'],['bank','Banco'],['charges','Cobros por corredor']].map(([id,label])=>`<button data-finance="${id}">${label}</button>`).join('')}</div>`;
let totals='';if(kind==='days'){const total=rows.reduce((sum,r)=>sum+r.days,0);totals='<div class="note">Total de días registrados: <b>'+total+'</b></div>';}if(event){
  const subtotals=new Map();
  for(const row of rows){
    if(row.status==='Anulado')continue;
    const category=row.category||'Otros';
    subtotals.set(category,(subtotals.get(category)||0)+row.amount);
  }
  totals=`<div class="note"><strong>Coste total de la actividad: ${euros([...subtotals.values()].reduce((a,b)=>a+b,0))}</strong>
    ${[...subtotals].map(([label,amount])=>`<div>${esc(label)} · ${euros(amount)}</div>`).join('')}</div>`;
}else if(kind==='charge'){
 const active=rows.filter(row=>row.status!=='Anulado');
 const charged=active.reduce((sum,row)=>sum+row.amount,0);
 const paid=active.filter(row=>row.status==='Pagado').reduce((sum,row)=>sum+row.amount,0);
 totals=`<div class="metricgrid"><div class="card">Cargos registrados<strong class="metric">${euros(charged)}</strong></div><div class="card">Pagado<strong class="metric">${euros(paid)}</strong></div><div class="card">Pendiente<strong class="metric">${euros(charged-paid)}</strong></div></div>`;
}else if(['entry','budget','bank'].includes(kind)){let income=rows.filter(x=>x.direction==='Ingreso').reduce((s,x)=>s+x.amount,0),expense=rows.filter(x=>x.direction==='Gasto').reduce((s,x)=>s+x.amount,0);totals=kind==='entry'||kind==='bank'?`<div class="note">Ingresos: <b>${euros(income)}</b> · Gastos: <b>${euros(expense)}</b> · Saldo: <b>${euros(income-expense)}</b></div>`:`<div class="note">Total: <b>${euros(rows.filter(x=>x.status!=='Anulado').reduce((s,x)=>s+x.amount,0))}</b></div>`;if(kind==='entry'){const budgets=ctx.budget;totals+=`<p>Presupuesto de gasto: ${euros(budgets.reduce((s,x)=>s+x.amount,0))} · Disponible: ${euros(budgets.reduce((s,x)=>s+x.amount,0)-expense)}</p>`;}}
const renderField=f=>event&&['event','direction'].includes(f[0])?`<input type="hidden" name="${f[0]}" value="${esc(f[0]==='event'?event.id:'Gasto')}">`:moduleInput(f,edit,ctx);
const primaryEntryFields=['amount','direction','event','date','category','counterparty','concept'];
const fields=kind==='entry'?`<p>Solo necesitas indicar el importe. Puedes guardar la foto o el PDF sin usar OCR.</p>
 <p>Si vinculas el gasto a una actividad, usa <strong>Repartir gasto</strong> en su fila para cargarlo a los convocados.</p>
 <div class="grid">${spec.filter(([key])=>primaryEntryFields.includes(key)).map(renderField).join('')}</div>
 <details class="card"><summary>Más datos opcionales</summary><div class="grid">${spec.filter(([key])=>!primaryEntryFields.includes(key)).map(renderField).join('')}</div></details>`:
 `<div class="grid">${spec.map(renderField).join('')}</div>`;
c.innerHTML=`${event?'<h2>Facturas y gastos de la actividad</h2>':`<h1>${kind==='charge'&&me.role==='runner'?'Mi cuenta · gastos y recibos':moduleLabels[kind]}</h1>`}${subnav}${totals}<div class="toolbar">${event?'':`<a class="button" href="/api/modules/${kind}/export">Descargar Excel</a>`}${event?'<button id="openNew" type="button">+ Añadir factura o gasto</button>':canEdit?'<button id="openNew">+ Añadir registro</button>':''}</div>${kind==='charge'?'<p>Liquidaciones de desplazamientos y compras de la tienda. Los importes pendientes son deudas registradas.</p>':''}${kind==='bank'&&canEdit?'<div class="card"><h2>Importar extracto bancario</h2><small>Excel .xlsx o CSV. El Excel admite Fecha e Importe, o Fecha y Debe/Haber. Revisa los cargos y abonos antes de importar.</small><input type="file" id="bankcsv" accept=".csv,.xlsx"><div id="bankpreview"></div></div><section class="card" id="bankReconciliation"></section>':''}<div id="moduleEditor" ${editing?'':'hidden'}>${canEdit?`<form method="post" id="moduleForm" class="card"><h2>${editing?'Editar':'Nuevo registro'}</h2>${fields}<button class="primary" type="submit">Guardar</button> <button type="button" id="cancelEdit">Cancelar</button></form>`:''}</div><div class="toolbar"><label>Buscar<input id="moduleSearch" placeholder="Nombre, carrera, concepto…"></label>${kind==='license'?'<label>Estado<select id="licenseStatus"><option>Todos</option><option>No aportada</option><option>Pendiente de revisión</option><option>Verificada</option><option>Caducada</option></select></label>':''}</div><div id="moduleRows"></div>${event?`<details class="card"><summary>Repartir gastos entre los convocados</summary>
 <form id="splitExpenses"><p>Marca solo los gastos que se cobran a los corredores. Se dividen a partes iguales entre los convocados de la convocatoria publicada.</p>
 ${rows.filter(row=>row.amount>0&&row.status!=='Anulado').map(row=>`<label class="checkline"><input type="checkbox" name="expense" value="${esc(row.id)}" ${row.splitRecorded?'disabled':''}>${esc(row.concept||row.counterparty||row.category||'Gasto')} · ${euros(row.amount)}${row.splitRecorded?' · Ya repartido':''}</label>`).join('')}
 <button type="submit">Registrar cobros por corredor</button></form></details>`:''}`;
if(kind==='entry'&&canEdit){
 const exports=document.createElement('details');
 exports.className='card';
 exports.innerHTML=`<summary>Descargar facturas y relación de gastos</summary>
  <p>El PDF reúne los justificantes adjuntos. El Excel incluye los gastos, su total y los justificantes pendientes.</p>
  <form method="get" class="toolbar">
   ${event?`<input type="hidden" name="event" value="${esc(event.id)}">`:''}
   <label>Desde<input type="date" name="from"></label>
   <label>Hasta<input type="date" name="to"></label>
   <button type="submit" formaction="/api/invoices/report.pdf">Descargar facturas en PDF</button>
   <button type="submit" formaction="/api/invoices/report.xlsx">Descargar relación en Excel</button>
  </form><small>Deja las fechas vacías para incluir todos los gastos.</small>`;
 c.querySelector('.toolbar').after(exports);
}
const eventForExpense=row=>ctx.events.find(activity=>activity.id===row.event);
const canSplit=row=>row.event&&row.direction==='Gasto'&&row.amount>0&&row.status!=='Anulado';
async function splitExpenses(activity,selected){
 if(activity?.callStatus!=='Publicada')throw Error('Publica la convocatoria antes de repartir los gastos.');
 const expectedRiders=[...new Set(activity.called||[])].sort();
 if(!expectedRiders.length)throw Error('Selecciona y guarda los corredores de la convocatoria.');
 const amount=selected.reduce((sum,row)=>sum+row.amount,0);
 const names=expectedRiders.map(id=>ctx.riders.find(rider=>rider.id===id)?.name||'Corredor convocado');
 if(!confirm(`¿Cargar ${euros(amount)} de ${activity.name} a ${names.join(', ')}?`))return;
 const expenses=selected.map(row=>row.id);
 const result=await api('/events/'+encodeURIComponent(activity.id)+'/split-expenses','POST',{expenses,expectedRiders,expectedTotal:amount});
 selected.forEach(row=>{row.splitRecorded=true;});
 table();
 if(event)c.querySelectorAll('#splitExpenses input[name=expense]').forEach(input=>{
  if(!expenses.includes(input.value))return;
  input.checked=false;
  input.disabled=true;
  input.parentElement.append(' · Ya repartido');
 });
 message(`Cobro de ${euros(result.total)} registrado en ${result.riders===1?'la cuenta del corredor':`las cuentas de ${result.riders} corredores`}.`);
}
if(event)bindForm('splitExpenses',async form=>{
 const expenses=new Set(new FormData(form).getAll('expense'));
 if(!expenses.size)throw Error('Selecciona los gastos que quieres repartir.');
 await splitExpenses(ctx.events.find(activity=>activity.id===event.id),rows.filter(row=>expenses.has(row.id)));
});
function expenseSplitCell(row){
 if(kind!=='entry')return '';
 if(row.splitRecorded)return '<td>Ya repartido</td>';
 if(!canSplit(row))return '<td>—</td>';
 const activity=eventForExpense(row);
 if(!activity?.called?.length)return '<td>Sin corredores seleccionados</td>';
 if(activity.callStatus!=='Publicada')return '<td>Convocatoria por publicar</td>';
 return `<td><button type="button" data-split-expense="${esc(row.id)}">Repartir gasto</button></td>`;
}
function licenseCells(row){
 if(kind!=='license'||!me.documents)return '';
 const photos=row.photos||{};
 const original=['licencia','licencia_reverso'].map(key=>`<td>${photos[key]?`<a href="/api/file/${encodeURIComponent(photos[key])}">Ver archivo</a>`:'Pendiente'}</td>`).join('');
 const download=photos.licencia||photos.licencia_reverso?`<a class="button" href="/api/licenses/${encodeURIComponent(row.rider)}/pdf">Descargar licencia en PDF</a>`:'Sin licencia subida';
 return original+`<td>${download}</td>`;
}
function table(){const query=(document.getElementById('moduleSearch').value||'').toLocaleLowerCase('es');const status=document.getElementById('licenseStatus')?.value||'Todos';const filtered=rows.filter(r=>(status==='Todos'||r.status===status)&&spec.map(([key])=>key==='budget'?(r.budgetName||'Sin asignar'):moduleValue(r[key],key,ctx,spec)).join(' ').toLocaleLowerCase('es').includes(query));const columns=event?spec.filter(([key])=>['date','category','budget','concept','counterparty','amount','status'].includes(key)):kind==='entry'?spec.slice(0,6):spec.slice(0,5);document.getElementById('moduleRows').innerHTML=filtered.length?`<div class="card scroll"><table><thead><tr>${columns.map(x=>'<th>'+esc(x[1])+'</th>').join('')}${kind==='entry'?'<th>Justificante original</th><th>Cobro a convocados</th>':''}${kind==='budget'?'<th>Gasto asignado</th><th>Disponible</th>':''}${kind==='license'&&me.documents?'<th>Anverso</th><th>Reverso</th><th>Descarga</th>':''}<th>Detalle</th>${canEdit?'<th>Acciones</th>':''}</tr></thead><tbody>${filtered.map(r=>`<tr>${columns.map(([key])=>'<td>'+esc(key==='budget'?(r.budgetName||'Sin asignar'):moduleValue(r[key],key,ctx,spec))+'</td>').join('')}${kind==='entry'?`<td>${(r.attachments||[]).map(a=>`<a href="/api/invoice-file/${a.id}">${esc(a.name)}</a>`).join('<br>')||'Sin adjuntar'}</td>`:''}${kind==='budget'?`<td>${euros(r.spent)}</td><td>${euros(r.amount-r.spent)}</td>`:''}${expenseSplitCell(r)}${licenseCells(r)}<td><details><summary>Ver ficha</summary><dl>${spec.filter(([key])=>r[key]!==undefined).map(([key,label])=>`<dt>${esc(label)}</dt><dd>${esc(key==='budget'?(r.budgetName||'Sin asignar'):moduleValue(r[key],key,ctx,spec))}</dd>`).join('')}</dl></details></td>${canEdit&&kind==='license'&&!r.id?`<td><button data-new-license="${esc(r.rider)}">Añadir ficha</button></td>`:canEdit?`<td><button data-edit="${r.id}">Editar</button> <button data-archive="${r.id}">Archivar</button></td>`:''}</tr>`).join('')}</tbody></table></div>`:'<div class="card">Sin registros para mostrar.</div>';c.querySelectorAll('[data-new-license]').forEach(button=>button.onclick=()=>{
 document.getElementById('openNew').click();
 document.getElementById('moduleForm').elements.rider.value=button.dataset.newLicense;
});
c.querySelectorAll('[data-split-expense]').forEach(button=>button.onclick=async()=>{
 button.disabled=true;
 try{
  message('');
  const expense=rows.find(row=>row.id===button.dataset.splitExpense);
  await splitExpenses(eventForExpense(expense),[expense]);
 }catch(error){message(error.message);}
 finally{button.disabled=false;}
});
c.querySelectorAll('[data-edit]').forEach(b=>{
 b.onclick=()=>redraw(b.dataset.edit).catch(e=>message(e.message));
 if(kind==='staff')bindStaffPassword(b,rows.find(row=>row.id===b.dataset.edit),issuedStaff);
});c.querySelectorAll('[data-archive]').forEach(b=>b.onclick=async()=>{if(!confirm('¿Archivar este registro? Se puede restaurar desde Archivados.'))return;try{await api('/modules/'+kind+'/'+b.dataset.archive+'/archive','POST',{});await redraw();}catch(e){message(e.message);}});}
table();document.getElementById('moduleSearch').oninput=table;if(document.getElementById('licenseStatus'))document.getElementById('licenseStatus').onchange=table;c.querySelectorAll('[data-finance]').forEach(b=>b.onclick=()=>navigate(b.dataset.finance));if(canEdit){document.getElementById('openNew').onclick=async()=>{
 if(event&&editing){try{await redraw();}catch(err){message(err.message);return;}}
 document.getElementById('moduleEditor').hidden=false;
};document.getElementById('cancelEdit').onclick=()=>redraw().catch(e=>message(e.message));bindForm('moduleForm',async(f,data)=>{if(f.dataset.ocrReview==='true'&&!f.elements.ocrReviewed?.checked)throw Error('Revisa los datos detectados y marca la confirmación antes de guardar.');const out={};for(const [key,,type] of spec){if(type==='money'){const v=Number(data[key]);if(!Number.isFinite(v)||v<0)throw Error('Importe no válido');out[key]=Math.round(v*100);}else if(type==='integer')out[key]=Number(data[key]);else if(String(type).endsWith('[]'))out[key]=new FormData(f).getAll(key);else out[key]=data[key]||'';}if(event){out.event=event.id;out.direction='Gasto';}
if(kind==='entry'&&out.amount<=0)throw Error('Introduce un importe mayor que cero.');const savedId=editing||f.dataset.invoiceSavedId||'';const saved=await api('/modules/'+kind+(savedId?'/'+savedId:''),'POST',out);if(kind==='entry'&&f.invoiceOriginal){const id=savedId||saved.id;f.dataset.invoiceSavedId=id;const upload=new FormData();upload.append('file',f.invoiceOriginal);try{await api('/invoices/'+id,'POST',upload);}catch(error){throw Error('El apunte ya está guardado, pero no el original: '+error.message+'. Puedes volver a pulsar Guardar para adjuntarlo sin duplicar el gasto.');}}await redraw();message(kind==='entry'&&f.invoiceOriginal?'Apunte y original guardados.':'Registro guardado.');});}if(kind==='entry'&&canEdit)addInvoiceOCR(c,ctx);if(kind==='bank'&&canEdit){document.getElementById('bankcsv').onchange=bankPreview;await bankPanel(c.querySelector('#bankReconciliation'));}if(kind==='vehicle')await vehicleAvailability(c,rows,ctx.events);}
function bindStaffPassword(editButton,staff,issued){
 const button=document.createElement('button');
 button.type='button';
 const output=document.createElement('div');
 output.setAttribute('aria-live','polite');
 editButton.before(button);
 editButton.parentElement.append(output);
 const render=()=>{
  const account=issued.get(staff.id);
  const linked=Boolean(staff.user||account);
  button.hidden=linked&&!me.owner;
  button.textContent=linked?'Cambiar contraseña':'Generar contraseña';
  if(account)showTechnicianCredentials(output,[account]);
 };
 render();
 button.onclick=async()=>{
  const replace=Boolean(staff.user||issued.has(staff.id));
  if(replace&&!confirm('¿Cambiar la contraseña de '+staff.name+'? Se cerrarán sus sesiones y la contraseña anterior dejará de funcionar.'))return;
  button.disabled=true;
  try{
   message('');
   const {accounts:[account]}=await api('/staff/accounts','POST',{staffId:staff.id,replace});
   issued.set(staff.id,account);
   render();
  }catch(error){message(error.message);}
  finally{button.disabled=false;}
 };
}
function showTechnicianCredentials(container,accounts){
 container.innerHTML=`<p>Copia cada usuario y contraseña antes de salir de esta pantalla.</p>
  ${accounts.map(({name,username,password})=>`<div class="row"><strong>${esc(name)}</strong>
    <label>Usuario y contraseña<textarea rows="2" readonly spellcheck="false">${esc(username)}&#10;${esc(password)}</textarea></label>
    <button type="button" data-copy-technician>Copiar acceso</button></div>`).join('')}`;
 container.querySelectorAll('[data-copy-technician]').forEach(button=>button.onclick=async()=>{
  const input=button.parentElement.querySelector('textarea');
  try{await navigator.clipboard.writeText(input.value);button.textContent='Copiado';}
  catch{input.focus();input.select();}
 });
}
async function refreshHotelGuests(container,eventId){
  if(!container)return;
  const path='/events/'+encodeURIComponent(eventId)+'/hotel';
  const [people,attachments]=await Promise.all([api(path+'/guests'),api(path+'/identity-files')]);
  const guests=people.guests||[];
  const filesByGuest=new Map((attachments.guests||[]).map(guest=>[guest.id,guest.files]));
  container.innerHTML=`<summary>Huéspedes y DNI · ${guests.length}</summary>
    <div class="toolbar">
      <a class="button" href="/api/events/${encodeURIComponent(eventId)}/hotel/identity-pdf">Descargar DNI de todos · PDF único</a>

    </div><p>DNI guardados de los corredores seleccionados y técnicos asignados en este viaje.</p>
    ${guests.map(guest=>`<div class="row"><span>${esc(guest.name)} · ${guest.role} · ${guest.hasDni?'Número registrado':'Número pendiente'} · ${guest.photos||0} archivos del DNI</span>
      <div>${(filesByGuest.get(guest.id)||[]).map(file=>`<a class="button" href="/api/file/${encodeURIComponent(file.id)}">Descargar ${esc(file.side)} · ${esc(file.format)}</a>`).join(' ')||'<small>Documento pendiente de subir</small>'}</div>
      ${guest.role==='Técnico'?`<form method="post" data-staff-photo="${esc(guest.id)}">${select('Cara del DNI','side',[['front','Anverso'],['back','Reverso']])}<label>DNI · PDF, JPG o PNG<input type="file" name="file" accept="image/jpeg,image/png,application/pdf" required></label><button type="submit">Guardar documento del técnico</button></form>`:''}
      ${guest.role==='Técnico'?`<form method="post" data-staff-identity="${esc(guest.id)}"><label>Número de documento<input name="dni" maxlength="20" autocomplete="off" required></label><button type="submit">Guardar número</button>${guest.hasDni?'<button type="button" data-remove-identity>Quitar número</button>':''}</form>`:''}</div>`).join('')||'<p>Selecciona corredores o asigna técnicos en la ficha del viaje.</p>'}`;
  container.querySelectorAll('[data-staff-photo]').forEach(form=>{
    form.onsubmit=async e=>{
      e.preventDefault();
      const button=form.querySelector('button');
      button.disabled=true;
      try{
        await api(path+'/staff/'+encodeURIComponent(form.dataset.staffPhoto)+'/photo','POST',new FormData(form));
        form.reset();await refreshHotelGuests(container,eventId);message('Foto del DNI del técnico guardada.');
      }catch(err){message(err.message);}
      finally{button.disabled=false;}
    };
  });
  container.querySelectorAll('[data-staff-identity]').forEach(form=>{
    const save=async dni=>{
      try{
        await api(path+'/staff/'+encodeURIComponent(form.dataset.staffIdentity),'POST',{dni});
        await refreshHotelGuests(container,eventId);
        message(dni?'Número guardado.':'Número eliminado.');
      }catch(err){message(err.message);}
    };
    form.onsubmit=async e=>{
      e.preventDefault();
      await save(form.elements.dni.value.trim());
    };
    const remove=form.querySelector('[data-remove-identity]');
    if(remove)remove.onclick=()=>save('');
  });
}
async function eventTravelPanel(panel,event){
  const [travels,staff,vehicles]=await Promise.all([
    api('/modules/travel'),api('/modules/staff'),api('/modules/vehicle')
  ]);
  const travel=travels.records.find(item=>item.event===event.id)||{};
  const ctx={staff:staff.records,vehicle:vehicles.records};
  const spec=moduleSpecs.travel.filter(([key])=>key!=='event');
  let published=event.callStatus==='Publicada';
  const hotelLink=()=>me.documents?(published?`<a class="button" href="/api/events/${encodeURIComponent(event.id)}/hotel">Descargar listado del hotel con DNI</a> <a class="button" href="/api/events/${encodeURIComponent(event.id)}/hotel/identity-pdf">Descargar PDF privado de DNI</a>`:'<small>Publica la convocatoria para descargar los DNI del hotel.</small>'):'';
  panel.innerHTML=`<h2>Ficha del viaje</h2>
    <div class="toolbar">
      <span class="pill" id="travelCallStatus">Convocatoria: ${published?'Publicada':'Borrador'}</span>
      <button type="button" id="travelPublish">${published?'Volver a borrador':'Publicar convocatoria'}</button>
      <div id="travelHotelDownload">${hotelLink()}</div>
    </div>
    <form method="post" id="eventTravel">
      <div class="grid">${spec.map(field=>moduleInput(field,travel,ctx)).join('')}</div>
      <button type="submit" class="primary">Guardar ficha del viaje</button>
    </form>${me.documents?'<details class="card" id="hotelGuests"></details>':''}`;
  const guests=panel.querySelector('#hotelGuests');
  document.getElementById('travelPublish').onclick=async e=>{
    const button=e.currentTarget;
    button.disabled=true;
    try{
      await api('/events/'+event.id+'/details','POST',{callStatus:published?'Borrador':'Publicada'});
      published=!published;
      panel.querySelector('#travelCallStatus').textContent='Convocatoria: '+(published?'Publicada':'Borrador');
      panel.querySelector('#travelHotelDownload').innerHTML=hotelLink();
      button.textContent=published?'Volver a borrador':'Publicar convocatoria';
      message(published?'Convocatoria publicada.':'Convocatoria en borrador.');
    }catch(err){message(err.message);}
    finally{button.disabled=false;}
  };
  bindForm('eventTravel',async (form,data)=>{
    const formData=new FormData(form);
    const out={event:event.id};
    for(const [key,,type] of spec)out[key]=String(type).endsWith('[]')?formData.getAll(key):data[key]||'';
    const saved=await api('/modules/travel'+(travel.id?'/'+travel.id:''),'POST',out);
    travel.id=travel.id||saved.id;
    await refreshHotelGuests(guests,event.id);
    message('Ficha del viaje guardada.');
  });
  await refreshHotelGuests(guests,event.id);
}

async function vehicleAvailability(container,vehicles,events){
  const {records}=await api('/modules/travel');
  const section=document.createElement('section');
  section.className='card';
  section.innerHTML=`<details><summary>Calendario de reservas de vehículos</summary>
    <label>Consultar día<input type="date" id="vehicleDay" value="${calendarDateKey(new Date())}"></label>
    <div id="vehicleBookings"></div></details>`;
  container.prepend(section);
  const day=section.querySelector('#vehicleDay');
  const redraw=()=>{
    const output=section.querySelector('#vehicleBookings');
    if(!day.value){output.textContent='Selecciona un día.';return;}
    output.innerHTML=vehicles.map(vehicle=>{
      const assigned=records.filter(row=>row.vehicles?.includes(vehicle.id))
        .map(row=>events.find(event=>event.id===row.event)).filter(Boolean);
      const booked=assigned.filter(event=>event.date&&event.date<=day.value&&(event.date===day.value||event.endDate>=day.value));
      const undated=assigned.filter(event=>!event.date);
      return `<div class="row"><strong>${esc(vehicle.name)}</strong><span>${booked.length?'Reservado · '+booked.map(event=>esc(event.name)).join(', '):'Libre'}${undated.length?' · '+undated.length+' sin fecha confirmada':''}</span></div>`;
    }).join('')||'<p>No hay vehículos registrados.</p>';
  };
  day.onchange=redraw;
  redraw();
}
async function shopPage(c){
 const shop=await api('/shop');
 const director=me.role==='director';
 const sizes=['XXS','XS','S','M','L','XL','XXL','XXXL'];
 const products=shop.products.filter(product=>product.price!=null);
 c.innerHTML=`<h1>Tienda</h1><p>Compra de ropa adicional del equipo.</p>
  ${director?`<form id="shopSettings" class="card"><h2>Precios y director asignado</h2>
   ${select('Director que recibe los pedidos','director',[['','Seleccionar'],...shop.directors.map(user=>[user.id,user.name])],shop.director)}
   <div class="grid">${shop.products.map((product,index)=>`<label>${esc(product.name)} · €<input name="price-${index}" type="number" min="0.01" max="1000" step="0.01" value="${product.price==null?'':product.price/100}"></label>`).join('')}</div>
   <small>Deja el precio vacío para que la prenda no esté a la venta.</small><button type="submit">Guardar tienda</button></form>`:
   products.length?`<form id="shopOrder" class="card"><h2>Pedido adicional</h2><div class="grid">
    ${products.map((product,index)=>`<fieldset><legend>${esc(product.name)} · ${euros(product.price)}</legend>
     ${select('Talla','size-'+index,[['','Seleccionar'],...sizes])}<label>Unidades<input type="number" name="qty-${index}" min="0" max="20" step="1" value="0"></label></fieldset>`).join('')}</div>
    <p id="shopTotal"></p><button type="submit" class="primary">Confirmar pedido y registrar deuda</button></form>`:'<p>Todavía no hay prendas con precio.</p>'}
  <section class="card"><h2>${director?'Pedidos recibidos':'Mis pedidos'}</h2>
   ${shop.orders.map(order=>`<article class="row"><div><strong>${esc(order.name)} · ${euros(order.amount)}</strong>
   <p>${order.items.map(item=>esc(item.quantity+' × '+item.name+' · '+item.size)).join('<br>')}</p>
   <small>Correo a Dirección: ${esc(order.emailStatus)}</small></div>
   ${director&&order.emailStatus!=='Enviado'?`<button type="button" data-notify-order="${esc(order.id)}">Reintentar correo</button>`:''}</article>`).join('')||'<p>Aún no hay pedidos.</p>'}</section>`;
 bindForm('shopSettings',async(_,data)=>{
  const prices={};
  shop.products.forEach((product,index)=>{
   const price=data['price-'+index];
   if(price)prices[product.name]=Math.round(Number(price)*100);
  });
  await api('/shop/settings','POST',{director:data.director,prices});
  await shopPage(c);message('Tienda actualizada.');
 });
 const form=c.querySelector('#shopOrder');
 if(form){
  const token=crypto.randomUUID();
  const total=()=>products.reduce((sum,product,index)=>sum+product.price*Number(form.elements['qty-'+index].value),0);
  const showTotal=()=>{c.querySelector('#shopTotal').textContent='Total del pedido: '+euros(total());};
  form.oninput=showTotal;
  showTotal();
  bindForm('shopOrder',async(_,data)=>{
   const items=products.map((product,index)=>({name:product.name,size:data['size-'+index],quantity:Number(data['qty-'+index])})).filter(item=>item.quantity>0);
   if(!items.length)throw Error('Selecciona al menos una prenda.');
   if(items.some(item=>!item.size))throw Error('Elige la talla de cada prenda.');
   if(!confirm('¿Registrar el pedido de '+euros(total())+' en tu cuenta?'))return;
   const order=await api('/shop/orders','POST',{token,items,amount:total()});
   await shopPage(c);
   message(order.emailStatus==='Enviado'?'Pedido registrado y correo enviado.':'Pedido registrado. Correo pendiente de envío.');
  });
 }
 c.querySelectorAll('[data-notify-order]').forEach(button=>button.onclick=async()=>{
  button.disabled=true;
  try{
   const result=await api('/shop/orders/'+button.dataset.notifyOrder+'/notify','POST',{});
   await shopPage(c);
   message(result.emailStatus==='Enviado'?'Correo enviado.':'Correo pendiente. Revisa la configuración de envío.');
  }catch(err){message(err.message);}
  finally{button.disabled=false;}
 });
}
async function resourcesPage(c){
 c.innerHTML='<h1>Técnicos y vehículos</h1><div class="toolbar"><button type="button" id="availabilityTab">Disponibilidad y convocatorias</button><button type="button" id="stafftab">Personal técnico</button><button type="button" id="vehicletab">Vehículos</button></div><div id="resourcescontent"></div>';
 const content=c.querySelector('#resourcescontent');
 const show=async kind=>{
  c.querySelector('#availabilityTab').classList.toggle('active',kind==='all');
  c.querySelector('#stafftab').classList.toggle('active',kind==='staff');
  c.querySelector('#vehicletab').classList.toggle('active',kind==='vehicles');
  await resourceMatrix(content,kind);
 };
 c.querySelector('#availabilityTab').onclick=()=>show('all').catch(err=>message(err.message));
 c.querySelector('#stafftab').onclick=()=>show('staff').catch(err=>message(err.message));
 c.querySelector('#vehicletab').onclick=()=>show('vehicles').catch(err=>message(err.message));
 await show('all');
}

async function resourceMatrix(c,section){
 const [calendar,staff,vehicles,travel,overrides]=await Promise.all([
  api('/events'),api('/modules/staff'),api('/modules/vehicle'),api('/modules/travel'),api('/resource-availability')
 ]);
 const events=sortActivities(calendar.events);
 const statusRows=overrides.records||[];
 const resources={staff:staff.records,vehicles:vehicles.records};
 const assignments=new Map(travel.records.map(trip=>[trip.event,trip]));
 const range=event=>[event.date,event.endDate&&event.endDate>event.date?event.endDate:event.date];
 const overlap=(first,second)=>{
  const [a,b]=range(first),[x,y]=range(second);
  return a&&x&&a<=y&&x<=b;
 };
 function status(event,resource,kind){
  if((assignments.get(event.id)?.[kind]||[]).includes(resource.id)){
   return {label:kind==='staff'?'Convocado':'Reservado',style:'assigned',fixed:true};
  }
  const other=events.find(candidate=>candidate.id!==event.id&&overlap(event,candidate)&&
   (assignments.get(candidate.id)?.[kind]||[]).includes(resource.id));
  if(other)return {label:kind==='vehicles'?'Reservado':'No disponible',style:'unavailable',fixed:true,note:other.name};
  const manual=statusRows.find(row=>row.event===event.id&&row.resource===resource.id);
  const answer=manual?.status||(kind==='staff'?event.responses?.[resource.user]:null);
  const label=answer||(kind==='vehicles'?(event.date?'Disponible':'Por confirmar'):'Por confirmar');
  return {label,style:label==='No disponible'?'unavailable':label==='Disponible'||label==='Libre'?'available':'pending'};
 }
 c.innerHTML=`<h2>${section==='all'?'Disponibilidad y convocatorias':section==='staff'?'Disponibilidad de técnicos por carrera':'Disponibilidad de vehículos por carrera'}</h2>${section==='all'?'':`<button type="button" id="manageResources">Gestionar fichas de ${section==='staff'?'técnicos':'vehículos'}</button>`}
  ${section==='staff'&&me.role==='director'?`<details class="card"><summary>Dar de alta técnico</summary>
   <form id="createTechnician"><label>Nombre y apellidos<input name="name" maxlength="150" required></label>
    <button class="primary" type="submit">Guardar técnico y crear acceso</button></form>
   <p>Para las fichas que ya existen, genera los accesos pendientes con un solo botón.</p>
   <button type="button" id="createPendingTechnicians">Generar accesos pendientes</button>
   <p id="technicianAccountStatus" role="status"></p>
   <div id="technicianCredentials" hidden></div>
  </details>`:''}
  <div class="toolbar"><label>Buscar actividad<input type="search" id="resourceSearch" placeholder="Carrera, lugar…"></label>
   <label>Mes<input type="month" id="resourceMonth"></label><button type="button" id="resourceClear">Ver todo</button></div>
  <div class="toolbar resource-legend"><span class="resource-state available">Disponible</span><span class="resource-state assigned">Convocado / Reservado</span><span class="resource-state unavailable">No disponible</span><span class="resource-state pending">Por confirmar</span></div>
  <p>Abre una actividad pulsando su nombre. Las asignaciones se cargan de la ficha del viaje.${me.role==='director'?' Puedes indicar la disponibilidad en las celdas que aún no están asignadas.':''}</p>
  <div id="resourceTables"></div>`;
 const host=c.querySelector('#resourceTables');
 const search=c.querySelector('#resourceSearch'),month=c.querySelector('#resourceMonth');
 const newAccounts=c.querySelector('#createPendingTechnicians');
 if(newAccounts){
  const issued=[];
  const createAccounts=async data=>{
   const {accounts,skipped}=await api('/staff/accounts','POST',data);
   const results=c.querySelector('#technicianCredentials');
   if(!results)return;
   c.querySelector('#technicianAccountStatus').textContent=accounts.length?
    (accounts.length===1?'Se ha creado un acceso.':`Se han creado ${accounts.length} accesos.`):
    'No hay accesos pendientes. Revisa las fichas y los usuarios vinculados.';
   if(!accounts.length)return;
   issued.push(...accounts);
   results.hidden=false;
   showTechnicianCredentials(results,issued);
   if(skipped.length)c.querySelector('#technicianAccountStatus').textContent+=` ${skipped.length} fichas ya tenían un acceso o una cuenta con ese nombre.`;
   resources.staff=(await api('/modules/staff')).records;
   if(host.isConnected)render();
  };
  bindForm('createTechnician',async(form,data)=>{await createAccounts(data);form.reset();});
  newAccounts.onclick=async()=>{
   newAccounts.disabled=true;
   try{message('');await createAccounts({});}
   catch(error){message(error.message);}
   finally{newAccounts.disabled=false;}
  };
 }
 const render=()=>{
  const query=search.value.toLocaleLowerCase('es').trim();
  const filtered=events.filter(event=>(event.name+' '+(event.place||'')).toLocaleLowerCase('es').includes(query)&&
   (!month.value||activityMonth(event)===month.value||(event.date<month.value+'-01'&&event.endDate>=month.value+'-01')));
  host.innerHTML=[['staff','Técnicos'],['vehicles','Vehículos']].filter(([kind])=>section==='all'||kind===section).map(([kind,title])=>{
   const cols=[...resources[kind]].sort((a,b)=>a.name.localeCompare(b.name,'es'));
   return `<section class="card"><h2>${title}</h2>${cols.length?`<div class="resource-scroll" role="region" aria-label="Disponibilidad de ${title.toLowerCase()}" tabindex="0"><table class="resource-matrix">
    <thead><tr><th scope="col">Fecha · actividad</th>${cols.map(resource=>`<th scope="col">${esc(resource.name)}${resource.function?`<small>${esc(resource.function)}</small>`:''}${resource.plate?`<small>${esc(resource.plate)}</small>`:''}</th>`).join('')}</tr></thead>
    <tbody>${filtered.map(event=>`<tr><th scope="row"><small>${esc(activityDateLabel(event))}${event.endDate&&event.endDate!==event.date?' – '+esc(event.endDate):''}</small><button type="button" data-resource-event="${esc(event.id)}">${esc(event.name)}</button></th>
    ${cols.map(resource=>{
     const cell=status(event,resource,kind);
     return `<td class="resource-cell ${cell.style}">${me.role==='director'&&!cell.fixed?`<select data-resource="${esc(resource.id)}" data-resource-activity="${esc(event.id)}" aria-label="${esc(resource.name+' · '+event.name)}">
       ${[['Disponible','Disponible'],['No disponible','No disponible'],['Por confirmar','Por confirmar']].map(([value,label])=>`<option value="${value}" ${cell.label===label||cell.label===value?'selected':''}>${label}</option>`).join('')}
      </select>`:`<span>${esc(cell.label)}</span>`}${cell.note?`<small>${esc(cell.note)}</small>`:''}</td>`;
    }).join('')}</tr>`).join('')||`<tr><td colspan="${cols.length+1}">No hay actividades con estos filtros.</td></tr>`}</tbody></table></div>`:'<p>Aún no hay recursos registrados. Añádelos desde sus fichas.</p>'}</section>`;
  }).join('');
  host.querySelectorAll('[data-resource-event]').forEach(button=>button.onclick=()=>{
   page='calendar';
   const content=shell();
   calendarPage(content,button.dataset.resourceEvent).catch(err=>message(err.message));
  });
  host.querySelectorAll('[data-resource]').forEach(select=>select.onchange=async()=>{
   select.disabled=true;
   try{
    const update={event:select.dataset.resourceActivity,resource:select.dataset.resource,status:select.value};
    await api('/resource-availability','POST',update);
    const previous=statusRows.find(row=>row.event===update.event&&row.resource===update.resource);
    if(previous)Object.assign(previous,update);else statusRows.push(update);
    render();message('Disponibilidad guardada.');
   }catch(err){message(err.message);render();}
  });
 };
 const manage=c.querySelector('#manageResources');
 if(manage)manage.onclick=()=>modulePage(c,section==='staff'?'staff':'vehicle').catch(err=>message(err.message));
 search.oninput=render;month.onchange=render;
 c.querySelector('#resourceClear').onclick=()=>{search.value='';month.value='';render();};
 render();
}
async function callsPage(c){const [events,riders]=await Promise.all([api('/events'),api('/roster')]);let list=sortActivities(events.events);if(me.role==='runner')list=list.filter(x=>x.called.includes(me.id)&&x.callStatus==='Publicada');c.innerHTML=`<h1>${me.role==='runner'?'Mis convocatorias':'Convocatorias'}</h1>${me.role==='director'?'<p>Primero recoge disponibilidad en el calendario. Guarda la selección y publica la convocatoria aquí.</p>':''}<label>Buscar prueba o actividad<input id="callsSearch" type="search" placeholder="Ej. Guadiana"></label><div id="callsResults">`+list.map(ev=>`<div class="card" data-activity-search="${esc(ev.name)}"><h2>${esc(ev.name)}</h2><p>${esc(activityDateLabel(ev))} · ${esc(ev.place||'Lugar por confirmar')}</p><span class="pill">${esc(ev.callStatus||'Borrador')}</span><h3>Corredores seleccionados</h3><ul>${ev.called.map(id=>'<li>'+esc(riders.riders.find(r=>r.id===id)?.name||'Corredor')+'</li>').join('')||'<li>Sin corredores seleccionados.</li>'}</ul>${me.role==='director'?`<button data-open-call-event="${esc(ev.id)}">Abrir ficha y convocar</button> <button data-call-publish="${ev.id}" data-status="${ev.callStatus==='Publicada'?'Borrador':'Publicada'}">${ev.callStatus==='Publicada'?'Volver a borrador':'Publicar convocatoria'}</button>`:''}${me.role!=='director'?`<button data-planning="${ev.id}">Planning de viaje</button>`:''}${me.role==='director'?`<a class="button" href="/api/events/${ev.id}/package">Descargar convocatoria y paquete hotel</a>`:''}</div>`).join('')+'<p data-no-activities hidden>No hay convocatorias que coincidan.</p></div>';bindActivitySearch(document.getElementById('callsSearch'),document.getElementById('callsResults'));c.querySelectorAll('[data-open-call-event]').forEach(button=>button.onclick=()=>{page='calendar';const content=shell();calendarPage(content,button.dataset.openCallEvent).catch(err=>message(err.message));});c.querySelectorAll('[data-call-publish]').forEach(b=>b.onclick=async()=>{try{const e=events.events.find(x=>x.id===b.dataset.callPublish);if(b.dataset.status==='Publicada'&&!e.called.length)throw Error('Selecciona corredores antes de publicar.');await api('/events/'+e.id+'/details','POST',{callStatus:b.dataset.status});await callsPage(c);}catch(e){message(e.message);}});c.querySelectorAll('[data-planning]').forEach(b=>b.onclick=()=>navigate('planning'));}
async function archivePage(c){const d=await api('/archive');c.innerHTML='<h1>Registros archivados</h1><div class="card">'+(d.records.map(r=>`<div class="row"><span>${esc(moduleLabels[r.kind]||r.kind)} · ${esc(r.name||r.concept||r.hotel||r.number||r.date||r.id)}</span><button data-restore="${r.id}">Restaurar</button></div>`).join('')||'No hay registros archivados.')+'</div>';c.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{try{await api('/archive/'+b.dataset.restore+'/restore','POST',{});await archivePage(c);}catch(e){message(e.message);}});}
async function bankPanel(container){
 const {movements=[]}=await api('/bank/reconciliation');
 const groups=[
  ['Conciliados',movements.filter(row=>row.state==='Conciliado')],
  ['Facturas por revisar',movements.filter(row=>['Coincidencia única','Revisar coincidencias','Revisar enlace'].includes(row.state))],
  ['Cargos sin factura',movements.filter(row=>row.state==='Sin factura')]
 ];
 const total=rows=>euros(rows.reduce((sum,row)=>sum+row.amount,0));
 const links=invoice=>(invoice?.files||[]).map((id,index)=>`<a href="/api/invoice-file/${encodeURIComponent(id)}">Justificante ${index+1}</a>`).join(' · ');
 const invoiceLabel=invoice=>[invoice.date,invoice.supplier||invoice.concept||'Factura',invoice.reference].filter(Boolean).join(' · ');
 container.innerHTML=`<h2>Conciliar gastos con facturas</h2>
  <p>Las propuestas coinciden por importe total. Comprueba la fecha y el proveedor antes de confirmar.</p>
  <div class="metricgrid">${groups.map(([title,items])=>`<div class="card"><small>${title} · ${items.length}</small><strong class="metric">${total(items)}</strong></div>`).join('')}</div>
  ${groups.map(([title,items])=>`<details class="card" ${title==='Conciliados'?'':'open'}><summary>${title} · ${items.length} · ${total(items)}</summary>
   ${items.length?`<div class="scroll"><table><thead><tr><th>Fecha</th><th>Movimiento bancario</th><th>Importe</th><th>Justificante</th></tr></thead><tbody>${items.map(row=>`<tr>
    <td>${esc(row.date)}</td><td>${esc(row.concept||'Sin concepto')}${row.reference?`<small>${esc(row.reference)}</small>`:''}</td><td>${euros(row.amount)}</td>
    <td>${row.invoice?`<strong>${esc(invoiceLabel(row.invoice))}</strong><small>${esc(row.state)}</small><div>${links(row.invoice)}</div>`:''}
    ${row.candidates.length?`<label>Factura con el mismo importe<select data-invoice-option="${esc(row.id)}">
      ${row.candidates.length>1?'<option value="">Elige una factura</option>':''}
      ${row.candidates.map(invoice=>`<option value="${esc(invoice.id)}">${esc(invoiceLabel(invoice))}</option>`).join('')}</select></label>
      <div data-bank-files>${row.candidates.length===1?links(row.candidates[0]):''}</div>
      <button type="button" data-match-bank="${esc(row.id)}">Conciliar</button>`:''}
    ${row.matched?`<button type="button" data-unmatch-bank="${esc(row.id)}">Desvincular</button>`:''}
    ${!row.invoice&&!row.candidates.length?`<small>${esc(row.state)}</small>`:''}</td></tr>`).join('')}</tbody></table></div>`:'<p>Sin movimientos en este grupo.</p>'}</details>`).join('')}`;
 const save=async(button,movement,invoice)=>{
  button.disabled=true;
  try{
   await api('/bank/reconciliation/'+encodeURIComponent(movement),'POST',{invoice});
   await bankPanel(container);
   message(invoice?'Movimiento conciliado.':'Enlace retirado.');
  }catch(err){message(err.message);}
  finally{button.disabled=false;}
 };
 container.querySelectorAll('[data-invoice-option]').forEach(select=>select.onchange=()=>{
  const movement=movements.find(row=>row.id===select.dataset.invoiceOption);
  select.closest('td').querySelector('[data-bank-files]').innerHTML=links(movement.candidates.find(invoice=>invoice.id===select.value));
 });
 container.querySelectorAll('[data-match-bank]').forEach(button=>button.onclick=()=>{
  const row=button.closest('td');
  const invoice=row.querySelector('[data-invoice-option]').value;
  if(!invoice){message('Selecciona una factura.');return;}
  save(button,button.dataset.matchBank,invoice);
 });
 container.querySelectorAll('[data-unmatch-bank]').forEach(button=>button.onclick=()=>save(button,button.dataset.unmatchBank,''));
}
async function bankPreview(e){try{const file=e.target.files[0];if(!file)return;let parsed=[];
if(/\.xlsx$/i.test(file.name)){
 const upload=new FormData();upload.append('file',file);
 parsed=(await api('/bank/preview','POST',upload)).rows;
}else{
 const text=(await file.text()).replace(/^\uFEFF/,'').trim(),lines=text.split(/\r?\n/);for(const line of lines.slice(1)){const cells=line.split(';');if(cells.length<3)throw Error('Formato esperado: fecha;concepto;importe;referencia');let date=cells[0].trim();if(/^\d{2}\/\d{2}\/\d{4}$/.test(date))date=date.split('/').reverse().join('-');const amount=Number(cells[2].trim().replace(',','.'));if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(amount))throw Error('Fecha o importe no válido');parsed.push({date,concept:cells[1].trim(),amount:Math.round(Math.abs(amount)*100),direction:amount<0?'Gasto':'Ingreso',reference:(cells[3]||'').trim(),matched:''});}}const panel=document.getElementById('bankpreview');panel.innerHTML='<p>'+parsed.length+' movimientos para revisar</p><div class="scroll"><table><tr><th>Fecha</th><th>Concepto</th><th>Importe</th></tr>'+parsed.map(r=>`<tr><td>${esc(r.date)}</td><td>${esc(r.concept)}</td><td>${r.direction==='Gasto'?'-':''}${euros(r.amount)}</td></tr>`).join('')+'</table></div><button id="confirmBank" type="button">Confirmar importación</button>';document.getElementById('confirmBank').onclick=async()=>{try{const result=await api('/bank/import','POST',{rows:parsed});await navigate('bank');message(result.imported+' movimientos importados · '+result.duplicates+' ya registrados.');}catch(err){message(err.message);}};}catch(err){message(err.message);}}
async function communicationPage(c){const [posts,evs,media]=await Promise.all([api('/modules/post'),api('/events'),api('/media/roster')]);const editing=['director','communication'].includes(me.role);const events=evs.events.filter(e=>e.callStatus==='Publicada'&&e.called.length);let currentPost=null;const people=media.riders;let saved=posts.records;c.innerHTML=`<h1>${editing?'Comunicación del equipo':'Mis publicaciones'}</h1>${editing?`<form method="post" id="postForm" class="card"><h2>Crear publicación</h2><div class="grid">${select('Carrera · convocatoria publicada','event',events.map(e=>[e.id,e.name]))}${select('Publicación','type',['Colectiva','Individual'])}${select('Plantilla','template',[[1,'Convocatoria'],[2,'Protagonista'],[3,'Cartel de carrera'],[4,'Equipo'],[5,'Resultado']])}${select('Formato','format',['Cuadrado','Vertical','Story'])}${field('Titular','title')}${field('Texto secundario / fecha / resultado','subtitle')}</div><div id="postRiders"></div><button type="button" id="previewPost">Vista previa</button> <button class="primary" type="submit">Guardar borrador</button></form>`:''}<div class="card"><h2>Vista previa</h2><canvas id="postCanvas" width="1080" height="1080" aria-label="Vista previa de la publicación"></canvas><div class="toolbar"><button id="downloadPost" disabled>Descargar PNG</button><button id="sharePost" disabled>Compartir</button></div><p id="postHint">Selecciona una publicación o prepara una vista previa.</p></div><div class="card"><h2>Publicaciones guardadas</h2><div id="savedPosts"></div></div>`;
function renderSaved(){document.getElementById('savedPosts').innerHTML=saved.length?saved.map(p=>`<div class="row"><span><strong>${esc(p.title||evs.events.find(e=>e.id===p.event)?.name||'Publicación')}</strong><small>${esc(p.type)} · ${esc(p.format)} · ${esc(p.status)}</small></span><div><button data-view-post="${p.id}">Abrir</button>${editing?` <button data-post-status="${p.id}">${p.status==='Aprobada'?'Retirar aprobación':'Aprobar y entregar'}</button>`:''}</div></div>`).join(''):'No hay publicaciones guardadas.';c.querySelectorAll('[data-view-post]').forEach(b=>b.onclick=async()=>{currentPost=saved.find(p=>p.id===b.dataset.viewPost);try{await drawPost(currentPost);}catch(e){message(e.message);}});c.querySelectorAll('[data-post-status]').forEach(b=>b.onclick=async()=>{const p=saved.find(p=>p.id===b.dataset.postStatus);try{const {id,...data}=p;data.status=p.status==='Aprobada'?'Borrador':'Aprobada';await api('/modules/post/'+id,'POST',data);await communicationPage(c);}catch(e){message(e.message);}});}
renderSaved();
function updateRiders(){const form=document.getElementById('postForm');const event=events.find(e=>e.id===form.elements.event.value);const ids=event?.called||[];document.getElementById('postRiders').innerHTML='<h3>Corredores de la convocatoria</h3>'+(ids.length?ids.map(id=>{const p=people.find(x=>x.id===id);return p?`<label class="checkline"><input type="checkbox" name="riders" value="${id}" checked>${esc(p.name)}</label>`:'<p class="danger">Un corredor convocado no tiene permiso de imagen registrado.</p>';}).join(''):'<p>Publica una convocatoria desde Dirección para generar diseños.</p>');}
function readPost(){const f=document.getElementById('postForm');const data=Object.fromEntries(new FormData(f));data.template=Number(data.template);data.riders=new FormData(f).getAll('riders');data.status='Borrador';const ev=events.find(e=>e.id===data.event);if(!ev||!data.riders.length)throw Error('Selecciona una convocatoria y corredores autorizados.');if(data.type==='Individual'&&data.riders.length!==1)throw Error('Para el diseño individual selecciona un solo corredor.');if(data.type==='Colectiva'&&ev.called.some(id=>!people.some(p=>p.id===id)))throw Error('Falta autorización de imagen de algún corredor convocado.');return data;}
if(editing){updateRiders();document.getElementById('postForm').elements.event.onchange=updateRiders;document.getElementById('previewPost').onclick=async()=>{try{currentPost=readPost();await drawPost(currentPost);}catch(e){message(e.message);}};bindForm('postForm',async()=>{const data=readPost();await api('/modules/post','POST',data);await communicationPage(c);message('Borrador guardado. Revisa el diseño y apruébalo para entregarlo a los corredores.');});}
async function imageFor(rider){if(!rider)return null;const f=rider.photos.find(x=>x.kind==='portrait')||rider.photos[0];if(!f)return null;const r=await fetch('/api/file/'+f.id,{credentials:'same-origin'});if(!r.ok)return null;const blob=await r.blob();return createImageBitmap(blob);}
async function drawPost(p){const canvas=document.getElementById('postCanvas'),ctx=canvas.getContext('2d'),event=evs.events.find(e=>e.id===p.event);canvas.width=1080;canvas.height=p.format==='Story'?1920:p.format==='Vertical'?1350:1080;const h=canvas.height;const template=Number(p.template)||1;const bg=template===2||template===4?'#f3f5f7':'#122b43',fg=template===2||template===4?'#122b43':'#ffffff';ctx.fillStyle=bg;ctx.fillRect(0,0,1080,h);ctx.fillStyle='#e46b13';if(template===3){ctx.fillRect(0,0,1080,300);}else if(template===5){ctx.fillRect(0,0,35,h);}else{ctx.fillRect(0,0,1080,22);}ctx.fillStyle=fg;ctx.font='600 32px sans-serif';ctx.fillText('MIRIBILLA × ECOTISA',64,90);ctx.font='400 25px sans-serif';ctx.fillText('JÚNIOR 2027',64,132);
function wrapped(text,x,y,width,font,lineHeight){ctx.font=font;const words=String(text).split(/\s+/);let line='',yy=y;for(const word of words){const test=line?line+' '+word:word;if(ctx.measureText(test).width>width&&line){ctx.fillText(line,x,yy);line=word;yy+=lineHeight;}else line=test;}ctx.fillText(line,x,yy);return yy+lineHeight;}
let y=wrapped(p.title||event?.name||'Equipo',64,230,950,'600 62px sans-serif',74);ctx.font='400 30px sans-serif';y=wrapped(p.subtitle||event?.date||'Fecha por confirmar',64,y+10,950,'400 30px sans-serif',40)+20;const selected=p.riders.map(id=>people.find(x=>x.id===id)||{id,name:me.id===id?me.name:'Corredor',photos:[]});const cols=selected.length===1?1:selected.length<=4?2:selected.length>12?4:3;const gap=20,w=(950-gap*(cols-1))/cols;const rows=Math.ceil(selected.length/cols);const cardH=Math.min(selected.length===1?Math.min(650,h-y-120):300,Math.max(90,(h-y-110)/Math.max(rows,1)-20));for(let i=0;i<selected.length;i++){const rider=selected[i],x=64+(i%cols)*(w+gap),cy=y+Math.floor(i/cols)*(cardH+20);ctx.fillStyle=template===2||template===4?'#dce4eb':'#23445f';ctx.fillRect(x,cy,w,cardH);const img=await imageFor(rider);if(img){const photoH=Math.max(0,cardH-60);if(photoH){const scale=Math.max(w/img.width,photoH/img.height);ctx.save();ctx.beginPath();ctx.rect(x,cy,w,photoH);ctx.clip();ctx.drawImage(img,x+(w-img.width*scale)/2,cy+(photoH-img.height*scale)/2,img.width*scale,img.height*scale);ctx.restore();}img.close();}else{ctx.fillStyle=fg;ctx.font='600 60px sans-serif';ctx.fillText(rider.name.slice(0,1),x+24,cy+Math.min(80,cardH-10));}ctx.fillStyle=fg;ctx.font='500 25px sans-serif';let name=rider.name;while(ctx.measureText(name).width>w-24&&name.length>1)name=name.slice(0,-1);ctx.fillText(name,x+12,cy+cardH-20);}ctx.fillStyle=fg;ctx.font='400 24px sans-serif';ctx.fillText(event?.place||'Miribilla Cycling · Ecotisa',64,h-45);document.getElementById('downloadPost').disabled=false;document.getElementById('sharePost').disabled=false;document.getElementById('postHint').textContent=(p.status||'Vista previa')+' · '+p.format;}
document.getElementById('downloadPost').onclick=()=>{const a=document.createElement('a');a.download='Miribilla_Ecotisa_'+(currentPost?.type||'publicacion')+'.png';a.href=document.getElementById('postCanvas').toDataURL('image/png');a.click();};document.getElementById('sharePost').onclick=()=>{document.getElementById('postCanvas').toBlob(async blob=>{try{const f=new File([blob],'Miribilla_Ecotisa.png',{type:'image/png'});if(navigator.canShare?.({files:[f]})){await navigator.share({files:[f],title:currentPost?.title||'Miribilla Ecotisa'});}else{document.getElementById('downloadPost').click();message('Imagen descargada. Puedes publicarla desde tu red social.');}}catch(e){if(e.name!=='AbortError')message(e.message);}},'image/png');};if(saved.length){currentPost=saved[saved.length-1];await drawPost(currentPost);}}
function editEvent(c,event){c.innerHTML=`<h1>Editar actividad</h1><form method="post" id="eventDetails" class="card"><div class="grid">${[['name','Nombre'],['date','Fecha de inicio','date'],['endDate','Fecha de fin','date'],['place','Lugar'],['category','Actividad',['Carrera','Concentración','Entrenamiento de equipo','Trabajo de equipo']],['type','Categoría de carrera / circuito'],['status','Estado',['Programada','Confirmada','Finalizada','Cancelada']],['owner','Responsable']].map(f=>moduleInput(f,event,{})).join('')}</div><label>Información / horarios<textarea name="notes" rows="5">${esc(event.notes||'')}</textarea></label><button type="submit" class="primary">Guardar actividad</button><button id="backCalendar" type="button">Volver a la actividad</button></form>`;bindForm('eventDetails',async(_,data)=>{await api('/events/'+event.id+'/details','POST',data);await calendarPage(c,event.id);message('Actividad actualizada.');});document.getElementById('backCalendar').onclick=()=>calendarPage(c,event.id).catch(err=>message(err.message));}
function addBulkUserImport(c){if(!me.owner)return;const box=document.createElement('div');box.className='card';box.innerHTML='<h2>Alta de usuarios desde listado</h2><small>CSV con columnas: nombre;correo;perfil. Perfiles: Dirección, Técnico, Corredor o Comunicación.</small><input type="file" id="usersCsv" accept=".csv"><div id="usersCsvPreview"></div>';c.prepend(box);document.getElementById('usersCsv').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;const lines=(await f.text()).replace(/^\uFEFF/,'').trim().split(/\r?\n/);const map={'dirección':'director','direccion':'director','técnico':'technician','tecnico':'technician','corredor':'runner','comunicación':'communication','comunicacion':'communication'};const rows=lines.slice(1).map(l=>{const p=l.split(';').map(x=>x.trim());return {name:p[0],email:p[1],role:map[(p[2]||'').toLowerCase()]||p[2]};});if(rows.some(r=>!r.name||!r.email?.includes('@')||!roles[r.role]))throw Error('Revisa nombre, correo y perfil en cada fila.');document.getElementById('usersCsvPreview').innerHTML='<p>'+rows.length+' usuarios para revisar</p>'+rows.map(r=>'<p>'+esc(r.name)+' · '+esc(r.email)+' · '+esc(roles[r.role])+'</p>').join('')+'<button id="bulkUsersConfirm">Crear invitaciones</button>';document.getElementById('bulkUsersConfirm').onclick=async()=>{try{const response=await api('/invites/import','POST',{rows});document.getElementById('usersCsvPreview').innerHTML='<h3>Invitaciones creadas · entrega cada enlace a su destinatario</h3>'+response.invitations.map(i=>'<div class="row"><div>'+esc(i.name)+' · '+esc(i.email)+'<p class="secret">'+esc(inviteLink(i.token))+'</p></div></div>').join('')+'<small>No se ha enviado ningún correo. Los enlaces caducan en 48 horas.</small>';}catch(err){message(err.message);}};}catch(err){message(err.message);}};}
