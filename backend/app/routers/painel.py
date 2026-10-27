"""Dashboard e configurações."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..config import salvar_env, settings
from ..database import get_db
from ..schemas import ConfigIAIn, ConfigOut, MovimentacaoOut
from ..services.importacao import ia

router = APIRouter(tags=["painel"])

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def serie_mensal(db: Session, meses: int = 12) -> list[dict]:
    """Movimentações por mês nos últimos `meses` meses e o total de objetos ativos no fim de cada mês."""
    hoje = date.today()
    chaves = []
    ano, mes = hoje.year, hoje.month
    for _ in range(meses):
        chaves.append((ano, mes))
        ano, mes = (ano, mes - 1) if mes > 1 else (ano - 1, 12)
    chaves.reverse()
    serie = {k: {"cadastros": 0, "transferencias": 0, "defeitos": 0, "arquivados": 0} for k in chaves}
    saldo_antes = 0  # objetos ativos antes do primeiro mês da série
    for tipo, status_novo, data in db.execute(select(m.Movimentacao.tipo, m.Movimentacao.status_novo, m.Movimentacao.data)):
        k = (data.year, data.month)
        delta = 1 if tipo in ("cadastro", "restauracao") else -1 if tipo == "arquivamento" else 0
        if k < chaves[0]:
            saldo_antes += delta
            continue
        if k not in serie:
            continue
        if tipo == "cadastro":
            serie[k]["cadastros"] += 1
        elif tipo == "transferencia":
            serie[k]["transferencias"] += 1
        elif tipo == "status" and status_novo == "com_defeito":
            serie[k]["defeitos"] += 1
        elif tipo == "arquivamento":
            serie[k]["arquivados"] += 1
        serie[k]["_delta"] = serie[k].get("_delta", 0) + delta
    saida, saldo = [], saldo_antes
    for (a, mm) in chaves:
        d = serie[(a, mm)]
        saldo += d.pop("_delta", 0)
        saida.append({"mes": f"{a}-{mm:02d}", "rotulo": MESES[mm - 1], "ano": a, "ativos": saldo, **d})
    return saida


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
                      .order_by(m.Movimentacao.data.desc(), m.Movimentacao.id.desc()).limit(10)).all()
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
        "serie_mensal": serie_mensal(db),
    }


def _mascarar(chave: str) -> str | None:
    if not chave:
        return None
    return chave[:4] + "…" + chave[-4:] if len(chave) > 10 else "…"


@router.get("/config", response_model=ConfigOut)
def ler_config():
    status = ia.ollama_status()
    try:
        ia.verificar_pronto()
        problema = None
    except ia.ErroIA as e:
        problema = str(e)
    return {
        "ia_provedor": settings.ia_provedor if settings.ia_provedor in ("ollama", "gemini") else "ollama",
        "ia_pronta": problema is None,
        "ia_problema": problema,
        "ollama_url": settings.ollama_url,
        "ollama_modelo": settings.ollama_modelo,
        "ollama_rodando": status["rodando"],
        "ollama_modelos": status["modelos"],
        "gemini_configurado": bool(settings.gemini_api_key),
        "gemini_modelo": settings.gemini_model,
        "gemini_chave_mascarada": _mascarar(settings.gemini_api_key),
    }


@router.put("/config/ia", response_model=ConfigOut)
def salvar_config(dados: ConfigIAIn):
    """Grava a escolha no backend/.env (o sistema roda local)."""
    novas: dict[str, str] = {}
    if dados.provedor:
        settings.ia_provedor = dados.provedor
        novas["IA_PROVEDOR"] = dados.provedor
    if dados.ollama_url:
        settings.ollama_url = dados.ollama_url.rstrip("/")
        novas["OLLAMA_URL"] = settings.ollama_url
    if dados.ollama_modelo:
        settings.ollama_modelo = dados.ollama_modelo
        novas["OLLAMA_MODELO"] = dados.ollama_modelo
    if dados.gemini_api_key is not None:
        settings.gemini_api_key = dados.gemini_api_key
        novas["GEMINI_API_KEY"] = dados.gemini_api_key
    if dados.gemini_modelo:
        settings.gemini_model = dados.gemini_modelo
        novas["GEMINI_MODEL"] = dados.gemini_modelo
    if novas:
        salvar_env(novas)
    return ler_config()
