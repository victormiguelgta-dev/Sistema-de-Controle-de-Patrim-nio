"""Extração de objetos com o Google Gemini.

O Gemini recebe os blocos de texto numerados e a descrição de cada categoria (campos, tipos e
sinônimos) e devolve JSON estruturado. Nada é gravado direto: o resultado vira itens de revisão.
"""
from __future__ import annotations

import json
import logging
import time

from pydantic import BaseModel

from ... import models as m
from ...config import settings
from .parsers import Bloco

log = logging.getLogger(__name__)


class ErroIA(Exception):
    pass


class CampoExtraido(BaseModel):
    chave: str
    valor: str


class ObjetoExtraido(BaseModel):
    blocos: list[int]
    categoria: str
    patrimonio: str
    nome: str
    unidade: str
    setor: str
    pessoa: str
    observacao: str
    campos: list[CampoExtraido]
    confianca: float


class RespostaIA(BaseModel):
    objetos: list[ObjetoExtraido]


INSTRUCOES = """Você organiza dados de controle de patrimônio (equipamentos de uma instituição pública).
Receberá BLOCOS de texto numerados vindos de planilhas, PDFs, arquivos de texto ou conversas de WhatsApp,
e a lista de CATEGORIAS com seus campos.

Para cada objeto físico descrito nos blocos, devolva um item em "objetos":
- "blocos": números dos blocos de onde tirou os dados (normalmente um só).
- "categoria": o slug exato de uma das categorias. Se nenhuma servir, use "".
- "patrimonio": número de patrimônio/plaqueta/tombamento ("Pat", "Patrimônio"). Só os dígitos/código, sem rótulo. "" se não houver.
- "nome": um nome curto que identifique o objeto (ex.: hostname ou modelo). "" se não houver.
- "unidade": a unidade/defensoria/fórum/prédio onde o objeto está, como escrito no texto. "" se não houver.
- "setor" e "pessoa": só se o texto disser explicitamente. "" se não houver.
- "observacao": informação útil que não cabe nos campos (ex.: "sem rede", "aguardando peça"). "" se não houver.
- "campos": pares {chave, valor} usando SOMENTE as chaves dos campos da categoria escolhida.
  Valores limpos: IP só o endereço (sem "IP Fixo"), datas em dd/mm/aaaa, listas com uma das opções.
- "confianca": de 0 a 1, o quanto você tem certeza de que é um objeto real e de que os dados estão corretos.

Regras:
- Ignore blocos que não descrevem um objeto (conversas, saudações, combinados, modelos em branco como "XXX.XXX").
- Não invente valores. Se um dado não estiver no texto, deixe vazio.
- Um bloco pode descrever mais de um objeto, e um objeto não deve ser repetido.
"""


def descrever_categorias(categorias: list[m.Categoria]) -> str:
    linhas = []
    for c in categorias:
        if not c.ativa:
            continue
        linhas.append(f'Categoria "{c.slug}" ({c.nome}){": " + c.descricao if c.descricao else ""}')
        for campo in c.campos:
            if not campo.ativo:
                continue
            extra = []
            if campo.obrigatorio:
                extra.append("obrigatório")
            if campo.opcoes:
                extra.append("opções: " + ", ".join(campo.opcoes))
            if campo.sinonimos:
                extra.append("também aparece como: " + ", ".join(campo.sinonimos))
            linhas.append(f'  - {campo.chave} ({campo.tipo}) "{campo.rotulo}"' + (f" [{'; '.join(extra)}]" if extra else ""))
    return "\n".join(linhas)


def montar_lotes(blocos: list[Bloco], max_chars: int) -> list[list[int]]:
    lotes: list[list[int]] = []
    atual: list[int] = []
    tamanho = 0
    for i, b in enumerate(blocos):
        n = len(b.texto) + 20
        if atual and tamanho + n > max_chars:
            lotes.append(atual)
            atual, tamanho = [], 0
        atual.append(i)
        tamanho += n
    if atual:
        lotes.append(atual)
    return lotes


def _chamar_gemini(prompt: str) -> RespostaIA:
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:  # pragma: no cover
        raise ErroIA("Pacote google-genai não instalado (pip install -r requirements.txt)") from e

    client = genai.Client(api_key=settings.gemini_api_key)
    ultimo_erro: Exception | None = None
    for tentativa in range(4):
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RespostaIA,
                    temperature=0.1,
                ),
            )
            if isinstance(resp.parsed, RespostaIA):
                return resp.parsed
            return RespostaIA.model_validate(json.loads(resp.text or "{}"))
        except Exception as e:  # erros de rede/limite chegam com tipos variados
            ultimo_erro = e
            texto = str(e)
            limite = "429" in texto or "RESOURCE_EXHAUSTED" in texto or "quota" in texto.lower()
            if "API key not valid" in texto or "API_KEY_INVALID" in texto or "PERMISSION_DENIED" in texto:
                raise ErroIA("Chave do Gemini inválida. Confira em Configurações.") from e
            espera = 30 * (tentativa + 1) if limite else 5 * (tentativa + 1)
            log.warning("Gemini falhou (tentativa %s): %s — esperando %ss", tentativa + 1, texto[:200], espera)
            time.sleep(espera)
    raise ErroIA(f"O Gemini não respondeu depois de 4 tentativas: {ultimo_erro}")


def extrair(blocos: list[Bloco], categorias: list[m.Categoria], unidades: list[str],
            categoria_dica: m.Categoria | None = None,
            ao_progredir=None) -> list[tuple[list[int], dict, float]]:
    """Devolve [(índices dos blocos, dados normalizados, confiança)]."""
    if not settings.gemini_api_key:
        raise ErroIA("Configure a chave do Gemini em Configurações (ou GEMINI_API_KEY no backend/.env).")
    por_slug = {c.slug: c for c in categorias}
    contexto = INSTRUCOES + "\nCATEGORIAS:\n" + descrever_categorias(categorias)
    if categoria_dica:
        contexto += f'\n\nDica: o arquivo provavelmente trata da categoria "{categoria_dica.slug}".'
    if unidades:
        contexto += "\n\nUnidades já cadastradas (use o nome igual quando for a mesma): " + "; ".join(unidades[:200])

    lotes = montar_lotes(blocos, settings.gemini_max_chars)
    saida: list[tuple[list[int], dict, float]] = []
    for n, lote in enumerate(lotes):
        if n > 0 and settings.gemini_intervalo > 0:
            time.sleep(settings.gemini_intervalo)
        texto_blocos = "\n\n".join(f"### BLOCO {i + 1}\n{blocos[i].texto}" for i in lote)
        resposta = _chamar_gemini(contexto + "\n\nBLOCOS:\n" + texto_blocos)
        for obj in resposta.objetos:
            indices = sorted({b - 1 for b in obj.blocos if 1 <= b <= len(blocos)}) or [lote[0]]
            cat = por_slug.get(obj.categoria) or categoria_dica
            chaves_validas = {c.chave for c in cat.campos if c.ativo} if cat else set()
            dados = {
                "categoria_id": cat.id if cat else None,
                "patrimonio": obj.patrimonio.strip() or None,
                "nome": obj.nome.strip() or None,
                "unidade_id": None,
                "unidade": obj.unidade.strip() or None,
                "setor": obj.setor.strip() or None,
                "pessoa": obj.pessoa.strip() or None,
                "observacao": obj.observacao.strip() or None,
                "campos": {c.chave: c.valor.strip() for c in obj.campos
                           if c.valor.strip() and c.chave in chaves_validas},
            }
            saida.append((indices, dados, max(0.0, min(1.0, float(obj.confianca)))))
        if ao_progredir:
            ao_progredir(n + 1, len(lotes))
    return saida
