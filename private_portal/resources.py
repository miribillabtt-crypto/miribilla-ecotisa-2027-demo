"""Availability overrides for a technical resource and one team activity."""
import hashlib
from flask import g, jsonify, abort
from sqlalchemy import select


def availability_key(event, resource):
    return 'resource-status:'+hashlib.sha256((event+':'+resource).encode()).hexdigest()


def register_resources(app, Record, seal, unseal, audit, require, body):
    @app.get('/api/resource-availability')
    @require('director','technician')
    def resource_availability():
        return jsonify(records=[unseal(row.data) for row in g.db.scalars(
            select(Record).where(Record.kind=='system:resource-availability'))])

    @app.post('/api/resource-availability')
    @require('director')
    def save_availability():
        data=body()
        event_id,resource_id,status=data.get('event'),data.get('resource'),data.get('status')
        if not isinstance(event_id,str) or not isinstance(resource_id,str):
            abort(400)
        if g.db.get_bind().dialect.name=='postgresql':
            from sqlalchemy import text
            g.db.execute(text('SELECT pg_advisory_xact_lock(20273001)'))
        event=g.db.get(Record,event_id,with_for_update=True)
        resource=g.db.get(Record,resource_id)
        if not event or event.kind!='event' or not resource or resource.kind not in ('module:staff','module:vehicle'):
            abort(404)
        if status not in ('Disponible','No disponible','Por confirmar'):
            abort(400)
        for travel in g.db.scalars(select(Record).where(Record.kind=='module:travel')):
            trip=unseal(travel.data)
            if trip.get('event')==event_id and resource_id in trip.get('staff',[])+trip.get('vehicles',[]):
                abort(409,'El recurso ya está asignado. Modifica la ficha del viaje')
        key=availability_key(event_id,resource_id)
        record=g.db.get(Record,key)
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
