"""Trip allocations and optional clothing orders, stored as existing rider charges."""
import json
import os
import re
from team_scope import team_record_key
from hashlib import sha256
from urllib.request import Request, urlopen
from flask import abort, g, jsonify
from sqlalchemy import select


def clothing_orders(db, Record, unseal, rider_id=None):
    query = select(Record).where(Record.kind == 'shop-order')
    charges = select(Record).where(Record.kind == 'module:charge')
    if rider_id:
        query = query.where(Record.owner_id == rider_id)
    payments = {}
    for charge in db.scalars(charges):
        data = unseal(charge.data)
        if data.get('notes', '').startswith('Pedido '):
            payments[(data['notes'][7:], data.get('rider'))] = data.get('status', 'Pendiente')
    orders = []
    for row in db.scalars(query):
        data = unseal(row.data)
        orders.append(dict(data, id=row.id, rider=row.owner_id,
                           paymentStatus=payments.get((row.id, row.owner_id), 'Cargo pendiente de localizar')))
    return sorted(orders, key=lambda order: order['created'], reverse=True)


def register_settlements(app, Record, User, clothes, seal, unseal, audit, require, body):
    def record(record_id, kind, lock=False):
        item = g.db.get(Record, record_id, with_for_update=lock)
        if not item or item.kind != kind:
            abort(404)
        return item

    @app.post('/api/events/<event_id>/split-expenses')
    @require('director')
    def split_expenses(event_id):
        event = unseal(record(event_id, 'event', True).data)
        if event.get('callStatus') != 'Publicada':
            abort(400, 'Publica la convocatoria antes de repartir los gastos')
        data = body()
        ids = data.get('expenses')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(not isinstance(i, str) for i in ids):
            abort(400, 'Selecciona los gastos que se cargarán a los corredores')
        called = sorted(set(event.get('called', [])))
        if 'expectedRiders' in data and data['expectedRiders'] != called:
            abort(409, 'La convocatoria ha cambiado. Recarga la actividad y revisa los corredores antes de repartir.')
        riders = [g.db.get(User, rid) for rid in called]
        if not riders or any(not rider or rider.role != 'runner' for rider in riders):
            abort(400, 'Revisa los corredores convocados')
        expense_ids = sorted(set(ids))
        total = 0
        markers = []
        for expense_id in expense_ids:
            expense = unseal(record(expense_id, 'module:entry', True).data)
            if expense.get('event') != event_id or expense.get('direction') != 'Gasto' or expense.get('status') == 'Anulado':
                abort(400, 'El gasto debe estar activo y vinculado a este viaje')
            marker = 'trip-share:'+expense_id
            if g.db.get(Record, marker):
                abort(409, 'Algún gasto seleccionado ya se ha repartido')
            markers.append(marker)
            total += expense['amount']
        if total <= 0:
            abort(400, 'El importe total debe ser mayor que cero')
        if 'expectedTotal' in data and data['expectedTotal'] != total:
            abort(409, 'El importe ha cambiado. Recarga los gastos antes de repartir.')
        quotient, remainder = divmod(total, len(riders))
        for index, rider in enumerate(riders):
            share = quotient + int(index < remainder)
            if share:
                g.db.add(Record(kind='module:charge', owner_id=g.user.id, data=seal(dict(
                    event=event_id, rider=rider.id, concept='Desplazamiento · '+event['name'],
                    amount=share, status='Pendiente', notes='Reparto de los gastos seleccionados'))))
        for marker in markers:
            g.db.add(Record(id=marker, kind='system:trip-share', owner_id=event_id, data=seal({})))
        audit('trip_expenses_split', event_id)
        return jsonify(total=total, riders=len(riders))

    def shop_key():
        return team_record_key(g.team,'clothing-shop')

    def shop_settings():
        config = g.db.get(Record, shop_key())
        return unseal(config.data) if config else dict(prices={}, director='')

    @app.get('/api/shop')
    @require('director', 'runner')
    def shop():
        config = shop_settings()
        result = dict(products=[dict(name=name, price=config['prices'].get(name)) for name in clothes],
                      orders=clothing_orders(g.db,Record,unseal,g.user.id if g.user.role=='runner' else None))
        if g.user.role == 'director':
            result['director'] = config['director']
            result['directors'] = [dict(id=u.id, name=u.name) for u in g.db.scalars(
                select(User).where(User.role == 'director', User.active == True, User.email.contains('@')))]
        return jsonify(result)

    @app.post('/api/shop/settings')
    @require('director')
    def configure_shop():
        config = body()
        prices, director_id = config.get('prices'), config.get('director')
        if not isinstance(prices, dict) or set(prices)-set(clothes) or any(
            type(price) != int or not 1 <= price <= 100000 for price in prices.values()
        ):
            abort(400, 'Revisa los precios')
        director = g.db.get(User, director_id) if isinstance(director_id, str) and director_id else None
        if not director or director.role != 'director' or not director.active or (not director.email or '@' not in director.email):
            abort(400, 'Elige un director con correo registrado')
        item = g.db.get(Record, shop_key(), with_for_update=True)
        data = seal(dict(prices=prices, director=director.id))
        if item:
            item.data = data
        else:
            g.db.add(Record(id=shop_key(), kind='system:shop', owner_id=g.user.id, data=data))
        audit('shop_configured', director.id)
        return jsonify(ok=True)

    def notify_order(item):
        order = unseal(item.data)
        if order['emailStatus'] == 'Enviado':
            return order
        director = g.db.get(User, order['director'])
        key, sender = os.getenv('RESEND_API_KEY'), os.getenv('SHOP_FROM_EMAIL')
        if not key or not sender or not director or not director.active or director.role != 'director' or (not director.email or '@' not in director.email):
            return order
        summary = '\n'.join(f"{line['quantity']} × {line['name']} · talla {line['size']}" for line in order['items'])
        payload = dict(to=[director.email], subject='Pedido de ropa del equipo', text=(
            f"Pedido {item.id}\nCorredor: {order['name']}\n{summary}\nTotal: {order['amount']/100:.2f} EUR"
        ))
        payload['from'] = sender
        try:
            request = Request('https://api.resend.com/emails', data=json.dumps(payload).encode(),
                              headers={'Authorization':'Bearer '+key, 'Content-Type':'application/json',
                                       'Idempotency-Key':item.id}, method='POST')
            with urlopen(request, timeout=4):
                pass
        except OSError:
            return order
        order['emailStatus'] = 'Enviado'
        item.data = seal(order)
        return order

    @app.post('/api/shop/orders')
    @require('runner')
    def order_clothes():
        from datetime import datetime, timezone
        data = body()
        token, items = data.get('token'), data.get('items')
        if not isinstance(token, str) or not re.fullmatch(r'[a-f0-9-]{36}', token):
            abort(400, 'Identificador de pedido no válido')
        g.db.get(User, g.user.id, with_for_update=True)
        order_id = 'shop-'+sha256((g.user.id+':'+token).encode()).hexdigest()[:32]
        existing = g.db.get(Record, order_id)
        if existing:
            return jsonify(id=order_id, **unseal(existing.data))
        settings = shop_settings()
        director = g.db.get(User, settings['director']) if settings['director'] else None
        if not director or not director.active or director.role != 'director' or (not director.email or '@' not in director.email):
            abort(400, 'Dirección debe configurar primero la tienda')
        if not isinstance(items, list) or not 1 <= len(items) <= len(clothes):
            abort(400, 'Selecciona al menos una prenda')
        lines = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                abort(400)
            name, size, qty = item.get('name'), item.get('size'), item.get('quantity')
            if not isinstance(name, str) or name in seen or name not in settings['prices'] or size not in (
                'XXS','XS','S','M','L','XL','XXL','XXXL'
            ) or type(qty) != int or not 1 <= qty <= 20:
                abort(400, 'Revisa las prendas, tallas y unidades')
            seen.add(name)
            lines.append(dict(name=name,size=size,quantity=qty,price=settings['prices'][name]))
        amount = sum(line['price']*line['quantity'] for line in lines)
        if type(data.get('amount')) != int or amount != data['amount']:
            abort(409, 'Los precios han cambiado. Recarga la tienda y revisa el total')
        order = dict(name=g.user.name, items=lines, amount=amount, director=director.id,
                     created=datetime.now(timezone.utc).isoformat(),emailStatus='Pendiente')
        item = Record(id=order_id, kind='shop-order', owner_id=g.user.id, data=seal(order))
        g.db.add(item)
        g.db.add(Record(kind='module:charge', owner_id=g.user.id, data=seal(dict(
            event='', rider=g.user.id, concept='Compra de ropa', amount=amount, status='Pendiente', notes='Pedido '+order_id))))
        audit('shop_order_created', order_id)
        g.db.commit()
        item = record(order_id, 'shop-order', True)
        return jsonify(id=order_id, **notify_order(item))

    @app.post('/api/shop/orders/<order_id>/notify')
    @require('director')
    def retry_order_notification(order_id):
        item = record(order_id, 'shop-order', True)
        return jsonify(emailStatus=notify_order(item)['emailStatus'])
