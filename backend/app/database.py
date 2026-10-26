from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def criar_engine(url: str, **kwargs):
    eng = create_engine(url, connect_args={"check_same_thread": False}, **kwargs)

    @event.listens_for(eng, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if ":memory:" not in url:
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return eng


engine = criar_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def nova_sessao():
    """Abre uma sessão usando a fábrica atual (os testes podem trocá-la)."""
    import app.database as mod

    return mod.SessionLocal()


def get_db():
    db = nova_sessao()
    try:
        yield db
    finally:
        db.close()
