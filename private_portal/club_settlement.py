"""Read-only monthly compensation of paid invoices between the two clubs."""
import io,re,datetime
from flask import request,jsonify,abort,send_file,g
from sqlalchemy import select
from openpyxl import Workbook

CLUBS=('Miribilla','Ecotisa')

def monthly_settlement(entries,month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month):
        raise ValueError('Selecciona un mes válido')
    totals={club:dict(paid=0,share=0,balance=0) for club in CLUBS}
    details=[];pending=[]
    for row in entries:
        if row.get('direction')!='Gasto' or row.get('status')=='Anulado':continue
        day=row.get('paymentDate') or row.get('date') or ''
        if day and not day.startswith(month+'-'):continue
        reasons=[]
        if not row.get('paymentDate'):reasons.append('Falta fecha de pago')
        if row.get('status')!='Pagado':reasons.append('Pendiente de pago')
        if row.get('payerClub') not in CLUBS:reasons.append('Falta club que adelanta')
        if not row.get('paidBy','').strip():reasons.append('Falta quién paga')
        amount=row.get('amount',0)
        if type(amount)!=int or amount<=0:reasons.append('Falta importe')
        rule=row.get('allocationRule','')
        percent={'Miribilla':100,'Ecotisa':0,'Mitad':50}.get(rule)
        if rule=='Personalizado':percent=row.get('miribillaPercent')
        if type(percent)!=int or not 0<=percent<=100:reasons.append('Falta criterio de reparto')
        item={**row,'issues':reasons,'included':not reasons}
        if reasons:
            pending.append(item);continue
        # Round once to cents; the other club receives the exact remainder.
        miribilla=(amount*percent+50)//100
        shares={'Miribilla':miribilla,'Ecotisa':amount-miribilla}
        item['shares']=shares;details.append(item)
        totals[row['payerClub']]['paid']+=amount
        for club in CLUBS:totals[club]['share']+=shares[club]
    for club in CLUBS:totals[club]['balance']=totals[club]['paid']-totals[club]['share']
    balance=totals['Miribilla']['balance']
    transfer=dict(fromClub='Ecotisa' if balance>0 else 'Miribilla',toClub='Miribilla' if balance>0 else 'Ecotisa',amount=abs(balance))
    return dict(month=month,totals=totals,transfer=transfer,entries=details,pending=pending,
                total=sum(r['amount'] for r in details),pendingTotal=sum(r.get('amount',0) for r in pending))

def register_club_settlement(app,Record,unseal,require,audit):
    def report():
        month=request.args.get('month',datetime.date.today().strftime('%Y-%m'))
        entries=[dict(unseal(r.data),id=r.id) for r in g.db.scalars(select(Record).where(Record.kind=='module:entry'))]
        try:return monthly_settlement(entries,month)
        except ValueError as error:abort(400,str(error))

    @app.get('/api/club-settlement')
    @require('director')
    def club_settlement():return jsonify(report())

    @app.get('/api/club-settlement/export')
    @require('director')
    def club_settlement_export():
        result=report();wb=Workbook();ws=wb.active;ws.title='Liquidación mensual'
        ws.append(['Mes de pago',result['month']]);ws.append(['Club','Adelantado (€)','Le corresponde (€)','A recibir (+) / aportar (-) (€)'])
        for club in CLUBS:
            item=result['totals'][club];ws.append([club,item['paid']/100,item['share']/100,item['balance']/100])
        ws.append(['Facturas pendientes de revisar',len(result['pending'])]);ws.append(['Importe pendiente de revisión (€)',result['pendingTotal']/100])
        ws.append(['Cálculo provisional. No registra transferencias. Revisa los pendientes antes del cierre.'])
        for title,rows in [('Facturas incluidas',result['entries']),('Pendientes de revisar',result['pending'])]:
            sheet=wb.create_sheet(title)
            sheet.append(['Fecha factura','Fecha pago','Concepto','Proveedor','Importe (€)','Club que adelanta','Quién paga','Criterio','% Miribilla','Parte Miribilla (€)','Parte Ecotisa (€)','Motivo pendiente'])
            for row in rows:
                shares=row.get('shares',{})
                sheet.append([row.get('date',''),row.get('paymentDate',''),row.get('concept',''),row.get('counterparty',''),row.get('amount',0)/100,row.get('payerClub',''),row.get('paidBy',''),row.get('allocationRule',''),row.get('miribillaPercent',''),shares.get('Miribilla',0)/100,shares.get('Ecotisa',0)/100,'; '.join(row['issues'])])
            sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for sheet in wb:
            for row in sheet:
                for cell in row:
                    if isinstance(cell.value,str):cell.data_type='s'
                    elif isinstance(cell.value,(int,float)):cell.number_format='#,##0.00'
            for column in sheet.columns:sheet.column_dimensions[column[0].column_letter].width=25
        out=io.BytesIO();wb.save(out);out.seek(0);audit('club_settlement_exported',result['month'])
        return send_file(out,as_attachment=True,download_name='Liquidacion_clubes_'+result['month']+'.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
