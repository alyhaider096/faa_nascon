import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.app.domain.models import Base
from backend.app.domain.seeds import reset_domain
from backend.app.domain.common import signer


@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        reset_domain(s)
        s.commit()
        yield s
    engine.dispose()


@pytest.fixture
def sign():
    return signer('demo-salt')
