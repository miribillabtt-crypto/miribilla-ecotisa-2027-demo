'use strict';

const communicationViews = [
 ['photos','Fotos por equipo'],['logos','Logos de patrocinadores'],['calendar','Calendario de publicación'],
];
let editorialCalendar=null;
const editorialColors={occident:'#9c400d',netkom:'#123f9a',surne:'#075488',escuela:'#34363c'};

function closeEditorialCalendar(){
 editorialCalendar?.destroy();
 editorialCalendar=null;
}

let communicationSelection = {view:'dashboard',team:'all',month:''};

function communicationTeams(){
 const teams=me.role==='communication'||me.canInviteCommunication?portalTeams:{[me.team]:teamName(me.team)};
 return ['occident','netkom','surne','escuela'].filter(team=>teams[team]).map(team=>[team,teams[team]]);
}

function openCommunication(view,team){
 communicationSelection={...communicationSelection,view,team};
 return navigate('communication');
}

async function communicationDashboard(content){
 const teams=communicationTeams();
 const {view,team}=communicationSelection;
 if(view==='dashboard'){
  content.innerHTML=`<h1>Comunicación</h1><div class="card scroll">
   <table class="communication-matrix"><thead><tr><th scope="col">Apartado</th>
   ${teams.map(([key,label])=>`<th scope="col" class="communication-${key}">${esc(label)}</th>`).join('')}</tr></thead>
   <tbody>${communicationViews.map(([key,label])=>`<tr><th scope="row">${label}</th>
   ${teams.map(([id,name])=>`<td><button type="button" data-editorial-view="${key}" data-editorial-team="${id}" aria-label="${label} · ${esc(name)}">Abrir</button></td>`).join('')}</tr>`).join('')}</tbody></table>
   </div><div class="toolbar"><button type="button" class="primary" data-editorial-view="calendar" data-editorial-team="all">Calendario · Todos los equipos</button></div>
   ${me.canInviteCommunication?`<details class="card"><summary>Invitar a Comunicación</summary>
    <form id="editorialInvite"><div class="grid">${field('Nombre y apellidos','name')}${field('Correo personal de acceso','email','email')}</div>
    <button type="submit" class="primary">Crear enlace de activación</button></form><div id="editorialInviteResult"></div></details>`:''}`;
  content.querySelectorAll('[data-editorial-view]').forEach(button=>button.onclick=()=>openCommunication(button.dataset.editorialView,button.dataset.editorialTeam));
  bindForm('editorialInvite',async(_,data)=>{
   const result=await api('/communication/invite','POST',data);
   const output=content.querySelector('#editorialInviteResult');
   output.innerHTML=`<p>Comparte este enlace individual. Caduca en 48 horas.</p>
    <input aria-label="Enlace de activación" value="${esc(inviteLink(result.token))}" readonly>
    <button type="button">Copiar enlace</button>`;
   output.querySelector('button').onclick=async()=>{
    const link=output.querySelector('input');
    try{await navigator.clipboard.writeText(link.value);message('Enlace copiado.');}
    catch{link.select();}
   };
  });
  return;
 }
 const title=communicationViews.find(([key])=>key===view)[1];
 content.innerHTML=`<button type="button" id="editorialHome">Volver a Comunicación</button>
  <h1>${title} · ${esc(team==='all'?'Todos los equipos':teamName(team))}</h1>
  <div class="toolbar">${select('Equipo','editorialTeam',view==='calendar'?[['all','Todos los equipos'],...teams]:teams,team)}</div>
  <div id="editorialContent"></div>`;
 content.querySelector('#editorialHome').onclick=()=>openCommunication('dashboard','all');
 content.querySelector('[name=editorialTeam]').onchange=e=>openCommunication(view,e.target.value);
 const host=content.querySelector('#editorialContent');
 if(view==='photos')await communicationPhotos(host,team);
 if(view==='logos')await communicationLogos(host,team);
 if(view==='calendar')await communicationCalendar(host,team,teams);
}

async function communicationPhotos(host,team){
 const {riders}=await api('/communication/photos/'+team);
 const ordered=[...riders].sort((a,b)=>a.name.localeCompare(b.name,'es'));
 const editable=me.role==='communication'||me.team===team;
 host.innerHTML=`<label>Buscar corredor<input id="searchEditorialPhoto" type="search"></label><div id="editorialRiders">
  ${ordered.map(rider=>`<section class="card" data-search-name="${esc(rider.name)}"><h2>${esc(rider.name)}</h2>
   <div class="communication-gallery">${rider.photos.map(photo=>{
    const label=photo.kind==='portrait'?'Retrato':'En bicicleta';
    const url='/api/communication/photo/'+encodeURIComponent(photo.id);
    return `<figure><img src="${url}" alt="${label} de ${esc(rider.name)}" loading="lazy"><figcaption><a href="${url}?download=1">Descargar · ${label}</a></figcaption></figure>`;
   }).join('')||'<p>Sin fotos guardadas.</p>'}</div>
   ${editable?`<details><summary>Subir foto</summary><form id="editorialPhoto-${esc(rider.id)}" class="toolbar">
    ${select('Tipo','kind',[['portrait','Retrato'],['action','En bicicleta']])}
    <label>Imagen<input type="file" name="file" accept="image/*" required></label><button type="submit">Guardar foto</button>
   </form></details>`:''}</section>`).join('')}
  <p data-no-matches>No hay corredores con autorización de imagen para mostrar.</p></div>`;
 bindNameSearch(host.querySelector('#searchEditorialPhoto'),host.querySelector('#editorialRiders'));
 ordered.forEach(rider=>bindForm('editorialPhoto-'+rider.id,async form=>{
  await api('/documents/'+encodeURIComponent(rider.id),'POST',new FormData(form),form);
  await communicationPhotos(host,team);
  message('Foto guardada.');
 }));
}

async function communicationLogos(host,team){
 const {logos}=await api('/communication/logos/'+team);
 host.innerHTML=`<form id="editorialLogo" class="card toolbar">
  ${field('Patrocinador','name')}<label>Logo · PNG, JPG o WEBP<input type="file" name="file" accept="image/png,image/jpeg,image/webp" required></label>
  <button type="submit" class="primary">Subir logo</button></form>
  <div class="communication-gallery">${logos.map(logo=>{
   const id=encodeURIComponent(logo.id),url='/api/communication/logo/'+id;
   return `<figure class="card"><img src="${url}" alt="${esc(logo.name)}" loading="lazy">
    <figcaption><strong>${esc(logo.name)}</strong><div class="toolbar">
    <a href="${url}?download=1">Descargar</a><button type="button" data-logo-remove="${id}">Eliminar</button></div></figcaption></figure>`;
  }).join('')||'<p>Aún no hay logos guardados para este equipo.</p>'}</div>`;
 bindForm('editorialLogo',async form=>{
  await api('/communication/logos/'+team,'POST',new FormData(form));
  await communicationLogos(host,team);message('Logo guardado.');
 });
 host.querySelectorAll('[data-logo-remove]').forEach(button=>button.onclick=async()=>{
  if(!confirm('¿Eliminar este logo del equipo?'))return;
  button.disabled=true;
  try{
   await api('/communication/logo/'+button.dataset.logoRemove,'DELETE');
   await communicationLogos(host,team);message('Logo eliminado.');
  }catch(error){message(error.message);button.disabled=false;}
 });
}

async function communicationCalendar(host,team,teams){
 const {events,plans}=await api('/communication/calendar');
 const visible=row=>team==='all'||row.team===team;
 const initialTeam=team==='all'?teams[0][0]:team;
 if(!host.isConnected)return;
 closeEditorialCalendar();
 const dated=events.filter(row=>visible(row)&&row.date).map(row=>row.date)
  .concat(plans.filter(visible).map(row=>row.date)).sort();
 const currentMonth=calendarDateKey(new Date()).slice(0,7);
 const initialDate=communicationSelection.month?communicationSelection.month+'-01':
  dated.find(day=>day.slice(0,7)>=currentMonth)||dated.at(-1)||currentMonth+'-01';
 host.innerHTML=`<div class="toolbar">
  <button id="editorialNew" type="button" class="primary">Nueva publicación</button>
  <label>Ir a mes<input type="month" id="editorialMonth" value="${esc(initialDate.slice(0,7))}"></label></div>
  <div id="editorialEditor"></div><div id="editorialAgenda" class="card"></div>
  <div id="editorialUndated"></div>`;
 const editor=host.querySelector('#editorialEditor'),month=host.querySelector('#editorialMonth');
 function edit(plan={}){
  editor.innerHTML=`<form class="card" id="editorialPlan"><h2>${plan.id?'Editar publicación':'Nueva publicación'}</h2>
   <div class="grid">${select('Equipo','team',teams,plan.team||initialTeam)}${field('Título','title','text',plan.title)}
    ${field('Fecha de publicación','date','date',plan.date)}${field('Hora','time','time',plan.time)}
    ${select('Estado','status',['Borrador','Programada','Publicada'],plan.status||'Borrador')}
    ${field('Canal','channel','text',plan.channel)}<div id="editorialEventField"></div>
   </div><label>Texto y notas<textarea name="notes" rows="4" maxlength="2000">${esc(plan.notes)}</textarea></label>
   <div class="toolbar"><button type="submit" class="primary">Guardar publicación</button>
    <button type="button" id="editorialCancel">Cancelar</button>
    ${plan.id?'<button type="button" id="editorialDelete">Eliminar publicación</button>':''}</div></form>`;
  const form=editor.querySelector('form');
  form.elements.title.required=true;form.elements.title.maxLength=150;form.elements.date.required=true;form.elements.channel.maxLength=60;
  const eventField=editor.querySelector('#editorialEventField');
  const showEvents=selected=>{
   const options=events.filter(event=>event.team===form.elements.team.value).map(event=>[event.id,event.name+(event.date?' · '+event.date:'')]);
   if(selected&&!options.some(([id])=>id===selected))options.push([selected,'Actividad archivada']);
   eventField.innerHTML=select('Actividad vinculada','event',[['','Sin actividad asociada'],...options],selected);
  };
  showEvents(plan.event||'');
  form.elements.team.onchange=()=>showEvents('');
  editor.querySelector('#editorialCancel').onclick=()=>editor.replaceChildren();
  bindForm(form.id,async(_,data)=>{
   const url='/communication/plans'+(plan.id?'/'+encodeURIComponent(plan.id):'');
   await api(url,plan.id?'PUT':'POST',data);
   await communicationCalendar(host,team,teams);
   message('Publicación guardada.');
  });
  const remove=editor.querySelector('#editorialDelete');
  if(remove)remove.onclick=async()=>{
   if(!confirm('¿Eliminar esta publicación del calendario?'))return;
   remove.disabled=true;
   try{
    await api('/communication/plans/'+encodeURIComponent(plan.id),'DELETE');
    await communicationCalendar(host,team,teams);message('Publicación eliminada.');
   }catch(error){message(error.message);remove.disabled=false;}
  };
  form.elements.title.focus();
 }
 function editActivity(event){
  edit({team:event.team,date:event.date,title:event.name,event:event.id});
 }
 const undated=events.filter(event=>visible(event)&&!event.date);
 if(undated.length){
  const panel=host.querySelector('#editorialUndated');
  panel.innerHTML=`<details class="card"><summary>Actividades con fecha pendiente (${undated.length})</summary>
   ${undated.map(event=>`<div class="row"><span>${esc(teamName(event.team))} · ${esc(event.name)}</span>
    <button type="button" data-editorial-activity="${esc(event.id)}">Planificar publicación</button></div>`).join('')}</details>`;
  panel.querySelectorAll('[data-editorial-activity]').forEach(button=>button.onclick=()=>{
   editActivity(undated.find(event=>event.id===button.dataset.editorialActivity));
  });
 }

 const calendarEvents=[
  ...events.filter(event=>visible(event)&&event.date).map(event=>{
   const end=event.endDate?new Date(event.endDate+'T12:00:00Z'):null;
   if(end)end.setUTCDate(end.getUTCDate()+1);
   return {title:'Actividad · '+teamName(event.team)+' · '+event.name,start:event.date,
    end:end&&!Number.isNaN(end.getTime())?end.toISOString().slice(0,10):undefined,allDay:true,
    color:editorialColors[event.team],extendedProps:{activity:event}};
  }),
  ...plans.filter(visible).map(plan=>({
   title:plan.status+' · '+teamName(plan.team)+' · '+plan.title,
   start:plan.date+(plan.time?'T'+plan.time:''),allDay:!plan.time,
   color:editorialColors[plan.team],extendedProps:{plan},
  })),
 ];
 const calendar=new FullCalendar.Calendar(host.querySelector('#editorialAgenda'),{
  locale:'es',initialDate,initialView:window.matchMedia?.('(max-width: 650px)').matches?'listMonth':'dayGridMonth',
  headerToolbar:{left:'prev,next today',center:'title',right:'dayGridMonth,listMonth'},
  buttonText:{today:'Hoy',month:'Mes',list:'Agenda'},height:'auto',dayMaxEvents:3,events:calendarEvents,
  datesSet(){month.value=communicationSelection.month=calendarDateKey(calendar.getDate()).slice(0,7);},
  eventClick({event}){
   if(event.extendedProps.activity)editActivity(event.extendedProps.activity);
   else edit(event.extendedProps.plan);
  },
  eventDidMount({el}){
   el.tabIndex=0;
   el.addEventListener('keydown',event=>{
    if(event.key==='Enter'||event.key===' '){event.preventDefault();el.click();}
   });
  },
 });
 editorialCalendar=calendar;
 host.querySelector('#editorialNew').onclick=()=>edit();
 month.onchange=()=>{if(month.value)calendar.gotoDate(month.value+'-01');};
 calendar.render();
}
