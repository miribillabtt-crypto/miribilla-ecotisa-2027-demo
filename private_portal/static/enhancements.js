'use strict';
// Read-only table views. Files go only to the existing authenticated API.
window.PortalEnhancements=(()=>{
 const loads=new Map(),grids=new Map();
 function load(name){
  if(!loads.has(name))loads.set(name,new Promise((resolve,reject)=>{
   const script=document.createElement('script');script.src='/static/vendor/'+name+'.js';
   script.onload=resolve;script.onerror=()=>{loads.delete(name);script.remove();reject(Error('No se pudo cargar la mejora. Recarga la página.'));};
   document.head.append(script);
  }));return loads.get(name);
 }
 const safeCsv=value=>/^[\s]*[=+@\-\t\r]/.test(String(value))?"'"+value:value;
 async function enhanceTable(table){
  if(table.dataset.enhanced||table.querySelector('input,select,textarea')||!table.tBodies.length||!table.tBodies[0].rows.length)return;
  table.dataset.enhanced='pending';
  try{
   await load('table');if(!table.isConnected)return;
   const heads=[...table.tHead?.rows[0]?.cells||[]];
   if(!heads.length)return;
   const originalRows=[...table.tBodies[0].rows];
   const interactive=heads.map((head,i)=>/^(Detalle|Acciones|Descarga)$/.test(head.textContent.trim())||originalRows.some(row=>row.cells[i]?.querySelector('button,details')));
   const nodes=originalRows.map(row=>[...row.cells].map(cell=>{const node=document.createElement('div');node.append(...cell.childNodes);return node;}));
   const data=nodes.map((cells,index)=>Object.assign({id:index},Object.fromEntries(cells.map((cell,i)=>['f'+i,cell.textContent.trim()]))));
   const box=document.createElement('section');box.className='data-grid-section';
   const toolbar=document.createElement('div');toolbar.className='toolbar';
   const reset=document.createElement('button');reset.type='button';reset.textContent='Limpiar filtros y orden';
   const download=document.createElement('button');download.type='button';download.textContent='Descargar vista filtrada · CSV';
   const count=document.createElement('small');count.setAttribute('role','status');
   toolbar.append(reset,download,count);const host=document.createElement('div');host.className='portal-data-grid';host.setAttribute('aria-label','Listado con filtros y ordenación');box.append(toolbar,host);table.before(box);
   let grid;
   try{
    grid=new window.PortalTableVendor(host,{data,layout:'fitDataStretch',renderVertical:'basic',placeholder:'Sin registros con estos filtros',columnDefaults:{minWidth:130,headerWordWrap:true,variableHeight:true},columns:heads.map((head,i)=>({title:head.textContent.trim()||'Acciones',field:'f'+i,headerFilter:interactive[i]?false:'input',headerFilterPlaceholder:'Filtrar…',headerSort:!interactive[i],download:!interactive[i],accessorDownload:safeCsv,formatter:cell=>nodes[cell.getRow().getData().id][i]}))});
   }catch(error){originalRows.forEach((row,r)=>[...row.cells].forEach((cell,i)=>cell.append(...nodes[r][i].childNodes)));box.remove();throw error;}
   table.hidden=true;table.dataset.enhanced='ready';grids.set(box,{grid,table});
   const update=()=>{count.textContent=grid.getDataCount('active')+' de '+data.length+' registros';};
   grid.on('tableBuilt',update);grid.on('dataFiltered',(_,rows)=>{count.textContent=rows.length+' de '+data.length+' registros';});
   reset.onclick=()=>{grid.clearHeaderFilter();grid.clearSort();};
   download.onclick=()=>grid.download('csv','Listado_filtrado.csv',{delimiter:';',bom:true},'active');
  }catch(error){table.dataset.enhanced='failed';console.warn('Se conserva el listado original:',error.message);}
 }
 function decorateFiles(root){
  root.querySelectorAll('input[type=file]').forEach(input=>{
   if(input.dataset.filePicker||!input.accept.includes('image'))return;
   input.dataset.filePicker='true';
   const info=document.createElement('small');info.className='file-selection';info.setAttribute('role','status');input.after(info);
   const display=()=>{const file=input.files[0];info.textContent=file?file.name+' · '+(file.size/1024/1024).toFixed(2)+' MB · Pendiente de guardar':'Sin archivo seleccionado';};
   input.addEventListener('change',display);input.form?.addEventListener('reset',()=>setTimeout(display,0));display();
   // A separate camera input leaves the ordinary file picker available.
   const camera=document.createElement('input');camera.type='file';camera.dataset.filePicker='true';camera.accept='image/*';camera.capture='environment';camera.hidden=true;
   const button=document.createElement('button');button.type='button';button.className='camera-pick';button.textContent='Hacer foto';button.onclick=()=>camera.click();
   camera.onchange=()=>{if(!camera.files.length)return;try{input.files=camera.files;input.dispatchEvent(new Event('change',{bubbles:true}));}catch{info.textContent='Selecciona la foto con el selector de archivos.';}};
   input.parentElement.after(button,camera);
  });
 }
 function start(isDirector){
  let queued=false;
  const scan=()=>{queued=false;for(const [box,{grid,table}] of grids)if(!box.isConnected){grid.destroy();grids.delete(box);if(table.isConnected){table.hidden=false;delete table.dataset.enhanced;}}
   const content=document.getElementById('content');if(!content)return;decorateFiles(content);
   if(isDirector())content.querySelectorAll('#moduleRows table, #clothesSummary table').forEach(enhanceTable);
  };
  new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(scan);}}).observe(document.getElementById('app'),{childList:true,subtree:true});scan();
 }
 async function upload(path,data,token,form){
  const file=data.get('file');if(!(file instanceof Blob))throw Error('Selecciona un archivo antes de guardar.');
  const mount=form||document.getElementById('notice');
  let status=mount.querySelector('.upload-status');if(!status){status=document.createElement('div');status.className='upload-status';status.setAttribute('role','status');mount.append(status);}
  const label=document.createElement('span'),progress=document.createElement('progress');progress.max=100;progress.value=0;progress.setAttribute('aria-label','Progreso de subida');status.replaceChildren(label,progress);label.textContent='Preparando archivo…';
  let uppy,serverError;
  try{
   await load('upload');const {Uppy,XHRUpload}=window.PortalUploadVendor;
   const meta=Object.fromEntries([...data].filter(([key,value])=>key!=='file'&&typeof value==='string'));
   uppy=new Uppy({autoProceed:false,restrictions:{maxNumberOfFiles:1},allowMultipleUploadBatches:false});
   uppy.use(XHRUpload,{endpoint:path,method:'POST',fieldName:'file',formData:true,allowedMetaFields:Object.keys(meta),headers:{'X-CSRF-Token':token},withCredentials:true,shouldRetry:()=>false,timeout:60000,onAfterResponse:xhr=>{if(xhr.status>=400){let error;try{error=JSON.parse(xhr.responseText).error;}catch{}serverError=error;throw Error(error||'No se pudo guardar el archivo. Comprueba la conexión antes de volver a intentarlo.');}}});
   uppy.on('upload-progress',(_,p)=>{const n=p.bytesTotal?Math.round(p.bytesUploaded/p.bytesTotal*100):0;progress.value=n;label.textContent=n===100?'Archivo enviado. Confirmando guardado…':'Subiendo archivo · '+n+' %';});
   uppy.addFile({name:file.name||'documento',type:file.type,data:file,meta});
   const result=await uppy.upload();if(result.failed?.length)throw Error(serverError||'No se pudo confirmar el guardado. Comprueba la conexión y los archivos registrados antes de reintentar.');
   if(!result.successful?.length)throw Error('No se ha enviado el archivo.');
   progress.value=100;label.textContent='Archivo guardado correctamente.';return result.successful[0].response.body;
  }catch(error){label.textContent=error.message||'Error al subir el archivo. Revisa los archivos registrados antes de reintentar.';throw error;}
  finally{uppy?.destroy();}
 }
 return {start,upload,safeCsv};
})();
