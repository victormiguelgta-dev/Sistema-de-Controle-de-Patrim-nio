from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..database import get_db
from ..schemas import (CampoAtualizar, CampoCriar, CampoOut, CategoriaAtualizar, CategoriaCriar,
                       CategoriaOut, OrdemIn)
from ..services import auditoria
from ..services.validacao import slugificar

router = APIRouter(tags=["categorias"])


def _lista_limpa(valores: list[str] | None) -> list[str]:
    vistos, out = set(), []
    for v in valores or []:
        v = str(v).strip()
        if v and v.lower() not in vistos:
            vistos.add(v.lower())
            out.append(v)
    return out


def _saida(db: Session, cat: m.Categoria) -> CategoriaOut:
    total = db.scalar(select(func.count(m.Ativo.id)).where(
        m.Ativo.categoria_id == cat.id, m.Ativo.arquivado_em.is_(None))) or 0
    out = CategoriaOut.model_validate(cat)
    out.total_ativos = total
    return out


def _obter(db: Session, categoria_id: int) -> m.Categoria:
    cat = db.scalar(select(m.Categoria).where(m.Categoria.id == categoria_id)
                    .options(selectinload(m.Categoria.campos)))
    if not cat:
        raise HTTPException(404, "Categoria não encontrada")
    return cat


def _novo_campo(cat: m.Categoria, dados: CampoCriar) -> m.Campo:
    chave = slugificar(dados.chave or dados.rotulo)
    if any(c.chave == chave for c in cat.campos):
        raise HTTPException(409, f"Já existe um campo com a chave “{chave}” nesta categoria")
    opcoes = _lista_limpa(dados.opcoes)
    if dados.tipo == "lista" and not opcoes:
        raise HTTPException(400, f"O campo “{dados.rotulo}” é do tipo lista e precisa de opções")
    ordem = dados.ordem if dados.ordem is not None else (max((c.ordem for c in cat.campos), default=-1) + 1)
    campo = m.Campo(chave=chave, rotulo=dados.rotulo.strip(), tipo=dados.tipo, obrigatorio=dados.obrigatorio,
                    unico=dados.unico, filtravel=dados.filtravel, opcoes=opcoes,
                    sinonimos=_lista_limpa(dados.sinonimos), ordem=ordem)
    cat.campos.append(campo)
    return campo


@router.get("/categorias", response_model=list[CategoriaOut])
def listar(incluir_inativas: bool = False, db: Session = Depends(get_db)):
    q = select(m.Categoria).options(selectinload(m.Categoria.campos)).order_by(m.Categoria.nome)
    if not incluir_inativas:
        q = q.where(m.Categoria.ativa.is_(True))
    return [_saida(db, c) for c in db.scalars(q).all()]


@router.get("/categorias/{categoria_id}", response_model=CategoriaOut)
def obter(categoria_id: int, db: Session = Depends(get_db)):
    return _saida(db, _obter(db, categoria_id))


@router.post("/categorias", response_model=CategoriaOut, status_code=201)
def criar(dados: CategoriaCriar, db: Session = Depends(get_db)):
    nome = dados.nome.strip()
    slug = slugificar(nome)
    if db.scalar(select(m.Categoria).where((func.lower(m.Categoria.nome) == nome.lower()) | (m.Categoria.slug == slug))):
        raise HTTPException(409, f"Já existe a categoria “{nome}”")
    cat = m.Categoria(nome=nome, slug=slug, icone=dados.icone, descricao=dados.descricao)
    db.add(cat)
    for campo in dados.campos:
        _novo_campo(cat, campo)
    db.flush()
    auditoria.registrar(db, "categoria", cat.id, "criar", None, {"nome": cat.nome})
    db.commit()
    return _saida(db, cat)


@router.put("/categorias/{categoria_id}", response_model=CategoriaOut)
def atualizar(categoria_id: int, dados: CategoriaAtualizar, db: Session = Depends(get_db)):
    cat = _obter(db, categoria_id)
    antes = {"nome": cat.nome, "icone": cat.icone, "descricao": cat.descricao, "ativa": cat.ativa}
    if dados.nome is not None and dados.nome.strip() != cat.nome:
        nome = dados.nome.strip()
        if db.scalar(select(m.Categoria).where(func.lower(m.Categoria.nome) == nome.lower(), m.Categoria.id != cat.id)):
            raise HTTPException(409, f"Já existe a categoria “{nome}”")
        cat.nome = nome  # o slug fica estável: a IA e as importações usam ele
    for attr in ("icone", "descricao", "ativa"):
        if attr in dados.model_fields_set:
            setattr(cat, attr, getattr(dados, attr))
    auditoria.registrar(db, "categoria", cat.id, "editar", antes,
                        {"nome": cat.nome, "icone": cat.icone, "descricao": cat.descricao, "ativa": cat.ativa})
    db.commit()
    return _saida(db, cat)


@router.post("/categorias/{categoria_id}/campos", response_model=CampoOut, status_code=201)
def criar_campo(categoria_id: int, dados: CampoCriar, db: Session = Depends(get_db)):
    cat = _obter(db, categoria_id)
    campo = _novo_campo(cat, dados)
    db.flush()
    auditoria.registrar(db, "campo", campo.id, "criar", None, {"categoria": cat.nome, "chave": campo.chave})
    db.commit()
    return campo


@router.put("/campos/{campo_id}", response_model=CampoOut)
def atualizar_campo(campo_id: int, dados: CampoAtualizar, db: Session = Depends(get_db)):
    campo = db.get(m.Campo, campo_id)
    if not campo:
        raise HTTPException(404, "Campo não encontrado")
    antes = CampoOut.model_validate(campo).model_dump()
    tem_valores = db.scalar(select(func.count(m.AtivoValor.id)).where(m.AtivoValor.campo_id == campo.id)) or 0
    if dados.tipo and dados.tipo != campo.tipo and tem_valores:
        raise HTTPException(409, f"Não dá para mudar o tipo: {tem_valores} objeto(s) já têm valor neste campo")
    if dados.unico and not campo.unico:
        repetido = db.execute(
            select(m.AtivoValor.valor_texto, func.count())
            .join(m.Ativo, m.Ativo.id == m.AtivoValor.ativo_id)
            .where(m.AtivoValor.campo_id == campo.id, m.Ativo.arquivado_em.is_(None))
            .group_by(m.AtivoValor.valor_texto).having(func.count() > 1).limit(1)
        ).first()
        if repetido:
            raise HTTPException(409, f"Não dá para tornar único: o valor “{repetido[0]}” aparece {repetido[1]} vezes")
    for attr in ("rotulo", "tipo", "obrigatorio", "unico", "filtravel", "ativo"):
        v = getattr(dados, attr)
        if v is not None:
            setattr(campo, attr, v.strip() if isinstance(v, str) and attr == "rotulo" else v)
    if dados.opcoes is not None:
        campo.opcoes = _lista_limpa(dados.opcoes)
    if dados.sinonimos is not None:
        campo.sinonimos = _lista_limpa(dados.sinonimos)
    if campo.tipo == "lista" and not campo.opcoes:
        raise HTTPException(400, "Campos do tipo lista precisam de opções")
    db.flush()
    auditoria.registrar(db, "campo", campo.id, "editar", antes, CampoOut.model_validate(campo).model_dump())
    db.commit()
    return campo


@router.delete("/campos/{campo_id}")
def remover_campo(campo_id: int, db: Session = Depends(get_db)):
    campo = db.get(m.Campo, campo_id)
    if not campo:
        raise HTTPException(404, "Campo não encontrado")
    tem_valores = db.scalar(select(func.count(m.AtivoValor.id)).where(m.AtivoValor.campo_id == campo.id)) or 0
    if tem_valores:
        campo.ativo = False
        auditoria.registrar(db, "campo", campo.id, "desativar", None, {"chave": campo.chave})
        db.commit()
        return {"resultado": "desativado",
                "mensagem": f"O campo tem valores em {tem_valores} objeto(s); foi desativado e os valores foram mantidos."}
    auditoria.registrar(db, "campo", campo.id, "remover", {"chave": campo.chave}, None)
    db.delete(campo)
    db.commit()
    return {"resultado": "removido", "mensagem": "Campo removido."}


@router.put("/categorias/{categoria_id}/ordem", response_model=CategoriaOut)
def reordenar(categoria_id: int, dados: OrdemIn, db: Session = Depends(get_db)):
    cat = _obter(db, categoria_id)
    por_id = {c.id: c for c in cat.campos}
    if set(dados.campo_ids) != set(por_id):
        raise HTTPException(400, "Envie todos os campos da categoria")
    for i, cid in enumerate(dados.campo_ids):
        por_id[cid].ordem = i
    db.commit()
    db.expire(cat)
    return _saida(db, _obter(db, categoria_id))
