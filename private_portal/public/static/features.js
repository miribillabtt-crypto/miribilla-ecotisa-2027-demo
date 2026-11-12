'use strict';
const moduleLabels={fine:'Multa',event:'Carrera o actividad',staff:'Técnicos',vehicle:'Vehículos',travel:'Viajes, hoteles e inscripciones',result:'Resultados',days:'Días de actividad',entry:'CONTA · Ingresos y gastos',budget:'Presupuesto',bank:'Banco y conciliación',charge:'Liquidaciones por corredor',license:'Licencias',sport:'Material y medidas',post:'Publicaciones'};
const moduleSpecs={
 staff:[['name','Nombre'],['function','Función'],['city','Población'],['phone','Teléfono'],['user','Usuario técnico','person?'],['notes','Observaciones','textarea']],
 vehicle:[['name','Vehículo'],['plate','Matrícula'],['seats','Plazas','integer'],['driver','Conductor habitual'],['notes','Observaciones','textarea']],
 travel:[['event','Actividad','event'],['manager','Responsable general'],['registrationDeadline','Plazo de inscripción','date'],['registrationStatus','Estado inscripción',['Pendiente','Solicitada','Confirmada']],['registrationReference','Referencia inscripción'],['hotel','Hotel'],['hotelAddress','Dirección hotel'],['hotelPhone','Teléfono hotel'],['booking','Referencia de reserva'],['departureBilbao','Salida Bilbao'],['departureZaragoza','Salida Zaragoza'],['meeting','Punto y hora de encuentro'],['staff','Personal asignado','staff[]'],['vehicles','Vehículos asignados','vehicle[]'],['rooming','Distribución de habitaciones','textarea'],['routeUrl','Enlace al recorrido','url'],['scheduleUrl','Enlace horarios','url'],['plan','Planning y notas','textarea']],
 result:[['event','Carrera','event'],['rider','Corredor','runner'],['place','Puesto','integer'],['days','Días de competición','integer'],['discipline','Disciplina',['Carretera','Ciclocrós','XCO','Pista']],['notes','Valoración técnica','textarea']],
 days:[['event','Actividad','event'],['person','Persona','person'],['days','Días realizados','integer'],['function','Función'],['notes','Observaciones','textarea']],
 entry:[['date','Fecha','date'],['event','Actividad (opcional)','event?'],['direction','Movimiento',['Gasto','Ingreso']],['category','Categoría',['Inscripciones','Alojamiento','Gasolina','Supermercado','Manutención','Transporte','Material','Ropa','Patrocinio','Aportación clubes','Otros']],['budget','Partida presupuestaria','budget?'],['concept','Concepto'],['counterparty','Proveedor / emisor'],['reference','Referencia factura'],['taxId','NIF/CIF proveedor'],['baseAmount','Base imponible (€)','money'],['taxAmount','IVA (€)','money'],['amount','Importe (€)','money'],['status','Estado',['Pendiente','Pagado','Cobrado']],['payerClub','Club que adelanta el dinero',[['','Sin asignar'],'Miribilla','Ecotisa']],['paidBy','Quién paga · nombre o cuenta utilizada'],['paymentDate','Fecha de pago','date'],['allocationRule','Criterio de reparto',[['','Pendiente de decidir'],['Miribilla','100 % Miribilla'],['Ecotisa','100 % Ecotisa'],['Mitad','50 % cada club'],['Personalizado','Porcentaje personalizado']]],['miribillaPercent','% a cargo de Miribilla · resto Ecotisa','integer'],['notes','Notas','textarea']],
 budget:[['category','Partida'],['amount','Presupuesto (€)','money'],['notes','Notas','textarea']],
 bank:[['date','Fecha','date'],['direction','Movimiento',['Ingreso','Gasto']],['concept','Concepto'],['reference','Referencia'],['amount','Importe (€)','money'],['matched','Conciliado con apunte CONTA','entry?']],
 charge:[['event','Actividad','event?'],['rider','Corredor','runner'],['concept','Concepto'],['amount','Importe (€)','money'],['status','Estado',['Pendiente','Pagado','Anulado']],['notes','Observaciones','textarea']],
 license:[['rider','Corredor','runner'],['number','Número de licencia'],['status','Estado',['No aportada','Pendiente de revisión','Verificada','Caducada']],['expiration','Caducidad','date'],['notes','Observaciones','textarea']],
 sport:[['rider','Corredor','runner'],['bike','Bicicleta · marca y modelo'],['bikeSize','Talla bicicleta'],['helmet','Talla casco'],['pedals','Pedales'],['saddleHeight','Altura sillín (mm)','integer'],['saddleToBar','Distancia sillín–manillar (mm)','integer'],['coach','Preparador'],['club','Club de procedencia'],['notes','Notas deportivas','textarea']]
};
const featureViews={vehicles:c=>resourceMatrix(c,'vehicles'),vehiclefiles:c=>modulePage(c,'vehicle'),whatsapp:whatsAppPage,vehiclelogs:vehicleLogsPage,clubsettlement:clubSettlementPage,shop:shopPage,dashboard:dashboardPage,calls:callsPage,planning:c=>modulePage(c,'travel'),resources:resourcesPage,licenses:c=>modulePage(c,'license'),equipment:equipmentPage,results:c=>modulePage(c,'result'),days:c=>modulePage(c,'days'),conta:c=>modulePage(c,'entry'),budgets:c=>modulePage(c,'budget'),bank:c=>modulePage(c,'bank'),charges:c=>modulePage(c,'charge'),publications:communicationPage,archive:archivePage};
const euros=n=>new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format((Number(n)||0)/100);
let moduleContext={};
async function dashboardPage(c){
 if(me.role!=='director'){c.innerHTML='<h1>Mi equipo</h1><p>Utiliza el menú para consultar tus actividades y tu ficha.</p>';
 if(me.role==='technician'){
  c.insertAdjacentHTML('beforeend','<button type="button" class="primary" id="quickVehicleKm">Registrar km</button>');
  c.querySelector('#quickVehicleKm').onclick=()=>navigate('vehiclelogs');
 }
 return;}
 const s=await api('/summary');
 const actions=[
  ['calendar','Calendario','Carreras, convocatorias, viajes y gastos por actividad'],
  ['roster','Equipo','Corredores, fichas, licencias y ropa'],
  ['resources','Técnicos','Disponibilidad, fichas y accesos técnicos'],
  ['vehicles','Vehículos','Reservas, fichas y kilómetros'],
  ['conta','Contabilidad','Facturas, cobros por corredor y conciliación'],
  ['whatsapp','Avisos por WhatsApp','Preparar un aviso para un contacto o grupo'],
 ];
 c.innerHTML=`<h1>Panel de Dirección · ${me.team==='occident'?'Occident':'Netkom'}</h1>
  ${me.team==='occident'&&me.canSwitchTeam?`<section class="card"><h2>Acceso de Alex Toledo</h2><button type="button" id="inviteOccidentAdmin">Generar enlace de activación</button><div id="occidentInviteResult" aria-live="polite"></div></section>`:''}
  <div class="grid direction-actions">${actions.map(([id,title,desc])=>`<button type="button" class="tile" data-shortcut="${id}"><strong>${title}</strong><small>${desc}</small></button>`).join('')}</div>
  <h2>Resumen del equipo</h2><div class="metricgrid">${[[s.riders,'Corredores activos'],[s.events,'Actividades'],[s.staff,'Técnicos'],[s.vehicles,'Vehículos'],[euros(s.income),'Ingresos registrados'],[euros(s.expenses),'Gastos registrados']].map(([v,label])=>`<div class="card"><small>${label}</small><strong class="metric">${v}</strong></div>`).join('')}</div>`;
 c.querySelectorAll('[data-shortcut]').forEach(b=>b.onclick=()=>navigate(b.dataset.shortcut));
 const invite=c.querySelector('#inviteOccidentAdmin');
 if(invite)invite.onclick=async()=>{
  invite.disabled=true;
  try{
   const {token,username}=await api('/occident/administrator-invite','POST',{});
   c.querySelector('#occidentInviteResult').innerHTML=`<p>Usuario <strong>${esc(username)}</strong>. El enlace caduca en 48 horas.</p><label>Enlace para Alex Toledo<input readonly value="${esc(inviteLink(token))}"></label>`;
  }catch(error){message(error.message);}
  finally{invite.disabled=false;}
 };
}
async function getContext(kind){const [events,riders]=await Promise.all([api('/events'),api('/roster')]);const ctx={events:events.events,riders:riders.riders,people:[],staff:[],vehicle:[],entry:[],budget:[]};if(['director','technician'].includes(me.role))ctx.people=(await api('/people')).people;if(kind==='travel'){if(me.role!=='runner'){ctx.staff=(await api('/modules/staff')).records;ctx.vehicle=(await api('/modules/vehicle')).records;}}if(kind==='entry')ctx.budget=(await api('/modules/budget')).records;if(kind==='bank')ctx.entry=(await api('/modules/entry')).records;return ctx;}
async function equipmentPage(c){
 const [{riders},{records}]=await Promise.all([api('/roster'),api('/modules/sport')]);
 const byRider=new Map(records.map(record=>[record.rider,record]));
 const director=me.role==='director';
 const measure=value=>Number(value)>0?esc(value):'Sin indicar';
 c.innerHTML=`<h1>Medidas de la bici</h1>
  <p>Alto: altura del sillín. Largo: distancia sillín–manillar. Medidas en milímetros.</p>
  <div class="toolbar"><label>Buscar corredor<input type="search" id="bikeRiderSearch" placeholder="Nombre o apellidos"></label>
   <a class="button" href="/api/modules/sport/export">Descargar Excel</a></div>
  <div class="card scroll" id="bikeMeasurements"><table>
   <thead><tr><th>Corredor</th><th>Talla de bici</th><th>Alto (mm)</th><th>Largo (mm)</th></tr></thead>
   <tbody>${[...riders].sort((a,b)=>a.name.localeCompare(b.name,'es')).map(rider=>{
    const record=byRider.get(rider.id)||{};
    return `<tr data-search-name="${esc(rider.name)}"><td><strong>${esc(rider.name)}</strong>
     ${director?`<button type="button" data-edit-bike="${esc(rider.id)}">Editar</button>`:''}</td>
     <td>${esc(record.bikeSize||'Sin indicar')}</td><td>${measure(record.saddleHeight)}</td><td>${measure(record.saddleToBar)}</td></tr>`;
   }).join('')}</tbody></table><p data-no-matches hidden>No hay corredores que coincidan.</p></div>`;
 bindNameSearch(c.querySelector('#bikeRiderSearch'),c.querySelector('#bikeMeasurements'));
 c.querySelectorAll('[data-edit-bike]').forEach(button=>button.onclick=async()=>{
  try{
   const record=byRider.get(button.dataset.editBike);
   await modulePage(c,'sport',record?.id);
   if(!record){
    c.querySelector('#openNew').click();
    c.querySelector('#moduleForm').elements.rider.value=button.dataset.editBike;
   }
  }catch(error){message(error.message);}
 });
}
function fieldOptions(type,ctx){const optional=String(type).endsWith('?');let values=[];if(type.startsWith('event'))values=ctx.events.map(x=>[x.id,x.name]);else if(type.startsWith('runner'))values=ctx.riders.map(x=>[x.id,x.name]);else if(type.startsWith('person'))values=ctx.people.map(x=>[x.id,x.name+' · '+roles[x.role]]);else if(type==='entry?')values=ctx.entry.map(x=>[x.id,x.concept+' · '+euros(x.amount)]);else values=(ctx[type]||[]).map(x=>[x.id,x.name]);return optional?[['','Sin asignar'],...values]:values;}
function moduleInput([key,label,type='text'],data,ctx){let v=data[key]??'';if(key==='miribillaPercent')return `<label>${esc(label)}<input name="miribillaPercent" type="number" min="0" max="100" step="1" value="${v===''?50:v}"><small>Solo se usa con Porcentaje personalizado.</small></label>`;if(type==='budget?'){
 const options=[['','Sin asignar'],...ctx.budget.map(part=>[part.id,part.category])];
 if(v&&!ctx.budget.some(part=>part.id===v))options.push([v,(data.budgetName||'Partida')+' (archivada)']);
 return select(label,key,options,v);
}if(Array.isArray(type))return select(label,key,type,v);if(type==='textarea')return `<label>${esc(label)}<textarea name="${key}" maxlength="2500" rows="3">${esc(v)}</textarea></label>`;if(String(type).endsWith('[]')){const opts=fieldOptions(type.slice(0,-2),ctx);return `<fieldset><legend>${esc(label)}</legend>${opts.length?opts.map(([id,name])=>`<label class="checkline"><input type="checkbox" name="${key}" value="${id}" ${(data[key]||[]).includes(id)?'checked':''}>${esc(name)}</label>`).join(''):'Sin recursos registrados'}</fieldset>`;}if(['event','event?','runner','person','person?','entry?'].includes(type))return select(label,key,fieldOptions(type,ctx),v);if(type==='money')return `<label>${esc(label)}<input name="${key}" type="number" step="0.01" min="0" value="${v===''&&['baseAmount','taxAmount','amount'].includes(key)&&data.direction!==undefined?'':(Number(v)||0)/100}" ${['baseAmount','taxAmount'].includes(key)?'':'required'}></label>`;if(type==='integer')return `<label>${esc(label)}<input name="${key}" type="number" min="0" step="1" value="${v||0}" required></label>`;return field(label,key,type==='url'?'url':type==='date'?'date':'text',v);}
function moduleValue(value,key,ctx,spec){if(key==='payerClub')return value||'Sin asignar';if(['saddleHeight','saddleToBar'].includes(key))return Number(value)>0?String(value)+' mm':'Sin indicar';if(value===undefined)return '';if(spec.find(x=>x[0]===key)?.[2]==='money')return euros(value);if(['event','rider','person','matched'].includes(key))return [...ctx.events,...ctx.riders,...ctx.people,...ctx.entry].find(x=>x.id===value)?.name||ctx.entry.find(x=>x.id===value)?.concept||value||'Sin asignar';if(Array.isArray(value))return value.map(id=>[...ctx.staff,...ctx.vehicle].find(x=>x.id===id)?.name||id).join(', ');return String(value);}
function entryClubSummary(rows){
 const expenses=rows.filter(row=>row.direction==='Gasto'&&row.status!=='Anulado');
 return '<div class="card scroll"><h2>Dinero adelantado por club</h2><button type="button" id="openClubSettlement">Liquidación mensual entre clubes</button><table><thead><tr><th>Club</th><th>Gastos registrados</th><th>Pagado</th><th>Pendiente</th></tr></thead><tbody>'+['Miribilla','Ecotisa',''].map(club=>{
  const selected=expenses.filter(row=>(row.payerClub||'')===club);
  const total=selected.reduce((sum,row)=>sum+(row.amount||0),0);
  const paid=selected.filter(row=>row.status==='Pagado').reduce((sum,row)=>sum+(row.amount||0),0);
  return `<tr><td>${club||'Sin asignar'}</td><td>${euros(total)}</td><td>${euros(paid)}</td><td>${euros(total-paid)}</td></tr>`;
 }).join('')+'</tbody></table><small>Importes de los gastos mostrados. Los registros anteriores quedan sin asignar hasta que indiques el club.</small></div>';
}
async function modulePage(c,kind,editing=null,event=null){
const [ctx,d,accounts]=await Promise.all([getContext(kind),api('/modules/'+kind+(event?'?event='+encodeURIComponent(event.id):'')),kind==='charge'?api('/accounts'):Promise.resolve(null)]);
if(event)ctx.fixedEvent=event;
const redraw=(id=null)=>kind==='sport'&&!id?equipmentPage(c):modulePage(c,kind,id,event);
const issuedStaff=new Map();
moduleContext=ctx;const spec=moduleSpecs[kind];let rows=d.records;if(kind==='license')rows.sort((a,b)=>(ctx.riders.find(r=>r.id===a.rider)?.name||'').localeCompare(ctx.riders.find(r=>r.id===b.rider)?.name||'','es'));const canEdit=me.role==='director';if(me.role==='communication'&&kind!=='post')throw Error('Sin permiso');const edit=editing?rows.find(x=>x.id===editing)||{}:kind==='entry'?{event:event?.id||'',direction:'Gasto',status:'Pendiente',category:'Otros'}:{};
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
 totals=accounts?.riders?accountSummaryPanel(accounts):`<div class="metricgrid"><div class="card">Cargos registrados<strong class="metric">${euros(charged)}</strong></div><div class="card">Pagado<strong class="metric">${euros(paid)}</strong></div><div class="card">Pendiente<strong class="metric">${euros(charged-paid)}</strong></div></div>`;
}else if(['entry','budget','bank'].includes(kind)){let income=rows.filter(x=>x.direction==='Ingreso').reduce((s,x)=>s+x.amount,0),expense=rows.filter(x=>x.direction==='Gasto').reduce((s,x)=>s+x.amount,0);totals=kind==='entry'||kind==='bank'?`<div class="note">Ingresos: <b>${euros(income)}</b> · Gastos: <b>${euros(expense)}</b> · Saldo: <b>${euros(income-expense)}</b></div>`:`<div class="note">Total: <b>${euros(rows.filter(x=>x.status!=='Anulado').reduce((s,x)=>s+x.amount,0))}</b></div>`;if(kind==='entry'){const budgets=ctx.budget;totals+=`<p>Presupuesto de gasto: ${euros(budgets.reduce((s,x)=>s+x.amount,0))} · Disponible: ${euros(budgets.reduce((s,x)=>s+x.amount,0)-expense)}</p>`;}}
const renderField=f=>event&&['event','direction'].includes(f[0])?`<input type="hidden" name="${f[0]}" value="${esc(f[0]==='event'?event.id:'Gasto')}">`:moduleInput(f,edit,ctx);
const primaryEntryFields=['amount','direction','event','date','category','counterparty','concept','status','payerClub','paidBy','paymentDate','allocationRule','miribillaPercent'];
const fields=kind==='entry'?`<p>Lee la factura con OCR o introduce el importe. Indica quién adelanta el dinero, quién paga, fecha de pago y criterio de reparto para liquidarla entre los clubes.</p>
 <p>Si vinculas el gasto a una actividad, usa <strong>Repartir gasto</strong> en su fila para cargarlo a los convocados.</p>
 <div class="grid">${spec.filter(([key])=>primaryEntryFields.includes(key)).map(renderField).join('')}</div>
 <details class="card"><summary>Más datos opcionales</summary><div class="grid">${spec.filter(([key])=>!primaryEntryFields.includes(key)).map(renderField).join('')}</div></details>`:
 `<div class="grid">${spec.map(renderField).join('')}</div>`;
c.innerHTML=`${event?'<h2>Facturas y gastos de la actividad</h2>':`<h1>${kind==='charge'&&me.role==='runner'?'Mi cuenta · gastos y recibos':moduleLabels[kind]}</h1>`}${totals}<div class="toolbar">${event?'':`<a class="button" href="/api/modules/${kind}/export">Descargar Excel</a>`}${event?'<button id="openNew" type="button">+ Añadir factura o gasto</button>':canEdit?'<button id="openNew">+ Añadir registro</button>':''}</div>${kind==='charge'?'<p>Liquidaciones de desplazamientos y compras de la tienda. Los importes pendientes son deudas registradas.</p>':''}${kind==='bank'&&canEdit?'<div class="card"><h2>Importar extracto bancario</h2><small>Excel .xlsx o CSV. El Excel admite Fecha e Importe, o Fecha y Debe/Haber. Revisa los cargos y abonos antes de importar.</small><input type="file" id="bankcsv" accept=".csv,.xlsx"><div id="bankpreview"></div></div><section class="card" id="bankReconciliation"></section>':''}<div id="moduleEditor" ${editing?'':'hidden'}>${canEdit?`<form method="post" id="moduleForm" class="card"><h2>${editing?'Editar':'Nuevo registro'}</h2>${fields}<button class="primary" type="submit">Guardar</button> <button type="button" id="cancelEdit">Cancelar</button></form>`:''}</div><div class="toolbar"><label>Buscar<input id="moduleSearch" placeholder="Nombre, carrera, concepto…"></label>${kind==='license'?'<label>Estado<select id="licenseStatus"><option>Todos</option><option>No aportada</option><option>Pendiente de revisión</option><option>Verificada</option><option>Caducada</option></select></label>':''}</div>${kind==='entry'?'<label>Club que paga<select id="entryClubFilter"><option value="all">Todos</option><option>Miribilla</option><option>Ecotisa</option><option value="">Sin asignar</option></select></label><div id="entryClubTotals"></div>':''}<div id="moduleRows"></div>${event?`<details class="card"><summary>Repartir gastos entre los convocados</summary>
 <form id="splitExpenses"><p>Marca solo los gastos que se cobran a los corredores. Se dividen a partes iguales entre los convocados de la convocatoria publicada.</p>
 ${rows.filter(row=>row.amount>0&&row.status!=='Anulado').map(row=>`<label class="checkline"><input type="checkbox" name="expense" value="${esc(row.id)}" ${row.splitRecorded?'disabled':''}>${esc(row.concept||row.counterparty||row.category||'Gasto')} · ${euros(row.amount)}${row.splitRecorded?' · Ya repartido':''}</label>`).join('')}
 <button type="submit">Registrar cobros por corredor</button></form></details>`:''}`;
if(kind==='sport'){
 const note=document.createElement('p');
 note.textContent='Alto: altura del sillín. Largo: distancia sillín–manillar. Medidas en milímetros.';
 c.querySelector('h1').after(note);
}
if(kind==='charge'){
 const fines=c.querySelector('[data-account-fines]');
 if(fines)fines.onclick=()=>navigate('fines');
}
if(kind==='entry'&&canEdit){
 const form=c.querySelector('#moduleForm');
 const showCriterion=()=>{form.elements.miribillaPercent.closest('label').hidden=form.elements.allocationRule.value!=='Personalizado';};
 form.elements.allocationRule.onchange=showCriterion;showCriterion();
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
const eventForExpense=row=>event?.id===row.event?event:ctx.events.find(activity=>activity.id===row.event);
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
 await splitExpenses(event,rows.filter(row=>expenses.has(row.id)));
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
function table(){const query=(document.getElementById('moduleSearch').value||'').toLocaleLowerCase('es');const status=document.getElementById('licenseStatus')?.value||'Todos';const club=c.querySelector('#entryClubFilter')?.value??'all';const filtered=rows.filter(r=>(kind!=='entry'||club==='all'||(r.payerClub||'')===club)&&(status==='Todos'||r.status===status)&&spec.map(([key])=>key==='budget'?(r.budgetName||'Sin asignar'):moduleValue(r[key],key,ctx,spec)).join(' ').toLocaleLowerCase('es').includes(query));const columns=event?spec.filter(([key])=>['date','category','budget','concept','counterparty','payerClub','paidBy','allocationRule','amount','status'].includes(key)):kind==='entry'?spec.filter(([key])=>['date','concept','counterparty','category','payerClub','paidBy','allocationRule','amount','status'].includes(key)):kind==='sport'?[['rider','Corredor'],['bike','Bicicleta'],['bikeSize','Talla'],['saddleHeight','Alto'],['saddleToBar','Largo']]:spec.slice(0,5);if(kind==='entry')c.querySelector('#entryClubTotals').innerHTML=entryClubSummary(filtered);document.getElementById('moduleRows').innerHTML=filtered.length?`<div class="card scroll"><table><thead><tr>${columns.map(x=>'<th>'+esc(x[1])+'</th>').join('')}${kind==='entry'?'<th>Justificante original</th><th>Cobro a convocados</th>':''}${kind==='budget'?'<th>Gasto asignado</th><th>Disponible</th>':''}${kind==='license'&&me.documents?'<th>Anverso</th><th>Reverso</th><th>Descarga</th>':''}<th>Detalle</th>${canEdit?'<th>Acciones</th>':''}</tr></thead><tbody>${filtered.map(r=>`<tr>${columns.map(([key])=>'<td>'+esc(key==='budget'?(r.budgetName||'Sin asignar'):moduleValue(r[key],key,ctx,spec))+'</td>').join('')}${kind==='entry'?`<td>${(r.attachments||[]).map(a=>`<a href="/api/invoice-file/${a.id}">${esc(a.name)}</a>`).join('<br>')||'Sin adjuntar'}</td>`:''}${kind==='budget'?`<td>${euros(r.spent)}</td><td>${euros(r.amount-r.spent)}</td>`:''}${expenseSplitCell(r)}${licenseCells(r)}<td><details><summary>Ver ficha</summary><dl>${spec.filter(([key])=>r[key]!==undefined).map(([key,label])=>`<dt>${esc(label)}</dt><dd>${esc(key==='budget'?(r.budgetName||'Sin asignar'):moduleValue(r[key],key,ctx,spec))}</dd>`).join('')}</dl></details></td>${canEdit&&kind==='license'&&!r.id?`<td><button data-new-license="${esc(r.rider)}">Añadir ficha</button></td>`:canEdit?`<td><button data-edit="${r.id}">Editar</button> <button data-archive="${r.id}">Archivar</button></td>`:''}</tr>`).join('')}</tbody></table></div>`:'<div class="card">Sin registros para mostrar.</div>';c.querySelectorAll('[data-new-license]').forEach(button=>button.onclick=()=>{
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
 if(kind==='staff'&&me.team!=='occident')bindStaffPassword(b,rows.find(row=>row.id===b.dataset.edit),issuedStaff);
});c.querySelectorAll('[data-archive]').forEach(b=>b.onclick=async()=>{if(!confirm('¿Archivar este registro? Se puede restaurar desde Archivados.'))return;try{await api('/modules/'+kind+'/'+b.dataset.archive+'/archive','POST',{});await redraw();}catch(e){message(e.message);}});}
table();if(kind==='entry')c.querySelector('#entryClubTotals').onclick=event=>{if(event.target.id==='openClubSettlement')navigate('clubsettlement');};if(event)c.refreshActivitySection=table;document.getElementById('moduleSearch').oninput=table;if(kind==='entry')c.querySelector('#entryClubFilter').onchange=table;if(document.getElementById('licenseStatus'))document.getElementById('licenseStatus').onchange=table;if(canEdit){document.getElementById('openNew').onclick=async()=>{
 if(event&&editing){try{await redraw();}catch(err){message(err.message);return;}}
 document.getElementById('moduleEditor').hidden=false;
};document.getElementById('cancelEdit').onclick=()=>redraw().catch(e=>message(e.message));bindForm('moduleForm',async(f,data)=>{if(f.dataset.ocrReview==='true'&&!f.elements.ocrReviewed?.checked)throw Error('Revisa los datos detectados y marca la confirmación antes de guardar.');const out={};for(const [key,,type] of spec){if(type==='money'){const v=Number(data[key]);if(!Number.isFinite(v)||v<0)throw Error('Importe no válido');out[key]=Math.round(v*100);}else if(type==='integer')out[key]=Number(data[key]);else if(String(type).endsWith('[]'))out[key]=new FormData(f).getAll(key);else out[key]=data[key]||'';}if(event){out.event=event.id;out.direction='Gasto';}
if(kind==='entry'&&out.amount<=0)throw Error('Introduce un importe mayor que cero.');const savedId=editing||f.dataset.invoiceSavedId||'';const saved=await api('/modules/'+kind+(savedId?'/'+savedId:''),'POST',out);if(kind==='entry'&&f.invoiceOriginal){const id=savedId||saved.id;f.dataset.invoiceSavedId=id;const upload=new FormData();upload.append('file',f.invoiceOriginal);try{await api('/invoices/'+id,'POST',upload,f);}catch(error){throw Error('El apunte ya está guardado, pero no el original: '+error.message+'. Puedes volver a pulsar Guardar para adjuntarlo sin duplicar el gasto.');}}await redraw();message(kind==='entry'&&f.invoiceOriginal?'Apunte y original guardados.':'Registro guardado.');});}if(kind==='entry'&&canEdit)addInvoiceOCR(c,ctx);if(kind==='bank'&&canEdit){document.getElementById('bankcsv').onchange=bankPreview;await bankPanel(c.querySelector('#bankReconciliation'));}}
function accountSummaryPanel(data){
 const fields=[['clothes','Ropa'],['races','Gastos de carreras'],['fines','Multas']];
 if(data.totals.other)fields.push(['other','Otros']);
 fields.push(['total','Total'],['paid','Pagado'],['pending','Pendiente']);
 return `<div class="metricgrid"><div class="card">Total registrado<strong class="metric">${euros(data.totals.total)}</strong></div>
  <div class="card">Pagado<strong class="metric">${euros(data.totals.paid)}</strong></div>
  <div class="card">Pendiente<strong class="metric">${euros(data.totals.pending)}</strong></div></div>
  <section class="card"><h2>Resumen por corredor y concepto</h2>
   <p>Ropa adicional comprada en la tienda, cargos de desplazamientos y multas económicas.</p>
   <div class="toolbar"><a class="button" href="/api/accounts/export">Descargar resumen · Excel</a>
    <button type="button" data-account-fines>Ver multas</button></div>
   <div class="scroll"><table><thead><tr><th>Corredor</th>${fields.map(([,label])=>`<th>${label}</th>`).join('')}</tr></thead>
   <tbody>${data.riders.map(row=>`<tr><td>${esc(row.name)}</td>${fields.map(([key])=>`<td>${euros(row[key])}</td>`).join('')}</tr>`).join('')}</tbody>
   <tfoot><tr><th>TOTAL</th>${fields.map(([key])=>`<th>${euros(data.totals[key])}</th>`).join('')}</tr></tfoot></table></div>
  </section><h2>Detalle de cargos</h2>`;
}
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
  const hotelLink=()=>me.documents?(event.callStatus==='Publicada'?`<a class="button" href="/api/events/${encodeURIComponent(event.id)}/hotel">Descargar listado del hotel con DNI</a> <a class="button" href="/api/events/${encodeURIComponent(event.id)}/hotel/identity-pdf">Descargar PDF privado de DNI</a>`:'<small>Publica la convocatoria para descargar los DNI del hotel.</small>'):'';
  panel.innerHTML=`<h2>Viaje, hotel e inscripciones</h2>
    <div class="toolbar" id="travelHotelDownload">${hotelLink()}</div>
    <form method="post" id="eventTravel">
      <div class="grid">${spec.map(field=>moduleInput(field,travel,ctx)).join('')}</div>
      <button type="submit" class="primary">Guardar ficha del viaje</button>
    </form>${me.documents?'<details class="card" id="hotelGuests"></details>':''}`;
  panel.refreshActivitySection=()=>{panel.querySelector('#travelHotelDownload').innerHTML=hotelLink();};
  const guests=panel.querySelector('#hotelGuests');
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

function vehicleAvailability(container,vehicles,events,bookings){
  const section=document.createElement('section');
  section.className='card';
  section.innerHTML=`<details open><summary>Reservas de vehículos · Netkom y Occident</summary>
    <label>Consultar día<input type="date" id="vehicleDay" value="${esc(vehicleBookingDay||calendarDateKey(new Date()))}"></label>
    <div id="vehicleBookings"></div><div id="vehicleBookingDates"></div></details>
    ${me.role==='director'&&vehicles.length?`<details><summary>Reservar sin actividad</summary>
     <form id="standaloneVehicleBooking">
      <div class="grid">
       ${select('Vehículo','vehicle',[['','Selecciona un vehículo'],...vehicles.map(vehicle=>[vehicle.id,vehicle.name])])}
       <label>Desde<input name="date" type="date" required></label>
       <label>Hasta (opcional)<input name="endDate" type="date"></label>
       <label>Motivo (opcional)<input name="reason" maxlength="250"></label>
      </div>
      <button type="submit" class="primary">Guardar reserva</button>
     </form></details>`:''}`;
  container.prepend(section);
  const day=section.querySelector('#vehicleDay');
  const form=section.querySelector('#standaloneVehicleBooking');
  if(form){
   const start=form.elements.date,end=form.elements.endDate;
   form.elements.vehicle.required=true;
   const syncDate=()=>{start.value=day.value;end.min=start.value;};
   syncDate();
   start.onchange=()=>{end.min=start.value;};
   day.addEventListener('change',syncDate);
   bindForm(form.id,async(_,data)=>{
    await api('/vehicle-reservations','POST',data);
    vehicleBookingDay=data.date;
    await navigate('vehicles');
    message('Vehículo reservado.');
   });
  }
  const activeIds=new Set(vehicles.map(vehicle=>vehicle.id));
  const future=bookings.filter(row=>row.endDate>=calendarDateKey(new Date())&&row.vehicles.some(id=>activeIds.has(id)));
  const upcoming=[...new Set(future.map(row=>row.date))].sort();
  section.querySelector('#vehicleBookingDates').innerHTML=upcoming.length?`<label>Ir a una fecha con reservas
    <select><option value="">Seleccionar fecha</option>${upcoming.map(date=>`<option>${esc(date)}</option>`).join('')}</select></label>`:'';
  const dates=section.querySelector('#vehicleBookingDates select');
  if(dates)dates.onchange=()=>{if(dates.value){day.value=dates.value;day.dispatchEvent(new Event('change'));}};
  const redraw=()=>{
    vehicleBookingDay=day.value;
    const output=section.querySelector('#vehicleBookings');
    if(!day.value){output.textContent='Selecciona un día.';return;}
    output.innerHTML=vehicles.map(vehicle=>{
      const matching=bookings.filter(row=>row.vehicles.includes(vehicle.id)&&row.date<=day.value&&row.endDate>=day.value);
      const labels=[...new Set(matching.map(row=>{
        const team=row.team==='occident'?'Occident':'Netkom';
        const activity=events.find(event=>event.id===row.event);
        return activity?team+' · '+activity.name:team;
      }))];
      const direct=matching.filter(row=>row.direct&&row.id&&me.role==='director').map(row=>
        `<div class="row"><small>${esc(row.reason||'Reserva sin actividad')}</small><button type="button" data-cancel-reservation="${esc(row.id)}">Cancelar reserva</button></div>`
      ).join('');
      return `<div class="row"><strong>${esc(vehicle.name)}</strong><span class="resource-state ${labels.length?'assigned':'available'}">${labels.length?'Reservado · '+labels.map(esc).join(', '):'Libre'}</span>${direct}</div>`;
    }).join('')||'<p>No hay vehículos registrados.</p>';
    output.querySelectorAll('[data-cancel-reservation]').forEach(button=>button.onclick=async()=>{
     if(!confirm('¿Cancelar esta reserva del vehículo?'))return;
     button.disabled=true;
     try{
      await api('/vehicle-reservations/'+encodeURIComponent(button.dataset.cancelReservation),'DELETE');
      await navigate('vehicles');
      message('Reserva cancelada.');
     }catch(error){message(error.message);button.disabled=false;}
    });
  };
  day.onchange=redraw;
  redraw();
}
let vehicleBookingDay='';


function clothingCatalog(){
 return `<details class="card clothing-catalog"><summary>Ver diseños de la ropa · Júnior 2027</summary>
  <p>Consulta cómo quedan las prendas antes de elegir tu talla o pedir ropa adicional.</p>
  <a href="/static/ropa-calle-junior-2027.pdf" target="_blank" rel="noopener">
   <img src="/static/ropa-calle-junior-2027.jpg" alt="Vista general del maillot y la colección de calle Miribilla Ecotisa Júnior 2027" width="1400" height="788" loading="lazy">
  </a><div class="toolbar">
   <a class="button" href="/static/ropa-calle-junior-2027.pdf" target="_blank" rel="noopener">Ver catálogo completo · 5 páginas</a>
   <a href="/static/ropa-calle-junior-2027.pdf" download="Ropa_calle_Junior_2027.pdf">Descargar PDF</a>
  </div></details>`;
}
function extraClothingOrders(orders){
 return orders.map(order=>`<article class="row"><div>
  <strong>${esc(order.created?.slice(0,10)||'Pedido')} · ${euros(order.amount)}</strong>
  <p>${order.items.map(item=>`${esc(item.quantity+' × '+item.name+' · '+item.size)} · ${euros(item.price*item.quantity)}`).join('<br>')}</p>
  <small>Estado del cargo · ${esc(order.paymentStatus||'Pendiente')}</small>
 </div></article>`).join('')||'<p>Sin compras extra registradas.</p>';
}
async function shopPage(c){
 const shop=await api('/shop');
 const director=me.role==='director';
 const sizes=['XXS','XS','S','M','L','XL','XXL','XXXL'];
 const products=shop.products.filter(product=>product.price!=null);
 c.innerHTML=`<h1>Tienda</h1><p>Compra de ropa adicional del equipo.</p>${clothingCatalog()}
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
   <small>Estado del cargo: ${esc(order.paymentStatus||'Pendiente')}</small>
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
async function resourcesPage(c){await resourceMatrix(c,'staff');}

async function resourceMatrix(c,section){
 const [calendar,staff,vehicles,travel,overrides]=await Promise.all([
  api('/events'),api('/modules/staff'),api('/modules/vehicle'),api('/modules/travel'),api('/resource-availability')
 ]);
 const events=sortActivities(calendar.events);
 const statusRows=overrides.records||[];
 const vehicleBookings=overrides.vehicleBookings||[];
 const resources={staff:staff.records,vehicles:vehicles.records};
 const assignments=new Map(travel.records.map(trip=>[trip.event,trip]));
 const range=event=>[event.date,event.endDate&&event.endDate>event.date?event.endDate:event.date];
 const overlap=(first,second)=>{
  const [a,b]=range(first),[x,y]=range(second);
  return a&&x&&a<=y&&x<=b;
 };
 function status(event,resource,kind){
  if(kind==='vehicles'){
   const reserved=vehicleBookings.filter(row=>row.vehicles.includes(resource.id)&&overlap(event,row));
   const other=reserved.find(row=>row.team!==me.team||row.event!==event.id);
   if(other)return {label:'Reservado',style:'assigned',fixed:true,note:other.team!==me.team?(other.team==='occident'?'Occident':'Netkom'):events.find(item=>item.id===other.event)?.name||(other.direct?'Reserva sin actividad':'')};
   const assigned=(assignments.get(event.id)?.vehicles||[]).includes(resource.id);
   const manual=statusRows.some(row=>row.event===event.id&&row.resource===resource.id&&['Reservado','No disponible'].includes(row.status));
   return assigned||manual?{label:'Reservado',style:'assigned',fixed:assigned}:{label:'Libre',style:'available',fixed:!event.date};
  }
  if((assignments.get(event.id)?.[kind]||[]).includes(resource.id)){
   return {label:'Convocado',style:'assigned',fixed:true};
  }
  const other=events.find(candidate=>candidate.id!==event.id&&overlap(event,candidate)&&
   (assignments.get(candidate.id)?.[kind]||[]).includes(resource.id));
  if(other)return {label:'No disponible',style:'unavailable',fixed:true,note:other.name};
  if((overrides.shared||[]).some(booking=>booking.resources.includes(resource.id)&&overlap(event,booking))){
   return {label:'No disponible',style:'unavailable',fixed:true,note:me.team==='occident'?'Netkom':'Occident'};
  }
  const manual=statusRows.find(row=>row.event===event.id&&row.resource===resource.id);
  const label=manual?.status||event.responses?.[resource.user]||'Por confirmar';
  return {label,style:label==='No disponible'?'unavailable':label==='Disponible'||label==='Libre'?'available':'pending'};
 }
 c.innerHTML=`<h2>${section==='all'?'Disponibilidad y convocatorias':section==='staff'?'Disponibilidad de técnicos por carrera':'Disponibilidad de vehículos por carrera'}</h2>${section==='all'?'':`<button type="button" id="manageResources">Gestionar fichas de ${section==='staff'?'técnicos':'vehículos'}</button>`}
  ${section==='staff'&&me.role==='director'&&me.team!=='occident'?`<details class="card"><summary>Altas y contraseñas de técnicos</summary>
   <form id="createTechnician"><label>Nombre y apellidos<input name="name" maxlength="150" required></label>
    <button class="primary" type="submit">Guardar técnico y crear acceso</button></form>
   <p>Para las fichas que ya existen, genera los accesos pendientes con un solo botón.</p>
   <button type="button" id="createPendingTechnicians">Generar accesos pendientes</button>
   <p>Las contraseñas nuevas tienen 8 caracteres: minúsculas y números, sin signos.</p>
   ${me.owner?'<button type="button" id="simplifyTechnicianPasswords">Simplificar contraseñas existentes</button>':''}
   <p id="technicianAccountStatus" role="status"></p>
   <div id="technicianCredentials" hidden></div>
  </details>`:''}
  <div class="toolbar"><label>Buscar actividad<input type="search" id="resourceSearch" placeholder="Carrera, lugar…"></label>
   <label>Mes<input type="month" id="resourceMonth"></label><button type="button" id="resourceClear">Ver todo</button></div>
  ${section!=='staff'?'<div class="toolbar resource-legend"><span class="resource-state available">Libre</span><span class="resource-state assigned">Reservado</span></div>':''}
  ${section!=='vehicles'?'<div class="toolbar resource-legend"><span class="resource-state available">Disponible</span><span class="resource-state assigned">Convocado</span><span class="resource-state unavailable">No disponible</span><span class="resource-state pending">Por confirmar</span></div>':''}
  <p>Abre una actividad pulsando su nombre.${section!=='staff'?' Las reservas del viaje se modifican en su ficha.':''}</p>
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
    (accounts.length===1?'Acceso listo para copiar.':`${accounts.length} accesos listos para copiar.`):
    'No hay accesos pendientes. Revisa las fichas y los usuarios vinculados.';
   if(!accounts.length)return;
   for(const account of accounts){
    const previous=issued.findIndex(item=>item.username===account.username);
    if(previous===-1)issued.push(account);else issued[previous]=account;
   }
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
  const simplify=c.querySelector('#simplifyTechnicianPasswords');
  if(simplify)simplify.onclick=async()=>{
   if(!confirm('¿Cambiar las contraseñas de los técnicos por claves de 8 caracteres? Se cerrarán sus sesiones y tendrás que entregarles las claves nuevas.'))return;
   simplify.disabled=true;
   newAccounts.disabled=true;
   try{message('');await createAccounts({replaceAll:true});}
   catch(error){message(error.message);}
   finally{simplify.disabled=false;newAccounts.disabled=false;}
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
       ${(kind==='vehicles'?['Libre','Reservado']:['Disponible','No disponible','Por confirmar']).map(label=>`<option ${cell.label===label?'selected':''}>${label}</option>`).join('')}
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
    if(['Libre','Reservado'].includes(update.status)){
     await resourceMatrix(c,section);
     message('Reserva actualizada.');
     return;
    }
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
 if(section==='vehicles')vehicleAvailability(c,resources.vehicles,events,vehicleBookings);
}
async function callsPage(c){
 const [events,riders]=await Promise.all([api('/events'),api('/roster')]);
 const runner=me.role==='runner';
 const list=sortActivities(events.events).filter(event=>!runner||(event.called.includes(me.id)&&event.callStatus==='Publicada'));
 c.innerHTML=`<h1>${runner?'Mis convocatorias':'Convocatorias'}</h1>
  <label>Buscar actividad<input id="callsSearch" type="search" placeholder="Ej. Guadiana"></label>
  <div id="callsResults">${list.map(event=>`<article class="card" data-search-name="${esc(event.name)}">
   <h2>${esc(event.name)}</h2><p>${esc(activityDateLabel(event))} · ${esc(event.place||'Lugar por confirmar')}</p>
   <span class="pill">${esc(event.callStatus||'Borrador')}</span><h3>Corredores seleccionados</h3>
   <ul>${event.called.map(id=>`<li>${esc(riders.riders.find(rider=>rider.id===id)?.name||'Corredor')}</li>`).join('')||'<li>Sin corredores seleccionados.</li>'}</ul>
   <button type="button" data-planning="${esc(event.id)}">Planning de viaje</button>
  </article>`).join('')}<p data-no-matches hidden>No hay convocatorias que coincidan.</p></div>`;
 bindNameSearch(c.querySelector('#callsSearch'),c.querySelector('#callsResults'));
 c.querySelectorAll('[data-planning]').forEach(button=>button.onclick=()=>navigate('planning'));
}
async function archivePage(c){const d=await api('/archive');c.innerHTML='<h1>Registros archivados</h1><div class="card">'+(d.records.map(r=>`<div class="row"><span>${esc(moduleLabels[r.kind]||r.kind)} · ${esc(r.name||r.concept||r.reason||r.hotel||r.number||r.date||r.id)}</span><button data-restore="${r.id}">Restaurar</button></div>`).join('')||'No hay registros archivados.')+'</div>';c.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{try{await api('/archive/'+b.dataset.restore+'/restore','POST',{});await archivePage(c);}catch(e){message(e.message);}});}
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
async function removeCalendarEvent(c,event){
 if(!confirm('¿Eliminar «'+event.name+'» del calendario? Se conservarán sus gastos, documentos y convocatorias. Podrás recuperarla desde Archivados.'))return;
 const buttons=c.querySelectorAll('#removeCalendarEvent');buttons.forEach(button=>button.disabled=true);
 try{await api('/events/'+encodeURIComponent(event.id)+'/archive','POST',{});await calendarPage(c);message('Actividad eliminada del calendario. Puedes recuperarla desde Archivados.');}
 catch(error){message(error.message);buttons.forEach(button=>button.disabled=false);}
}
function moveCalendarEvent(c,event){
 c.innerHTML=`<h1>Cambiar fecha · ${esc(event.name)}</h1><form method="post" id="moveEventDate" class="card">
  <p>Para una carrera o concentración de varios días, indica el inicio y el final.</p>
  <div class="grid">${field('Fecha de inicio','date','date',event.date||'')}${field('Fecha de fin (opcional)','endDate','date',event.endDate||'')}</div>
  <p>Se conservan la convocatoria, el viaje y los gastos. Revisa la disponibilidad de corredores, técnicos y vehículos para las nuevas fechas.</p>
  <button type="submit" class="primary">Guardar nueva fecha</button><button type="button" id="cancelMoveEvent">Cancelar</button></form>`;
 const form=c.querySelector('#moveEventDate'),start=form.elements.date,end=form.elements.endDate;
 start.required=true;end.min=start.value;
 let previous=start.value;
 start.onchange=()=>{
  if(previous&&end.value&&start.value){const days=(Date.parse(end.value)-Date.parse(previous))/86400000;if(days>=0){const shifted=new Date(Date.parse(start.value)+days*86400000);if(!Number.isNaN(shifted.valueOf()))end.value=shifted.toISOString().slice(0,10);}}
  end.min=start.value;previous=start.value;
 };
 bindForm('moveEventDate',async(_,data)=>{await api('/events/'+encodeURIComponent(event.id)+'/details','POST',data);await calendarPage(c,event.id);message('Fechas actualizadas. Revisa la disponibilidad para las nuevas fechas.');});
 c.querySelector('#cancelMoveEvent').onclick=()=>calendarPage(c,event.id).catch(error=>message(error.message));
}
function editEvent(c,event){
 c.innerHTML=`<h1>Editar actividad</h1><form method="post" id="eventDetails" class="card">
  <div class="grid">${activityClassification(event)}${[['name','Nombre'],['date','Fecha de inicio','date'],['endDate','Fecha de fin','date'],['place','Lugar'],['status','Estado',['Programada','Confirmada','Finalizada','Cancelada']],['owner','Responsable']].map(field=>moduleInput(field,event,{})).join('')}</div>
  <label>Información y horarios<textarea name="notes" rows="5">${esc(event.notes||'')}</textarea></label>
  <button type="submit" class="primary">Guardar actividad</button>
  <button id="backCalendar" type="button">Volver a la actividad</button></form>`;
 const form=c.querySelector('#eventDetails');
 bindActivityClassification(form);
 bindForm('eventDetails',async(_,data)=>{
  if(form.elements.type.disabled)data.type='';
  await api('/events/'+event.id+'/details','POST',data);
  await calendarPage(c,event.id);message('Actividad actualizada.');
 });
 c.querySelector('#backCalendar').onclick=()=>calendarPage(c,event.id).catch(error=>message(error.message));
}

function addBulkUserImport(c){if(!me.owner)return;const box=document.createElement('details');box.className='card';box.innerHTML='<summary>Importar invitaciones desde CSV</summary><small>CSV con columnas: nombre;correo;perfil. Perfiles: Dirección, Técnico, Corredor o Comunicación.</small><input type="file" id="usersCsv" accept=".csv"><div id="usersCsvPreview"></div>';c.querySelector('h1').after(box);document.getElementById('usersCsv').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;const lines=(await f.text()).replace(/^\uFEFF/,'').trim().split(/\r?\n/);const map={'dirección':'director','direccion':'director','técnico':'technician','tecnico':'technician','corredor':'runner','comunicación':'communication','comunicacion':'communication'};const rows=lines.slice(1).map(l=>{const p=l.split(';').map(x=>x.trim());return {name:p[0],email:p[1],role:map[(p[2]||'').toLowerCase()]||p[2]};});if(rows.some(r=>!r.name||!r.email?.includes('@')||!roles[r.role]))throw Error('Revisa nombre, correo y perfil en cada fila.');document.getElementById('usersCsvPreview').innerHTML='<p>'+rows.length+' usuarios para revisar</p>'+rows.map(r=>'<p>'+esc(r.name)+' · '+esc(r.email)+' · '+esc(roles[r.role])+'</p>').join('')+'<button id="bulkUsersConfirm">Crear invitaciones</button>';document.getElementById('bulkUsersConfirm').onclick=async()=>{try{const response=await api('/invites/import','POST',{rows});document.getElementById('usersCsvPreview').innerHTML='<h3>Invitaciones creadas · entrega cada enlace a su destinatario</h3>'+response.invitations.map(i=>'<div class="row"><div>'+esc(i.name)+' · '+esc(i.email)+'<p class="secret">'+esc(inviteLink(i.token))+'</p></div></div>').join('')+'<small>No se ha enviado ningún correo. Los enlaces caducan en 48 horas.</small>';}catch(err){message(err.message);}};}catch(err){message(err.message);}};}

let clubSettlementMonth='';
async function clubSettlementPage(c){
 if(me.role!=='director')throw Error('Solo Dirección puede consultar la liquidación');
 if(!clubSettlementMonth)clubSettlementMonth=calendarDateKey(new Date()).slice(0,7);
 const report=await api('/club-settlement?month='+encodeURIComponent(clubSettlementMonth));
 const transfer=report.transfer;
 c.innerHTML=`<h1>Liquidación mensual entre clubes</h1>
 <p>Se calcula por <strong>fecha de pago</strong>. Compara lo adelantado por cada club con el gasto que le corresponde según el criterio de cada factura. Los pendientes se muestran aparte y no se compensan.</p>
 <div class="toolbar"><label>Mes de pago<input type="month" id="clubSettlementMonth" value="${esc(report.month)}"></label>
 <a class="button" href="/api/club-settlement/export?month=${encodeURIComponent(report.month)}">Descargar liquidación · Excel</a><button type="button" id="backInvoices">Volver a facturas</button></div>
 <div class="card scroll"><table><thead><tr><th>Club</th><th>Dinero adelantado</th><th>Gasto que le corresponde</th><th>A recibir (+) / aportar (−)</th></tr></thead><tbody>${['Miribilla','Ecotisa'].map(club=>{const item=report.totals[club];return `<tr><th>${club}</th><td>${euros(item.paid)}</td><td>${euros(item.share)}</td><td>${euros(item.balance)}</td></tr>`;}).join('')}</tbody></table>
 <p><strong>${transfer.amount?`${esc(transfer.fromClub)} debe compensar a ${esc(transfer.toClub)} con ${euros(transfer.amount)}`:'Sin saldo a compensar entre clubes'}</strong></p>
 <small>Cálculo provisional sobre ${report.entries.length} facturas completas por ${euros(report.total)}. No registra ni ejecuta transferencias. Las compensaciones ya realizadas deben revisarse antes del cierre.</small></div>
 <h2>Facturas incluidas</h2>${settlementInvoiceTable(report.entries,false)}
 <h2>Pendientes de revisar · ${report.pending.length} · ${euros(report.pendingTotal)}</h2><p>Las facturas sin fecha de pago se muestran por su fecha de factura. Las que no tienen ninguna fecha aparecen como pendientes en todos los meses hasta que se completen.</p>${settlementInvoiceTable(report.pending,true)}`;
 c.querySelector('#clubSettlementMonth').onchange=async e=>{if(!e.target.value)return;clubSettlementMonth=e.target.value;try{await clubSettlementPage(c);}catch(error){message(error.message);}};
 c.querySelector('#backInvoices').onclick=()=>navigate('conta');
 c.querySelectorAll('[data-settlement-edit]').forEach(button=>button.onclick=()=>modulePage(c,'entry',button.dataset.settlementEdit).catch(error=>message(error.message)));
}
function settlementInvoiceTable(rows,pending){
 if(!rows.length)return '<div class="card">No hay facturas en este apartado.</div>';
 return `<div class="card scroll"><table><thead><tr><th>Fecha pago</th><th>Factura / concepto</th><th>Importe</th><th>Club que adelanta</th><th>Quién paga</th><th>Criterio</th>${pending?'<th>Revisar</th>':'<th>Miribilla</th><th>Ecotisa</th>'}<th></th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(row.paymentDate||'Sin indicar')}</td><td>${esc(row.reference||row.concept||row.counterparty||'Sin concepto')}</td><td>${euros(row.amount)}</td><td>${esc(row.payerClub||'Sin asignar')}</td><td>${esc(row.paidBy||'Sin indicar')}</td><td>${esc(row.allocationRule==='Mitad'?'50 % cada club':row.allocationRule==='Personalizado'?row.miribillaPercent+' % Miribilla / '+(100-row.miribillaPercent)+' % Ecotisa':row.allocationRule||'Pendiente')}</td>${pending?`<td>${esc(row.issues.join(' · '))}</td>`:`<td>${euros(row.shares.Miribilla)}</td><td>${euros(row.shares.Ecotisa)}</td>`}<td><button type="button" data-settlement-edit="${esc(row.id)}">Completar / editar</button></td></tr>`).join('')}</tbody></table></div>`;
}

async function vehicleLogsPage(c){
 const [{records},{records:vehicles}]=await Promise.all([api('/vehicle-logs'),api('/modules/vehicle')]);
 const open=records.filter(log=>log.end===null);
 const completed=records.filter(log=>log.end!==null);
 const totals=new Map();
 for(const log of completed){
  const item=totals.get(log.vehicle)||{name:log.name,km:0};
  item.km+=log.end-log.start;
  totals.set(log.vehicle,item);
 }
 const km=value=>new Intl.NumberFormat('es-ES').format(value)+' km';
 const time=value=>new Date(value).toLocaleString('es-ES',{timeZone:'Europe/Madrid'});
 const deleteButton=log=>me.role==='director'||log.user===me.id
  ? `<button type="button" data-delete-vehicle-log="${esc(log.id)}">Borrar registro</button>` : '';
 const options=[['','Selecciona un vehículo'],...vehicles.filter(v=>!open.some(log=>log.vehicle===v.id)).map(v=>[v.id,v.name])];
 c.innerHTML=`<h1>Kilómetros e historial de vehículos</h1>
 <form id="vehicleDeparture" class="card"><h2>Registrar salida</h2><div class="grid">
 ${select('Vehículo','vehicle',options)}
 <label>Km de salida<input type="number" name="start" min="0" max="9999999" step="1" inputmode="numeric" required></label>
 <label>Motivo<input name="purpose" maxlength="250" placeholder="Carrera, entrenamiento, taller…"></label>
 </div><button type="submit" class="primary">Guardar salida</button></form>
 <h2>Salidas abiertas</h2>${open.map(log=>`<div class="card"><strong>${esc(log.name)}</strong>
 <p>${esc(log.driver)} · ${esc(time(log.started))} · Salida: ${km(log.start)}</p>
 ${me.role==='director'||log.user===me.id?`<form id="return-${esc(log.id)}">
 <div class="grid"><label>Km de regreso<input type="number" name="end" min="${log.start}" max="9999999" step="1" inputmode="numeric" required></label>
 <label>Observaciones<input name="notes" maxlength="1000" placeholder="Combustible, incidencias…"></label></div>
 <button type="submit" class="primary">Registrar regreso</button></form>`:''}${deleteButton(log)}</div>`).join('')||'<p>No hay salidas abiertas.</p>'}
 <h2>Historial</h2>${completed.length?`<p>${[...totals.values()].map(item=>`${esc(item.name)} · ${km(item.km)}`).join(' · ')}</p>
 <div class="card scroll"><table><thead><tr><th>Vehículo</th><th>Conductor</th><th>Salida</th><th>Regreso</th><th>Km recorridos</th><th>Motivo y observaciones</th><th>Acciones</th></tr></thead>
 <tbody>${completed.map(log=>`<tr><td>${esc(log.name)}</td><td>${esc(log.driver)}</td>
 <td>${esc(time(log.started))}<br>${km(log.start)}</td><td>${esc(time(log.finished))}<br>${km(log.end)}</td><td>${km(log.end-log.start)}</td>
 <td>${esc([log.purpose,log.notes].filter(Boolean).join(' · '))}</td><td>${deleteButton(log)}</td></tr>`).join('')}</tbody></table></div>`:'<p>No hay trayectos cerrados.</p>'}`;
 c.querySelector('#vehicleDeparture select').required=true;
 for(const button of c.querySelectorAll('[data-delete-vehicle-log]')){
  button.onclick=async()=>{
   if(!confirm('¿Borrar este registro de kilómetros?'))return;
   button.disabled=true;
   try{
    await api('/vehicle-logs/'+encodeURIComponent(button.dataset.deleteVehicleLog),'DELETE');
    await vehicleLogsPage(c);
    message('Registro borrado.');
   }catch(error){
    message(error.message);
    button.disabled=false;
   }
  };
 }

 bindForm('vehicleDeparture',async(_,data)=>{
  await api('/vehicle-logs','POST',{vehicle:data.vehicle,start:Number(data.start),purpose:data.purpose});
  await vehicleLogsPage(c);message('Salida registrada.');
 });
 for(const log of open){
  bindForm('return-'+log.id,async(_,data)=>{
   await api('/vehicle-logs/'+encodeURIComponent(log.id)+'/close','POST',{end:Number(data.end),notes:data.notes});
   await vehicleLogsPage(c);message('Regreso registrado. Distancia: '+km(Number(data.end)-log.start)+'.');
  });
 }
}

function whatsAppPage(content){
 if(!['director','communication'].includes(me.role))return;
 const team=me.team==='occident'?'Occident':'Netkom';
 content.innerHTML=`<h1>Avisos por WhatsApp · ${team}</h1>
 <div class="card">
  <p>Prepara el mensaje aquí. En WhatsApp podrás elegir un contacto o grupo y pulsar Enviar.</p>
  <label>Mensaje<textarea id="whatsappMessage" rows="7" maxlength="1000" placeholder="Escribe el aviso para el equipo"></textarea></label>
  <div class="row">
   <button type="button" data-whatsapp-template="training">Entrenamiento</button>
   <button type="button" data-whatsapp-template="call">Convocatoria</button>
   <button type="button" data-whatsapp-template="reminder">Recordatorio</button>
  </div>
  <div class="row">
   <button type="button" class="primary" id="openWhatsApp" disabled>Abrir WhatsApp</button>
   <button type="button" id="copyWhatsApp" disabled>Copiar mensaje</button>
  </div>
  <p id="whatsappStatus" role="status"></p>
 </div>`;
 const input=content.querySelector('#whatsappMessage');
 const open=content.querySelector('#openWhatsApp');
 const copy=content.querySelector('#copyWhatsApp');
 const status=content.querySelector('#whatsappStatus');
 const templates={
  training:`*${team} · Entrenamiento*\nDía: \nHora: \nPunto de encuentro: \nIndicaciones: `,
  call:`*${team} · Convocatoria*\nActividad: \nDía: \nHora y punto de encuentro: \nPor favor, confirma tu disponibilidad en la app.`,
  reminder:`*${team} · Recordatorio*\n`
 };
 function updateButtons(){
  open.disabled=copy.disabled=!input.value.trim();
  status.textContent='';
 }
 input.addEventListener('input',updateButtons);
 content.querySelectorAll('[data-whatsapp-template]').forEach(button=>{
  button.onclick=()=>{
   if(input.value.trim()&&!confirm('¿Sustituir el mensaje actual por esta plantilla?'))return;
   input.value=templates[button.dataset.whatsappTemplate];
   updateButtons();
   input.focus();
  };
 });
 open.onclick=()=>{
  const url=new URL('https://wa.me/');
  url.searchParams.set('text',input.value.trim());
  window.open(url.href,'_blank','noopener,noreferrer');
 };
 copy.onclick=async()=>{
  try{
   await navigator.clipboard.writeText(input.value.trim());
   status.textContent='Mensaje copiado.';
  }catch{
   input.focus();
   input.select();
   status.textContent='Copia el texto seleccionado.';
  }
 };
}
