"""Unidades (Defensorias), setores e pessoas."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..database import get_db
from ..schemas import (PessoaAtualizar, PessoaCriar, PessoaOut, SetorAtualizar, SetorCriar, SetorOut,
                       UnidadeAtualizar, UnidadeCriar, UnidadeOut)
from ..services import auditoria

router = APIRouter(tags=["cadastros"])


def _limpo(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


# ---------- unidades ----------
def _unidade_out(db: Session, u: m.Unidade) -> UnidadeOut:
    out = UnidadeOut.model_validate(u)
    out.total_ativos = db.scalar(select(func.count(m.Ativo.id)).where(
        m.Ativo.unidade_id == u.id, m.Ativo.arquivado_em.is_(None))) or 0
    return out


@router.get("/unidades", response_model=list[UnidadeOut])
def listar_unidades(incluir_inativas: bool = False, db: Session = Depends(get_db)):
    q = select(m.Unidade).options(selectinload(m.Unidade.setores)).order_by(m.Unidade.nome)
    if not incluir_inativas:
        q = q.where(m.Unidade.ativa.is_(True))
    return [_unidade_out(db, u) for u in db.scalars(q).all()]


@router.post("/unidades", response_model=UnidadeOut, status_code=201)
def criar_unidade(dados: UnidadeCriar, db: Session = Depends(get_db)):
    nome = dados.nome.strip()
    if db.scalar(select(m.Unidade).where(func.lower(m.Unidade.nome) == nome.lower())):
        raise HTTPException(409, f"Já existe a unidade “{nome}”")
    u = m.Unidade(nome=nome, sigla=_limpo(dados.sigla), endereco=_limpo(dados.endereco))
    db.add(u)
    db.flush()
    auditoria.registrar(db, "unidade", u.id, "criar", None, {"nome": u.nome})
    db.commit()
    return _unidade_out(db, u)


@router.put("/unidades/{unidade_id}", response_model=UnidadeOut)
def atualizar_unidade(unidade_id: int, dados: UnidadeAtualizar, db: Session = Depends(get_db)):
    u = db.get(m.Unidade, unidade_id)
    if not u:
        raise HTTPException(404, "Unidade não encontrada")
    antes = {"nome": u.nome, "sigla": u.sigla, "endereco": u.endereco, "ativa": u.ativa}
    if dados.nome is not None:
        nome = dados.nome.strip()
        if db.scalar(select(m.Unidade).where(func.lower(m.Unidade.nome) == nome.lower(), m.Unidade.id != u.id)):
            raise HTTPException(409, f"Já existe a unidade “{nome}”")
        u.nome = nome
    for attr in ("sigla", "endereco"):
        if attr in dados.model_fields_set:
            setattr(u, attr, _limpo(getattr(dados, attr)))
    if dados.ativa is not None:
        u.ativa = dados.ativa
    auditoria.registrar(db, "unidade", u.id, "editar", antes,
                        {"nome": u.nome, "sigla": u.sigla, "endereco": u.endereco, "ativa": u.ativa})
    db.commit()
    return _unidade_out(db, u)


@router.post("/unidades/{unidade_id}/setores", response_model=SetorOut, status_code=201)
def criar_setor(unidade_id: int, dados: SetorCriar, db: Session = Depends(get_db)):
    u = db.get(m.Unidade, unidade_id)
    if not u:
        raise HTTPException(404, "Unidade não encontrada")
    nome = dados.nome.strip()
    if any(s.nome.lower() == nome.lower() for s in u.setores):
        raise HTTPException(409, f"A unidade já tem o setor “{nome}”")
    s = m.Setor(unidade_id=u.id, nome=nome)
    db.add(s)
    db.flush()
    auditoria.registrar(db, "setor", s.id, "criar", None, {"nome": s.nome, "unidade": u.nome})
    db.commit()
    return s


@router.put("/setores/{setor_id}", response_model=SetorOut)
def atualizar_setor(setor_id: int, dados: SetorAtualizar, db: Session = Depends(get_db)):
    s = db.get(m.Setor, setor_id)
    if not s:
        raise HTTPException(404, "Setor não encontrado")
    antes = {"nome": s.nome, "ativo": s.ativo}
    if dados.nome is not None:
        nome = dados.nome.strip()
        if db.scalar(select(m.Setor).where(m.Setor.unidade_id == s.unidade_id,
                                           func.lower(m.Setor.nome) == nome.lower(), m.Setor.id != s.id)):
            raise HTTPException(409, f"A unidade já tem o setor “{nome}”")
        s.nome = nome
    if dados.ativo is not None:
        s.ativo = dados.ativo
    auditoria.registrar(db, "setor", s.id, "editar", antes, {"nome": s.nome, "ativo": s.ativo})
    db.commit()
    return s


# ---------- pessoas ----------
def _validar_lotacao(db: Session, unidade_id: int | None, setor_id: int | None) -> None:
    if unidade_id is not None and not db.get(m.Unidade, unidade_id):
        raise HTTPException(400, "Unidade não encontrada")
    if setor_id is not None:
        s = db.get(m.Setor, setor_id)
        if not s:
            raise HTTPException(400, "Setor não encontrado")
        if unidade_id is None or s.unidade_id != unidade_id:
            raise HTTPException(400, "O setor precisa ser da unidade escolhida")


def _pessoa_out(p: m.Pessoa) -> PessoaOut:
    return PessoaOut.model_validate(p)


@router.get("/pessoas", response_model=list[PessoaOut])
def listar_pessoas(q: str | None = None, unidade_id: int | None = None, setor_id: int | None = None,
                   incluir_inativas: bool = False, db: Session = Depends(get_db)):
    query = select(m.Pessoa).options(selectinload(m.Pessoa.unidade), selectinload(m.Pessoa.setor)).order_by(m.Pessoa.nome)
    if q:
        termo = f"%{q.strip()}%"
        query = query.where(or_(m.Pessoa.nome.ilike(termo), m.Pessoa.matricula.ilike(termo)))
    if unidade_id:
        query = query.where(m.Pessoa.unidade_id == unidade_id)
    if setor_id:
        query = query.where(m.Pessoa.setor_id == setor_id)
    if not incluir_inativas:
        query = query.where(m.Pessoa.ativa.is_(True))
    return [_pessoa_out(p) for p in db.scalars(query).all()]


@router.post("/pessoas", response_model=PessoaOut, status_code=201)
def criar_pessoa(dados: PessoaCriar, db: Session = Depends(get_db)):
    _validar_lotacao(db, dados.unidade_id, dados.setor_id)
    p = m.Pessoa(nome=dados.nome.strip(), matricula=_limpo(dados.matricula), unidade_id=dados.unidade_id,
                 setor_id=dados.setor_id, email=_limpo(dados.email), telefone=_limpo(dados.telefone))
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Já existe uma pessoa com a matrícula “{dados.matricula}”")
    auditoria.registrar(db, "pessoa", p.id, "criar", None, {"nome": p.nome})
    db.commit()
    db.refresh(p)
    return _pessoa_out(p)


@router.put("/pessoas/{pessoa_id}", response_model=PessoaOut)
def atualizar_pessoa(pessoa_id: int, dados: PessoaAtualizar, db: Session = Depends(get_db)):
    p = db.get(m.Pessoa, pessoa_id)
    if not p:
        raise HTTPException(404, "Pessoa não encontrada")
    antes = PessoaOut.model_validate(p).model_dump(exclude={"unidade", "setor"})
    enviados = dados.model_fields_set
    unidade_id = dados.unidade_id if "unidade_id" in enviados else p.unidade_id
    setor_id = dados.setor_id if "setor_id" in enviados else p.setor_id
    _validar_lotacao(db, unidade_id, setor_id)
    if dados.nome is not None:
        p.nome = dados.nome.strip()
    for attr in ("matricula", "email", "telefone"):
        if attr in enviados:
            setattr(p, attr, _limpo(getattr(dados, attr)))
    p.unidade_id, p.setor_id = unidade_id, setor_id
    if dados.ativa is not None:
        p.ativa = dados.ativa
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Já existe uma pessoa com a matrícula “{dados.matricula}”")
    db.refresh(p)
    auditoria.registrar(db, "pessoa", p.id, "editar", antes,
                        PessoaOut.model_validate(p).model_dump(exclude={"unidade", "setor"}))
    db.commit()
    return _pessoa_out(p)
