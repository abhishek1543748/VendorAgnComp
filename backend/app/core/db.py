from sqlmodel import create_engine, Session
from sqlalchemy import event
from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=True, connect_args=connect_args)


# Phase 7a: Enable SQLite foreign-key enforcement.
# SQLite ignores FK constraints by default; this listener fires the PRAGMA
# on every new connection so cascading deletes (Device → ParseRun,
# NormalizedField, FindingDB) actually work.
@event.listens_for(engine, "connect")
def _enable_fk(dbapi_conn, _):
    if settings.DATABASE_URL.startswith("sqlite"):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


def get_session():
    with Session(engine) as session:
        yield session
