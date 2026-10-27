"""Extração de objetos com IA: Ollama (modelo local) ou Google Gemini.

O modelo recebe os blocos de texto numerados e a descrição de cada categoria (campos, tipos e
sinônimos) e devolve JSON estruturado. Nada é gravado direto: o resultado vira itens de revisão.
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from pydantic import BaseModel

from ... import models as m
from ...config import settings
from .parsers import Bloco

log = logging.getLogger(__name__)


class ErroIA(Exception):
    pass


NOME_PROVEDOR = {"ollama": "Ollama (local)", "gemini": "Gemini"}


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


def _esquema_sem_refs(esquema: dict) -> dict:
    """Ollama converte o JSON Schema em gramática; mais seguro sem $ref/$defs."""
    defs = esquema.get("$defs", {})

    def resolver(no):
        if isinstance(no, dict):
            if "$ref" in no:
                return resolver(defs[no["$ref"].split("/")[-1]])
            return {k: resolver(v) for k, v in no.items() if k not in ("$defs", "title")}
        if isinstance(no, list):
            return [resolver(x) for x in no]
        return no

    return resolver(esquema)


ESQUEMA_RESPOSTA = _esquema_sem_refs(RespostaIA.model_json_schema())


def ollama_status() -> dict:
    """Consulta o Ollama: está rodando? quais modelos foram baixados?"""
    try:
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        r.raise_for_status()
        modelos = sorted(m_["name"] for m_ in r.json().get("models", []))
        return {"rodando": True, "modelos": modelos}
    except Exception:  # conexão recusada, timeout, resposta inesperada
        return {"rodando": False, "modelos": []}


def _modelo_instalado(modelos: list[str], modelo: str) -> bool:
    alvo = modelo if ":" in modelo else f"{modelo}:latest"
    return alvo in modelos or modelo in modelos


def verificar_pronto() -> None:
    """Lança ErroIA com instrução clara se o provedor escolhido não estiver pronto."""
    if settings.ia_provedor == "gemini":
        if not settings.gemini_api_key:
            raise ErroIA("Configure a chave do Gemini em Configurações (ou GEMINI_API_KEY no backend/.env), "
                         "ou troque para o Ollama.")
        return
    status = ollama_status()
    if not status["rodando"]:
        raise ErroIA(f"O Ollama não está rodando em {settings.ollama_url}. Instale em ollama.com, abra o programa "
                     "e tente de novo — ou use o método “Regras”.")
    if not _modelo_instalado(status["modelos"], settings.ollama_modelo):
        raise ErroIA(f"O modelo “{settings.ollama_modelo}” não foi baixado. No terminal, rode: "
                     f"ollama pull {settings.ollama_modelo}")


def _chamar_ollama(prompt: str) -> RespostaIA:
    corpo = {
        "model": settings.ollama_modelo,
        "messages": [{"role": "user", "content": prompt}],
        "format": ESQUEMA_RESPOSTA,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": settings.ollama_contexto},
    }
    ultimo_erro: Exception | None = None
    for tentativa in range(2):
        try:
            r = httpx.post(f"{settings.ollama_url}/api/chat", json=corpo, timeout=settings.ollama_timeout)
            if r.status_code == 404:
                raise ErroIA(f"O modelo “{settings.ollama_modelo}” não foi baixado. Rode: ollama pull {settings.ollama_modelo}")
            r.raise_for_status()
            conteudo = r.json().get("message", {}).get("content") or "{}"
            return RespostaIA.model_validate(json.loads(conteudo))
        except ErroIA:
            raise
        except httpx.ConnectError as e:
            raise ErroIA(f"O Ollama parou de responder em {settings.ollama_url}. Ele está aberto?") from e
        except Exception as e:  # timeout, JSON incompleto, validação
            ultimo_erro = e
            log.warning("Ollama falhou (tentativa %s): %s", tentativa + 1, str(e)[:200])
    raise ErroIA(f"O modelo local não devolveu uma resposta válida: {ultimo_erro}. "
                 "Se o computador for lento, aumente OLLAMA_TIMEOUT_SEGUNDOS ou use um modelo menor.")


def _chamar_modelo(prompt: str) -> RespostaIA:
    if settings.ia_provedor == "gemini":
        return _chamar_gemini(prompt)
    return _chamar_ollama(prompt)


def extrair(blocos: list[Bloco], categorias: list[m.Categoria], unidades: list[str],
            categoria_dica: m.Categoria | None = None,
            ao_progredir=None) -> list[tuple[list[int], dict, float]]:
    """Devolve [(índices dos blocos, dados normalizados, confiança)]."""
    verificar_pronto()
    gemini = settings.ia_provedor == "gemini"
    por_slug = {c.slug: c for c in categorias}
    contexto = INSTRUCOES + "\nCATEGORIAS:\n" + descrever_categorias(categorias)
    if categoria_dica:
        contexto += f'\n\nDica: o arquivo provavelmente trata da categoria "{categoria_dica.slug}".'
    if unidades:
        contexto += "\n\nUnidades já cadastradas (use o nome igual quando for a mesma): " + "; ".join(unidades[:200])

    lotes = montar_lotes(blocos, settings.gemini_max_chars if gemini else settings.ollama_max_chars)
    saida: list[tuple[list[int], dict, float]] = []
    for n, lote in enumerate(lotes):
        if gemini and n > 0 and settings.gemini_intervalo > 0:
            time.sleep(settings.gemini_intervalo)
        texto_blocos = "\n\n".join(f"### BLOCO {i + 1}\n{blocos[i].texto}" for i in lote)
        resposta = _chamar_modelo(contexto + "\n\nBLOCOS:\n" + texto_blocos)
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
