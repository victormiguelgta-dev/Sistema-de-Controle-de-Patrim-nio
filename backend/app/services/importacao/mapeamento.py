"""Reconhece nomes de colunas/rótulos usando chave, rótulo e sinônimos dos campos.

Usado pelo mapeamento de colunas de planilhas e pela extração por regras (sem IA).
"""
from __future__ import annotations

import re

from ... import models as m
from ..validacao import normalizar_texto
from .parsers import Bloco, Tabela

# Destinos fixos (fora dos campos da categoria)
BASE = {
    "__patrimonio__": ["patrimonio", "pat", "plaqueta", "tombamento", "n patrimonio", "numero patrimonio",
                       "num patrimonio", "nº patrimonio", "etiqueta patrimonio"],
    "__nome__": ["nome", "descricao", "equipamento", "item", "objeto"],
    "__unidade__": ["unidade", "defensoria", "nucleo", "local", "lotacao", "forum", "sede"],
    "__setor__": ["setor", "departamento", "sala", "area"],
    "__pessoa__": ["responsavel", "pessoa", "usuario", "servidor responsavel", "posse"],
    "__observacao__": ["observacao", "observacoes", "obs", "comentario"],
}
ROTULOS_BASE = {
    "__patrimonio__": "Patrimônio",
    "__nome__": "Nome",
    "__unidade__": "Unidade",
    "__setor__": "Setor",
    "__pessoa__": "Pessoa",
    "__observacao__": "Observação",
}
KV = re.compile(r"^\s*([^:\n]{1,40}?)\s*[:=]\s*(.+?)\s*$")


def termos_campo(campo: m.Campo) -> list[str]:
    termos = [campo.chave.replace("_", " "), campo.rotulo, *(campo.sinonimos or [])]
    return [t for t in (normalizar_texto(x) for x in termos) if t]


def casar(rotulo: str, alvos: dict[str, list[str]]) -> str | None:
    """Devolve o destino cujo termo casa com o rótulo (exato primeiro, depois contido)."""
    r = normalizar_texto(rotulo)
    if not r:
        return None
    for destino, termos in alvos.items():
        if r in termos:
            return destino
    melhor, tam = None, 0
    for destino, termos in alvos.items():
        for t in termos:
            if len(t) >= 3 and (re.search(rf"\b{re.escape(t)}\b", r) or (len(r) >= 3 and r in t.split())):
                if len(t) > tam:
                    melhor, tam = destino, len(t)
    return melhor


def alvos_categoria(categoria: m.Categoria | None) -> dict[str, list[str]]:
    alvos: dict[str, list[str]] = {}
    if categoria:
        for c in categoria.campos:
            if c.ativo:
                alvos[c.chave] = termos_campo(c)
    for k, termos in BASE.items():
        alvos[k] = [normalizar_texto(t) for t in termos]
    return alvos


def sugerir_mapa(tabela: Tabela, categoria: m.Categoria) -> dict[str, str | None]:
    alvos = alvos_categoria(categoria)
    mapa: dict[str, str | None] = {}
    usados: set[str] = set()
    for col in tabela.colunas:
        destino = casar(col, alvos)
        if destino and destino not in usados:
            mapa[col] = destino
            usados.add(destino)
        else:
            mapa[col] = None
    return mapa


def dados_vazios(categoria_id: int | None) -> dict:
    return {"categoria_id": categoria_id, "patrimonio": None, "nome": None, "unidade_id": None,
            "unidade": None, "setor": None, "pessoa": None, "observacao": None, "campos": {}}


def aplicar_destino(dados: dict, destino: str, valor: str) -> None:
    chave_base = {"__patrimonio__": "patrimonio", "__nome__": "nome", "__unidade__": "unidade",
                  "__setor__": "setor", "__pessoa__": "pessoa", "__observacao__": "observacao"}
    if destino in chave_base:
        k = chave_base[destino]
        dados[k] = f"{dados[k]} · {valor}" if (k == "observacao" and dados.get(k)) else valor
    else:
        dados["campos"][destino] = valor


def linha_para_dados(linha: dict[str, str], mapa: dict[str, str | None], categoria_id: int) -> dict:
    dados = dados_vazios(categoria_id)
    for col, valor in linha.items():
        destino = mapa.get(col)
        if destino:
            aplicar_destino(dados, destino, valor)
    return dados


def extrair_por_regras(blocos: list[Bloco], categorias: list[m.Categoria],
                       categoria_dica: m.Categoria | None = None) -> list[tuple[Bloco, dict, float]]:
    """Lê linhas “Rótulo: valor” e escolhe a categoria com mais campos reconhecidos."""
    resultado = []
    for bloco in blocos:
        pares = [KV.match(l) for l in bloco.texto.splitlines()]
        pares = [(p.group(1), p.group(2)) for p in pares if p]
        if not pares:
            continue
        candidatas = [categoria_dica] if categoria_dica else categorias
        melhor = None
        for cat in candidatas:
            alvos = alvos_categoria(cat)
            dados = dados_vazios(cat.id)
            casados = 0
            for rotulo, valor in pares:
                destino = casar(rotulo, alvos)
                if destino:
                    aplicar_destino(dados, destino, valor)
                    casados += 1
            n_campos = len(dados["campos"])
            pontos = (n_campos, casados)
            if n_campos and (melhor is None or pontos > melhor[0]):
                melhor = (pontos, dados)
        if not melhor:
            continue
        (n_campos, casados), dados = melhor
        if not dados["nome"]:
            primeira = bloco.texto.strip().splitlines()[0]
            if not KV.match(primeira):
                dados["observacao"] = primeira[:200]
        confianca = round(min(0.95, 0.5 + 0.45 * casados / max(1, len(pares))), 2)
        resultado.append((bloco, dados, confianca))
    return resultado
