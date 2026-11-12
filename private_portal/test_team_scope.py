from datetime import date,timedelta
from test_security import env
from server import User
from werkzeug.security import generate_password_hash

def test_occident_isolated_and_shared(env):
    app,ids,login,_=env
    db=app.extensions['db_sessions']()
    profile=app.extensions['cipher'].encrypt(b'{}')
    db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',documents=True,
                password=generate_password_hash('a-password-for-testing'),profile=profile))
    db.commit()
    db.close()
    director,h=login('director')
    assert director.post('/api/team',json={'team':'occident'},headers=h).status_code==403
    day=(date.today()+timedelta(days=30)).isoformat()
    client=app.test_client()
    assert client.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200
    current=client.get('/api/me').json
    assert current['team']=='netkom' and current['canSwitchTeam']
    headers={'X-CSRF-Token':current['csrf']}
    vehicle=client.post('/api/modules/vehicle',json={'name':'Furgo común'},headers=headers).json['id']
    staff=client.post('/api/modules/staff',json={'name':'Técnico común'},headers=headers).json['id']
    created=client.post('/api/events',json={'name':'Carrera privada de Netkom','date':day},headers=headers)
    assert created.status_code==200,created.json
    event=client.get('/api/events').json['events'][0]['id']
    assert client.post('/api/modules/travel',json={'event':event,'vehicles':[vehicle],'staff':[staff]},headers=headers).status_code==200
    reservation=dict(space='Gela',date=day,start='18:00',end='19:00',title='Entrenamiento Netkom')
    booking=client.post('/api/space-reservations',json=reservation,headers=headers)
    assert booking.status_code==201,booking.json
    assert client.post('/api/team',json={'team':'occident'},headers=headers).status_code==200
    assert client.get('/api/events').json['events']==[]
    assert client.get('/api/roster').json['riders']==[]
    assert client.get('/api/modules/travel').json['records']==[]
    assert client.get('/api/profile/'+ids['runner']).status_code==404
    assert client.get('/api/modules/vehicle').json['records'][0]['id']==vehicle
    assert client.get('/api/modules/staff').json['records'][0]['id']==staff
    assert client.post('/api/events',json={'name':'stale'},headers=headers).status_code==403
    headers={'X-CSRF-Token':client.get('/api/me').json['csrf']}
    assert client.post('/api/events/'+event+'/details',json={'name':'changed'},headers=headers).status_code==404
    assert client.post('/api/space-reservations',json=reservation,headers=headers).status_code==409
    assert client.get('/api/space-reservations?date='+day).json['reservations'][0]['team']=='netkom'
    assert client.post('/api/events',json={'name':'Carrera Occident','date':day},headers=headers).status_code==200
    other=client.get('/api/events').json['events'][0]['id']
    assert client.post('/api/modules/travel',json={'event':other,'vehicles':[vehicle]},headers=headers).status_code==409
    assert client.post('/api/modules/travel',json={'event':other,'staff':[staff]},headers=headers).status_code==409
    token=client.post('/api/occident/administrator-invite',json={},headers=headers).json['token']
    alex=app.test_client()
    assert alex.post('/api/activate/start',json={'token':token}).json['name']=='Alex Toledo'
    password='another-password-for-testing'
    activated=alex.post('/api/activate/finish',json={'token':token,'password':password})
    assert activated.status_code==200,activated.json
    assert alex.post('/api/login',json={'email':'occident.alextoledo','password':password}).status_code==200
    info=alex.get('/api/me').json
    assert info['team']=='occident' and not info['canSwitchTeam']
    assert alex.get('/api/events').json['events'][0]['name']=='Carrera Occident'
    assert alex.get('/api/users').json['users'][0]['name']=='Alex Toledo'
    assert alex.post('/api/team',json={'team':'netkom'},headers={'X-CSRF-Token':info['csrf']}).status_code==403
    assert director.get('/api/events').json['events'][0]['name']=='Carrera privada de Netkom'

def test_vehicle_bookings_are_shared_even_without_a_matching_activity(env):
    app,_,_,_=env
    with app.extensions['db_sessions'].begin() as db:
        db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',
                    documents=True,password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    client=app.test_client()
    assert client.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200

    def post(path,data):
        return client.post('/api/'+path,json=data,headers={'X-CSRF-Token':client.get('/api/me').json['csrf']})

    def activity(name, date, end=''):
        assert post('events',{'name':name,'date':date,'endDate':end}).status_code==200
        return next(e['id'] for e in client.get('/api/events').json['events'] if e['name']==name)

    vehicle=post('modules/vehicle',{'name':'Furgo'}).json['id']
    assert post('team',{'team':'occident'}).status_code==200
    occident=activity('Privada Occident','2027-03-01','2027-03-03')
    reserve={'event':occident,'resource':vehicle,'status':'Reservado'}
    assert post('resource-availability',reserve).status_code==200

    assert post('team',{'team':'netkom'}).status_code==200
    assert client.get('/api/events').json['events']==[]
    shared=client.get('/api/resource-availability').json['vehicleBookings']
    assert shared==[{'team':'occident','event':None,'date':'2027-03-01','endDate':'2027-03-03','vehicles':[vehicle]}]
    netkom=activity('Privada Netkom','2027-03-03')
    assert post('resource-availability',dict(reserve,event=netkom)).status_code==409
    assert post('modules/travel',{'event':netkom,'vehicles':[vehicle]}).status_code==409

    assert post('team',{'team':'occident'}).status_code==200
    assert post('resource-availability',dict(reserve,status='Libre')).status_code==200
    assert post('team',{'team':'netkom'}).status_code==200
    assert client.get('/api/resource-availability').json['vehicleBookings']==[]
    assert post('modules/travel',{'event':netkom,'vehicles':[vehicle]}).status_code==200
    assert post('team',{'team':'occident'}).status_code==200
    assert client.get('/api/resource-availability').json['vehicleBookings']==[
        {'team':'netkom','event':None,'date':'2027-03-03','endDate':'2027-03-03','vehicles':[vehicle]}]
