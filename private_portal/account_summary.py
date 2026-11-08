"""Read-only rider account totals from charges and fines."""
from io import BytesIO

from flask import g, jsonify, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select


def register_account_summary(app, User, Record, unseal, audit, require):
    def summary():
        query = select(User).where(User.role == 'runner').order_by(User.name, User.id)
        if g.user.role == 'runner':
            query = query.where(User.id == g.user.id)
        riders = {}
        for user in g.db.scalars(query):
            riders[user.id] = dict(id=user.id, name=user.name, active=user.active,
                                   clothes=0, races=0, fines=0, other=0, total=0, paid=0, pending=0)

        def add(rider_id, category, amount, paid):
            row = riders.get(rider_id)
            if row is None or not isinstance(amount, int) or amount <= 0:
                return
            row[category] += amount
            row['total'] += amount
            row['paid' if paid else 'pending'] += amount

        for record in g.db.scalars(select(Record).where(Record.kind == 'module:charge')):
            charge = unseal(record.data)
            if charge.get('status') == 'Anulado':
                continue
            concept = charge.get('concept', '').casefold()
            if 'ropa' in concept or charge.get('notes', '').startswith('Pedido '):
                category = 'clothes'
            elif 'multa' in concept:
                category = 'fines'
            elif charge.get('event'):
                category = 'races'
            else:
                category = 'other'
            add(charge.get('rider'), category, charge.get('amount', 0), charge.get('status') in ('Pagado', 'Cobrado'))
        fines_query = select(Record).where(Record.kind == 'fine')
        if g.user.role == 'runner':
            fines_query = fines_query.where(Record.owner_id == g.user.id)
        for record in g.db.scalars(fines_query):
            fine = unseal(record.data)
            if fine.get('status') == 'Anulada':
                continue
            amount = fine.get('amount')
            if type(amount) == int:
                add(record.owner_id, 'fines', amount * 100, fine.get('status') == 'Pagada')
        rows = [row for row in riders.values() if row['active'] or row['total']]
        fields = ('clothes', 'races', 'fines', 'other', 'total', 'paid', 'pending')
        return dict(riders=rows, totals={field: sum(row[field] for row in rows) for field in fields})

    @app.get('/api/accounts')
    @require('director', 'runner')
    def accounts():
        return jsonify(summary())

    @app.get('/api/accounts/export')
    @require('director', 'runner')
    def accounts_export():
        data = summary()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Cuentas por corredor'
        sheet.append(['Corredor', 'Ropa (€)', 'Carreras (€)', 'Multas (€)', 'Otros (€)',
                      'Total (€)', 'Pagado (€)', 'Pendiente (€)'])
        fields = ('clothes', 'races', 'fines', 'other', 'total', 'paid', 'pending')
        for row in data['riders']:
            sheet.append([row['name'], *[row[field] / 100 for field in fields]])
            sheet.cell(sheet.max_row, 1).data_type = 's'
        sheet.append(['TOTAL', *[data['totals'][field] / 100 for field in fields]])
        for cells in sheet.iter_rows(min_row=2, min_col=2):
            for cell in cells:
                cell.number_format = '#,##0.00'
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='073BD9')
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = 'B2'
        sheet.column_dimensions['A'].width = 32
        for column in 'BCDEFGH':
            sheet.column_dimensions[column].width = 18
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        audit('rider_accounts_exported', str(len(data['riders'])))
        return send_file(output, as_attachment=True, download_name='Cuentas_por_corredor.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
