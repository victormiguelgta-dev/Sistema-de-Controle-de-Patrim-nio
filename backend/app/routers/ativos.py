from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..database import get_db
from ..schemas import (ArquivarIn, AtivoAtualizar, AtivoCriar, AtivoDetalhe, AtivoLista, AtivoOut,
                       AuditoriaOut, CampoOut, MovimentacaoOut, RestaurarIn, StatusIn, TransferirIn,
                       VinculoCriar)
from ..services import ativos as svc
from ..services import auditoria
from ..services.relatorio import gerar_pdf

router = APIRouter(tags=["objetos"])

ORDENACAO = {
    "patrimonio": m.Ativo.patrimonio,
    "nome": m.Ativo.nome,
    "status": m.Ativo.status,
    "criado_em": m.Ativo.criado_em,
    "atualizado_em": m.Ativo.atualizado_em,
    "arquivado_em": m.Ativo.arquivado_em,
}


def _consulta(request: Request, q: str | None, categoria_id: int | None, status: str | None,
              unidade_id: int | None, setor_id: int | None, pessoa_id: int | None, arquivados: bool):
    query = select(m.Ativo)
    filtros: list[str] = []
    if arquivados:
        query = query.where(m.Ativo.arquivado_em.is_not(None))
        filtros.append("arquivados")
    else:
        query = query.where(m.Ativo.arquivado_em.is_(None))
    if categoria_id:
        query = query.where(m.Ativo.categoria_id == categoria_id)
    if status:
        query = query.where(m.Ativo.status.in_(status.split(",")))
        filtros.append("status " + ", ".join(m.STATUS_ROTULO.get(s, s) for s in status.split(",")))
    if unidade_id:
        query = query.where(m.Ativo.unidade_id == unidade_id)
    if setor_id:
        query = query.where(m.Ativo.setor_id == setor_id)
    if pessoa_id:
        query = query.where(m.Ativo.pessoa_id == pessoa_id)
    if q and q.strip():
        termo = f"%{q.strip()}%"
        em_valores = select(m.AtivoValor.id).where(m.AtivoValor.ativo_id == m.Ativo.id,
                                                    m.AtivoValor.valor_texto.ilike(termo)).exists()
        query = query.where(or_(m.Ativo.patrimonio.ilike(termo), m.Ativo.nome.ilike(termo),
                                m.Ativo.observacao.ilike(termo), em_valores))
        filtros.append(f"busca “{q.strip()}”")
    # filtros dinâmicos: ?campo_<chave>=valor
    for nome, valor in request.query_params.items():
        if not nome.startswith("campo_") or not valor.strip():
            continue
        chave = nome[len("campo_"):]
        cond = (select(m.AtivoValor.id).join(m.Campo, m.Campo.id == m.AtivoValor.campo_id)
                .where(m.AtivoValor.ativo_id == m.Ativo.id, m.Campo.chave == chave,
                       m.AtivoValor.valor_texto.ilike(f"%{valor.strip()}%")).exists())
        query = query.where(cond)
        filtros.append(f"{chave} “{valor.strip()}”")
    return query, filtros


def _opcoes_carga():
    return (selectinload(m.Ativo.valores).selectinload(m.AtivoValor.campo), selectinload(m.Ativo.categoria),
            selectinload(m.Ativo.unidade), selectinload(m.Ativo.setor), selectinload(m.Ativo.pessoa))


@router.get("/ativos", response_model=AtivoLista)
def listar(request: Request, q: str | None = None, categoria_id: int | None = None, status: str | None = None,
           unidade_id: int | None = None, setor_id: int | None = None, pessoa_id: int | None = None,
           arquivados: bool = False, ordenar: str = "atualizado_em", direcao: str = "desc",
           pagina: int = 1, por_pagina: int = 50, db: Session = Depends(get_db)):
    query, _ = _consulta(request, q, categoria_id, status, unidade_id, setor_id, pessoa_id, arquivados)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    coluna = ORDENACAO.get(ordenar, m.Ativo.atualizado_em)
    ordem = coluna.asc() if direcao == "asc" else coluna.desc()
    por_pagina = max(1, min(por_pagina, 500))
    pagina = max(1, pagina)
    itens = db.scalars(query.options(*_opcoes_carga()).order_by(ordem, m.Ativo.id.desc())
                       .offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "itens": [svc.serializar(a) for a in itens]}


@router.get("/ativos/relatorio.pdf")
def relatorio(request: Request, q: str | None = None, categoria_id: int | None = None, status: str | None = None,
              unidade_id: int | None = None, setor_id: int | None = None, pessoa_id: int | None = None,
              arquivados: bool = False, db: Session = Depends(get_db)):
    query, filtros = _consulta(request, q, categoria_id, status, unidade_id, setor_id, pessoa_id, arquivados)
    itens = db.scalars(query.options(*_opcoes_carga()).order_by(m.Ativo.patrimonio, m.Ativo.id)).all()
    categoria = db.get(m.Categoria, categoria_id) if categoria_id else None
    if categoria:
        filtros.insert(0, f"categoria {categoria.nome}")
    for chave, modelo in (("unidade", m.Unidade), ("setor", m.Setor), ("pessoa", m.Pessoa)):
        ident = {"unidade": unidade_id, "setor": setor_id, "pessoa": pessoa_id}[chave]
        if ident and (obj := db.get(modelo, ident)):
            filtros.append(f"{chave} {obj.nome}")
    pdf = gerar_pdf(list(itens), filtros, categoria)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="relatorio-patrimonio.pdf"'})


@router.post("/ativos", response_model=AtivoOut, status_code=201)
def criar(dados: AtivoCriar, db: Session = Depends(get_db)):
    ativo = svc.criar(db, dados)
    db.commit()
    return svc.serializar(svc.carregar(db, ativo.id))


def _vinculos(db: Session, ativo_id: int) -> list[dict]:
    vinc = db.scalars(select(m.Vinculo).where(or_(m.Vinculo.ativo_origem_id == ativo_id,
                                                  m.Vinculo.ativo_destino_id == ativo_id))
                      .options(selectinload(m.Vinculo.origem).selectinload(m.Ativo.categoria),
                               selectinload(m.Vinculo.destino).selectinload(m.Ativo.categoria))
                      .order_by(m.Vinculo.criado_em.desc())).all()
    out = []
    for v in vinc:
        sou_origem = v.ativo_origem_id == ativo_id
        outro = v.destino if sou_origem else v.origem
        out.append({"id": v.id, "tipo": v.tipo, "observacao": v.observacao, "criado_em": v.criado_em,
                    "direcao": "origem" if sou_origem else "destino",
                    "outro": {"id": outro.id, "nome": outro.nome, "patrimonio": outro.patrimonio,
                              "categoria": outro.categoria.nome, "status": outro.status}})
    return out


@router.get("/ativos/{ativo_id}", response_model=AtivoDetalhe)
def detalhe(ativo_id: int, db: Session = Depends(get_db)):
    ativo = svc.carregar(db, ativo_id)
    movs = db.scalars(select(m.Movimentacao).where(m.Movimentacao.ativo_id == ativo_id)
                      .options(*(selectinload(getattr(m.Movimentacao, r)) for r in (
                          "unidade_origem", "unidade_destino", "setor_origem", "setor_destino",
                          "pessoa_origem", "pessoa_destino")))
                      .order_by(m.Movimentacao.data.desc(), m.Movimentacao.id.desc())).all()
    aud = db.scalars(select(m.Auditoria).where(m.Auditoria.entidade == "ativo", m.Auditoria.entidade_id == ativo_id)
                     .order_by(m.Auditoria.id.desc()).limit(100)).all()
    return {**svc.serializar(ativo),
            "campos": [CampoOut.model_validate(c) for c in ativo.categoria.campos],
            "movimentacoes": [MovimentacaoOut.model_validate(x) for x in movs],
            "vinculos": _vinculos(db, ativo_id),
            "auditoria": [AuditoriaOut.model_validate(x) for x in aud]}


@router.put("/ativos/{ativo_id}", response_model=AtivoOut)
def atualizar(ativo_id: int, dados: AtivoAtualizar, db: Session = Depends(get_db)):
    ativo = svc.carregar(db, ativo_id)
    if ativo.arquivado_em is not None:
        raise HTTPException(409, "Objeto arquivado. Restaure antes de editar.")
    svc.atualizar(db, ativo, dados)
    db.commit()
    return svc.serializar(svc.carregar(db, ativo_id))


@router.post("/ativos/{ativo_id}/transferir", response_model=AtivoOut)
def transferir(ativo_id: int, dados: TransferirIn, db: Session = Depends(get_db)):
    ativo = svc.carregar(db, ativo_id)
    svc.transferir(db, ativo, dados.unidade_id, dados.setor_id, dados.pessoa_id, dados.observacao)
    db.commit()
    return svc.serializar(svc.carregar(db, ativo_id))


@router.post("/ativos/{ativo_id}/status", response_model=AtivoOut)
def mudar_status(ativo_id: int, dados: StatusIn, db: Session = Depends(get_db)):
    ativo = svc.carregar(db, ativo_id)
    svc.mudar_status(db, ativo, dados.status, dados.observacao)
    db.commit()
    return svc.serializar(svc.carregar(db, ativo_id))


@router.post("/ativos/{ativo_id}/arquivar", response_model=AtivoOut)
def arquivar(ativo_id: int, dados: ArquivarIn, db: Session = Depends(get_db)):
    ativo = svc.carregar(db, ativo_id)
    svc.arquivar(db, ativo, dados.motivo)
    db.commit()
    return svc.serializar(svc.carregar(db, ativo_id))


@router.post("/ativos/{ativo_id}/restaurar", response_model=AtivoOut)
def restaurar(ativo_id: int, dados: RestaurarIn, db: Session = Depends(get_db)):
    ativo = svc.carregar(db, ativo_id)
    svc.restaurar(db, ativo, dados.observacao)
    db.commit()
    return svc.serializar(svc.carregar(db, ativo_id))


@router.post("/ativos/{ativo_id}/vinculos", status_code=201)
def vincular(ativo_id: int, dados: VinculoCriar, db: Session = Depends(get_db)):
    origem = svc.carregar(db, ativo_id)
    if dados.ativo_destino_id == ativo_id:
        raise HTTPException(400, "Um objeto não pode ser vinculado a ele mesmo")
    destino = db.get(m.Ativo, dados.ativo_destino_id)
    if not destino:
        raise HTTPException(404, "Objeto de destino não encontrado")
    tipo = dados.tipo.strip().lower()
    existe = db.scalar(select(m.Vinculo).where(
        or_((m.Vinculo.ativo_origem_id == origem.id) & (m.Vinculo.ativo_destino_id == destino.id),
            (m.Vinculo.ativo_origem_id == destino.id) & (m.Vinculo.ativo_destino_id == origem.id)),
        m.Vinculo.tipo == tipo))
    if existe:
        raise HTTPException(409, "Esses objetos já estão vinculados com esse tipo")
    v = m.Vinculo(ativo_origem_id=origem.id, ativo_destino_id=destino.id, tipo=tipo,
                  observacao=(dados.observacao or "").strip() or None)
    db.add(v)
    db.flush()
    info = {"vinculo_id": v.id, "tipo": tipo, "origem": origem.id, "destino": destino.id}
    auditoria.registrar(db, "ativo", origem.id, "vincular", None, info)
    auditoria.registrar(db, "ativo", destino.id, "vincular", None, info)
    db.commit()
    return {"id": v.id}


@router.delete("/vinculos/{vinculo_id}")
def desvincular(vinculo_id: int, db: Session = Depends(get_db)):
    v = db.get(m.Vinculo, vinculo_id)
    if not v:
        raise HTTPException(404, "Vínculo não encontrado")
    info = {"vinculo_id": v.id, "tipo": v.tipo, "origem": v.ativo_origem_id, "destino": v.ativo_destino_id}
    auditoria.registrar(db, "ativo", v.ativo_origem_id, "desvincular", info, None)
    auditoria.registrar(db, "ativo", v.ativo_destino_id, "desvincular", info, None)
    db.delete(v)
    db.commit()
    return {"resultado": "removido"}
