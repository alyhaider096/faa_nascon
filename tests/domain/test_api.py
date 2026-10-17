from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from backend.app.domain.api import build_router, domain_error_handler
from backend.app.domain.common import DomainError, signer
from backend.app.domain.models import Base
from backend.app.domain.seeds import reset_domain


def make_client(engine=None):
    if engine is None:
        engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s, s.begin():
        reset_domain(s)
    def get_session():
        with Session(engine) as s, s.begin():
            yield s
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(build_router(get_session, signer('demo-salt')))
    return TestClient(app)


def test_api_end_to_end():
    with make_client() as client:
        r=client.post('/audit/v1/leagues',json={'league_id':'lg','sport_id':'football','teams':['a','b'],
                   'fixtures':[{'match_id':'m','home':'a','away':'b'}],'qualification':{'spots':1}})
        assert r.status_code==201
        for i,(type_,payload) in enumerate([('match_start',{}),('score',{'team_id':'a','event_type':'goal'}),('match_end',{})]):
            body={'event_id':f'e{i}','match_id':'m','type':type_,'payload':payload}
            response=client.post('/audit/v1/events',json=body)
            assert response.status_code==201
            assert client.post('/audit/v1/events',json=body).status_code==200
        assert client.get('/audit/v1/score/m').json()['home']['score']==1
        assert client.get('/audit/v1/standings/lg').json()['table'][0]['status']=='clinched'
        assert client.get('/audit/v1/score/unknown').status_code==404
        assert client.post('/audit/v1/fixtures',json={'format':'single_elim','teams':['a','b']}).status_code==200


def test_api_validation_and_body_limit():
    with make_client() as client:
        assert client.post('/audit/v1/sports',content=b'{').status_code==400
        assert client.post('/audit/v1/sports',content=b'\xff').status_code==400
        assert client.post('/audit/v1/sports',content=b'NaN').status_code==400
        r=client.post('/audit/v1/events',json={})
        assert r.status_code==400 and r.json()['error']['details']['fields']
        r=client.post('/audit/v1/fixtures',content=b'x'*(1024*1024+1))
        assert r.status_code==413 and r.json()['error']['code']=='PAYLOAD_TOO_LARGE'
