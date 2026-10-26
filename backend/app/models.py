"""Modelo de dados — ver docs/ARQUITETURA.md."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

STATUS = ["em_estoque", "em_uso", "em_manutencao", "com_defeito", "arquivado"]
STATUS_ROTULO = {
    "em_estoque": "Em estoque",
    "em_uso": "Em uso",
    "em_manutencao": "Em manutenção",
    "com_defeito": "Com defeito",
    "arquivado": "Arquivado",
}
TIPOS_CAMPO = ["texto", "numero", "data", "bool", "ip", "mac", "telefone", "lista"]
ORIGENS = ["manual", "planilha", "ia", "regras"]


def agora() -> datetime:
    return datetime.now().replace(microsecond=0)


class Categoria(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    icone: Mapped[str | None] = mapped_column(String(40))
    descricao: Mapped[str | None] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    campos: Mapped[list[Campo]] = relationship(
        back_populates="categoria", order_by="Campo.ordem", cascade="all, delete-orphan"
    )


class Campo(Base):
    __tablename__ = "campo"
    __table_args__ = (UniqueConstraint("categoria_id", "chave"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    chave: Mapped[str] = mapped_column(String(60))
    rotulo: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(20), default="texto")
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    unico: Mapped[bool] = mapped_column(Boolean, default=False)
    filtravel: Mapped[bool] = mapped_column(Boolean, default=False)
    opcoes: Mapped[list] = mapped_column(JSON, default=list)
    sinonimos: Mapped[list] = mapped_column(JSON, default=list)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    categoria: Mapped[Categoria] = relationship(back_populates="campos")


class Unidade(Base):
    __tablename__ = "unidade"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    sigla: Mapped[str | None] = mapped_column(String(30))
    endereco: Mapped[str | None] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    setores: Mapped[list[Setor]] = relationship(
        back_populates="unidade", order_by="Setor.nome"
    )


class Setor(Base):
    __tablename__ = "setor"
    __table_args__ = (UniqueConstraint("unidade_id", "nome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"))
    nome: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    unidade: Mapped[Unidade] = relationship(back_populates="setores")


class Pessoa(Base):
    __tablename__ = "pessoa"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    matricula: Mapped[str | None] = mapped_column(String(40), unique=True)
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"))
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setor.id"))
    email: Mapped[str | None] = mapped_column(String(150))
    telefone: Mapped[str | None] = mapped_column(String(40))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    unidade: Mapped[Unidade | None] = relationship()
    setor: Mapped[Setor | None] = relationship()


class Ativo(Base):
    __tablename__ = "ativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    patrimonio: Mapped[str | None] = mapped_column(String(60), unique=True)
    nome: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default="em_estoque", index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"))
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setor.id"))
    pessoa_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))
    observacao: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(String(20), default="manual")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=agora, onupdate=agora)
    arquivado_em: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    motivo_arquivo: Mapped[str | None] = mapped_column(Text)

    categoria: Mapped[Categoria] = relationship()
    unidade: Mapped[Unidade] = relationship()
    setor: Mapped[Setor | None] = relationship()
    pessoa: Mapped[Pessoa | None] = relationship()
    valores: Mapped[list[AtivoValor]] = relationship(
        back_populates="ativo", cascade="all, delete-orphan"
    )


class AtivoValor(Base):
    __tablename__ = "ativo_valor"
    __table_args__ = (
        UniqueConstraint("ativo_id", "campo_id"),
        Index("ix_valor_campo_texto", "campo_id", "valor_texto"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    campo_id: Mapped[int] = mapped_column(ForeignKey("campo.id"))
    valor_texto: Mapped[str | None] = mapped_column(Text)
    valor_numero: Mapped[float | None] = mapped_column(Float)
    valor_data: Mapped[date | None] = mapped_column(Date)

    ativo: Mapped[Ativo] = relationship(back_populates="valores")
    campo: Mapped[Campo] = relationship()


class Movimentacao(Base):
    __tablename__ = "movimentacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # cadastro|transferencia|status|arquivamento|restauracao
    status_anterior: Mapped[str | None] = mapped_column(String(20))
    status_novo: Mapped[str | None] = mapped_column(String(20))
    unidade_origem_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"))
    unidade_destino_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"))
    setor_origem_id: Mapped[int | None] = mapped_column(ForeignKey("setor.id"))
    setor_destino_id: Mapped[int | None] = mapped_column(ForeignKey("setor.id"))
    pessoa_origem_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))
    pessoa_destino_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))
    data: Mapped[datetime] = mapped_column(DateTime, default=agora)
    observacao: Mapped[str | None] = mapped_column(Text)

    ativo: Mapped[Ativo] = relationship()
    unidade_origem: Mapped[Unidade | None] = relationship(foreign_keys=[unidade_origem_id])
    unidade_destino: Mapped[Unidade | None] = relationship(foreign_keys=[unidade_destino_id])
    setor_origem: Mapped[Setor | None] = relationship(foreign_keys=[setor_origem_id])
    setor_destino: Mapped[Setor | None] = relationship(foreign_keys=[setor_destino_id])
    pessoa_origem: Mapped[Pessoa | None] = relationship(foreign_keys=[pessoa_origem_id])
    pessoa_destino: Mapped[Pessoa | None] = relationship(foreign_keys=[pessoa_destino_id])


class Vinculo(Base):
    __tablename__ = "vinculo"
    __table_args__ = (UniqueConstraint("ativo_origem_id", "ativo_destino_id", "tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_origem_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    ativo_destino_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(40), default="outro")
    observacao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    origem: Mapped[Ativo] = relationship(foreign_keys=[ativo_origem_id])
    destino: Mapped[Ativo] = relationship(foreign_keys=[ativo_destino_id])


class Importacao(Base):
    __tablename__ = "importacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    arquivo_nome: Mapped[str] = mapped_column(String(255))
    arquivo_hash: Mapped[str] = mapped_column(String(64), index=True)
    formato: Mapped[str] = mapped_column(String(20))  # xlsx|csv|txt|whatsapp|pdf
    metodo: Mapped[str] = mapped_column(String(20))  # mapeamento|ia|regras
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    unidade_padrao_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"))
    # mapeamento|processando|revisao|concluida|erro
    status: Mapped[str] = mapped_column(String(20), default="processando")
    total_itens: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime)

    categoria: Mapped[Categoria | None] = relationship()
    unidade_padrao: Mapped[Unidade | None] = relationship()
    itens: Mapped[list[ImportacaoItem]] = relationship(
        back_populates="importacao", order_by="ImportacaoItem.ordem", cascade="all, delete-orphan"
    )


class ImportacaoItem(Base):
    __tablename__ = "importacao_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    importacao_id: Mapped[int] = mapped_column(ForeignKey("importacao.id"), index=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    trecho_original: Mapped[str] = mapped_column(Text, default="")
    origem_trecho: Mapped[str | None] = mapped_column(String(120))
    categoria_sugerida_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    dados_extraidos: Mapped[dict] = mapped_column(JSON, default=dict)
    confianca: Mapped[float] = mapped_column(Float, default=0.0)
    # pendente|aprovado|rejeitado|duplicado
    status: Mapped[str] = mapped_column(String(20), default="pendente", index=True)
    motivo_duplicado: Mapped[str | None] = mapped_column(String(40))
    ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"))
    mensagens: Mapped[list] = mapped_column(JSON, default=list)

    importacao: Mapped[Importacao] = relationship(back_populates="itens")
    categoria_sugerida: Mapped[Categoria | None] = relationship()


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (Index("ix_auditoria_entidade", "entidade", "entidade_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entidade: Mapped[str] = mapped_column(String(40))
    entidade_id: Mapped[int] = mapped_column(Integer)
    acao: Mapped[str] = mapped_column(String(40))
    antes: Mapped[dict | None] = mapped_column(JSON)
    depois: Mapped[dict | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
