import os
import tempfile

import pytest

# Banco e uploads isolados antes de importar o app
_TMP = tempfile.mkdtemp(prefix="patrimonio-test-")
os.environ["PATRIMONIO_DATA_DIR"] = _TMP
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_INTERVALO_SEGUNDOS"] = "0"
os.environ["IA_PROVEDOR"] = "ollama"
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"  # porta fechada: Ollama "desligado" nos testes

from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    database.Base.metadata.drop_all(database.engine)
    settings.gemini_api_key = ""
    settings.ia_provedor = "ollama"
    settings.ollama_url = "http://127.0.0.1:9"
    settings.ollama_modelo = "qwen2.5:7b"
    with TestClient(app) as c:  # lifespan cria tabelas e categorias padrão
        yield c


@pytest.fixture()
def unidade(client):
    return client.post("/api/unidades", json={"nome": "Unidade Centro", "sigla": "UC"}).json()


@pytest.fixture()
def cat(client):
    cats = client.get("/api/categorias").json()
    return {c["slug"]: c for c in cats}
