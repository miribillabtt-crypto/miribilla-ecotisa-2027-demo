"""Availability overrides for a technical resource and one team activity."""
import hashlib
from datetime import date
from flask import g, jsonify, abort
from sqlalchemy import select, text


def availability_key(event, resource):
    return 'resource-status:'+hashlib.sha256((event+':'+resource).encode()).hexdigest()


VEHICLE_RESERVED = ('Reservado', 'No disponible')
VEHICLE_BOOKING = 'system:vehicle-reservation'


def lock_vehicle_bookings(db):
    if db.get_bind().dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(20273001)'))


def resource_bookings(db, Record, unseal):
    # Read only projected rows so other-team records never enter the identity map.
    rows = db.execute(
        select(Record.kind, Record.id, Record.team, Record.data)
        .where(Record.kind.in_(('event', 'module:travel', 'system:resource-availability', VEHICLE_BOOKING)))
        .execution_options(shared_resource_lookup=True)
    ).all()
    dates = {}
    for row in rows:
        if row.kind == 'event':
            activity = unseal(row.data)
            start = activity.get('date', '')
            if start:
                dates[row.team, row.id] = (start, max(start, activity.get('endDate') or start))
    bookings = []
    for row in rows:
        if row.kind == 'event':
            continue
        data = unseal(row.data)
        if row.kind == VEHICLE_BOOKING:
            bookings.append(dict(team=row.team, event=None, date=data['date'], endDate=data['endDate'],
                                 vehicles=[data['vehicle']], staff=[], manual=True, reservation=row.id,
                                 reason=data.get('reason','')))
            continue
        event = data.get('event')
        if (row.team, event) not in dates:
            continue
        if row.kind == 'module:travel':
            vehicles, staff = data.get('vehicles', []), data.get('staff', [])
        elif data.get('status') in VEHICLE_RESERVED:
            # Legacy overrides have no type. Staff IDs are excluded below.
            vehicles, staff = [data['resource']], []
        else:
            continue
        start, end = dates[row.team, event]
        bookings.append(dict(team=row.team, event=event, date=start, endDate=end,
                             vehicles=vehicles, staff=staff, manual=row.kind!='module:travel'))
    return bookings


def check_manual_vehicle_booking(bookings, team, event, activity, vehicle):
    start = activity.get('date')
    if not start:abort(400, 'Indica la fecha de la actividad antes de reservar el vehículo')
    end = max(start, activity.get('endDate') or start)
    for booking in bookings:
        if event and booking['team']==team and booking['event']==event:continue
        if vehicle in booking['vehicles'] and start<=booking['endDate'] and booking['date']<=end:
            abort(409, 'El vehículo ya está reservado para esas fechas')


def check_manual_vehicle_dates(db, Record, unseal, team, event, activity):
    overrides = db.scalars(select(Record.data).where(Record.kind=='system:resource-availability'))
    vehicles = set(db.scalars(select(Record.id).where(Record.kind=='module:vehicle')))
    reserved = [row['resource'] for data in overrides if (row:=unseal(data)).get('event')==event
                and row.get('status') in VEHICLE_RESERVED and row.get('resource') in vehicles]
    if reserved:
        bookings = resource_bookings(db, Record, unseal)
        for vehicle in reserved:
            check_manual_vehicle_booking(bookings, team, event, activity, vehicle)


def register_resources(app, Record, seal, unseal, audit, require, body):
    @app.get('/api/resource-availability')
    @require('director','technician')
    def resource_availability():
        records = [unseal(row.data) for row in g.db.scalars(
            select(Record).where(Record.kind=='system:resource-availability'))]
        bookings = resource_bookings(g.db, Record, unseal)
        vehicle_ids = set(g.db.scalars(select(Record.id).where(Record.kind=='module:vehicle')))
        vehicles = []
        for booking in bookings:
            ids = [resource for resource in booking['vehicles'] if resource in vehicle_ids]
            if ids:
                same_team=booking['team']==g.team
                entry=dict(team=booking['team'], date=booking['date'], endDate=booking['endDate'],
                           vehicles=ids, event=booking['event'] if same_team else None)
                if 'reservation' in booking:
                    entry['direct']=True
                    if same_team:
                        entry.update(id=booking['reservation'],reason=booking['reason'])
                vehicles.append(entry)
        shared = [dict(date=row['date'], endDate=row['endDate'], resources=row['staff'])
                  for row in bookings if row['team']!=g.team and row['staff']]
        return jsonify(records=records, shared=shared, vehicleBookings=vehicles)

    @app.post('/api/vehicle-reservations')
    @require('director')
    def reserve_vehicle():
        data=body()
        vehicle=data.get('vehicle')
        start=data.get('date')
        end=data.get('endDate') or start
        reason=data.get('reason','')
        if not isinstance(vehicle,str) or not isinstance(reason,str) or len(reason)>250:
            abort(400,'Revisa el vehículo y el motivo')
        try:
            if date.fromisoformat(start).isoformat()!=start or date.fromisoformat(end).isoformat()!=end or end<start:
                raise ValueError()
        except (TypeError, ValueError):
            abort(400,'Indica una fecha de inicio y una fecha de fin válida')
        lock_vehicle_bookings(g.db)
        resource=g.db.get(Record,vehicle,with_for_update=True)
        if not resource or resource.kind!='module:vehicle':abort(404,'Vehículo no disponible')
        reservation=dict(vehicle=vehicle,date=start,endDate=end,reason=reason.strip())
        check_manual_vehicle_booking(resource_bookings(g.db,Record,unseal),g.team,None,reservation,vehicle)
        row=Record(kind=VEHICLE_BOOKING,owner_id=g.user.id,data=seal(reservation))
        g.db.add(row)
        g.db.flush()
        audit('vehicle_reserved',row.id)
        return jsonify(id=row.id),201

    @app.delete('/api/vehicle-reservations/<reservation_id>')
    @require('director')
    def cancel_vehicle_reservation(reservation_id):
        lock_vehicle_bookings(g.db)
        row=g.db.get(Record,reservation_id,with_for_update=True)
        if not row or row.kind!=VEHICLE_BOOKING:abort(404)
        g.db.delete(row)
        audit('vehicle_reservation_cancelled',row.id)
        return jsonify(ok=True)

    @app.post('/api/resource-availability')
    @require('director')
    def save_availability():
        data=body()
        event_id,resource_id,status=data.get('event'),data.get('resource'),data.get('status')
        if not isinstance(event_id,str) or not isinstance(resource_id,str):
            abort(400)
        lock_vehicle_bookings(g.db)
        event=g.db.get(Record,event_id,with_for_update=True)
        resource=g.db.get(Record,resource_id)
        if not event or event.kind!='event' or not resource or resource.kind not in ('module:staff','module:vehicle'):
            abort(404)
        vehicle=resource.kind=='module:vehicle'
        if status not in (('Libre','Reservado','Disponible','No disponible','Por confirmar') if vehicle else ('Disponible','No disponible','Por confirmar')):
            abort(400)
        for travel in g.db.scalars(select(Record).where(Record.kind=='module:travel')):
            trip=unseal(travel.data)
            if trip.get('event')==event_id and resource_id in trip.get('staff',[])+trip.get('vehicles',[]):
                abort(409,'El recurso ya está asignado. Modifica la ficha del viaje')
        key=availability_key(event_id,resource_id)
        record=g.db.get(Record,key)
        if vehicle and status in VEHICLE_RESERVED:
            check_manual_vehicle_booking(resource_bookings(g.db, Record, unseal),
                                         g.team, event_id, unseal(event.data), resource_id)
        if vehicle and status in ('Libre','Disponible','Por confirmar'):
            if record:g.db.delete(record)
            audit('resource_availability_updated',resource_id)
            return jsonify(ok=True)
        content=seal(dict(event=event_id,resource=resource_id,status=status))
        if record:record.data=content
        else:g.db.add(Record(id=key,kind='system:resource-availability',owner_id=g.user.id,data=content))
        audit('resource_availability_updated',resource_id)
        return jsonify(ok=True)

    @app.get('/api/vehicle-logs')
    @require('director','technician')
    def vehicle_logs():
        records = [dict(unseal(row.data), id=row.id) for row in g.db.scalars(
            select(Record).where(Record.kind == 'system:vehicle-log'))]
        return jsonify(records=sorted(records, key=lambda row: row['started'], reverse=True))

    @app.post('/api/vehicle-logs')
    @require('director','technician')
    def start_vehicle_log():
        from datetime import datetime, timezone

        data = body()
        vehicle_id = data.get('vehicle')
        start = data.get('start')
        purpose = data.get('purpose', '')
        if not isinstance(vehicle_id, str) or type(start) != int or not 0 <= start <= 9999999:
            abort(400, 'Selecciona un vehículo e indica los km de salida')
        if not isinstance(purpose, str) or len(purpose) > 250:
            abort(400, 'El motivo admite hasta 250 caracteres')
        vehicle = g.db.get(Record, vehicle_id, with_for_update=True)
        if not vehicle or vehicle.kind != 'module:vehicle':
            abort(404, 'Vehículo no disponible')
        for row in g.db.scalars(select(Record).where(Record.kind == 'system:vehicle-log')):
            log = unseal(row.data)
            if log['vehicle'] == vehicle_id and log['end'] is None:
                abort(409, 'Este vehículo tiene una salida abierta. Registra primero su regreso')
        log = dict(vehicle=vehicle_id, name=unseal(vehicle.data)['name'], start=start,
                   end=None, started=datetime.now(timezone.utc).isoformat(),
                   user=g.user.id, driver=g.user.name, purpose=purpose.strip())
        row = Record(kind='system:vehicle-log', owner_id=g.user.id, data=seal(log))
        g.db.add(row)
        g.db.flush()
        audit('vehicle_departure', row.id)
        return jsonify(id=row.id), 201

    @app.post('/api/vehicle-logs/<log_id>/close')
    @require('director','technician')
    def close_vehicle_log(log_id):
        from datetime import datetime, timezone

        row = g.db.get(Record, log_id, with_for_update=True)
        if not row or row.kind != 'system:vehicle-log':
            abort(404)
        if g.user.role != 'director' and row.owner_id != g.user.id:
            abort(403)
        log = unseal(row.data)
        data = body()
        end = data.get('end')
        notes = data.get('notes', '')
        if type(end) != int or not log['start'] <= end <= 9999999:
            abort(400, 'Los km de regreso deben ser iguales o mayores que los de salida')
        if not isinstance(notes, str) or len(notes) > 1000:
            abort(400, 'Las observaciones admiten hasta 1000 caracteres')
        if log['end'] is not None:
            if log['end'] == end and log.get('notes', '') == notes.strip():
                return jsonify(ok=True)
            abort(409, 'Esta salida ya está cerrada')
        log.update(end=end, notes=notes.strip(), finished=datetime.now(timezone.utc).isoformat())
        row.data = seal(log)
        audit('vehicle_return', row.id)
        return jsonify(ok=True)

    @app.delete('/api/vehicle-logs/<log_id>')
    @require('director','technician')
    def delete_vehicle_log(log_id):
        row = g.db.get(Record, log_id, with_for_update=True)
        if not row or row.kind != 'system:vehicle-log':
            abort(404)
        if g.user.role != 'director' and row.owner_id != g.user.id:
            abort(403)
        g.db.delete(row)
        audit('vehicle_log_deleted', log_id)
        return jsonify(ok=True)
