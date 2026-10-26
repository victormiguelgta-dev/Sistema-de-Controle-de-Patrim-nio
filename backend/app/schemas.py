from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import TIPOS_CAMPO

TipoCampo = Literal["texto", "numero", "data", "bool", "ip", "mac", "telefone", "lista"]
StatusEditavel = Literal["em_estoque", "em_uso", "em_manutencao", "com_defeito"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Ref(ORM):
    id: int
    nome: str


# ---------- Categorias e campos ----------
class CampoCriar(BaseModel):
    rotulo: str = Field(min_length=1, max_length=80)
    chave: str | None = Field(default=None, max_length=60)
    tipo: TipoCampo = "texto"
    obrigatorio: bool = False
    unico: bool = False
    filtravel: bool = False
    opcoes: list[str] = []
    sinonimos: list[str] = []
    ordem: int | None = None


class CampoAtualizar(BaseModel):
    rotulo: str | None = Field(default=None, min_length=1, max_length=80)
    tipo: TipoCampo | None = None
    obrigatorio: bool | None = None
    unico: bool | None = None
    filtravel: bool | None = None
    opcoes: list[str] | None = None
    sinonimos: list[str] | None = None
    ativo: bool | None = None


class CampoOut(ORM):
    id: int
    categoria_id: int
    chave: str
    rotulo: str
    tipo: str
    obrigatorio: bool
    unico: bool
    filtravel: bool
    opcoes: list[str]
    sinonimos: list[str]
    ordem: int
    ativo: bool


class CategoriaCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    icone: str | None = None
    descricao: str | None = None
    campos: list[CampoCriar] = []


class CategoriaAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=80)
    icone: str | None = None
    descricao: str | None = None
    ativa: bool | None = None


class CategoriaOut(ORM):
    id: int
    nome: str
    slug: str
    icone: str | None
    descricao: str | None
    ativa: bool
    campos: list[CampoOut]
    total_ativos: int = 0


class OrdemIn(BaseModel):
    campo_ids: list[int]


# ---------- Unidades, setores, pessoas ----------
class SetorCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=120)


class SetorAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    ativo: bool | None = None


class SetorOut(ORM):
    id: int
    unidade_id: int
    nome: str
    ativo: bool


class UnidadeCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    sigla: str | None = None
    endereco: str | None = None


class UnidadeAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    sigla: str | None = None
    endereco: str | None = None
    ativa: bool | None = None


class UnidadeOut(ORM):
    id: int
    nome: str
    sigla: str | None
    endereco: str | None
    ativa: bool
    setores: list[SetorOut] = []
    total_ativos: int = 0


class PessoaCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    matricula: str | None = None
    unidade_id: int | None = None
    setor_id: int | None = None
    email: str | None = None
    telefone: str | None = None


class PessoaAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    matricula: str | None = None
    unidade_id: int | None = None
    setor_id: int | None = None
    email: str | None = None
    telefone: str | None = None
    ativa: bool | None = None


class PessoaOut(ORM):
    id: int
    nome: str
    matricula: str | None
    unidade_id: int | None
    setor_id: int | None
    email: str | None
    telefone: str | None
    ativa: bool
    unidade: Ref | None = None
    setor: Ref | None = None


# ---------- Ativos ----------
class AtivoCriar(BaseModel):
    categoria_id: int
    patrimonio: str | None = None
    nome: str | None = None
    status: StatusEditavel = "em_estoque"
    unidade_id: int
    setor_id: int | None = None
    pessoa_id: int | None = None
    observacao: str | None = None
    valores: dict[str, Any] = {}


class AtivoAtualizar(BaseModel):
    patrimonio: str | None = None
    nome: str | None = None
    observacao: str | None = None
    valores: dict[str, Any] | None = None


class CategoriaRef(ORM):
    id: int
    nome: str
    slug: str
    icone: str | None


class AtivoOut(BaseModel):
    id: int
    categoria: CategoriaRef
    patrimonio: str | None
    nome: str | None
    status: str
    unidade: Ref
    setor: Ref | None
    pessoa: Ref | None
    observacao: str | None
    origem: str
    criado_em: datetime
    atualizado_em: datetime
    arquivado_em: datetime | None
    motivo_arquivo: str | None
    valores: dict[str, Any]


class AtivoLista(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[AtivoOut]


class TransferirIn(BaseModel):
    unidade_id: int
    setor_id: int | None = None
    pessoa_id: int | None = None
    observacao: str | None = None


class StatusIn(BaseModel):
    status: StatusEditavel
    observacao: str | None = None


class ArquivarIn(BaseModel):
    motivo: str = Field(min_length=3)


class RestaurarIn(BaseModel):
    observacao: str | None = None


class MovimentacaoOut(ORM):
    id: int
    ativo_id: int
    tipo: str
    status_anterior: str | None
    status_novo: str | None
    unidade_origem: Ref | None
    unidade_destino: Ref | None
    setor_origem: Ref | None
    setor_destino: Ref | None
    pessoa_origem: Ref | None
    pessoa_destino: Ref | None
    data: datetime
    observacao: str | None


class AtivoResumo(BaseModel):
    id: int
    nome: str | None
    patrimonio: str | None
    categoria: str
    status: str


class VinculoCriar(BaseModel):
    ativo_destino_id: int
    tipo: str = Field(default="outro", min_length=1, max_length=40)
    observacao: str | None = None


class VinculoOut(BaseModel):
    id: int
    tipo: str
    observacao: str | None
    criado_em: datetime
    direcao: Literal["origem", "destino"]
    outro: AtivoResumo


class AuditoriaOut(ORM):
    id: int
    entidade: str
    entidade_id: int
    acao: str
    antes: dict | None
    depois: dict | None
    criado_em: datetime


class AtivoDetalhe(AtivoOut):
    campos: list[CampoOut]
    movimentacoes: list[MovimentacaoOut]
    vinculos: list[VinculoOut]
    auditoria: list[AuditoriaOut]


# ---------- Importação ----------
class ItemOut(ORM):
    id: int
    ordem: int
    trecho_original: str
    origem_trecho: str | None
    categoria_sugerida_id: int | None
    dados_extraidos: dict
    confianca: float
    status: str
    motivo_duplicado: str | None
    ativo_id: int | None
    mensagens: list


class ImportacaoOut(ORM):
    id: int
    arquivo_nome: str
    formato: str
    metodo: str
    categoria_id: int | None
    unidade_padrao_id: int | None
    status: str
    total_itens: int
    erro: str | None
    meta: dict
    criado_em: datetime
    concluido_em: datetime | None
    contagem: dict[str, int] = {}


class ImportacaoDetalhe(ImportacaoOut):
    itens: list[ItemOut]


class MapeamentoIn(BaseModel):
    mapa: dict[str, str | None]


class ItemDadosIn(BaseModel):
    dados: dict[str, Any]


class AprovarLoteIn(BaseModel):
    confianca_minima: float = Field(default=0.9, ge=0, le=1)


class ConfigOut(BaseModel):
    gemini_configurado: bool
    gemini_modelo: str
    gemini_chave_mascarada: str | None


class ConfigGeminiIn(BaseModel):
    api_key: str | None = None
    modelo: str | None = None

    @field_validator("api_key", "modelo")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


assert set(TIPOS_CAMPO) == {"texto", "numero", "data", "bool", "ip", "mac", "telefone", "lista"}
