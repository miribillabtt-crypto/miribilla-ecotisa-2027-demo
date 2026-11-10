'use strict';
const app=document.getElementById('app'),notice=document.getElementById('notice');
const roles={director:'Dirección',technician:'Técnico',runner:'Corredor',communication:'Comunicación'};
let me=null,csrf='',page='home',clothes=[],fineTypes=[],roster=[],users=[],activationToken='';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(s){notice.textContent=s;}
async function api(path,method='GET',data,uploadForm){if(path==='/login'&&data?.email?.trim().toLowerCase()==='demo'){if(!window.DemoPortal)throw Error('La demostración no está disponible');DemoPortal.start(data.password);return {ok:true};}if(window.DemoPortal?.active)return DemoPortal.request(path,method,data);if(data instanceof FormData&&window.PortalEnhancements&&(/^\/documents\//.test(path)||/^\/invoices\//.test(path)))return PortalEnhancements.upload('/api'+path,data,csrf,uploadForm);const options={method,credentials:'same-origin',headers:{}};if(method!=='GET')options.headers['X-CSRF-Token']=csrf;if(data instanceof FormData)options.body=data;else if(data!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}const r=await fetch('/api'+path,options);let result;try{result=await r.json();}catch{throw Error('La operación no pudo completarse');}if(!r.ok)throw Error(result.error||'No se pudo completar');return result;}
function field(label,name,type='text',value=''){return `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${type==='password'?'minlength="6" autocomplete="new-password"':''}></label>`;}
function select(label,name,items,current=''){return `<label>${esc(label)}<select name="${name}">${items.map(i=>{const [v,l]=Array.isArray(i)?i:[i,i];return `<option value="${esc(v)}" ${v===current?'selected':''}>${esc(l)}</option>`;}).join('')}</select></label>`;}
function bindForm(id,fn){const form=document.getElementById(id);if(!form)return;form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button[type=submit]')||form.querySelector('button');if(button)button.disabled=true;try{message('');await fn(form,Object.fromEntries(new FormData(form)));}catch(err){message(err.message);}finally{if(button)button.disabled=false;}};}
function login(){app.innerHTML=`<main class="auth"><h1>Entrar al equipo</h1><p>Introduce tu usuario o correo y tu contraseña.</p><form method="post" id="login" class="card">${field('Usuario o correo','email','text')}${field('Contraseña','password','password')}<label class="checkline"><input type="checkbox" name="remember"> Recordarme en este dispositivo durante 30 días</label><button type="submit" class="primary">Entrar</button></form><small>Alta por invitación de Dirección. Si has perdido el acceso, solicita un nuevo enlace al responsable del equipo.</small></main>`;document.querySelector('[name=password]').autocomplete='current-password';document.querySelector('[name=password]').minLength=4;document.querySelector('[name=email]').autocomplete='username';document.querySelector('[name=email]').autocapitalize='none';document.querySelector('[name=email]').spellcheck=false;bindForm('login',async(_,d)=>{await api('/login','POST',d);await init();});}
async function activation(token){activationToken=token;const data=await api('/activate/start','POST',{token});app.innerHTML=`<main class="auth"><h1>Activar acceso · ${esc(roles[data.role])}</h1><div class="card"><strong>${esc(data.name)}</strong>${data.chooseEmail?'':`<p>${esc(data.email)}</p>`}<form method="post" id="activate">${data.chooseEmail?field('Tu correo electrónico','email','email'):''}${field('Contraseña personal · mínimo 6 caracteres','password','password')}${field('Repetir contraseña','repeat','password')}<button class="primary" type="submit">Activar mi usuario</button></form></div></main>`;bindForm('activate',async(_,d)=>{if(d.password!==d.repeat)throw Error('Las contraseñas no coinciden');await api('/activate/finish','POST',{token:activationToken,password:d.password,email:d.email});activationToken='';login();message('Cuenta activada. Ya puedes entrar con tu correo y contraseña.');});}
let quickInvoiceFile=null;
function directionSections(){
 return [
  ['Inicio',[['home','Inicio']]],
  ['Calendario',[['calendar','Calendario']]],
  ['Equipo',[['roster','Corredores'],['licenses','Licencias'],['equipment','Material y medidas'],['clothes','Pedido de ropa'],['shop','Tienda'],['results','Resultados'],['days','Días de actividad'],['fines','Multas']]],
  ['Técnicos y vehículos',[['resources','Técnicos y vehículos']]],
  ['Contabilidad',[['conta','Ingresos y gastos'],['charges','Cobros por corredor'],['budgets','Presupuesto'],['bank','Banco y conciliación']]],
  ['Comunicación',[['publications','Publicaciones'],['photos','Fotos autorizadas']]],
  ['Administración',[['users','Usuarios y accesos'],['archive','Archivados'],...(me.owner?[['audit','Registro de accesos']]:[])]],
 ];
}
function directionNavigation(sections){
 return sections.map(([title,items])=>{
  const active=items.some(([id])=>id===page);
  return `<button type="button" data-page="${items[0][0]}" ${active?'aria-current="location" class="active"':''}>${title}</button>`;
 }).join('');
}
function directionSubnav(sections){
 const section=sections.find(([,items])=>items.some(([id])=>id===page));
 if(!section||section[1].length===1)return '';
 const [title,items]=section;
 return `<div class="section-navigation"><strong>${title}</strong><div class="section-links" aria-label="Apartados de ${title}">${items.map(([id,label])=>`<button type="button" data-page="${id}" ${page===id?'aria-current="page" class="active"':''}>${label}</button>`).join('')}</div></div>`;
}
function shell(){const mobile=window.matchMedia?.('(max-width: 800px)').matches;const sections=me.role==='director'?directionSections():null;let groups=[];if(me.role==='runner')groups=[['Mi área',[['home','Inicio'],['calendar','Calendario del equipo'],['calls','Mis convocatorias'],['planning','Mi planning'],['profile','Mis datos y documentos'],['results','Mis resultados'],['days','Mis días de actividad'],['charges','Mis gastos y recibos'],['myclothes','Mi ropa'],['shop','Tienda'],['fines','Mis multas'],['publications','Mis publicaciones']]]];else if(me.role==='technician')groups=[['Área técnica',[['home','Inicio'],['calendar','Calendario del equipo'],['mine','Mi disponibilidad'],['calls','Convocatorias'],['planning','Planning y medios'],['resources','Técnicos y vehículos'],['equipment','Material y medidas'],['results','Resultados'],['days','Días de actividad']]]];else groups=[['Comunicación',[['home','Inicio'],['publications','Generar publicaciones'],['photos','Fotos autorizadas']]]];app.innerHTML=`<div class="portal-layout"><aside><div class="identity"><strong>${esc(me.name)}</strong><small>${esc(roles[me.role])}</small></div><button type="button" id="mobileMenu" aria-expanded="false" aria-controls="portalNavigation">☰ Menú</button><div id="portalNavigation"><nav aria-label="Menú del portal">${sections?directionNavigation(sections):groups.map(([title,items])=>`<details ${!mobile||items.some(([id])=>id===page)?'open':''}><summary>${title}</summary>${items.map(([id,label])=>`<button data-page="${id}" ${page===id?'aria-current="page"':''} class="${page===id?'active':''}">${label}</button>`).join('')}</details>`).join('')}</nav><button id="logout">Cerrar sesión</button></div></aside>
${['director','runner','technician'].includes(me.role)?`<div class="mobile-actions" aria-label="Acciones rápidas"><button type="button" data-page="calendar">Calendario</button>${me.role==='director'?'<button type="button" class="primary" id="mobileInvoice">Subir factura</button><input type="file" id="mobileInvoiceCamera" accept="image/*" capture="environment" hidden>':''}</div>`:''}<main>${sections?directionSubnav(sections):''}<section id="content"></section></main></div>`;document.getElementById('logout').onclick=async()=>{try{await api('/logout','POST');me=null;csrf='';login();}catch(e){message(e.message);}};const menu=document.getElementById('mobileMenu');
menu.onclick=()=>{
 const expanded=menu.getAttribute('aria-expanded')==='true';
 menu.setAttribute('aria-expanded',String(!expanded));
 document.getElementById('portalNavigation').classList.toggle('expanded',!expanded);
};
const quick=document.getElementById('mobileInvoiceCamera');
if(quick){
 document.getElementById('mobileInvoice').onclick=()=>quick.click();
 quick.onchange=()=>{
  if(!quick.files[0])return;
  quickInvoiceFile=quick.files[0];
  navigate('conta');
 };
}
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>navigate(b.dataset.page));window.DemoPortal?.banner();return document.getElementById('content');}
async function navigate(next){page=(me.role==='director'&&['calls','planning'].includes(next))||(me.role==='runner'&&next==='mine')?'calendar':next;message('');const content=shell();if(window.matchMedia?.('(max-width: 800px)').matches)window.scrollTo(0,0);try{if(page==='home'){await dashboardPage(content);}else if(featureViews[page]){await featureViews[page](content);}else if(page==='users'){await usersPage(content);addBulkUserImport(content);}else if(page==='calendar'||page==='mine')await calendarPage(content);else if(page==='profile')await profilePage(content,me.id);else if(page==='roster')await rosterPage(content);else if(page==='clothes')await clothesPage(content);else if(page==='myclothes')await myClothesPage(content);else if(page==='fines')await finesPage(content);else if(page==='photos')await photosPage(content);else if(page==='audit'){const d=await api('/audit');content.innerHTML='<h1>Registro de accesos y cambios</h1><div class="card scroll"><table><thead><tr><th>Fecha</th><th>Acción</th><th>Usuario</th><th>Referencia</th></tr></thead><tbody>'+d.entries.map(r=>`<tr><td>${esc(new Date(r.at*1000).toLocaleString('es-ES'))}</td><td>${esc(r.action)}</td><td>${esc(r.user||'Acceso no identificado')}</td><td>${esc(r.target)}</td></tr>`).join('')+'</tbody></table></div>';}}catch(e){message(e.message);}}
function inviteLink(token){return location.origin+'/#activar='+encodeURIComponent(token);}
async function usersPage(c){const d=await api('/users');users=d.users;c.innerHTML=`<h1>Usuarios del equipo</h1>${me.owner?`<details class="card"><summary>Invitar por correo</summary><p>Para crear una ficha de corredor o técnico, usa Equipo o Técnicos y vehículos.</p><form method="post" id="invite"><div class="grid">${field('Nombre y apellidos','name')}${field('Correo de acceso','email','email')}${select('Perfil','role',Object.entries(roles))}</div><label>Permitir consulta de DNI, SEPA y documentos privados (solo Dirección)<input type="checkbox" name="documents"></label><button type="submit" class="primary">Crear invitación</button><div id="inviteResult" aria-live="polite"></div></form></details>`:''}<div class="card scroll"><table><thead><tr><th>Nombre</th><th>Correo</th><th>Perfil</th><th>Acceso</th><th></th></tr></thead><tbody>${users.map(u=>`<tr><td>${esc(u.name)}</td><td>${esc(u.email||'—')}</td><td>${esc(roles[u.role])}${u.documents?' · Documentos':''}</td><td>${u.active?(u.accountReady?'Activo':'Sin acceso'):'Desactivado'}${me.owner&&!u.active?` <button data-restore-user="${u.id}">Restaurar acceso</button>`:''}</td><td>${me.owner&&u.active?`${u.accountReady?`<button data-reset="${u.id}">Restablecer acceso</button> `:''}${!u.owner?`<button data-disable="${u.id}">Desactivar</button>`:''}`:''}</td></tr>`).join('')}</tbody></table></div>`;c.querySelectorAll('[data-restore-user]').forEach(b=>b.onclick=async()=>{try{await api('/users/'+b.dataset.restoreUser+'/restore','POST',{});await navigate('users');}catch(e){message(e.message);}});bindForm('invite',async(f,data)=>{data.documents=f.elements.documents.checked;const result=await api('/invites','POST',data);document.getElementById('inviteResult').innerHTML=`<div class="note"><strong>Invitación creada · caduca en 48 horas</strong><p>Entrega este enlace únicamente a la persona indicada:</p><p class="secret">${esc(inviteLink(result.token))}</p><small>No se ha enviado ningún correo.</small></div>`;});c.querySelectorAll('[data-disable]').forEach(b=>b.onclick=async()=>{if(confirm('¿Desactivar este usuario y cerrar sus sesiones?')){try{await api('/users/'+b.dataset.disable+'/disable','POST',{});await navigate('users');}catch(e){message(e.message);}}});c.querySelectorAll('[data-reset]').forEach(b=>b.onclick=async()=>{if(!confirm('Se cerrarán sus sesiones y se generará un nuevo enlace de activación. ¿Continuar?'))return;try{const r=await api('/users/'+b.dataset.reset+'/reset','POST',{});message('Enlace de recuperación (1 hora): '+inviteLink(r.token));}catch(e){message(e.message);}});}
const calendarMonths=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const calendarDateKey=date=>date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
let calendarMonth='';
const activityMonth=event=>event.date?.slice(0,7)||(calendarMonths.includes(event.month)?'2027-'+String(calendarMonths.indexOf(event.month)+1).padStart(2,'0'):'');
const activityDateLabel=event=>event.date||(activityMonth(event)?event.month+' · día por confirmar':'Fecha por confirmar');
function activityClassification(event={}){
 const category=event.category||'Carrera';
 const categories=['Entrenamiento de equipo','Carrera','Concentración'];
 if(!categories.includes(category))categories.push(category);
 const types=[['','Seleccionar categoría'],'Euskaldun','Copa de España','Vueltas','Otras'];
 if(event.type&&!types.includes(event.type))types.push(event.type);
 return `${select('Tipo de actividad','category',categories,category)}
  <div data-race-category>${select('Categoría de carrera','type',types,event.type||'')}</div>`;
}
function bindActivityClassification(form){
 const category=form.elements.category;
 const type=form.elements.type;
 const update=()=>{
  const race=category.value==='Carrera';
  form.querySelector('[data-race-category]').hidden=!race;
  type.disabled=!race;type.required=race;
 };
 category.onchange=update;
 form.elements.name.required=true;
 update();
}
function sortActivities(events){
  const key=event=>event.date||(activityMonth(event)?activityMonth(event)+'-00':'9999-99-99');
  return [...events].sort((a,b)=>key(a).localeCompare(key(b))||a.name.localeCompare(b.name,'es')||a.id.localeCompare(b.id));
}
function bindNameSearch(input,container){
  const normalize=value=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().trim();
  const items=[...container.querySelectorAll('[data-search-name]')];
  const empty=container.querySelector('[data-no-matches]');
  input.oninput=()=>{
    const query=normalize(input.value);
    items.forEach(item=>{item.hidden=!normalize(item.dataset.searchName).includes(query);});
    empty.hidden=items.some(item=>!item.hidden);
    container.querySelectorAll('[data-search-group]').forEach(group=>{group.hidden=![...group.querySelectorAll('[data-search-name]')].some(item=>!item.hidden);});
  };
  input.oninput();
}

function setAllCallStates(form,state){
 if(!['No convocado','Preconvocado','Convocado'].includes(state))throw Error('Estado de convocatoria no válido');
 form.querySelectorAll('select[name^="call:"]').forEach(input=>{input.value=state;});
}
function riderCallState(event){
 if((event.precalled||[]).includes(me.id))return {label:'Preconvocado',style:'assigned'};
 if(!(event.called||[]).includes(me.id))return {label:'No convocado',style:'pending'};
 return event.callStatus==='Publicada'?{label:'Convocado',style:'available'}:{label:'Preconvocado',style:'assigned'};
}
function riderAvailabilityInput(event){
 const answered=['Disponible','No disponible'].includes(event.myStatus);
 return `<label class="agenda-availability">${answered?'Mi disponibilidad':'Indica tu disponibilidad · pendiente'}
  <select name="status" data-availability-event="${esc(event.id)}">
   <option value="" disabled ${answered?'':'selected'}>Selecciona una respuesta</option>
   ${['Disponible','No disponible'].map(status=>`<option ${event.myStatus===status?'selected':''}>${status}</option>`).join('')}
  </select></label>`;
}
function riderCalendar(c,events){
 const sorted=sortActivities(events);
 c.innerHTML=`<h1>Calendario del equipo</h1>
  <p>Responde Disponible o No disponible en cada carrera y concentración para informar a Dirección. Dirección decide la convocatoria.</p>
  <p id="riderAvailabilityPending" role="status"></p>
  <details class="card"><summary>Exportar calendario</summary>
   <form method="get" action="/api/calendar.ics" class="toolbar">
    ${select('Calendario que quieres descargar','scope',[['all','Todo el calendario del equipo'],['selected','Mi calendario · preconvocatorias y convocatorias']])}
    <button type="submit">Descargar para Google Calendar, iPhone u Outlook</button>
    <button type="submit" formaction="/api/calendar.pdf">Descargar PDF · listado por meses</button>
   </form><small>Se descargan las actividades con fecha, incluidos todos los días de las vueltas y concentraciones. Importa el archivo .ics en tu aplicación de calendario. Es una copia de los datos actuales.</small>
  </details>
  <div class="toolbar">
   <label>Buscar actividad<input id="riderCalendarSearch" type="search" placeholder="Nombre o lugar"></label>
   <label>Mes (opcional)<input name="calendarMonth" type="month"></label>
   ${select('Mi convocatoria','callState',['Todas','Convocado','Preconvocado','No convocado'])}
   ${select('Mi disponibilidad','availabilityFilter',['Todas','Pendiente de responder','Disponible','No disponible'])}
   <button type="button" id="riderCalendarAll">Ver todo</button>
  </div><div id="riderAgenda" class="rider-agenda"></div>`;
 const search=c.querySelector('#riderCalendarSearch');
 const month=c.querySelector('[name=calendarMonth]');
 const status=c.querySelector('[name=callState]');
 const availability=c.querySelector('[name=availabilityFilter]');
 const render=()=>{
  const normalize=value=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('es');
  const query=normalize(search.value.trim());
  const rows=sorted.filter(event=>
   normalize(event.name+' '+(event.place||'')).includes(query)&&
   (!month.value||activityMonth(event)===month.value||(event.date<month.value+'-01'&&event.endDate>=month.value+'-01'))&&
   (status.value==='Todas'||riderCallState(event).label===status.value)&&
   (availability.value==='Todas'||(availability.value==='Pendiente de responder'?
    !['Disponible','No disponible'].includes(event.myStatus):event.myStatus===availability.value)));
  const pending=sorted.filter(event=>!['Disponible','No disponible'].includes(event.myStatus)).length;
  c.querySelector('#riderAvailabilityPending').textContent=pending?
   `Tienes ${pending} ${pending===1?'actividad pendiente':'actividades pendientes'} de responder.`:'Has respondido a todas las actividades.';
  let previousMonth;
  c.querySelector('#riderAgenda').innerHTML=rows.map(event=>{
   const group=activityMonth(event);
   const heading=group!==previousMonth?`<h2>${group?calendarMonths[Number(group.slice(5))-1]+' '+group.slice(0,4):'Fecha por confirmar'}</h2>`:'';
   previousMonth=group;
   const state=riderCallState(event);
   return `${heading}<article class="card agenda-activity">
    <div><strong>${esc(activityDateLabel(event))}${event.endDate&&event.endDate!==event.date?' – '+esc(event.endDate):''}</strong>
     <small>${esc(event.place||'Lugar por confirmar')}</small></div>
    <button type="button" class="agenda-open" data-calendar-event="${esc(event.id)}">
     <strong>${esc(event.name)}</strong><span class="resource-state ${state.style}">${state.label}</span>
    </button>${riderAvailabilityInput(event)}
   </article>`;
  }).join('')||'<div class="card">No hay actividades que coincidan con estos filtros.</div>';
  c.querySelectorAll('[data-calendar-event]').forEach(button=>button.onclick=()=>calendarPage(c,button.dataset.calendarEvent).catch(error=>message(error.message)));
  c.querySelectorAll('[data-availability-event]').forEach(input=>input.onchange=async()=>{
   const event=sorted.find(activity=>activity.id===input.dataset.availabilityEvent);
   input.disabled=true;
   try{
    await api('/events/'+encodeURIComponent(event.id)+'/availability','POST',{status:input.value});
    event.myStatus=input.value;
    if(c.isConnected){render();message('Disponibilidad guardada.');}
   }catch(error){if(c.isConnected){render();message(error.message);}}
  });
 };
 search.oninput=render;month.onchange=render;status.onchange=render;availability.onchange=render;
 c.querySelector('#riderCalendarAll').onclick=()=>{search.value='';month.value='';status.value='Todas';availability.value='Todas';render();};
 render();
}
async function calendarPage(c,selectedId){
  const director=me.role==='director';
  const availableRole=['runner','technician'].includes(me.role);
  const {events}=await api('/events');
  const runner=me.role==='runner';
  const calledForMe=e=>e.callStatus==='Publicada'&&(e.called||[]).includes(me.id);
  const rows=events;
  if(runner&&!selectedId){riderCalendar(c,events);return;}
  if(!calendarMonth){
    const now=calendarDateKey(new Date()).slice(0,7);
    const months=rows.map(activityMonth).filter(Boolean).sort();
    calendarMonth=months.find(month=>month>=now)||months.at(-1)||now;
  }
  const event=rows.find(e=>e.id===selectedId);
  if(selectedId&&!event)throw Error('La actividad ya no está disponible. Vuelve a cargar el calendario.');
  if(event){
    if(activityMonth(event))calendarMonth=activityMonth(event);
    const riders=director?(await api('/roster')).riders:[];
    const responses=event.responses||{};
    const called=event.called||[];
    c.innerHTML=`<button type="button" id="backCalendar">Volver al calendario</button>
      <article class="card"><h1>${esc(event.name)}</h1>
      <p>${esc(activityDateLabel(event))}${event.endDate&&event.endDate!==event.date?' – '+esc(event.endDate):''} · ${esc(event.place||'Lugar por confirmar')}</p>
      ${event.category?`<p class="pill">${esc(event.category)}${event.type?' · '+esc(event.type):''}</p>`:''}
      ${event.status?`<p class="pill">${esc(event.status)}</p>`:''}
      ${event.owner?`<p>Responsable: ${esc(event.owner)}</p>`:''}
      ${event.notes?`<p class="event-notes">${esc(event.notes)}</p>`:''}
      ${availableRole?`${runner?`<p class="resource-state ${riderCallState(event).style}">${riderCallState(event).label}</p>${riderAvailabilityInput(event)}`:select('Mi disponibilidad','status',['Por confirmar','Disponible','No disponible'],event.myStatus)}`:''}
      ${director?'<div class="toolbar"><button type="button" id="editCalendarEvent">Editar prueba o actividad</button><button type="button" id="moveCalendarEvent">Cambiar fecha</button><button type="button" id="removeCalendarEvent">Eliminar del calendario</button></div>':''}
      </article>
      ${director?`<div class="section-links activity-sections" role="group" aria-label="Ficha de la actividad">
        <button type="button" data-activity-section="call" aria-pressed="true" class="active">Convocatoria</button>
        <button type="button" data-activity-section="travel" aria-pressed="false">Viaje, hotel e inscripciones</button>
        <button type="button" data-activity-section="expenses" aria-pressed="false">Gastos y cobros</button>
      </div>
      <section class="card" id="activityCallPanel">
      <h2>Convocatoria</h2>
      <div class="toolbar"><span class="pill" id="activityCallStatus"></span>
        <button type="button" id="activityPublish"></button>
        <a class="button" href="/api/events/${encodeURIComponent(event.id)}/package">Descargar convocatoria y paquete hotel</a>
      </div>
      <details class="event-call"><summary id="callSelectionSummary">Abrir corredores para convocar</summary>
      <form method="post" id="calendarCall"><p>La disponibilidad es informativa: puedes decidir la convocatoria aunque no haya respuesta o figure No disponible.</p><div class="toolbar"><button type="button" data-bulk-call="Convocado">Seleccionar todos · Convocar</button><button type="button" data-bulk-call="Preconvocado">Preconvocar a todos</button><button type="button" data-bulk-call="No convocado">Quitar selección de todos</button></div><small>Puedes ajustar cada corredor después. Pulsa Guardar convocatoria para aplicar los cambios.</small>${riders.map(r=>`<div class="card"><strong>${esc(r.name)}</strong><p>Disponibilidad: <strong>${esc(['Disponible','No disponible'].includes(responses[r.id])?responses[r.id]:'Sin responder')}</strong></p>${select('Convocatoria','call:'+r.id,['No convocado','Preconvocado','Convocado'],(event.precalled||[]).includes(r.id)?'Preconvocado':called.includes(r.id)?(event.callStatus==='Publicada'?'Convocado':'Preconvocado'):'No convocado')}</div>`).join('')||'<p>Aún no hay corredores registrados.</p>'}
      <button type="submit">Guardar convocatoria</button></form></details>
      </section><section class="card" id="eventTravelPanel" hidden></section><section class="card" id="eventExpensePanel" hidden></section>`:''}`;
    document.getElementById('backCalendar').onclick=()=>navigate(page);
    if(director){
      document.getElementById('editCalendarEvent').onclick=()=>editEvent(c,event);
      c.querySelector('#moveCalendarEvent').onclick=()=>moveCalendarEvent(c,event);
      c.querySelector('#removeCalendarEvent').onclick=()=>removeCalendarEvent(c,event);
      const publish=c.querySelector('#activityPublish');
      const callForm=c.querySelector('#calendarCall');
      const selection=()=>Object.fromEntries([...callForm.querySelectorAll('select[name^="call:"]')].map(input=>[input.name.slice(5),input.value]));
      const initial=JSON.stringify(selection());
      const renderCall=()=>{
        const states=selection(),values=Object.values(states);
        c.querySelector('#activityCallStatus').textContent=values.filter(value=>value==='Convocado').length+' convocados · '+values.filter(value=>value==='Preconvocado').length+' preconvocados';
        c.querySelector('#callSelectionSummary').textContent='Abrir corredores para convocar · '+values.filter(value=>value!=='No convocado').length+' seleccionados';
        publish.textContent=event.callStatus==='Publicada'?'Pasar todos a preconvocados':'Convocar a todos los preconvocados';
        publish.disabled=JSON.stringify(states)!==initial||!values.some(value=>value!=='No convocado');
      };
      renderCall();callForm.onchange=renderCall;
      callForm.querySelectorAll('[data-bulk-call]').forEach(button=>button.onclick=()=>{setAllCallStates(callForm,button.dataset.bulkCall);renderCall();});
      publish.onclick=async()=>{
        const states=selection(),next=event.callStatus==='Publicada'?'Preconvocado':'Convocado';
        Object.keys(states).forEach(id=>{if(states[id]!=='No convocado')states[id]=next;});
        publish.disabled=true;
        try{await api('/events/'+event.id+'/call','POST',{states});await calendarPage(c,event.id);message('Convocatoria actualizada.');}
        catch(error){message(error.message);renderCall();}
      };
      bindForm('calendarCall',async()=>{
        await api('/events/'+event.id+'/call','POST',{states:selection()});
        await calendarPage(c,event.id);message('Convocatoria guardada.');
      });
      const panels={call:c.querySelector('#activityCallPanel'),travel:c.querySelector('#eventTravelPanel'),expenses:c.querySelector('#eventExpensePanel')};
      const buttons=[...c.querySelectorAll('[data-activity-section]')];
      const loaders={
        travel:()=>eventTravelPanel(panels.travel,event),
        expenses:()=>modulePage(panels.expenses,'entry',null,event),
      };
      const loaded={};
      buttons.forEach(button=>button.onclick=async()=>{
        const section=button.dataset.activitySection;
        buttons.forEach(item=>{
          item.classList.toggle('active',item===button);
          item.setAttribute('aria-pressed',String(item===button));
          panels[item.dataset.activitySection].hidden=item!==button;
        });
        if(!loaders[section])return;
        if(!loaded[section]){
          panels[section].textContent='Cargando…';
          loaded[section]=loaders[section]();
        }
        try{
          await loaded[section];
          panels[section].refreshActivitySection?.();
        }
        catch(error){delete loaded[section];panels[section].textContent=error.message;}
      });
    }
    if(availableRole)c.querySelector('[name=status]').onchange=async e=>{
      const input=e.target;input.disabled=true;
      try{
        await api('/events/'+event.id+'/availability','POST',{status:input.value});
        await calendarPage(c,event.id);message('Disponibilidad guardada. Dirección puede ver tu respuesta.');
      }catch(err){input.value=['Disponible','No disponible'].includes(event.myStatus)?event.myStatus:'';message(err.message);}
      finally{input.disabled=false;}
    };
    return;
  }

  const [year,month]=calendarMonth.split('-').map(Number);
  const first=new Date(year,month-1,1);
  const days=new Date(year,month,0).getDate();
  const offset=(first.getDay()+6)%7;
  const activity=e=>`<button type="button" class="calendar-event" data-calendar-event="${esc(e.id)}">${esc(e.name)}${calledForMe(e)?' · Convocado':''}</button>`;
  const cells=Array.from({length:Math.ceil((offset+days)/7)*7},(_,index)=>{
    const day=index-offset+1;
    if(day<1||day>days)return '<div class="calendar-cell calendar-blank"></div>';
    const key=calendarDateKey(new Date(year,month-1,day));
    const dateLabel=director?`<button type="button" class="calendar-day" data-create-event-date="${key}" aria-label="Crear actividad el ${day} de ${calendarMonths[month-1]} de ${year}">${day} <span aria-hidden="true">+</span></button>`:`<span>${day}</span>`;
    return `<div class="calendar-cell">${dateLabel}${rows.filter(e=>e.date&&e.date<=key&&(e.date===key||e.endDate>=key)).map(activity).join('')}</div>`;
  }).join('');
  const monthEnd=calendarDateKey(new Date(year,month,0));
  const monthStart=calendarDateKey(first);
  const agenda=sortActivities(rows.filter(e=>e.date&&e.date<=monthEnd&&(e.date>=monthStart||e.endDate>=monthStart)));
  const pending=rows.filter(e=>!e.date&&activityMonth(e)===calendarMonth);
  const unscheduled=rows.filter(e=>!activityMonth(e));
  const title=page==='mine'?(me.role==='technician'?'Mi disponibilidad':'Mi calendario'):'Calendario del equipo';
  c.innerHTML=`<h1>${title}</h1>
    ${director?'<details class="card"><summary>Exportar calendario</summary><div class="toolbar"><a class="button" href="/api/calendar.ics?scope=all">Google Calendar, iPhone u Outlook</a><a class="button" href="/api/calendar.pdf?scope=all">Descargar PDF · listado por meses</a></div></details>':''}
    <details class="card"><summary>Buscar y ver todas las actividades · ${rows.length}</summary>
      <label>Nombre de la prueba o actividad<input id="calendarSearch" type="search" placeholder="Ej. Guadiana"></label>
      <div id="calendarSearchResults">${sortActivities(rows).map(e=>`<div data-search-name="${esc(e.name)}">${activity(e)}<small>${esc(activityDateLabel(e))}${director?` · ${e.callStatus==='Publicada'?'Publicada':'Borrador'} · ${(e.called||[]).length} seleccionados`:''}</small></div>`).join('')}
      <p data-no-matches hidden>No hay actividades que coincidan.</p></div>
    </details>
    <div class="toolbar calendar-controls">
      <button type="button" data-month-step="-1">Anterior</button>
      <label>Mes <input id="calendarMonth" type="month" value="${calendarMonth}"></label>
      <button type="button" data-month-step="1">Siguiente</button>
    </div>
    ${director?`<p>Pulsa un día del calendario para crear una carrera o actividad en esa fecha.</p>
    <details class="card"><summary>Nueva carrera o actividad</summary><form method="post" id="event">
      <div class="grid">${activityClassification()}${field('Nombre de la actividad','name')}${field('Lugar','place')}${field('Fecha de inicio','date','date')}${field('Fecha de fin (opcional)','endDate','date')}</div>
      <small>Para una carrera de un solo día, deja vacía la fecha de fin.</small>
      <button type="submit" class="primary">Crear actividad</button></form></details>`:''}
    <div class="calendar-scroll${director?' calendar-date-picker':''}"><div class="calendar-grid" aria-label="${calendarMonths[month-1]} ${year}">
    ${['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].map(day=>`<strong>${day}</strong>`).join('')}${cells}</div></div>
    <section class="mobile-agenda card"><h2>${calendarMonths[month-1]} ${year}</h2>
      ${agenda.map(e=>`<div><small>${esc(activityDateLabel(e))}${e.endDate&&e.endDate!==e.date?' – '+esc(e.endDate):''}</small>${activity(e)}</div>`).join('')||'<p>No hay actividades con día confirmado este mes.</p>'}
    </section>
    ${pending.length?`<section class="card"><h2>${calendarMonths[month-1]} · día por confirmar</h2>${pending.map(activity).join('')}</section>`:''}
    ${unscheduled.length?`<section class="card"><h2>Actividades sin fecha</h2>${unscheduled.map(activity).join('')}</section>`:''}`;
  bindNameSearch(document.getElementById('calendarSearch'),document.getElementById('calendarSearchResults'));
  const redraw=()=>calendarPage(c).catch(err=>message(err.message));
  c.querySelectorAll('[data-month-step]').forEach(button=>button.onclick=()=>{
    calendarMonth=calendarDateKey(new Date(year,month-1+Number(button.dataset.monthStep),1)).slice(0,7);
    redraw();
  });
  document.getElementById('calendarMonth').onchange=e=>{
    if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(e.target.value))return;
    calendarMonth=e.target.value;
    redraw();
  };
  c.querySelectorAll('[data-calendar-event]').forEach(button=>button.onclick=()=>calendarPage(c,button.dataset.calendarEvent).catch(err=>message(err.message)));
  const createForm=c.querySelector('#event');
  if(createForm){
    bindActivityClassification(createForm);
    const {date,endDate}=createForm.elements;
    const updateDateRange=()=>{endDate.min=date.value;};
    date.oninput=updateDateRange;
    c.querySelectorAll('[data-create-event-date]').forEach(button=>button.onclick=()=>{
      date.value=button.dataset.createEventDate;
      updateDateRange();
      createForm.closest('details').open=true;
      createForm.elements.name.focus();
    });
  }
  bindForm('event',async(_,data)=>{
    await api('/events','POST',data);
    if(data.date)calendarMonth=data.date.slice(0,7);
    await calendarPage(c);
    message('Actividad creada.');
  });
}
function showRiderInvites(results,invitations){
  results.innerHTML=invitations.map(({name,token})=>`<div class="row"><label>${esc(name)}<input class="secret" readonly value="${esc(inviteLink(token))}"></label><button type="button">Copiar enlace</button></div>`).join('');
  results.querySelectorAll('button').forEach(button=>button.onclick=async()=>{
    const input=button.parentElement.querySelector('input');
    try{await navigator.clipboard.writeText(input.value);button.textContent='Copiado';}
    catch{input.focus();input.select();}
  });
}
function juniorRosterGroups(riders){
 return [['2010','Júnior de primer año · 2010'],['2009','Júnior de segundo año · 2009'],['','Año pendiente u otra categoría']].map(([year,label])=>({label,riders:riders.filter(r=>year?String(r.birthYear)===year:!['2009','2010'].includes(String(r.birthYear))).sort((a,b)=>a.name.localeCompare(b.name,'es'))}));
}
async function rosterPage(c){
  const [activeResult,inactiveResult]=await Promise.all([api('/roster'),api('/roster?status=inactive')]);
  roster=activeResult.riders;
  const inactive=inactiveResult.riders;
  const accounts=me.owner?(await api('/users')).users:[];
  const eligible=new Set(accounts.filter(u=>u.active&&u.role==='runner'&&!u.accountReady&&!u.email).map(u=>u.id));
  c.innerHTML=`<h1>Corredores · Altas y bajas</h1><p>Da de alta nuevos corredores o utiliza Dar de baja junto a su ficha. Las bajas conservan el historial y cierran el acceso al área privada.</p>
    <details class="card"><summary>Dar de alta corredor</summary>
      <form id="createRider">
        <label>Nombre<input name="firstName" maxlength="100" required></label>
        <label>Apellidos<input name="surname" maxlength="180" required></label>
        <label class="checkline"><input type="checkbox" name="invite" checked> Generar enlace de registro</label>
        <button type="submit" class="primary">Guardar corredor</button>
      </form>
    </details>
    <div id="riderCreated" class="card" hidden>
      <p id="riderCreatedMessage" role="status"></p>
      <button type="button" id="openNewRider">Abrir ficha</button>
      <div id="newRiderInvite"></div>
    </div>
    ${eligible.size?`<form id="rosterInvites" class="card"><h2>Enlaces de registro para corredores</h2>
    <p>Marca los corredores que quieres invitar. Cada enlace sirve para una sola ficha y caduca en 7 días. Generar otro para ese corredor sustituye el anterior.</p>
    ${roster.filter(r=>eligible.has(r.id)).map(r=>`<label class="checkline"><input type="checkbox" name="rider" value="${esc(r.id)}" checked>${esc(r.name)}</label>`).join('')}
    <button type="submit" class="primary">Generar enlaces de registro</button><div id="rosterInviteResults" aria-live="polite"></div></form>`:''}
    <label>Buscar corredor<input type="search" id="riderSearch" placeholder="Nombre o apellidos"></label>
    <div class="card" id="riderSearchResults">${juniorRosterGroups(roster).filter(group=>group.riders.length).map(group=>`<section data-search-group><h2>${esc(group.label)} · ${group.riders.length}</h2>${group.riders.map(r=>`<div class="row" data-search-name="${esc(r.name)}"><strong>${esc(r.name)}</strong><button type="button" data-profile="${esc(r.id)}">Abrir ficha</button><button type="button" data-rider-status="${esc(r.id)}" data-active="false">Dar de baja</button></div>`).join('')}</section>`).join('')}
    <p data-no-matches hidden>${roster.length?'No hay corredores que coincidan.':'Aún no hay corredores registrados.'}</p></div><details class="card"><summary>Corredores de baja · ${inactive.length}</summary>${inactive.map(r=>`<div class="row"><strong>${esc(r.name)}</strong><button type="button" data-rider-status="${esc(r.id)}" data-active="true">Volver a dar de alta</button></div>`).join('')||'<p>No hay corredores de baja.</p>'}</details>`;
  c.querySelectorAll('[data-rider-status]').forEach(button=>button.onclick=async()=>{
    const active=button.dataset.active==='true';
    const rider=[...roster,...inactive].find(r=>r.id===button.dataset.riderStatus);
    if(!confirm(active?`¿Volver a dar de alta a ${rider.name}?`:`¿Dar de baja a ${rider.name}? Se cerrará su acceso y se conservarán su ficha, documentos e historial.`))return;
    button.disabled=true;
    try{await api('/roster/'+encodeURIComponent(rider.id)+'/status','POST',{active});await rosterPage(c);message(active?'Corredor dado de alta de nuevo.':'Corredor dado de baja. Su historial se conserva.');}
    catch(error){message(error.message);button.disabled=false;}
  });
  bindNameSearch(c.querySelector('#riderSearch'),c.querySelector('#riderSearchResults'));
  c.querySelectorAll('[data-profile]').forEach(b=>b.onclick=()=>profilePage(c,b.dataset.profile).catch(e=>message(e.message)));
  bindForm('createRider',async(form,{firstName,surname})=>{
    const {rider,invitation}=await api('/roster','POST',{firstName,surname,invite:form.elements.invite.checked});
    if(!form.isConnected)return;
    form.reset();
    form.closest('details').open=false;
    await rosterPage(c).catch(()=>message('La ficha se ha creado. Vuelve a Corredores para actualizar el listado.'));
    const result=c.querySelector('#riderCreated');
    if(!result)return;
    c.querySelector('#riderCreatedMessage').textContent=`${rider.name} ya está dado de alta.${invitation?' El enlace de registro caduca en 7 días.':''}`;
    c.querySelector('#openNewRider').onclick=()=>profilePage(c,rider.id).catch(e=>message(e.message));
    if(invitation)showRiderInvites(c.querySelector('#newRiderInvite'),[invitation]);
    result.hidden=false;
  });
  bindForm('rosterInvites',async form=>{
    const riders=new FormData(form).getAll('rider');
    if(!riders.length)throw Error('Selecciona al menos un corredor.');
    const {invitations}=await api('/roster/invites','POST',{riders});
    showRiderInvites(c.querySelector('#rosterInviteResults'),invitations);
  });
}
async function prepareIdentityFile(file){
 if(!file)return file;
 const pdf=file.type==='application/pdf'||/\.pdf$/i.test(file.name);
 if(pdf){
  if(file.size>4*1024*1024)throw Error('El PDF debe ocupar como máximo 4 MB.');
  return file;
 }
 if(/^image\/(jpeg|png)$/.test(file.type)&&file.size<=4*1024*1024)return file;
 const url=URL.createObjectURL(file);
 try{
  const image=new Image();
  image.src=url;
  await image.decode();
  const scale=Math.min(1,2000/Math.max(image.naturalWidth,image.naturalHeight));
  const canvas=document.createElement('canvas');
  canvas.width=Math.round(image.naturalWidth*scale);
  canvas.height=Math.round(image.naturalHeight*scale);
  canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
  const jpeg=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.85));
  if(!jpeg||jpeg.size>4*1024*1024)throw Error('Imagen demasiado grande');
  return new File([jpeg],'documento.jpg',{type:'image/jpeg'});
 }catch{
  throw Error('No se pudo abrir esa foto. Selecciona PDF, JPG o PNG de hasta 4 MB.');
 }finally{URL.revokeObjectURL(url);}
}
async function profilePage(c,id){const d=await api('/profile/'+id),p=d.profile;const privateAccess=me.id===id||me.documents;const personalFields=[['Nombre','firstName','text'],['Apellidos','surname','text'],['Año de nacimiento','birthYear','text'],['DNI','dni','text'],['Estado del DNI','dniStatus','text'],['Teléfono','phone','tel'],['Dirección','address','text'],['Fecha de nacimiento','birth','date'],['Tutor/a','guardian','text'],['Teléfono tutor/a','guardianPhone','tel'],['Titular de cuenta','bankHolder','text'],['IBAN','iban','text'],['Email tutor/a','guardianEmail','email'],['Segundo tutor/a','guardian2','text'],['Teléfono segundo tutor/a','guardianPhone2','tel'],['Email segundo tutor/a','guardianEmail2','email'],['Población','city','text'],['Código postal','zip','text'],['Provincia','province','text'],['Salida habitual (Bilbao / Zaragoza)','departureDefault','text'],['Punto de recogida','pickupPoint','text']];
const healthFields=[
 ['medication','¿Tomas alguna medicación?','¿Cuál?'],
 ['allergies','¿Tienes alguna alergia?','¿Cuáles?'],
 ['intolerances','¿Tienes alguna intolerancia?','¿Cuáles?']
];c.innerHTML=`<h1>${me.id===id?'Mi ficha':esc(roster.find(r=>r.id===id)?.name||'Ficha del corredor')}</h1>${me.id!==id?'<button type="button" id="backToRoster">Volver a Corredores</button>':''}<form method="post" id="profile" class="card"><h2>Datos deportivos y tallas</h2><div class="grid">${field('Club','club','text',p.club)}${field('Preparador','coach','text',p.coach)}<label>Días de competición en 2026<input name="competitionDays2026" type="number" min="0" max="365" step="1" placeholder="Sin indicar" value="${esc(p.competitionDays2026??'')}"></label>${[['bike','Bicicleta'],['bikeSize','Talla bicicleta'],['helmet','Talla de casco (ej. M o 54–58 cm)'],['pedals','Pedales'],['saddleHeight','Altura sillín (mm)'],['saddleToBar','Distancia sillín–manillar (mm)']].map(([key,label])=>field(label,key,'text',p[key])).join('')}${clothes.map(item=>select(item,'size:'+item,['','XXS','XS','S','M','L','XL','XXL','XXXL'],p.sizes?.[item]||'')).join('')}</div>${privateAccess?`<h2>Datos personales privados</h2><div class="grid">${personalFields.map(([label,key,type])=>field(label,key,type,p[key])).join('')}</div><h2>Medicación, alergias e intolerancias</h2>
<small>Información privada para el propio corredor y Dirección con permiso de documentos.</small>
<div class="grid">${healthFields.map(([key,question,detail])=>`<fieldset>${select(question,key+'Status',[['','Sin indicar'],'Sí','No'],p[key+'Status']||'')}<label>${detail}<textarea name="${key}Details" maxlength="250" rows="3">${esc(p[key+'Details']||'')}</textarea></label></fieldset>`).join('')}</div>`:''}<label>Permitir a Comunicación acceder a mis fotos para las publicaciones del equipo<input type="checkbox" name="photoConsent" ${p.photoConsent?'checked':''}></label><small>En menores, Dirección debe conservar la autorización de sus representantes antes de marcar este permiso.</small><button type="submit" class="primary">Guardar ficha</button></form>${privateAccess?`<form method="post" id="upload" class="card"><h2>Documentos privados</h2>${select('Tipo de documento','kind',[['dni','DNI · anverso'],['dni_reverso','DNI · reverso'],['licencia','Licencia federativa · anverso'],['licencia_reverso','Licencia federativa · reverso'],['contrato_club','Contrato del club'],['sepa','Mandato SEPA'],['autorizacion','Autorización de tutores']])}<label>Foto o PDF · máximo 4 MB<input type="file" name="file" accept="image/*,application/pdf,.heic,.heif" required></label><small>Sube una foto legible de cada cara de la licencia por separado. También puedes subir tu DNI. Dirección con permiso de documentos podrá consultarla.</small><button type="submit">Subir documento privado</button></form>`:''}${privateAccess?`<section class="card"><h2>Fotos del corredor</h2><p>Sube las dos fotos para preparar las publicaciones del equipo.</p><div class="grid">${[['portrait','Foto de medio cuerpo con la equipación del equipo'],['action','Foto en acción sobre la bicicleta']].map(([kind,label])=>`<form method="post" id="photo-${kind}"><label>${label}<input type="file" name="file" accept="image/jpeg,image/png" required></label><small>JPG o PNG · máximo 3 MB</small><button type="submit">Subir foto</button></form>`).join('')}</div></section>`:''}<div id="documents" class="card"></div>`;const upload=c.querySelector('#upload');
const profile=c.querySelector('#profile');
if(upload){
 profile.before(upload);
 upload.querySelector('h2').textContent='1. Escanear y subir documentos';
 addIdentityOCR(upload,profile);
}
const back=c.querySelector('#backToRoster');if(back)back.onclick=()=>navigate('roster');bindForm('profile',async(f,data)=>{const sizes={};Object.entries(data).filter(([k])=>k.startsWith('size:')).forEach(([k,v])=>sizes[k.slice(5)]=v);const output={club:data.club,coach:data.coach,sizes,photoConsent:f.elements.photoConsent.checked,competitionDays2026:data.competitionDays2026===''?'':Number(data.competitionDays2026)};for(const key of ['bike','bikeSize','helmet','pedals','saddleHeight','saddleToBar'])output[key]=data[key]||'';if(privateAccess){
 for(const [,key] of personalFields)output[key]=data[key];
 for(const [key] of healthFields){
  output[key+'Status']=data[key+'Status'];
  output[key+'Details']=data[key+'Details']||'';
 }
}await api('/profile/'+id,'POST',output);message('Ficha guardada.');});bindForm('upload',async f=>{
 const data=new FormData(f);
 data.set('file',await prepareIdentityFile(f.elements.file.files[0]));
 await api('/documents/'+id,'POST',data,f);await listDocuments(id);message('Documento privado guardado.');f.reset();});for(const kind of ['portrait','action'])bindForm('photo-'+kind,async form=>{
  const payload=new FormData(form);payload.set('kind',kind);
  await api('/documents/'+id,'POST',payload,form);
  form.reset();await listDocuments(id);message('Foto guardada.');
});await listDocuments(id);}
async function listDocuments(id){const d=await api('/documents/'+id);document.getElementById('documents').innerHTML='<h2>Archivos registrados</h2>'+(d.documents.map(f=>`<div class="row"><span>${esc(({contrato_club:'Contrato del club',dni:'DNI · anverso',dni_reverso:'DNI · reverso',licencia:'Licencia federativa · anverso',licencia_reverso:'Licencia federativa · reverso',portrait:'Foto con equipación',action:'Foto en bicicleta'})[f.kind]||f.kind)} · ${Math.round(f.size/1024)} KB</span><div><a href="/api/file/${f.id}">Descargar</a> <button data-delete-file="${f.id}">Eliminar</button></div></div>`).join('')||'No hay documentos registrados.');document.querySelectorAll('[data-delete-file]').forEach(b=>b.onclick=async()=>{if(!confirm('¿Eliminar este documento? Las copias de seguridad conservan su plazo de retención.'))return;try{await api('/file/'+b.dataset.deleteFile+'/delete','POST',{});await listDocuments(id);}catch(e){message(e.message);}});}
async function myClothesPage(c){
 const [kit,shop]=await Promise.all([api('/clothes/mine'),api('/shop')]);
 c.innerHTML=`<h1>Mi ropa</h1>${clothingCatalog()}<section class="card"><h2>Dotación del equipo</h2>
  <p>Prendas asignadas por el equipo.</p><div class="scroll"><table>
  <thead><tr><th>Prenda</th><th>Talla</th><th>Unidades</th></tr></thead><tbody>
  ${clothes.map(item=>`<tr><td>${esc(item)}</td><td>${esc(kit.sizes[item]||'Sin indicar')}</td><td>${kit.quantities[item]??0}</td></tr>`).join('')}
  </tbody></table></div></section><section class="card"><h2>Mis compras extra</h2>
  <p>Estos pedidos se registran como un cargo en tu cuenta.</p>
  <button type="button" id="requestExtraClothes" class="primary">Pedir ropa extra</button>
  ${extraClothingOrders(shop.orders||[])}</section>`;
 c.querySelector('#requestExtraClothes').onclick=()=>navigate('shop');
}
async function clothesPage(c){
  const [{riders},shop]=await Promise.all([api('/clothes'),api('/shop')]);
  const orders=shop.orders||[];
  const activeOrders=orders.filter(order=>order.paymentStatus!=='Anulado');
  c.innerHTML=`<h1>Ropa por corredor · Dotación y extras</h1>${clothingCatalog()}
    <div class="toolbar"><button class="primary" type="button" id="clothesExport">Guardar y descargar dotación y extras · Excel</button>
    <button type="button" id="clothingShop">Gestionar tienda y precios</button>
    <button type="button" id="clothingCharges">Ver cobros por corredor</button></div>
    <p id="clothesTotal"></p>
    <p>Compras extra registradas: ${activeOrders.length} pedidos · ${euros(activeOrders.reduce((sum,order)=>sum+order.amount,0))}</p>
    <div class="note">Dotación del equipo: una unidad de cada prenda y dos camisetas por defecto. Se respetan las cantidades ajustadas y puedes poner 0 para excluir una prenda. Despliega el nombre de cada corredor para editar sus tallas y cantidades. Las compras extra muestran los pedidos de la tienda y su cargo en la cuenta del corredor. El Excel tiene hojas independientes para la dotación y las compras extra.</div>
    <details class="card"><summary>Total de la dotación por prenda</summary><div id="clothesSummary"></div></details>`+riders.map(r=>`
    <details class="card" data-rider-clothing="${esc(r.id)}">
      <summary><strong>${esc(r.name)}</strong> · Editar tallas y pedido</summary>
    <form method="post" data-clothing="${esc(r.id)}">
      <h3>Dotación del equipo · A cargo del club</h3>
      <div class="scroll"><table><thead><tr><th>Prenda</th><th>Talla</th><th>Unidades</th></tr></thead>
      <tbody>${clothes.map(item=>`<tr><td>${esc(item)}</td><td><select name="size:${esc(item)}" aria-label="Talla de ${esc(item)} de ${esc(r.name)}">${['','XXS','XS','S','M','L','XL','XXL','XXXL'].map(size=>`<option value="${esc(size)}" ${size===(r.sizes[item]||'')?'selected':''}>${esc(size||'Sin indicar')}</option>`).join('')}</select></td>
      <td><input type="number" name="${esc(item)}" min="0" max="100" step="1" required value="${r.quantities[item]??(item==='Camiseta'?2:1)}" aria-label="Cantidad de ${esc(item)}"></td></tr>`).join('')}</tbody></table></div>
      <button type="submit">Guardar tallas y dotación</button>
    </form><section><h3>Compras extra · A cargo del corredor</h3>
      ${extraClothingOrders(orders.filter(order=>order.rider===r.id))}
    </section></details>`).join('');
  c.querySelector('#clothingShop').onclick=()=>navigate('shop');
  c.querySelector('#clothingCharges').onclick=()=>navigate('charges');
  const forms=[...c.querySelectorAll('[data-clothing]')];
  const download=c.querySelector('#clothesExport');
  const total=()=>forms.flatMap(f=>[...f.querySelectorAll('input[type="number"]')]).reduce((sum,input)=>sum+Number(input.value),0);
  const showTotal=()=>{
    c.querySelector('#clothesTotal').textContent=`${riders.length} corredores · ${total()} unidades de dotación del equipo`;
    c.querySelector('#clothesSummary').innerHTML=`<table><thead><tr><th>Prenda</th><th>Unidades</th></tr></thead><tbody>${clothes.map(item=>{
      const quantity=forms.reduce((sum,form)=>sum+Number(form.elements.namedItem(item).value),0);
      return `<tr><td>${esc(item)}</td><td>${quantity}</td></tr>`;
    }).join('')}</tbody></table>`;
  };
  showTotal();
  const snapshot=form=>JSON.stringify(Object.fromEntries(new FormData(form)));
  const saved=new Map(forms.map(form=>[form,snapshot(form)]));
  const save=async form=>{
    const values=snapshot(form);
    if(values===saved.get(form))return;
    const entries=Object.entries(JSON.parse(values));
    const quantities=Object.fromEntries(entries.filter(([item])=>!item.startsWith('size:')).map(([item,value])=>[item,Number(value)]));
    const sizes=Object.fromEntries(entries.filter(([item])=>item.startsWith('size:')).map(([item,value])=>[item.slice(5),value]));
    await api('/profile/'+form.dataset.clothing,'POST',{quantities,sizes});
    saved.set(form,values);
  };
  const run=async action=>{
    if(download.disabled)return;
    download.disabled=true;
    try{await action();}catch(err){message(err.message);}
    finally{download.disabled=false;}
  };
  forms.forEach(form=>{
    form.oninput=showTotal;
    form.onsubmit=e=>{
      e.preventDefault();
      run(async()=>{if(!form.reportValidity())return;await save(form);message('Tallas y cantidades del corredor guardadas.');});
    };
  });
  download.onclick=()=>run(async()=>{
    for(const form of forms){
      if(!form.reportValidity())return;
      await save(form);
    }
    message(total()?'Pedido actualizado.':'El pedido todavía no tiene unidades. El Excel incluye las tallas registradas.');
    if(window.DemoPortal?.active){DemoPortal.downloadMessage();return;}
    const link=document.createElement('a');
    link.href='/api/clothes/export';
    link.download='Pedido_ropa_Miribilla_Ecotisa.xlsx';
    link.click();
  });
}
async function finesPage(c){
 const {fines}=await api('/fines');
 const director=me.role==='director';
 const personal=me.role==='runner';
 const rows=personal?fines.filter(fine=>fine.user===me.id):fines;
 const riders=director?(await api('/roster')).riders:[];
 c.innerHTML=`<h1>${personal?'Mis multas':'Multas'}</h1>
  ${director?`<form method="post" id="fine" class="card">
    ${select('Corredor','user',riders.map(rider=>[rider.id,rider.name]))}
    ${select('Motivo e importe','type',fineTypes.map(([reason,amount],index)=>[String(index),reason+' · '+(typeof amount==='number'?amount+' €':amount)]))}
    <label>Observaciones<textarea name="note" maxlength="300"></textarea></label>
    <small>Las faltas graves se registran para decisión de Dirección; no eliminan automáticamente al corredor.</small>
    <button type="submit" class="primary">Registrar multa</button></form>`:''}
  ${rows.length?`<div class="card scroll"><table><thead><tr>
    <th>Fecha</th>${director?'<th>Corredor</th>':''}<th>Motivo</th><th>Importe</th><th>Estado</th>${director?'<th>Acciones</th>':''}
   </tr></thead><tbody>${rows.map(fine=>`<tr><td>${esc(fine.date)}</td>
    ${director?`<td>${esc(riders.find(rider=>rider.id===fine.user)?.name||'Corredor')}</td>`:''}
    <td>${esc(fine.reason)}</td><td>${typeof fine.amount==='number'?fine.amount+' €':esc(fine.amount)}</td>
    <td>${esc(fine.status)}${director?`<select data-fine-status="${esc(fine.id)}" aria-label="Estado de la multa">
      ${['Pendiente','Pagada','Anulada','Pendiente de decisión','Resuelta'].map(status=>`<option ${status===fine.status?'selected':''}>${status}</option>`).join('')}
    </select>`:''}</td>${director?`<td><button type="button" data-remove-fine="${esc(fine.id)}">Eliminar</button></td>`:''}</tr>`).join('')}</tbody></table></div>`:
    `<div class="card">${personal?'No tienes multas registradas.':'No hay multas registradas.'}</div>`}`;
 c.querySelectorAll('[data-remove-fine]').forEach(button=>button.onclick=async()=>{
  if(!confirm('¿Eliminar esta multa? Dejará de aparecer al corredor y de sumar en su cuenta. Podrás recuperarla desde Archivados.'))return;
  button.disabled=true;
  try{await api('/fines/'+encodeURIComponent(button.dataset.removeFine)+'/archive','POST',{});await finesPage(c);message('Multa eliminada. La cuenta del corredor se ha actualizado.');}
  catch(error){button.disabled=false;message(error.message);}
 });
 c.querySelectorAll('[data-fine-status]').forEach(select=>select.onchange=async()=>{
  try{
   await api('/fines/'+select.dataset.fineStatus+'/status','POST',{status:select.value});
   message('Estado actualizado.');
  }catch(error){message(error.message);}
 });
 bindForm('fine',async(_,data)=>{
  data.type=Number(data.type);
  await api('/fines','POST',data);
  await navigate('fines');
 });
}
async function photosPage(c){const d=await api('/media/roster');c.innerHTML='<h1>Fotos autorizadas</h1><div class="note">Medio cuerpo y en bicicleta. Solo se muestran corredores con autorización de imagen registrada.</div>';for(const r of d.riders){const node=document.createElement('div');node.className='card';node.innerHTML='<h2>'+esc(r.name)+'</h2>'+(r.photos.map(f=>`<p>${esc(f.kind==='portrait'?'Medio cuerpo':'En bicicleta')} · <a href="/api/file/${f.id}">Descargar foto</a></p>`).join('')||'<p>Sin fotos registradas.</p>')+(['director','communication'].includes(me.role)?`<form method="post" data-photo-upload="${r.id}">${select('Tipo de foto','kind',[['portrait','Medio cuerpo'],['action','En bicicleta']])}<label>Foto JPG/PNG · máximo 3 MB<input type="file" name="file" accept="image/jpeg,image/png" required></label><button type="submit">Guardar foto</button></form>`:'');c.appendChild(node);}if(!d.riders.length)c.insertAdjacentHTML('beforeend','<div class="card">Sin corredores con autorización registrada todavía.</div>');c.querySelectorAll('[data-photo-upload]').forEach(f=>f.onsubmit=async e=>{e.preventDefault();try{await api('/documents/'+f.dataset.photoUpload,'POST',new FormData(f),f);await photosPage(c);message('Foto guardada en la ficha del corredor.');}catch(err){message(err.message);}});}
async function init(){try{if(window.DemoPortal?.active&&!DemoPortal.role){DemoPortal.selector();return;}const fragment=new URLSearchParams(location.hash.slice(1));const token=fragment.get('activar');const data=await api('/me');me=data.user;csrf=data.csrf||'';if(token){await activation(token);history.replaceState(null,'',location.pathname);return;}clothes=data.clothes||[];fineTypes=data.fines||[];if(!me){login();return;}page='home';await navigate(page);}catch(e){login();message(e.message);}}
window.PortalEnhancements?.start(()=>me?.role==='director');
init();
