'use strict';
window.DemoPortal=(()=>{
 const key='miribilla-demo-role';
 let active=false,role=null,state;
 const garments=['Maillot corto','Maillot largo','Culote corto','Culote largo','Gava','Buzo','Chaleco','Pantalón largo','Pantalón corto','Camiseta','Polo','Sudadera','Plumas'];
 const people=[
  {id:'demo-director',name:'Dirección Demo',role:'director',owner:true,documents:true,email:'direccion.demo',active:true,accountReady:true},
  {id:'demo-runner',name:'Corredor Demo',role:'runner',owner:false,documents:false,email:'corredor.demo',active:true,accountReady:true},
  {id:'demo-runner2',name:'Segundo Corredor Demo',role:'runner',owner:false,documents:false,email:'corredor2.demo',active:true,accountReady:true},
  {id:'demo-technician',name:'Técnico Demo',role:'technician',owner:false,documents:false,email:'tecnico.demo',active:true,accountReady:true},
  {id:'demo-communication',name:'Comunicación Demo',role:'communication',owner:false,documents:false,email:'comunicacion.demo',active:true,accountReady:true},
 ];
 const current=()=>people.find(person=>person.role===role);
 const copy=value=>JSON.parse(JSON.stringify(value));
 function reset(){
  state={
   events:[
    {id:'demo-race',name:'Carrera de demostración',date:'2027-02-27',endDate:'2027-02-28',place:'Localidad de ejemplo',called:['demo-runner'],callStatus:'Publicada'},
    {id:'demo-camp',name:'Concentración de demostración',date:'2027-03-05',endDate:'2027-03-07',place:'Sede de ejemplo',called:['demo-runner'],callStatus:'Borrador'},
    {id:'demo-training',name:'Entrenamiento de equipo',date:'2027-03-13',place:'Punto de encuentro de ejemplo',called:[],callStatus:'Borrador'},
   ],
   answers:{'demo-race':{'demo-runner':'Disponible','demo-runner2':'Disponible'},'demo-camp':{'demo-runner':'Disponible'}},
   profiles:Object.fromEntries(people.filter(person=>person.role==='runner').map(person=>[person.id,{firstName:person.id==='demo-runner'?'Corredor':'Segundo',surname:'Demo',bike:'Bicicleta de ejemplo',bikeSize:'S',saddleHeight:'720',saddleToBar:'510',sizes:Object.fromEntries(garments.map(item=>[item,'S'])),quantities:Object.fromEntries(garments.map(item=>[item,item==='Camiseta'?2:1])),photoConsent:true}])),
   modules:{
    staff:[{id:'demo-staff',name:'Técnico Demo',function:'Mecánico',city:'Ciudad de ejemplo',user:'demo-technician'}],
    vehicle:[{id:'demo-vehicle',name:'Furgoneta Demo',plate:'DEMO',seats:9}],
    travel:[{id:'demo-trip',event:'demo-race',hotel:'Hotel de demostración',hotelAddress:'Dirección de ejemplo',staff:['demo-staff'],vehicles:['demo-vehicle'],manager:'Dirección Demo',plan:'Plan de viaje de ejemplo'}],
    sport:[{id:'demo-bike',rider:'demo-runner',bike:'Bicicleta de ejemplo',bikeSize:'S',saddleHeight:720,saddleToBar:510}],
    entry:[{id:'demo-expense',event:'demo-race',direction:'Gasto',amount:12000,date:'2027-02-27',category:'Alojamiento',concept:'Hotel de ejemplo',counterparty:'Proveedor Demo',status:'Pagado',attachments:[],splitRecorded:false}],
    budget:[{id:'demo-budget',category:'Alojamiento',amount:200000,spent:12000}],
    charge:[{id:'demo-charge',rider:'demo-runner',event:'demo-race',concept:'Desplazamiento de ejemplo',amount:6000,status:'Pendiente',notes:'Dato ficticio'}],
    license:people.filter(person=>person.role==='runner').map((person,index)=>({id:'demo-license-'+index,rider:person.id,number:'DEMO-'+index,status:'Pendiente de revisión',photos:{}})),
    result:[{id:'demo-result',rider:'demo-runner',event:'demo-race',place:12,days:2,discipline:'Carretera'}],
    days:[{id:'demo-days',person:'demo-runner',event:'demo-race',days:2,function:'Corredor'}],
    bank:[],post:[],
   },
   orders:[],fines:[{id:'demo-fine',user:'demo-runner',date:'2027-02-27',reason:'Ejemplo de multa',amount:5,status:'Pendiente'}],
  };
 }
 function start(password){
  if(password!=='1234')throw Error('La contraseña de la demo es 1234');
  active=true;role=null;reset();sessionStorage.setItem(key,'choose');
 }
 function stop(){active=false;role=null;state=null;sessionStorage.removeItem(key);}
 function restore(){
  const saved=sessionStorage.getItem(key);
  if(saved){active=true;role=people.some(person=>person.role===saved)?saved:null;reset();}
 }
 function selector(){
  app.innerHTML=`<main class="auth"><h1>Elige un panel de demostración</h1>
   <p>Datos ficticios. Puedes cambiar de perfil y probar las pantallas. Los cambios de prueba se reinician al recargar.</p>
   <div class="grid">${Object.entries(roles).map(([value,label])=>`<button type="button" class="tile" data-demo-role="${value}">${label}</button>`).join('')}</div>
   <button type="button" id="exitDemo">Salir de la demo</button></main>`;
  app.querySelectorAll('[data-demo-role]').forEach(button=>button.onclick=async()=>{
   role=button.dataset.demoRole;sessionStorage.setItem(key,role);quickInvoiceFile=null;calendarMonth='';await init();
  });
  app.querySelector('#exitDemo').onclick=()=>{stop();me=null;login();};
 }
 function banner(){
  if(!active)return;
  const bar=document.createElement('div');bar.className='demo-banner';
  bar.innerHTML='<strong>DEMOSTRACIÓN · Datos ficticios</strong><button type="button">Cambiar de panel</button>';
  bar.querySelector('button').onclick=selector;
  app.prepend(bar);
 }
 function downloadMessage(){message('Descarga de demostración. Los documentos reales se gestionan desde una cuenta del equipo.');}
 new MutationObserver(()=>{
  if(!active)return;
  document.querySelectorAll('#app a[href]').forEach(anchor=>{
   if(new URL(anchor.href,location.href).pathname.startsWith('/api/')){
    anchor.dataset.demoDownload='true';anchor.href='#demo-download';
   }
  });
  document.querySelectorAll('#app form[method=get], #app [formaction]').forEach(element=>{
   const attribute=element.tagName==='FORM'?'action':'formaction';
   if(new URL(element.getAttribute(attribute)||location.href,location.href).pathname.startsWith('/api/')){
    element.dataset.demoDownload='true';element.setAttribute(attribute,'#demo-download');
   }
  });
 }).observe(document.documentElement,{childList:true,subtree:true});
 document.addEventListener('click',event=>{
  if(!active)return;
  const anchor=event.target.closest('a[href]');
  if(anchor&&(anchor.dataset.demoDownload||new URL(anchor.href,location.href).pathname.startsWith('/api/'))){
   event.preventDefault();event.stopImmediatePropagation();downloadMessage();
  }
 },true);
 document.addEventListener('submit',event=>{
  if(active&&event.target.method.toLowerCase()==='get'&&(event.target.dataset.demoDownload||event.submitter?.dataset.demoDownload||new URL(event.submitter?.formAction||event.target.action,location.href).pathname.startsWith('/api/'))){
   event.preventDefault();event.stopImmediatePropagation();downloadMessage();
  }
 },true);
 async function request(path,method='GET',data={}){
  if(!active||!role)throw Error('Elige un panel de demostración');
  const user=current(),url=new URL(path,'https://demo.invalid');
  const parts=url.pathname.split('/').filter(Boolean);
  const id=()=>crypto.randomUUID();
  if(method==='GET'){
   if(path==='/me')return copy({user,csrf:'demo',clothes:garments,fines:[['Falta de respeto leve',5],['Material mal estado',5],['Otras',10]]});
   if(path==='/summary')return {riders:2,events:state.events.length,staff:1,vehicles:1,income:0,expenses:12000};
   if(path==='/events')return copy({events:state.events.map(event=>({...event,myStatus:state.answers[event.id]?.[user.id]||'Por confirmar',responses:state.answers[event.id]||{}}))});
   if(path==='/roster')return copy({riders:people.filter(person=>person.role==='runner'&&(role!=='runner'||person.id===user.id)).map(({id,name})=>({id,name}))});
   if(path==='/users'||path==='/people')return copy(path==='/users'?{users:people}:{people});
   if(parts[0]==='profile')return copy({profile:state.profiles[parts[1]]||{}});
   if(parts[0]==='documents')return {documents:[]};
   if(path==='/clothes/mine')return copy(state.profiles[user.id]||{sizes:{},quantities:{}});
   if(path==='/clothes')return copy({riders:people.filter(person=>person.role==='runner').map(person=>({...person,...state.profiles[person.id]}))});
   if(parts[0]==='modules'){
    let records=state.modules[parts[1]]||[];
    if(role==='runner'&&['charge','license','sport','result'].includes(parts[1]))records=records.filter(record=>record.rider===user.id);
    if(url.searchParams.get('event'))records=records.filter(record=>record.event===url.searchParams.get('event'));
    return copy({records});
   }
   if(path==='/shop')return copy({products:garments.map(name=>({name,price:2000})),orders:state.orders.filter(order=>role!=='runner'||order.rider===user.id),director:'demo-director',directors:[people[0]]});
   if(path==='/fines')return copy({fines:state.fines.filter(fine=>role!=='runner'||fine.user===user.id)});
   if(path==='/accounts'){
    const riders=people.filter(person=>person.role==='runner'&&(role!=='runner'||person.id===user.id)).map(person=>{
     const row={id:person.id,name:person.name,clothes:0,races:0,fines:0,other:0,total:0,paid:0,pending:0};
     for(const charge of state.modules.charge.filter(item=>item.rider===person.id&&item.status!=='Anulado')){
      row[charge.concept?.includes('ropa')?'clothes':charge.event?'races':'other']+=charge.amount;
      row.total+=charge.amount;row[charge.status==='Pagado'?'paid':'pending']+=charge.amount;
     }
     for(const fine of state.fines.filter(item=>item.user===person.id&&item.status!=='Anulada')){
      if(typeof fine.amount!=='number')continue;
      row.fines+=fine.amount*100;row.total+=fine.amount*100;row[fine.status==='Pagada'?'paid':'pending']+=fine.amount*100;
     }
     return row;
    });
    const totals=Object.fromEntries(['clothes','races','fines','other','total','paid','pending'].map(field=>[field,riders.reduce((sum,row)=>sum+row[field],0)]));
    return {riders,totals};
   }
   if(path==='/audit')return {entries:[]};
   if(path==='/archive'||path==='/resource-availability')return {records:[]};
   if(path==='/bank/reconciliation')return {movements:[]};
   if(path==='/media/roster')return copy({riders:people.filter(person=>person.role==='runner').map(({id,name})=>({id,name,photos:[]}))});
   if(parts[2]==='hotel')return {guests:[]};
   throw Error('Esta pantalla no tiene más datos de ejemplo.');
  }
  if(path==='/logout'){stop();return {ok:true};}
  if(parts[0]==='profile'){Object.assign(state.profiles[parts[1]],data);return {ok:true};}
  if(path==='/events'){const event={...data,id:id(),called:[],callStatus:'Borrador'};state.events.push(event);return {ok:true};}
  if(parts[0]==='events'){
   const event=state.events.find(item=>item.id===parts[1]);
   if(!event)throw Error('Actividad de ejemplo no encontrada');
   if(parts[2]==='availability'){state.answers[event.id]??={};state.answers[event.id][user.id]=data.status;}
   else if(parts[2]==='details')Object.assign(event,data);
   else if(parts[2]==='call')event.called=data.users;
   else if(parts[2]==='split-expenses'){
    const total=data.expenses.reduce((sum,expense)=>sum+(state.modules.entry.find(row=>row.id===expense)?.amount||0),0);
    data.expenses.forEach(expense=>{state.modules.entry.find(row=>row.id===expense).splitRecorded=true;});
    return {total,riders:event.called.length};
   }
   return {ok:true};
  }
  if(parts[0]==='modules'){
   const records=state.modules[parts[1]]??=[];
   const existing=records.find(record=>record.id===parts[2]);
   if(parts[3]==='archive'){state.modules[parts[1]]=records.filter(record=>record!==existing);return {ok:true};}
   if(existing){Object.assign(existing,data);return {ok:true};}
   const record={...data,id:id()};records.push(record);return {id:record.id};
  }
  if(path==='/shop/orders'){
   const previous=state.orders.find(order=>order.token===data.token);
   if(previous)return copy(previous);
   const order={...data,id:id(),rider:user.id,name:user.name,created:new Date().toISOString(),paymentStatus:'Pendiente',emailStatus:'Demostración',items:data.items.map(item=>({...item,price:2000}))};
   state.orders.push(order);
   state.modules.charge.push({id:id(),rider:user.id,event:'',concept:'Compra de ropa',amount:order.amount,status:'Pendiente',notes:'Pedido '+order.id});
   return copy(order);
  }
  if(path==='/fines'){state.fines.push({id:id(),user:data.user,reason:'Multa de demostración',amount:5,date:'2027-02-27',status:'Pendiente'});return {ok:true};}
  if(parts[0]==='fines'){Object.assign(state.fines.find(fine=>fine.id===parts[1]),data);return {ok:true};}
  throw Error('Acción de demostración. Puedes consultar los paneles y editar los datos de ejemplo.');
 }
 restore();
 return {get active(){return active;},get role(){return role;},start,stop,selector,banner,request,downloadMessage};
})();
