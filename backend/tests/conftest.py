import os
import tempfile

import pytest

# Banco e uploads isolados antes de importar o app
_TMP = tempfile.mkdtemp(prefix="patrimonio-test-")
os.environ["PATRIMONIO_DATA_DIR"] = _TMP
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_INTERVALO_SEGUNDOS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    database.Base.metadata.drop_all(database.engine)
    settings.gemini_api_key = ""
    with TestClient(app) as c:  # lifespan cria tabelas e categorias padrão
        yield c


@pytest.fixture()
def unidade(client):
    return client.post("/api/unidades", json={"nome": "Fórum Gama", "sigla": "GAMA"}).json()


@pytest.fixture()
def cat(client):
    cats = client.get("/api/categorias").json()
    return {c["slug"]: c for c in cats}
