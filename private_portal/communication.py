"""Editorial planning and shared media for the communication area."""
import io
import re
import time
from datetime import date

from flask import abort, g, jsonify, request, send_file
from sqlalchemy import select
from werkzeug.utils import secure_filename

from invoices import invoice_file_type
from team_scope import TEAMS

PLAN = 'communication:plan'
LOGO = 'communication:logo'
PHOTO_KINDS = ('portrait', 'action')
STATUSES = ('Borrador', 'Programada', 'Publicada')


def register_communication(app, Record, User, Document, cipher, seal, unseal, audit, require, body):
    access = require('director', 'communication')

    def shared(query):
        return query.execution_options(shared_resource_lookup=True)

    def visible_teams():
        if g.user.role == 'communication' or g.user.owner or g.user.id == 'shared-direction':
            return tuple(TEAMS)
        return (g.team,)

    def team_key(value):
        if not isinstance(value, str) or value not in TEAMS:
            abort(400, 'Selecciona un equipo')
        if value not in visible_teams():
            abort(403)
        return value

    def string(data, name, limit):
        value = data.get(name, '')
        if not isinstance(value, str) or len(value) > limit:
            abort(400, 'Revisa los datos')
        return value.strip()

    @app.get('/api/communication/calendar')
    @access
    def communication_calendar():
        events, plans = [], []
        query = select(Record.id, Record.team, Record.kind, Record.data).where(
            Record.kind.in_(('event', PLAN)), Record.team.in_(visible_teams()))
        for row in g.db.execute(shared(query)):
            data = unseal(row.data)
            identity = dict(id=row.id, team=row.team)
            if row.kind == 'event':
                keys = ('name', 'date', 'endDate', 'month', 'place', 'category')
                events.append(dict(identity, **{key: data.get(key, '') for key in keys}))
            else:
                plans.append(dict(data, **identity))
        return jsonify(events=events, plans=plans)

    @app.post('/api/communication/plans', defaults={'target': None})
    @app.put('/api/communication/plans/<target>')
    @app.delete('/api/communication/plans/<target>')
    @access
    def communication_plan(target):
        row = None
        if target:
            query = select(Record).where(Record.id == target, Record.kind == PLAN, Record.team.in_(visible_teams())).with_for_update()
            row = g.db.scalar(shared(query))
            if not row:
                abort(404)
        if request.method == 'DELETE':
            g.db.delete(row)
            audit('communication_plan_deleted', target)
            return jsonify(ok=True)

        data = body()
        team = team_key(data.get('team'))
        plan = {key: string(data, key, limit) for key, limit in (
            ('title', 150), ('date', 10), ('time', 5), ('status', 20), ('channel', 60),
            ('notes', 2000), ('event', 100))}
        try:
            valid_date = date.fromisoformat(plan['date']).isoformat() == plan['date']
        except ValueError:
            valid_date = False
        if not valid_date or not plan['title'] or plan['status'] not in STATUSES:
            abort(400, 'Indica título, fecha y estado de publicación')
        if plan['time']:
            if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', plan['time']):
                abort(400, 'Indica una hora válida')
        old = unseal(row.data) if row else {}
        if plan['event'] and (not row or row.team != team or old.get('event') != plan['event']):
            query = select(Record.id).where(Record.id == plan['event'], Record.team == team, Record.kind == 'event')
            if not g.db.scalar(shared(query)):
                abort(400, 'Selecciona una actividad de ese equipo')
        if row:
            row.team = team
            row.data = seal(plan)
        else:
            row = Record(team=team, kind=PLAN, owner_id=g.user.id, data=seal(plan))
            g.db.add(row)
            g.db.flush()
        audit('communication_plan_saved', row.id)
        return jsonify(id=row.id)

    @app.get('/api/communication/photos/<team>')
    @access
    def communication_photos(team):
        team_key(team)
        people = {}
        query = select(User.id, User.name, User.profile).where(User.team == team, User.active.is_(True), User.role == 'runner')
        for row in g.db.execute(shared(query)):
            if unseal(row.profile).get('photoConsent'):
                people[row.id] = dict(id=row.id, name=row.name, photos=[])
        query = select(Document.id, Document.owner_id, Document.kind).where(
            Document.team == team, Document.owner_id.in_(people), Document.kind.in_(PHOTO_KINDS))
        for row in g.db.execute(shared(query)):
            people[row.owner_id]['photos'].append(dict(id=row.id, kind=row.kind))
        return jsonify(riders=list(people.values()))

    @app.get('/api/communication/photo/<target>')
    @access
    def communication_photo(target):
        query = select(Document, User.profile).join(User, User.id == Document.owner_id).where(
            Document.id == target, Document.kind.in_(PHOTO_KINDS), Document.team.in_(visible_teams()),
            Document.team == User.team, User.role == 'runner', User.active.is_(True))
        result = g.db.execute(shared(query)).first()
        if not result or not unseal(result.profile).get('photoConsent'):
            abort(404)
        doc = result[0]
        audit('communication_photo_read', doc.id)
        return send_file(io.BytesIO(cipher.decrypt(doc.content)), mimetype=doc.mime,
                         as_attachment=request.args.get('download') == '1', download_name=doc.kind+'.jpg')

    @app.get('/api/communication/logos/<team>')
    @app.post('/api/communication/logos/<team>')
    @access
    def communication_logos(team):
        team_key(team)
        if request.method == 'GET':
            query = select(Record.id, Record.data).where(Record.team == team, Record.kind == LOGO)
            return jsonify(logos=[dict(id=row.id, **unseal(row.data)) for row in g.db.execute(shared(query))])
        name = string(request.form, 'name', 120)
        file = request.files.get('file')
        raw = file.read(2*1024*1024+1) if file else b''
        if not name or not raw or len(raw) > 2*1024*1024:
            abort(400, 'Indica el patrocinador y adjunta un logo de hasta 2 MB')
        mime, extension = invoice_file_type(raw)
        if not mime.startswith('image/'):
            abort(400, 'Usa un logo JPG, PNG o WEBP')
        doc = Document(team=team, kind=LOGO, owner_id=g.user.id, size=len(raw), mime=mime,
                       created=int(time.time()), content=cipher.encrypt(raw))
        g.db.add(doc)
        g.db.flush()
        filename = secure_filename(name) or 'logo'
        g.db.add(Record(id=doc.id, team=team, kind=LOGO, owner_id=g.user.id,
                        data=seal(dict(name=name, filename=filename+extension))))
        audit('communication_logo_uploaded', doc.id)
        return jsonify(id=doc.id), 201

    @app.get('/api/communication/logo/<target>')
    @app.delete('/api/communication/logo/<target>')
    @access
    def communication_logo(target):
        query = select(Record, Document).join(Document, Document.id == Record.id).where(
            Record.id == target, Record.kind == LOGO, Record.team.in_(visible_teams()), Document.kind == LOGO, Document.team == Record.team)
        if request.method == 'DELETE':
            query = query.with_for_update()
        row = g.db.execute(shared(query)).first()
        if not row:
            abort(404)
        record, doc = row
        if request.method == 'DELETE':
            g.db.delete(record)
            g.db.delete(doc)
            audit('communication_logo_deleted', target)
            return jsonify(ok=True)
        return send_file(io.BytesIO(cipher.decrypt(doc.content)), mimetype=doc.mime,
                         as_attachment=request.args.get('download') == '1', download_name=unseal(record.data)['filename'])
