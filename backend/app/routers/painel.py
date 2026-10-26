"""Dashboard e configurações."""
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..config import salvar_env, settings
from ..database import get_db
from ..schemas import ConfigGeminiIn, ConfigOut, MovimentacaoOut

router = APIRouter(tags=["painel"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    ativos = m.Ativo.arquivado_em.is_(None)
    total = db.scalar(select(func.count(m.Ativo.id)).where(ativos)) or 0
    arquivados = db.scalar(select(func.count(m.Ativo.id)).where(m.Ativo.arquivado_em.is_not(None))) or 0

    por_status = {s: 0 for s in m.STATUS if s != "arquivado"}
    for status, n in db.execute(select(m.Ativo.status, func.count()).where(ativos).group_by(m.Ativo.status)):
        por_status[status] = n

    por_categoria = [
        {"id": cid, "nome": nome, "icone": icone, "total": n}
        for cid, nome, icone, n in db.execute(
            select(m.Categoria.id, m.Categoria.nome, m.Categoria.icone, func.count(m.Ativo.id))
            .join(m.Ativo, (m.Ativo.categoria_id == m.Categoria.id) & ativos, isouter=True)
            .group_by(m.Categoria.id).order_by(func.count(m.Ativo.id).desc(), m.Categoria.nome))
    ]
    por_unidade = [
        {"id": uid, "nome": nome, "total": n, "com_defeito": d or 0}
        for uid, nome, n, d in db.execute(
            select(m.Unidade.id, m.Unidade.nome, func.count(m.Ativo.id),
                   func.sum(case((m.Ativo.status == "com_defeito", 1), else_=0)))
            .join(m.Ativo, m.Ativo.unidade_id == m.Unidade.id)
            .where(ativos).group_by(m.Unidade.id).order_by(func.count(m.Ativo.id).desc()).limit(15))
    ]
    pendentes = db.scalar(select(func.count(m.ImportacaoItem.id)).join(m.Importacao)
                          .where(m.ImportacaoItem.status == "pendente", m.Importacao.status == "revisao")) or 0
    importacoes_revisao = db.scalar(select(func.count(m.Importacao.id))
                                    .where(m.Importacao.status.in_(["revisao", "mapeamento", "processando"]))) or 0
    sem_pessoa = db.scalar(select(func.count(m.Ativo.id)).where(ativos, m.Ativo.pessoa_id.is_(None))) or 0
    movs = db.scalars(select(m.Movimentacao)
                      .options(selectinload(m.Movimentacao.ativo).selectinload(m.Ativo.categoria),
                               *(selectinload(getattr(m.Movimentacao, r)) for r in (
                                   "unidade_origem", "unidade_destino", "setor_origem", "setor_destino",
                                   "pessoa_origem", "pessoa_destino")))
                      .order_by(m.Movimentacao.id.desc()).limit(10)).all()
    ultimas = []
    for mv in movs:
        d = MovimentacaoOut.model_validate(mv).model_dump()
        d["ativo"] = {"id": mv.ativo.id, "nome": mv.ativo.nome, "patrimonio": mv.ativo.patrimonio,
                      "categoria": mv.ativo.categoria.nome}
        ultimas.append(d)

    return {
        "total": total,
        "arquivados": arquivados,
        "por_status": por_status,
        "por_categoria": por_categoria,
        "por_unidade": por_unidade,
        "itens_pendentes_revisao": pendentes,
        "importacoes_abertas": importacoes_revisao,
        "sem_pessoa": sem_pessoa,
        "ultimas_movimentacoes": ultimas,
    }


def _mascarar(chave: str) -> str | None:
    if not chave:
        return None
    return chave[:4] + "…" + chave[-4:] if len(chave) > 10 else "…"


@router.get("/config", response_model=ConfigOut)
def ler_config():
    return {"gemini_configurado": bool(settings.gemini_api_key), "gemini_modelo": settings.gemini_model,
            "gemini_chave_mascarada": _mascarar(settings.gemini_api_key)}


@router.put("/config/gemini", response_model=ConfigOut)
def salvar_config(dados: ConfigGeminiIn):
    """Grava a chave no backend/.env (o sistema roda local)."""
    novas = {}
    if dados.api_key is not None:
        settings.gemini_api_key = dados.api_key
        novas["GEMINI_API_KEY"] = dados.api_key
    if dados.modelo:
        settings.gemini_model = dados.modelo
        novas["GEMINI_MODEL"] = dados.modelo
    if novas:
        salvar_env(novas)
    return ler_config()
