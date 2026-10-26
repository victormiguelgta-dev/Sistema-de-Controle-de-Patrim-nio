"""API do Sistema de Controle de Patrimônio.

Rodar:  uvicorn app.main:app --reload   (dentro da pasta backend)
Docs:   http://localhost:8000/docs
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .config import settings
from .routers import ativos, cadastros, categorias, importacoes, painel
from .seed import criar_categorias
from .services.validacao import ErroValidacao

FRONT_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def iniciar_banco() -> None:
    settings.preparar_pastas()
    database.Base.metadata.create_all(database.engine)
    db = database.nova_sessao()
    try:
        criar_categorias(db)
        # importações que estavam rodando quando o servidor caiu
        from . import models as m
        for imp in db.query(m.Importacao).filter(m.Importacao.status == "processando").all():
            imp.status = "erro"
            imp.erro = "O servidor foi reiniciado durante o processamento. Envie o arquivo de novo."
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    iniciar_banco()
    yield


app = FastAPI(title="Sistema de Controle de Patrimônio", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"])


@app.exception_handler(ErroValidacao)
async def _erro_validacao(_request: Request, exc: ErroValidacao):
    return JSONResponse(status_code=422, content={"detail": {"mensagem": exc.mensagem, "erros": exc.erros}})


for r in (painel.router, categorias.router, cadastros.router, ativos.router, importacoes.router):
    app.include_router(r, prefix="/api")


@app.get("/api/saude")
def saude():
    return {"ok": True}


# Se o front foi compilado (npm run build), a própria API serve as telas.
if FRONT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONT_DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        alvo = FRONT_DIST / caminho
        if caminho and alvo.is_file() and FRONT_DIST in alvo.resolve().parents:
            return FileResponse(alvo)
        return FileResponse(FRONT_DIST / "index.html")
