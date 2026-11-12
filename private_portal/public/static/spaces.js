'use strict';

async function spaceReservationsPage(content, selectedDate=''){
 const data=await api('/space-reservations'+(selectedDate?'?date='+encodeURIComponent(selectedDate):''));
 content.innerHTML=`<h1>Reservas de espacios</h1>
  <label>Consultar día <input id="spaceReservationDay" type="date" value="${esc(data.date)}"></label>
  <div class="grid">${data.spaces.map(space=>{
   const bookings=data.reservations.filter(item=>item.space===space);
   return `<section class="card"><h2>${esc(space)}</h2>
    ${bookings.length?bookings.map(item=>`<div class="row">
     <span><strong>${esc(item.start)}–${esc(item.end)}</strong> · ${esc(teamName(item.team))}<br>${esc(item.title)}</span>
     ${item.canCancel?`<button type="button" data-cancel-space="${esc(item.id)}">Cancelar reserva</button>`:''}
    </div>`).join(''):'<p>Sin reservas para este día.</p>'}
    <button type="button" data-reserve-space="${esc(space)}">Reservar ${esc(space)}</button>
   </section>`;
  }).join('')}</div>
  <form id="spaceReservationForm" class="card" hidden>
   <h2>Nueva reserva</h2>
   <div class="grid">
    ${select('Espacio','space',data.spaces)}
    <label>Fecha<input name="date" type="date" value="${esc(data.date)}" required></label>
    <label>Inicio<input name="start" type="time" required></label>
    <label>Fin<input name="end" type="time" required></label>
    <label>Motivo<input name="title" maxlength="120" required></label>
   </div>
   <button type="submit" class="primary">Guardar reserva</button>
  </form>`;
 const day=content.querySelector('#spaceReservationDay');
 day.onchange=()=>spaceReservationsPage(content,day.value).catch(error=>message(error.message));
 const form=content.querySelector('#spaceReservationForm');
 content.querySelectorAll('[data-reserve-space]').forEach(button=>button.onclick=()=>{
  form.elements.space.value=button.dataset.reserveSpace;
  form.hidden=false;
  form.scrollIntoView({block:'nearest'});
  form.elements.start.focus();
 });
 content.querySelectorAll('[data-cancel-space]').forEach(button=>button.onclick=async()=>{
  if(!confirm('¿Cancelar esta reserva?'))return;
  button.disabled=true;
  try{
   await api('/space-reservations/'+encodeURIComponent(button.dataset.cancelSpace),'DELETE');
   await spaceReservationsPage(content,data.date);
   message('Reserva cancelada.');
  }catch(error){message(error.message);button.disabled=false;}
 });
 bindForm('spaceReservationForm',async(_,values)=>{
  await api('/space-reservations','POST',values);
  await spaceReservationsPage(content,values.date);
  message('Reserva guardada para los dos equipos.');
 });
}

featureViews.spaces=spaceReservationsPage;
