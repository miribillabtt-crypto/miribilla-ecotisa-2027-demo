"""Authenticated calendar snapshots for calendar applications."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256

from flask import Response, abort, g, request
from sqlalchemy import select


def calendar_text(value):
    value = str(value or '').replace('\r\n', '\n').replace('\r', '\n')
    value = ''.join(char for char in value if char in '\n\t' or (ord(char) >= 32 and ord(char) != 127))
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold_line(line):
    parts = []
    current = ''
    length = 0
    for char in line:
        width = len(char.encode('utf-8'))
        if length + width > 75:
            parts.append(current)
            current = ' '
            length = 1
        current += char
        length += width
    parts.append(current)
    return '\r\n'.join(parts)


def register_calendar_exports(app, Record, unseal, audit, require):
    @app.get('/api/calendar.ics')
    @require('director', 'runner')
    def calendar_export():
        scope = request.args.get('scope', 'all')
        if scope not in ('all', 'selected'):
            abort(400, 'Selecciona el calendario del equipo o el personal')
        if scope == 'selected' and g.user.role != 'runner':
            abort(403)
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0',
                 'PRODID:-//Miribilla Ecotisa//Calendario del equipo//ES',
                 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:Miribilla Ecotisa']
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        count = 0
        for record in g.db.scalars(select(Record).where(Record.kind == 'event').order_by(Record.id)):
            event = unseal(record.data)
            selected = g.user.id in event.get('called', [])
            if scope == 'selected' and not selected:
                continue
            try:
                start = date.fromisoformat(event.get('date') or '')
                end = max(start, date.fromisoformat(event.get('endDate') or start.isoformat()))
                exclusive_end = end + timedelta(days=1)
            except (ValueError, OverflowError):
                continue
            description = ''
            title = event['name']
            if g.user.role == 'runner':
                state = ('Convocado' if event.get('callStatus') == 'Publicada' else 'Preconvocado') if selected else 'No convocado'
                answer = g.db.get(Record, sha256((record.id + ':' + g.user.id).encode()).hexdigest())
                availability = unseal(answer.data)['status'] if answer else 'Pendiente de responder'
                title += ' · ' + state
                description = f'Mi convocatoria: {state}\nMi disponibilidad: {availability}'
            uid = sha256((record.id + ':' + g.user.id).encode()).hexdigest() + '@miribillacycling.com'
            lines.extend(['BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp,
                          'DTSTART;VALUE=DATE:' + start.isoformat().replace('-', ''),
                          'DTEND;VALUE=DATE:' + exclusive_end.isoformat().replace('-', ''),
                          'SUMMARY:' + calendar_text(title),
                          'LOCATION:' + calendar_text(event.get('place', '')),
                          'DESCRIPTION:' + calendar_text(description),
                          'CLASS:PRIVATE', 'TRANSP:TRANSPARENT', 'END:VEVENT'])
            count += 1
        lines.append('END:VCALENDAR')
        payload = '\r\n'.join(fold_line(line) for line in lines) + '\r\n'
        audit('calendar_exported', f'{scope}:{count}')
        filename = 'Mi_calendario_Miribilla.ics' if scope == 'selected' else 'Calendario_equipo_Miribilla.ics'
        return Response(payload, content_type='text/calendar; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="{filename}"'})
