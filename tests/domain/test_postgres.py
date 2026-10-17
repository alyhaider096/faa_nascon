"""Opt-in tests: URL MUST point at a disposable database, never shared/live data."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.app.domain.common import DomainError, signer
from backend.app.domain.models import Base, Event
from backend.app.domain.scoring import append_event, project_score
from backend.app.domain.seeds import reset_domain


@pytest.fixture
def pg():
    url = os.environ.get('DOMAIN_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set DOMAIN_TEST_DATABASE_URL to a disposable PostgreSQL database')
    engine = create_engine(url, pool_size=20, max_overflow=5)
    assert engine.dialect.name == 'postgresql'
    # No DROP DATABASE or data deletion outside this fragment.
    Base.metadata.create_all(engine)
    with Session(engine) as s, s.begin():
        reset_domain(s)
        append_event(s, {'event_id':'init','match_id':'m','type':'match_init',
                        'payload':{'sport_id':'football','home_team_id':'a','away_team_id':'b'}}, signer('demo-salt'))
        append_event(s, {'event_id':'start','match_id':'m','type':'match_start','payload':{}}, signer('demo-salt'))
    yield engine
    engine.dispose()


@pytest.mark.parametrize('same_id', [False, True])
def test_twenty_concurrent_appends(pg, same_id):
    barrier = threading.Barrier(20)
    def append(i):
        with Session(pg) as session, session.begin():
            barrier.wait(timeout=10)
            return append_event(session, {'event_id':'e' if same_id else f'e{i}', 'match_id':'m', 'type':'score',
                                'payload':{'team_id':'a','event_type':'goal'}}, signer('demo-salt'))[0]
    with ThreadPoolExecutor(max_workers=20) as pool:
        statuses=list(pool.map(append, range(20)))
    assert statuses.count(201)==(1 if same_id else 20)
    assert statuses.count(200)==(19 if same_id else 0)
    with Session(pg) as session:
        projection=project_score(session,'m')
        assert projection['home']['score']==(1 if same_id else 20)
        assert [e['sequence'] for e in projection['events']]==list(range(1,projection['version']+1))


def test_transaction_rollback_and_savepoint(pg):
    request={'event_id':'rollback','match_id':'m','type':'score','payload':{'team_id':'a','event_type':'goal'}}
    with pytest.raises(RuntimeError):
        with Session(pg) as session, session.begin():
            append_event(session,request,signer('demo-salt'))
            raise RuntimeError('caller failed')
    with Session(pg) as session, session.begin():
        assert session.get(Event,'rollback') is None
        with pytest.raises(DomainError):
            with session.begin_nested():
                append_event(session,{**request,'payload':{'team_id':'z','event_type':'goal'}},signer('demo-salt'))
        assert append_event(session,request,signer('demo-salt'))[0]==201


def test_concurrent_http_replays_commit_before_response(pg):
    from test_api import make_client
    with make_client(pg) as client:
        assert client.post('/audit/v1/events',json={'event_id':'init','match_id':'m','type':'match_init',
            'payload':{'sport_id':'football','home_team_id':'a','away_team_id':'b'}}).status_code==201
        assert client.post('/audit/v1/events',json={'event_id':'start','match_id':'m','type':'match_start','payload':{}}).status_code==201
        barrier=threading.Barrier(20)
        def send(_):
            barrier.wait(timeout=10)
            return client.post('/audit/v1/events',json={'event_id':'same','match_id':'m','type':'score',
                'payload':{'team_id':'a','event_type':'goal'}}).status_code
        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses=list(pool.map(send,range(20)))
        assert statuses.count(201)==1 and statuses.count(200)==19
        assert client.get('/audit/v1/score/m').json()['home']['score']==1
