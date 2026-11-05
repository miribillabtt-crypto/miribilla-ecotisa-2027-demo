'use strict';
window.IdentityOCR=(()=>{
 const normalize=value=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toUpperCase();
 function validDate(year,month,day){
  const iso=year+'-'+month+'-'+day;
  const date=new Date(iso+'T00:00:00Z');
  return Number.isFinite(date.valueOf())&&date.toISOString().slice(0,10)===iso&&date<=new Date()?iso:'';
 }
 function calendarDate(text){
  const match=text.match(/\b(\d{2})[./-](\d{2})[./-]((?:19|20)\d{2})\b/);
  return match?validDate(match[3],match[2],match[1]):'';
 }
 function checkDigit(text){
  const weights=[7,3,1];
  return String([...text].reduce((sum,char,index)=>sum+(char==='<'?0:parseInt(char,36))*weights[index%3],0)%10);
 }
 function parse(raw){
  const lines=String(raw||'').split(/[\r\n]+/).map(line=>line.replace(/\s+/g,' ').trim()).filter(Boolean);
  const result={};
  const labels=/\b(?:APELLIDOS?|SURNAME|NOMBRE|GIVEN NAMES?|NACIMIENTO|BIRTH|DOMICILIO|ADDRESS|SEXO|SEX|NACIONALIDAD|NATIONALITY|VALIDEZ|EXPIRY|HIJO|PADRES|LUGAR|BIRTHPLACE|DNI|DOCUMENTO|SOPORTE|CAN|FIRMA|SIGNATURE|ESPANA)\b/;
  function labeled(pattern,maxLines=1){
   const start=lines.findIndex(line=>pattern.test(normalize(line)));
   if(start<0)return '';
   const normalized=normalize(lines[start]);
   const match=normalized.match(pattern);
   let rest=lines[start].slice(match.index+match[0].length).replace(/^[\s/:.-]+/,'').trim();
   const translations=['SURNAME','SURNAMES','GIVEN NAME','GIVEN NAMES','NAME','NAMES','NOM','COGNOM','COGNOMS','ABIZENAK','IZENA'];
   if(rest.split('/').every(value=>translations.includes(normalize(value.trim()))))rest='';
   if(rest&&!labels.test(normalize(rest))&&!/[<>\d]/.test(rest))return rest;
   const values=[];
   for(const line of lines.slice(start+1,start+1+maxLines)){
    if(labels.test(normalize(line))||/[<>\d]/.test(line))break;
    values.push(line);
   }
   return values.join(' ');
  }
  const firstName=labeled(/\b(?:NOMBRE(?:\s*\/\s*GIVEN NAMES?)?|GIVEN NAMES?)\b/);
  const surname=labeled(/\b(?:APELLIDOS?(?:\s*\/\s*SURNAME)?|SURNAME)\b/,2);
  if(firstName)result.firstName=firstName;
  if(surname)result.surname=surname;
  const birthLine=lines.findIndex(line=>/\b(?:NACIMIENTO|BIRTH)\b/.test(normalize(line)));
  if(birthLine>=0){
   const birth=calendarDate(lines.slice(birthLine,birthLine+2).join(' '));
   if(birth)result.birth=birth;
  }
  const text=normalize(lines.join('\n'));
  const candidates=[...text.matchAll(/\b(\d{8})[ -]?([A-Z])\b/g)];
  const dnis=[...new Set(candidates.filter(match=>'TRWAGMYFPDXBNJZSQVHLCKE'[Number(match[1])%23]===match[2]).map(match=>match[1]+match[2]))];
  if(dnis.length===1)result.dni=dnis[0];
  const mrz=lines.map(line=>normalize(line).replace(/\s/g,''));
  const mrzIndex=mrz.findIndex(line=>/^IDESP[A-Z0-9<]{25}$/.test(line));
  if(mrzIndex>=0&&mrz[mrzIndex+1]?.length===30){
   const dates=mrz[mrzIndex+1],birth=dates.slice(0,6);
   if(/^\d{6}$/.test(birth)&&checkDigit(birth)===dates[6]){
    const yy=Number(birth.slice(0,2));
    const current=new Date().getFullYear()%100;
    const date=validDate(String((yy<=current?2000:1900)+yy),birth.slice(2,4),birth.slice(4,6));
    if(date&&!result.birth)result.birth=date;
   }
   const names=mrz[mrzIndex+2];
   if(names?.length===30&&/^[A-Z<]+$/.test(names)&&names.endsWith('<')){
    const [family,given]=names.split('<<');
    if(family&&given){
     if(!result.surname)result.surname=family.replace(/</g,' ').trim();
     if(!result.firstName)result.firstName=given.replace(/</g,' ').trim();
    }
   }
  }
  if(result.birth)result.birthYear=result.birth.slice(0,4);
  const addressIndex=lines.findIndex(line=>/\b(?:DOMICILIO|ADDRESS)\b/.test(normalize(line)));
  if(addressIndex>=0){
   const parts=[];
   const heading=lines[addressIndex];
   const inline=heading.replace(/^.*?(?:DOMICILIO|ADDRESS)(?:\s*\/\s*ADDRESS)?\s*[:.-]?/i,'').trim();
   if(inline&&!labels.test(normalize(inline)))parts.push(inline);
   for(const line of lines.slice(addressIndex+1,addressIndex+4)){
    if(labels.test(normalize(line))||/[<]/.test(line))break;
    parts.push(line);
   }
   if(parts.length)result.address=parts.join(', ').slice(0,250);
  }
  return result;
 }
 return {parse};
})();

function addIdentityOCR(upload,profile){
 const controls=document.createElement('section');
 controls.innerHTML='<h3>Escanear DNI y completar datos</h3><p>Selecciona el anverso o reverso del DNI. La lectura propone nombre, apellidos, DNI, nacimiento y dirección cuando sean legibles.</p><button type="button" id="readIdentity">Volver a leer el DNI</button><button type="button" id="cancelIdentity" hidden>Cancelar</button><p id="identityProgress" role="status"></p><div id="identityResult"></div>';
 upload.querySelector('h2').after(controls);
 let current=null,sequence=0;
 const button=controls.querySelector('#readIdentity');
 const cancel=controls.querySelector('#cancelIdentity');
 const status=controls.querySelector('#identityProgress');
 const output=controls.querySelector('#identityResult');
 const run=async()=>{
  const kind=upload.elements.kind.value,file=upload.elements.file.files[0];
  if(!['dni','dni_reverso'].includes(kind)){status.textContent='Selecciona DNI anverso o reverso para completar la ficha.';return;}
  if(!file){status.textContent='Selecciona una foto o PDF del DNI.';return;}
  if(current)current.cancelled=true;
  const attempt=++sequence,control={documentType:'identity'};
  current=control;button.disabled=true;cancel.hidden=false;status.textContent='Preparando documento…';output.textContent='';
  try{
   const prepared=await prepareIdentityFile(file);
   const reading=await InvoiceOCR.read(prepared,text=>{if(attempt===sequence&&controls.isConnected)status.textContent=text;},control);
   if(control.cancelled||attempt!==sequence||!controls.isConnected)return;
   const fields=IdentityOCR.parse(reading.text);
   let count=0;
   for(const [key,value] of Object.entries(fields)){
    if(value&&profile.elements[key]){
     profile.elements[key].value=value;count++;
    }
   }
   if(fields.dni&&profile.elements.dniStatus)profile.elements.dniStatus.value='Leído por OCR · pendiente de revisión';
   output.innerHTML=count?'<p class="note">Datos completados. Revisa los campos y pulsa Guardar ficha para confirmarlos.</p>':'<p>No se han detectado datos fiables. Prueba otra foto con buena luz o completa los campos manualmente.</p>';
   status.textContent='Lectura terminada.';
  }catch(err){
   if(attempt===sequence&&!control.cancelled)status.textContent=err.message;
  }finally{
   if(attempt===sequence){button.disabled=false;cancel.hidden=true;}
  }
 };
 button.onclick=run;
 upload.elements.file.onchange=run;
 upload.elements.kind.onchange=()=>{
  if(current)current.cancelled=true;
  sequence++;button.disabled=false;cancel.hidden=true;status.textContent='';output.textContent='';
  if(['dni','dni_reverso'].includes(upload.elements.kind.value)&&upload.elements.file.files[0])run();
 };
 cancel.onclick=()=>{if(current)current.cancelled=true;status.textContent='Lectura cancelada.';};
}
