import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["MODE"] = "demo"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.main import app, db
from app.ingest import ingest
from app.collectors.demo import DemoCollector


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        yield session
    engine.dispose()


@pytest.fixture()
def client(session):
    ingest(session, DemoCollector().collect())
    app.dependency_overrides[db] = lambda: session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
