"""Exact original invoice files, encrypted and bound to a CONTA entry."""
import io,time,hashlib
from flask import request,g,jsonify,abort,send_file
from sqlalchemy import select,func
from werkzeug.utils import secure_filename
from PIL import Image

def register_invoices(app,Record,Document,cipher,seal,unseal,audit,require):
 def entry_or_404(entry_id):
  r=g.db.get(Record,entry_id)
  if not r or r.kind!='module:entry':abort(404,'Apunte CONTA no encontrado')
  return r
 @app.get('/api/invoices/<entry_id>')
 @require('director')
 def invoice_list(entry_id):
  entry_or_404(entry_id);out=[]
  for d in g.db.scalars(select(Document).where(Document.kind=='invoice:'+entry_id)):
   meta=g.db.get(Record,'invoice-meta-'+d.id);data=unseal(meta.data) if meta else {}
   out.append(dict(id=d.id,name=data.get('filename','factura'),size=d.size,created=d.created,sha256=data.get('sha256','')))
  return jsonify(files=out)
 @app.post('/api/invoices/<entry_id>')
 @require('director')
 def invoice_upload(entry_id):
  entry_or_404(entry_id);f=request.files.get('file')
  if not f:abort(400,'Selecciona el original')
  raw=f.read(4*1024*1024+1)
  if not raw or len(raw)>4*1024*1024:abort(400,'El original debe ocupar como máximo 4 MB')
  if raw.startswith(b'%PDF-'):
   if b'%%EOF' not in raw[-65536:]:abort(400,'El PDF parece incompleto')
   mime='application/pdf';extension='.pdf'
  else:
   try:
    im=Image.open(io.BytesIO(raw))
    if im.format not in ('JPEG','PNG','WEBP') or im.width*im.height>20_000_000:abort(400,'Imagen no admitida')
    fmt=im.format;im.verify();mime={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}[fmt];extension={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt]
   except Exception:abort(400,'Usa un PDF o foto JPG, PNG o WEBP válida')
  sha=hashlib.sha256(raw).hexdigest()
  for old in g.db.scalars(select(Document).where(Document.kind=='invoice:'+entry_id)):
   meta=g.db.get(Record,'invoice-meta-'+old.id)
   if meta and unseal(meta.data).get('sha256')==sha:return jsonify(id=old.id,duplicate=True)
  total=g.db.scalar(select(func.coalesce(func.sum(Document.size),0)))
  if total+len(raw)>400*1024*1024:abort(400,'Almacenamiento completo. Contacta con Dirección.')
  name=secure_filename(f.filename or 'factura')[:150]
  if not name.lower().endswith(extension) and not (extension=='.jpg' and name.lower().endswith('.jpeg')):name+=extension
  d=Document(owner_id=g.user.id,kind='invoice:'+entry_id,size=len(raw),mime=mime,created=int(time.time()),content=cipher.encrypt(raw));g.db.add(d);g.db.flush()
  g.db.add(Record(id='invoice-meta-'+d.id,kind='invoice-metadata',owner_id=entry_id,data=seal(dict(filename=name,sha256=sha))))
  audit('invoice_original_uploaded',d.id);return jsonify(id=d.id,duplicate=False)
 @app.get('/api/invoice-file/<file_id>')
 @require('director')
 def invoice_download(file_id):
  d=g.db.get(Document,file_id)
  if not d or not d.kind.startswith('invoice:'):abort(404)
  meta=g.db.get(Record,'invoice-meta-'+d.id);data=unseal(meta.data) if meta else {}
  audit('invoice_original_downloaded',d.id)
  return send_file(io.BytesIO(cipher.decrypt(d.content)),mimetype=d.mime,as_attachment=True,download_name=data.get('filename','factura'))
