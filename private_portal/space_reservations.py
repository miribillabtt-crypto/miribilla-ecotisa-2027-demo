"""Shared facility reservations for Netkom and Occident."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import abort, g, jsonify, request
from sqlalchemy import select, text

SPACES = ('Exterior', 'Gela', 'Taller', 'Pabellón', 'Gimnasio')
KIND = 'shared:space-reservation'


def time_value(value):
    if not isinstance(value, str) or len(value) != 5:
        abort(400, 'Indica las horas de inicio y fin')
    try:
        parsed = datetime.strptime(value, '%H:%M')
    except ValueError:
        abort(400, 'Hora no válida')
    if parsed.strftime('%H:%M') != value:
        abort(400, 'Hora no válida')
    return value


def date_value(value):
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        abort(400, 'Fecha no válida')
    if parsed.isoformat() != value:
        abort(400, 'Fecha no válida')
    return value


def register_space_reservations(app, Record, seal, unseal, audit, require, body):
    def reservations():
        return g.db.scalars(select(Record).where(Record.kind == KIND))

    def can_cancel(row):
        return row.owner_id == g.user.id or (g.user.role == 'director' and row.team == g.team)

    @app.get('/api/space-reservations')
    @require('director', 'technician')
    def list_space_reservations():
        day = date_value(request.args.get('date') or datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat())
        results = []
        for row in reservations():
            booking = unseal(row.data)
            if booking['date'] == day:
                results.append(dict(booking, id=row.id, team=row.team, canCancel=can_cancel(row)))
        return jsonify(spaces=SPACES, date=day, reservations=sorted(results, key=lambda booking: booking['start']))

    @app.post('/api/space-reservations')
    @require('director', 'technician')
    def reserve_space():
        data = body()
        day = date_value(data.get('date'))
        start = time_value(data.get('start'))
        end = time_value(data.get('end'))
        space, title = data.get('space'), data.get('title', '')
        if space not in SPACES or start >= end:
            abort(400, 'Elige un espacio y una hora de fin posterior al inicio')
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            abort(400, 'Indica el motivo de la reserva')
        if datetime.fromisoformat(day+'T'+start).replace(tzinfo=ZoneInfo('Europe/Madrid')) < datetime.now(ZoneInfo('Europe/Madrid')):
            abort(400, 'Selecciona una franja futura')
        if g.db.get_bind().dialect.name == 'postgresql':
            g.db.execute(text('SELECT pg_advisory_xact_lock(20273010)'))
        for row in reservations():
            booking = unseal(row.data)
            if booking['space'] == space and booking['date'] == day and start < booking['end'] and booking['start'] < end:
                abort(409, 'Ese espacio ya está reservado en parte de la franja')
        record = Record(kind=KIND, owner_id=g.user.id,
                        data=seal(dict(space=space, date=day, start=start, end=end, title=title.strip())))
        g.db.add(record)
        g.db.flush()
        audit('space_reserved', record.id)
        return jsonify(ok=True, id=record.id), 201

    @app.delete('/api/space-reservations/<record_id>')
    @require('director', 'technician')
    def cancel_space_reservation(record_id):
        row = g.db.get(Record, record_id, with_for_update=True)
        if not row or row.kind != KIND:
            abort(404)
        if not can_cancel(row):
            abort(403, 'Sin permiso para cancelar esta reserva')
        g.db.delete(row)
        audit('space_reservation_cancelled', record_id)
        return jsonify(ok=True)
