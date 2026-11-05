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
