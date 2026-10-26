"""Regras de negócio dos objetos (ativos): cadastro, edição, posse, status e arquivamento."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..schemas import AtivoCriar, AtivoAtualizar
from . import auditoria
from .validacao import ErroValidacao, converter, valor_para_saida, vazio


# ---------- leitura ----------
def carregar(db: Session, ativo_id: int) -> m.Ativo:
    ativo = db.scalar(
        select(m.Ativo)
        .where(m.Ativo.id == ativo_id)
        .options(
            selectinload(m.Ativo.valores).selectinload(m.AtivoValor.campo),
            selectinload(m.Ativo.categoria),
            selectinload(m.Ativo.unidade),
            selectinload(m.Ativo.setor),
            selectinload(m.Ativo.pessoa),
        )
    )
    if not ativo:
        raise HTTPException(404, "Objeto não encontrado")
    return ativo


def valores_dict(ativo: m.Ativo) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for v in ativo.valores:
        out[v.campo.chave] = valor_para_saida(v.campo.tipo, v.valor_texto, v.valor_numero)
    return out


def serializar(ativo: m.Ativo) -> dict:
    ref = lambda o: {"id": o.id, "nome": o.nome} if o else None  # noqa: E731
    return {
        "id": ativo.id,
        "categoria": {
            "id": ativo.categoria.id,
            "nome": ativo.categoria.nome,
            "slug": ativo.categoria.slug,
            "icone": ativo.categoria.icone,
        },
        "patrimonio": ativo.patrimonio,
        "nome": ativo.nome,
        "status": ativo.status,
        "unidade": ref(ativo.unidade),
        "setor": ref(ativo.setor),
        "pessoa": ref(ativo.pessoa),
        "observacao": ativo.observacao,
        "origem": ativo.origem,
        "criado_em": ativo.criado_em,
        "atualizado_em": ativo.atualizado_em,
        "arquivado_em": ativo.arquivado_em,
        "motivo_arquivo": ativo.motivo_arquivo,
        "valores": valores_dict(ativo),
    }


def snapshot(ativo: m.Ativo) -> dict:
    return {
        "patrimonio": ativo.patrimonio,
        "nome": ativo.nome,
        "status": ativo.status,
        "unidade_id": ativo.unidade_id,
        "setor_id": ativo.setor_id,
        "pessoa_id": ativo.pessoa_id,
        "observacao": ativo.observacao,
        "valores": {v.campo.chave: v.valor_texto for v in ativo.valores},
    }


# ---------- validações ----------
def _limpar(texto: str | None) -> str | None:
    if texto is None:
        return None
    texto = str(texto).strip()
    return texto or None


def validar_patrimonio(db: Session, patrimonio: str | None, ativo_id: int | None = None) -> str | None:
    patrimonio = _limpar(patrimonio)
    if patrimonio is None:
        return None
    existente = db.scalar(select(m.Ativo).where(m.Ativo.patrimonio == patrimonio))
    if existente and existente.id != ativo_id:
        raise ErroValidacao(
            {"patrimonio": f"Patrimônio {patrimonio} já está cadastrado (objeto #{existente.id})"}
        )
    return patrimonio


def validar_posse(db: Session, unidade_id: int, setor_id: int | None, pessoa_id: int | None):
    unidade = db.get(m.Unidade, unidade_id)
    if not unidade:
        raise ErroValidacao({"unidade_id": "Unidade não encontrada"})
    if setor_id is not None:
        setor = db.get(m.Setor, setor_id)
        if not setor:
            raise ErroValidacao({"setor_id": "Setor não encontrado"})
        if setor.unidade_id != unidade_id:
            raise ErroValidacao({"setor_id": f"O setor “{setor.nome}” não pertence a esta unidade"})
    if pessoa_id is not None and not db.get(m.Pessoa, pessoa_id):
        raise ErroValidacao({"pessoa_id": "Pessoa não encontrada"})


def converter_valores(
    db: Session,
    categoria: m.Categoria,
    valores: dict[str, Any],
    ativo_id: int | None = None,
    existentes: dict[str, Any] | None = None,
) -> dict[int, tuple[str, float | None, Any] | None]:
    """Valida os valores informados contra os campos da categoria.

    Retorna {campo_id: (texto, numero, data)} — None significa apagar o valor.
    `existentes` são os valores atuais (para checar obrigatórios em edições parciais).
    """
    campos = {c.chave: c for c in categoria.campos if c.ativo}
    erros: dict[str, str] = {}
    resultado: dict[int, tuple | None] = {}

    for chave in valores:
        if chave not in campos:
            erros[chave] = f"O campo “{chave}” não existe na categoria {categoria.nome}"

    for chave, campo in campos.items():
        informado = chave in valores
        bruto = valores.get(chave) if informado else (existentes or {}).get(chave)
        if vazio(bruto):
            if campo.obrigatorio:
                erros[chave] = f"{campo.rotulo} é obrigatório"
            elif informado:
                resultado[campo.id] = None
            continue
        if not informado:
            continue
        try:
            texto, numero, data = converter(campo.tipo, bruto, campo.opcoes)
        except ValueError as e:
            erros[chave] = f"{campo.rotulo}: {e}"
            continue
        if campo.unico:
            q = (
                select(m.Ativo.id)
                .join(m.AtivoValor, m.AtivoValor.ativo_id == m.Ativo.id)
                .where(
                    m.AtivoValor.campo_id == campo.id,
                    m.AtivoValor.valor_texto == texto,
                    m.Ativo.arquivado_em.is_(None),
                )
            )
            if ativo_id:
                q = q.where(m.Ativo.id != ativo_id)
            outro = db.scalar(q)
            if outro:
                erros[chave] = f"{campo.rotulo} “{texto}” já está em uso no objeto #{outro}"
                continue
        resultado[campo.id] = (texto, numero, data)

    if erros:
        raise ErroValidacao(erros)
    return resultado


def _gravar_valores(ativo: m.Ativo, convertidos: dict[int, tuple | None]) -> None:
    atuais = {v.campo_id: v for v in ativo.valores}
    for campo_id, conv in convertidos.items():
        if conv is None:
            if campo_id in atuais:
                ativo.valores.remove(atuais[campo_id])
            continue
        texto, numero, data = conv
        if campo_id in atuais:
            v = atuais[campo_id]
            v.valor_texto, v.valor_numero, v.valor_data = texto, numero, data
        else:
            ativo.valores.append(
                m.AtivoValor(campo_id=campo_id, valor_texto=texto, valor_numero=numero, valor_data=data)
            )


# ---------- escrita ----------
def criar(db: Session, dados: AtivoCriar, origem: str = "manual") -> m.Ativo:
    categoria = db.get(m.Categoria, dados.categoria_id)
    if not categoria:
        raise ErroValidacao({"categoria_id": "Categoria não encontrada"})
    erros: dict[str, str] = {}
    patrimonio = None
    try:
        patrimonio = validar_patrimonio(db, dados.patrimonio)
    except ErroValidacao as e:
        erros.update(e.erros)
    try:
        validar_posse(db, dados.unidade_id, dados.setor_id, dados.pessoa_id)
    except ErroValidacao as e:
        erros.update(e.erros)
    convertidos: dict = {}
    try:
        convertidos = converter_valores(db, categoria, dados.valores)
    except ErroValidacao as e:
        erros.update(e.erros)
    if erros:
        raise ErroValidacao(erros)

    ativo = m.Ativo(
        categoria_id=categoria.id,
        patrimonio=patrimonio,
        nome=_limpar(dados.nome),
        status=dados.status,
        unidade_id=dados.unidade_id,
        setor_id=dados.setor_id,
        pessoa_id=dados.pessoa_id,
        observacao=_limpar(dados.observacao),
        origem=origem,
    )
    db.add(ativo)
    db.flush()
    _gravar_valores(ativo, convertidos)
    db.add(
        m.Movimentacao(
            ativo_id=ativo.id,
            tipo="cadastro",
            status_novo=ativo.status,
            unidade_destino_id=ativo.unidade_id,
            setor_destino_id=ativo.setor_id,
            pessoa_destino_id=ativo.pessoa_id,
            observacao=f"Cadastrado ({origem})",
        )
    )
    db.flush()
    db.refresh(ativo)
    auditoria.registrar(db, "ativo", ativo.id, "criar", None, snapshot(ativo))
    return ativo


def atualizar(db: Session, ativo: m.Ativo, dados: AtivoAtualizar) -> m.Ativo:
    antes = snapshot(ativo)
    enviados = dados.model_fields_set
    erros: dict[str, str] = {}
    if "patrimonio" in enviados:
        try:
            ativo.patrimonio = validar_patrimonio(db, dados.patrimonio, ativo.id)
        except ErroValidacao as e:
            erros.update(e.erros)
    if "nome" in enviados:
        ativo.nome = _limpar(dados.nome)
    if "observacao" in enviados:
        ativo.observacao = _limpar(dados.observacao)
    if dados.valores is not None:
        try:
            convertidos = converter_valores(
                db, ativo.categoria, dados.valores, ativo.id, valores_dict(ativo)
            )
            _gravar_valores(ativo, convertidos)
        except ErroValidacao as e:
            erros.update(e.erros)
    if erros:
        db.rollback()
        raise ErroValidacao(erros)
    db.flush()
    db.refresh(ativo)
    depois = snapshot(ativo)
    if depois != antes:
        auditoria.registrar(db, "ativo", ativo.id, "editar", antes, depois)
    return ativo


def _exigir_nao_arquivado(ativo: m.Ativo) -> None:
    if ativo.arquivado_em is not None:
        raise HTTPException(409, "Objeto arquivado. Restaure antes de alterar.")


def transferir(db: Session, ativo: m.Ativo, unidade_id: int, setor_id: int | None,
               pessoa_id: int | None, observacao: str | None) -> m.Ativo:
    _exigir_nao_arquivado(ativo)
    validar_posse(db, unidade_id, setor_id, pessoa_id)
    if (ativo.unidade_id, ativo.setor_id, ativo.pessoa_id) == (unidade_id, setor_id, pessoa_id):
        raise HTTPException(400, "A posse informada é igual à atual")
    antes = snapshot(ativo)
    db.add(
        m.Movimentacao(
            ativo_id=ativo.id,
            tipo="transferencia",
            unidade_origem_id=ativo.unidade_id,
            unidade_destino_id=unidade_id,
            setor_origem_id=ativo.setor_id,
            setor_destino_id=setor_id,
            pessoa_origem_id=ativo.pessoa_id,
            pessoa_destino_id=pessoa_id,
            observacao=_limpar(observacao),
        )
    )
    ativo.unidade_id, ativo.setor_id, ativo.pessoa_id = unidade_id, setor_id, pessoa_id
    db.flush()
    db.refresh(ativo)
    auditoria.registrar(db, "ativo", ativo.id, "transferir", antes, snapshot(ativo))
    return ativo


def mudar_status(db: Session, ativo: m.Ativo, status: str, observacao: str | None) -> m.Ativo:
    _exigir_nao_arquivado(ativo)
    if status == ativo.status:
        raise HTTPException(400, "O objeto já está com esse status")
    antes = snapshot(ativo)
    db.add(
        m.Movimentacao(
            ativo_id=ativo.id,
            tipo="status",
            status_anterior=ativo.status,
            status_novo=status,
            observacao=_limpar(observacao),
        )
    )
    ativo.status = status
    db.flush()
    auditoria.registrar(db, "ativo", ativo.id, "status", antes, snapshot(ativo))
    return ativo


def arquivar(db: Session, ativo: m.Ativo, motivo: str) -> m.Ativo:
    _exigir_nao_arquivado(ativo)
    if ativo.status not in ("com_defeito", "em_manutencao"):
        raise HTTPException(
            409,
            "Só é possível arquivar um objeto com defeito ou em manutenção. "
            "Marque como “com defeito” antes de arquivar.",
        )
    antes = snapshot(ativo)
    db.add(
        m.Movimentacao(
            ativo_id=ativo.id,
            tipo="arquivamento",
            status_anterior=ativo.status,
            status_novo="arquivado",
            observacao=motivo.strip(),
        )
    )
    ativo.status = "arquivado"
    ativo.arquivado_em = m.agora()
    ativo.motivo_arquivo = motivo.strip()
    db.flush()
    auditoria.registrar(db, "ativo", ativo.id, "arquivar", antes, snapshot(ativo))
    return ativo


def restaurar(db: Session, ativo: m.Ativo, observacao: str | None) -> m.Ativo:
    if ativo.arquivado_em is None:
        raise HTTPException(409, "O objeto não está arquivado")
    # Um campo único pode ter sido reutilizado enquanto o objeto estava arquivado.
    conflitos: dict[str, str] = {}
    for v in ativo.valores:
        if not v.campo.unico or v.valor_texto is None:
            continue
        outro = db.scalar(
            select(m.Ativo.id)
            .join(m.AtivoValor, m.AtivoValor.ativo_id == m.Ativo.id)
            .where(
                m.AtivoValor.campo_id == v.campo_id,
                m.AtivoValor.valor_texto == v.valor_texto,
                m.Ativo.arquivado_em.is_(None),
                m.Ativo.id != ativo.id,
            )
        )
        if outro:
            conflitos[v.campo.chave] = (
                f"{v.campo.rotulo} “{v.valor_texto}” agora está em uso no objeto #{outro}"
            )
    if conflitos:
        raise ErroValidacao(conflitos, "Não foi possível restaurar")
    antes = snapshot(ativo)
    db.add(
        m.Movimentacao(
            ativo_id=ativo.id,
            tipo="restauracao",
            status_anterior="arquivado",
            status_novo="em_estoque",
            observacao=_limpar(observacao),
        )
    )
    ativo.status = "em_estoque"
    ativo.arquivado_em = None
    ativo.motivo_arquivo = None
    db.flush()
    auditoria.registrar(db, "ativo", ativo.id, "restaurar", antes, snapshot(ativo))
    return ativo
