"""Private PDF compilation of existing guest identity images."""
import io
import time
from flask import g, jsonify, request, abort, send_file
from sqlalchemy import select, func
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError


def register_hotel_documents(app, Record, Document, hotel_people, audit, require):
    cipher = app.extensions['cipher']

    def documents(guest):
        if guest['role'] == 'Corredor':
            query = select(Document).where(Document.owner_id == guest['id'],
                                           Document.kind.in_(['dni','dni_reverso']))
        else:
            query = select(Document).where(Document.kind.in_([
                'staff-dni:'+guest['id']+':front', 'staff-dni:'+guest['id']+':back']))
        rows = list(g.db.scalars(query.order_by(Document.created.desc(), Document.id.desc())))
        latest = {}
        for row in rows:
            latest.setdefault(row.kind, row)
        return list(latest.values())

    @app.post('/api/events/<event_id>/hotel/staff/<staff_id>/photo')
    @require('director')
    def staff_photo(event_id, staff_id):
        _, guests = hotel_people(event_id)
        if not any(guest['id'] == staff_id and guest['role'] == 'Técnico' for guest in guests):
            abort(404)
        side = request.form.get('side')
        upload = request.files.get('file')
        if side not in ('front','back') or not upload:
            abort(400, 'Selecciona la cara del DNI y una imagen')
        raw = upload.read(3*1024*1024+1)
        if not raw or len(raw) > 3*1024*1024:
            abort(400, 'Máximo 3 MB por imagen')
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG','PNG') or image.width*image.height > 20_000_000:
                    abort(400, 'Usa una imagen JPG o PNG')
                prepared = ImageOps.exif_transpose(image).convert('RGB')
                output = io.BytesIO()
                prepared.save(output, format='JPEG', quality=90)
                raw = output.getvalue()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            abort(400, 'Imagen no válida')
        total = g.db.scalar(select(func.coalesce(func.sum(Document.size), 0)))
        if total+len(raw) > 400*1024*1024:
            abort(400, 'Almacenamiento completo')
        g.db.add(Document(owner_id=g.user.id, kind='staff-dni:'+staff_id+':'+side,
                          size=len(raw), mime='image/jpeg', created=int(time.time()),
                          content=cipher.encrypt(raw)))
        audit('staff_identity_photo_uploaded', staff_id)
        return jsonify(ok=True)

    @app.get('/api/events/<event_id>/hotel/identity-pdf')
    @require('director')
    def identity_pdf(event_id):
        event, guests = hotel_people(event_id)
        if event.get('callStatus') != 'Publicada' or not guests:
            abort(400, 'Publica la convocatoria antes de descargar el PDF')
        font = ImageFont.load_default(size=23)
        pages = []
        sequence = []
        try:
            for guest in guests:
                scans = documents(guest)
                for document in scans or [None]:
                    page = Image.new('RGB', (1000,1414), 'white')
                    draw = ImageDraw.Draw(page)
                    draw.text((45,35), 'Documentación privada del equipo', fill='black', font=font)
                    name_lines = []
                    for word in guest['name'].split():
                        candidate = (name_lines[-1]+' '+word) if name_lines else word
                        if name_lines and draw.textlength(candidate,font=font) < 900:
                            name_lines[-1] = candidate
                        else:
                            name_lines.append(word)
                    y = 85
                    for line in name_lines:
                        draw.text((45,y), line, fill='black', font=font)
                        y += 32
                    draw.text((45,y), guest['role'], fill='black', font=font)
                    y += 55
                    if document:
                        side='Reverso' if document.kind=='dni_reverso' or document.kind.endswith(':back') else 'Anverso'
                        draw.text((45,y), side, fill='black', font=font)
                        y += 40
                        if len(scans)==1:
                            draw.text((45,1330), 'Solo consta una cara del DNI', fill='black', font=font)
                        raw=cipher.decrypt(document.content)
                        if document.mime=='application/pdf':
                            draw.text((45,y), 'Documento PDF adjunto en las páginas siguientes', fill='black', font=font)
                        else:
                            with Image.open(io.BytesIO(raw)) as original:
                                scan = ImageOps.exif_transpose(original).convert('RGB')
                                scan.thumbnail((910,1200-y))
                                page.paste(scan, ((1000-scan.width)//2,y))
                                scan.close()
                    else:
                        draw.text((45,y), 'DNI escaneado pendiente', fill='black', font=font)
                    pages.append(page)
                    sequence.append(page)
                    if document and document.mime=='application/pdf':
                        sequence.append(raw)
            stream = io.BytesIO()
            writer=PdfWriter()
            for part in sequence:
                if isinstance(part,bytes):
                    reader=PdfReader(io.BytesIO(part))
                    if reader.is_encrypted:abort(400,'Hay un DNI en PDF con contraseña')
                    writer.append(reader,import_outline=False,excluded_fields=['/Annots','/AA'])
                else:
                    image_pdf=io.BytesIO()
                    part.save(image_pdf,format='PDF',resolution=120,quality=65)
                    writer.append(PdfReader(image_pdf),import_outline=False)
            writer.write(stream)
            if stream.tell() > 4*1024*1024:
                abort(400, 'El PDF supera 4 MB. Reduce el tamaño de las fotos antes de descargar')
            stream.seek(0)
            audit('hotel_identity_pdf_exported', event_id)
            return send_file(stream,mimetype='application/pdf',as_attachment=True,
                             download_name='DNI_privados_viaje.pdf')
        finally:
            for page in pages:
                page.close()

    return documents
