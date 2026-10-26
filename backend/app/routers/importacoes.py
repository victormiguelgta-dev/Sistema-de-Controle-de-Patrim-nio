from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..database import get_db
from ..schemas import AprovarLoteIn, ImportacaoDetalhe, ImportacaoOut, ItemDadosIn, ItemOut, MapeamentoIn
from ..services.importacao import processamento as proc
from ..services.validacao import ErroValidacao

router = APIRouter(tags=["importações"])


def _obter(db: Session, importacao_id: int) -> m.Importacao:
    imp = db.scalar(select(m.Importacao).where(m.Importacao.id == importacao_id)
                    .options(selectinload(m.Importacao.itens), selectinload(m.Importacao.categoria)))
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    return imp


def _item(imp: m.Importacao, item_id: int) -> m.ImportacaoItem:
    item = next((i for i in imp.itens if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Item não encontrado nesta importação")
    return item


def _saida(imp: m.Importacao, com_itens: bool = False):
    base = ImportacaoOut.model_validate(imp).model_dump()
    base["contagem"] = proc.contagem(imp)
    if com_itens:
        base["itens"] = [ItemOut.model_validate(i).model_dump() for i in imp.itens]
    return base


@router.get("/importacoes", response_model=list[ImportacaoOut])
def listar(db: Session = Depends(get_db)):
    imps = db.scalars(select(m.Importacao).options(selectinload(m.Importacao.itens))
                      .order_by(m.Importacao.id.desc()).limit(200)).all()
    return [_saida(i) for i in imps]


@router.post("/importacoes", response_model=ImportacaoOut, status_code=201)
async def criar(background: BackgroundTasks, arquivo: UploadFile = File(...), metodo: str = Form("ia"),
                categoria_id: int | None = Form(None), unidade_padrao_id: int | None = Form(None),
                db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    imp, rodar_ia = proc.criar(db, arquivo.filename or "arquivo", conteudo, metodo,
                               categoria_id or None, unidade_padrao_id or None)
    db.commit()
    if rodar_ia:
        background.add_task(proc.processar_ia, imp.id)
    return _saida(_obter(db, imp.id))


@router.get("/importacoes/{importacao_id}", response_model=ImportacaoDetalhe)
def detalhe(importacao_id: int, db: Session = Depends(get_db)):
    return _saida(_obter(db, importacao_id), com_itens=True)


@router.post("/importacoes/{importacao_id}/mapeamento", response_model=ImportacaoDetalhe)
def mapear(importacao_id: int, dados: MapeamentoIn, db: Session = Depends(get_db)):
    imp = _obter(db, importacao_id)
    proc.aplicar_mapeamento(db, imp, dados.mapa)
    db.commit()
    return _saida(_obter(db, importacao_id), com_itens=True)


@router.put("/importacoes/{importacao_id}/itens/{item_id}", response_model=ItemOut)
def editar_item(importacao_id: int, item_id: int, dados: ItemDadosIn, db: Session = Depends(get_db)):
    imp = _obter(db, importacao_id)
    item = _item(imp, item_id)
    proc.editar_item(db, imp, item, dados.dados)
    db.commit()
    return item


@router.post("/importacoes/{importacao_id}/itens/{item_id}/aprovar", response_model=ItemOut)
def aprovar_item(importacao_id: int, item_id: int, db: Session = Depends(get_db)):
    imp = _obter(db, importacao_id)
    item = _item(imp, item_id)
    try:
        proc.aprovar_item(db, imp, item)
    except ErroValidacao:
        db.commit()  # guarda as mensagens de erro no item
        raise
    db.commit()
    return item


@router.post("/importacoes/{importacao_id}/itens/{item_id}/rejeitar", response_model=ItemOut)
def rejeitar_item(importacao_id: int, item_id: int, db: Session = Depends(get_db)):
    imp = _obter(db, importacao_id)
    item = _item(imp, item_id)
    proc.rejeitar_item(db, imp, item)
    db.commit()
    return item


@router.post("/importacoes/{importacao_id}/aprovar-lote")
def aprovar_lote(importacao_id: int, dados: AprovarLoteIn, db: Session = Depends(get_db)):
    imp = _obter(db, importacao_id)
    if imp.status != "revisao":
        raise HTTPException(409, "Esta importação não está em revisão")
    resultado = proc.aprovar_lote(db, imp, dados.confianca_minima)
    db.commit()
    return resultado
