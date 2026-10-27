"""Orquestra a importação: arquivo → itens de revisão → objetos aprovados."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import database
from ... import models as m
from ...config import settings
from ...schemas import AtivoCriar
from .. import ativos as svc_ativos
from .. import auditoria
from ..validacao import ErroValidacao, converter, normalizar_texto, vazio
from . import ia, mapeamento, parsers

log = logging.getLogger(__name__)

SERIAL_CHAVES = {"serial", "numero_serie", "n_serie", "num_serie", "serie"}
ORIGEM_POR_METODO = {"ia": "ia", "mapeamento": "planilha", "regras": "regras"}
METODOS = ("ia", "regras", "mapeamento")


# ---------- utilidades ----------
def contagem(imp: m.Importacao) -> dict[str, int]:
    c = {"pendente": 0, "duplicado": 0, "aprovado": 0, "rejeitado": 0}
    for it in imp.itens:
        c[it.status] = c.get(it.status, 0) + 1
    return c


def _caminho(imp: m.Importacao) -> Path:
    return settings.uploads_dir / imp.meta.get("arquivo", "")


def _set_meta(imp: m.Importacao, **kwargs) -> None:
    imp.meta = {**(imp.meta or {}), **kwargs}


def _normalizar_dados(dados: dict) -> dict:
    base = mapeamento.dados_vazios(None)
    base.update({k: v for k, v in (dados or {}).items() if k in base})
    base["campos"] = {str(k): v for k, v in (base.get("campos") or {}).items() if not vazio(v)}
    for k in ("patrimonio", "nome", "unidade", "setor", "pessoa", "observacao"):
        v = base.get(k)
        base[k] = str(v).strip() if not vazio(v) else None
    for k in ("categoria_id", "unidade_id"):
        try:
            base[k] = int(base[k]) if base.get(k) not in (None, "") else None
        except (TypeError, ValueError):
            base[k] = None
    if dados and dados.get("status") in ("em_estoque", "em_uso", "em_manutencao", "com_defeito"):
        base["status"] = dados["status"]
    return base


def achar_unidade(db: Session, nome: str | None) -> m.Unidade | None:
    alvo = normalizar_texto(nome)
    if not alvo:
        return None
    unidades = db.scalars(select(m.Unidade)).all()
    for u in unidades:
        if normalizar_texto(u.nome) == alvo or (u.sigla and normalizar_texto(u.sigla) == alvo):
            return u
    contidas = [u for u in unidades if len(normalizar_texto(u.nome)) >= 4 and (
        normalizar_texto(u.nome) in alvo or alvo in normalizar_texto(u.nome))]
    return contidas[0] if len(contidas) == 1 else None


def _chaves_unicas(db: Session, dados: dict) -> list[tuple[str, str]]:
    """(motivo, valor) usados para detectar duplicados: patrimônio, serial e IP."""
    chaves: list[tuple[str, str]] = []
    if dados.get("patrimonio"):
        chaves.append(("patrimonio", dados["patrimonio"].strip()))
    cat = db.get(m.Categoria, dados["categoria_id"]) if dados.get("categoria_id") else None
    if cat:
        for campo in cat.campos:
            valor = dados["campos"].get(campo.chave)
            if vazio(valor):
                continue
            if campo.tipo == "ip":
                try:
                    chaves.append(("ip", converter("ip", valor)[0]))
                except ValueError:
                    pass
            elif campo.chave in SERIAL_CHAVES:
                chaves.append(("serial", str(valor).strip().upper()))
    return chaves


def _existente(db: Session, motivo: str, valor: str) -> int | None:
    if motivo == "patrimonio":
        return db.scalar(select(m.Ativo.id).where(m.Ativo.patrimonio == valor))
    q = (select(m.Ativo.id)
         .join(m.AtivoValor, m.AtivoValor.ativo_id == m.Ativo.id)
         .join(m.Campo, m.Campo.id == m.AtivoValor.campo_id)
         .where(m.Ativo.arquivado_em.is_(None)))
    if motivo == "ip":
        q = q.where(m.Campo.tipo == "ip", m.AtivoValor.valor_texto == valor)
    else:
        q = q.where(m.Campo.chave.in_(SERIAL_CHAVES), func.upper(m.AtivoValor.valor_texto) == valor)
    return db.scalar(q.limit(1))


ROTULO_MOTIVO = {"patrimonio": "Patrimônio", "ip": "IP", "serial": "Serial"}


def avaliar(db: Session, imp: m.Importacao, item: m.ImportacaoItem,
            vistos: dict[tuple[str, str], int] | None = None) -> None:
    """Recalcula mensagens, unidade sugerida e situação de duplicado de um item."""
    if item.status in ("aprovado", "rejeitado"):
        return
    dados = _normalizar_dados(item.dados_extraidos)
    msgs: list[dict] = []
    item.status, item.motivo_duplicado, item.ativo_id = "pendente", None, None

    cat = db.get(m.Categoria, dados["categoria_id"]) if dados["categoria_id"] else None
    if not cat:
        dados["categoria_id"] = None
        msgs.append({"tipo": "erro", "texto": "Escolha a categoria"})
    item.categoria_sugerida_id = dados["categoria_id"]

    # duplicados no banco e dentro do próprio arquivo
    for motivo, valor in _chaves_unicas(db, dados):
        existente = _existente(db, motivo, valor)
        if existente:
            item.status, item.motivo_duplicado, item.ativo_id = "duplicado", motivo, existente
            msgs.append({"tipo": "aviso",
                         "texto": f"{ROTULO_MOTIVO[motivo]} {valor} já existe no objeto #{existente}. Item ignorado."})
            break
        if vistos is not None and (motivo, valor) in vistos:
            item.status, item.motivo_duplicado = "duplicado", motivo
            msgs.append({"tipo": "aviso",
                         "texto": f"{ROTULO_MOTIVO[motivo]} {valor} repetido no arquivo (item {vistos[(motivo, valor)]})."})
            break
    if vistos is not None and item.status == "pendente":
        for chave in _chaves_unicas(db, dados):
            vistos.setdefault(chave, item.ordem)

    # valores dos campos
    if cat:
        campos = {c.chave: c for c in cat.campos if c.ativo}
        for chave, valor in dados["campos"].items():
            campo = campos.get(chave)
            if not campo:
                msgs.append({"tipo": "aviso", "texto": f"Campo “{chave}” não existe em {cat.nome} e será descartado"})
                continue
            try:
                converter(campo.tipo, valor, campo.opcoes)
            except ValueError as e:
                msgs.append({"tipo": "erro", "texto": f"{campo.rotulo}: {e}"})
        for campo in campos.values():
            if campo.obrigatorio and vazio(dados["campos"].get(campo.chave)):
                msgs.append({"tipo": "erro", "texto": f"{campo.rotulo} é obrigatório"})

    # unidade
    unidade = db.get(m.Unidade, dados["unidade_id"]) if dados["unidade_id"] else None
    if not unidade and dados["unidade"]:
        unidade = achar_unidade(db, dados["unidade"])
        if not unidade:
            msgs.append({"tipo": "info", "texto": f"Unidade “{dados['unidade']}” não existe e será criada ao aprovar"})
    if not unidade and not dados["unidade"] and imp.unidade_padrao_id:
        unidade = db.get(m.Unidade, imp.unidade_padrao_id)
    dados["unidade_id"] = unidade.id if unidade else None
    if not unidade and not dados["unidade"]:
        msgs.append({"tipo": "erro", "texto": "Escolha a unidade"})

    item.dados_extraidos = dados
    item.mensagens = msgs


def _vistos_de_outros(db: Session, imp: m.Importacao, item: m.ImportacaoItem) -> dict:
    vistos: dict[tuple[str, str], int] = {}
    for outro in imp.itens:
        if outro.id == item.id or outro.status != "pendente" or outro.ordem > item.ordem:
            continue
        for chave in _chaves_unicas(db, _normalizar_dados(outro.dados_extraidos)):
            vistos.setdefault(chave, outro.ordem)
    return vistos


def _criar_itens(db: Session, imp: m.Importacao, entradas: list[tuple[str, str, dict, float]]) -> None:
    vistos: dict[tuple[str, str], int] = {}
    for n, (trecho, origem, dados, conf) in enumerate(entradas, start=1):
        item = m.ImportacaoItem(importacao_id=imp.id, ordem=n, trecho_original=trecho[:5000],
                                origem_trecho=(origem or "")[:120], dados_extraidos=dados,
                                confianca=round(conf, 2))
        imp.itens.append(item)
        db.flush()
        avaliar(db, imp, item, vistos)
    imp.total_itens = len(entradas)
    if entradas:
        imp.status = "revisao"
    else:
        imp.status = "concluida"
        imp.concluido_em = m.agora()
        imp.erro = "Nenhum objeto encontrado no arquivo"


# ---------- criação ----------
def criar(db: Session, nome: str, conteudo: bytes, metodo: str,
          categoria_id: int | None, unidade_padrao_id: int | None) -> tuple[m.Importacao, bool]:
    """Cria a importação. Retorna (importacao, precisa_rodar_ia_em_segundo_plano)."""
    if metodo not in METODOS:
        raise HTTPException(400, "Método inválido (use ia, regras ou mapeamento)")
    if len(conteudo) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Arquivo maior que {settings.max_upload_mb} MB")
    if not conteudo:
        raise HTTPException(400, "Arquivo vazio")
    try:
        formato = parsers.detectar_formato(nome, conteudo)
    except parsers.ErroArquivo as e:
        raise HTTPException(400, str(e))
    categoria = db.get(m.Categoria, categoria_id) if categoria_id else None
    if categoria_id and not categoria:
        raise HTTPException(400, "Categoria não encontrada")
    if unidade_padrao_id and not db.get(m.Unidade, unidade_padrao_id):
        raise HTTPException(400, "Unidade padrão não encontrada")
    if metodo == "mapeamento":
        if formato not in ("xlsx", "csv"):
            raise HTTPException(400, "O mapeamento de colunas só funciona com planilhas (xlsx ou csv)")
        if not categoria:
            raise HTTPException(400, "Escolha a categoria para mapear as colunas")

    sha = hashlib.sha256(conteudo).hexdigest()
    anterior = db.scalar(select(m.Importacao).where(m.Importacao.arquivo_hash == sha)
                         .order_by(m.Importacao.id.desc()))
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    arquivo = f"{sha}{Path(nome).suffix.lower()}"
    (settings.uploads_dir / arquivo).write_bytes(conteudo)

    imp = m.Importacao(arquivo_nome=Path(nome).name[:255], arquivo_hash=sha, formato=formato,
                       metodo=metodo, categoria_id=categoria_id, unidade_padrao_id=unidade_padrao_id,
                       status="processando", meta={"arquivo": arquivo})
    if anterior:
        _set_meta(imp, aviso=f"Este arquivo já foi importado antes (importação #{anterior.id}, "
                             f"{anterior.criado_em:%d/%m/%Y}). Duplicados serão ignorados.")
    db.add(imp)
    db.flush()

    try:
        if metodo == "mapeamento":
            tabela = parsers.ler_tabela(conteudo, formato)
            if not tabela.linhas:
                raise parsers.ErroArquivo("A planilha não tem linhas com dados")
            _set_meta(imp, colunas=tabela.colunas,
                      sugestao=mapeamento.sugerir_mapa(tabela, categoria),
                      amostra=tabela.linhas[:5], total_linhas=len(tabela.linhas))
            imp.status = "mapeamento"
            return imp, False
        if metodo == "regras":
            blocos = parsers.ler_blocos(conteudo, formato)
            categorias = db.scalars(select(m.Categoria).where(m.Categoria.ativa.is_(True))).all()
            achados = mapeamento.extrair_por_regras(blocos, list(categorias), categoria)
            _criar_itens(db, imp, [(b.texto, b.origem, d, c) for b, d, c in achados])
            return imp, False
        # ia: valida a leitura e o provedor agora, chama o modelo em segundo plano
        blocos = parsers.ler_blocos(conteudo, formato)
        if not blocos:
            raise parsers.ErroArquivo("Não encontrei texto aproveitável no arquivo")
        ia.verificar_pronto()
        _set_meta(imp, total_blocos=len(blocos), progresso="Na fila", provedor=settings.ia_provedor,
                  modelo=settings.gemini_model if settings.ia_provedor == "gemini" else settings.ollama_modelo)
        return imp, True
    except (parsers.ErroArquivo, ia.ErroIA) as e:
        imp.status = "erro"
        imp.erro = str(e)
        return imp, False


def processar_ia(importacao_id: int) -> None:
    """Roda em segundo plano (BackgroundTasks) com sessão própria."""
    db = database.nova_sessao()
    try:
        imp = db.get(m.Importacao, importacao_id)
        if not imp or imp.status != "processando":
            return
        try:
            conteudo = _caminho(imp).read_bytes()
            blocos = parsers.ler_blocos(conteudo, imp.formato)
            categorias = list(db.scalars(select(m.Categoria).where(m.Categoria.ativa.is_(True))).all())
            unidades = [u.nome for u in db.scalars(select(m.Unidade)).all()]

            def progresso(feito: int, total: int) -> None:
                _set_meta(imp, progresso=f"Lote {feito} de {total} analisado")
                db.commit()

            achados = ia.extrair(blocos, categorias, unidades, imp.categoria, progresso)
            entradas = []
            for indices, dados, conf in achados:
                trecho = "\n\n".join(blocos[i].texto for i in indices)
                origem = ", ".join(blocos[i].origem for i in indices)
                entradas.append((trecho, origem, dados, conf))
            _criar_itens(db, imp, entradas)
            _set_meta(imp, progresso="Concluído")
        except Exception as e:  # registra qualquer falha na própria importação
            log.exception("Falha na importação %s", importacao_id)
            db.rollback()
            imp = db.get(m.Importacao, importacao_id)
            imp.status = "erro"
            imp.erro = str(e) if isinstance(e, (ia.ErroIA, parsers.ErroArquivo)) else f"Erro inesperado: {e}"
        db.commit()
    finally:
        db.close()


def aplicar_mapeamento(db: Session, imp: m.Importacao, mapa: dict[str, str | None]) -> None:
    if imp.status != "mapeamento":
        raise HTTPException(409, "Esta importação não está aguardando mapeamento")
    categoria = imp.categoria
    validos = {c.chave for c in categoria.campos if c.ativo} | set(mapeamento.BASE)
    invalidos = [d for d in mapa.values() if d and d not in validos]
    if invalidos:
        raise HTTPException(400, f"Destino inválido: {', '.join(invalidos)}")
    usados = [d for d in mapa.values() if d]
    if len(usados) != len(set(usados)):
        raise HTTPException(400, "Cada campo só pode receber uma coluna")
    if not usados:
        raise HTTPException(400, "Mapeie pelo menos uma coluna")
    tabela = parsers.ler_tabela(_caminho(imp).read_bytes(), imp.formato)
    entradas = []
    for i, linha in enumerate(tabela.linhas, start=1):
        dados = mapeamento.linha_para_dados(linha, mapa, categoria.id)
        if not dados["campos"] and not dados["patrimonio"] and not dados["nome"]:
            continue
        trecho = "\n".join(f"{k}: {v}" for k, v in linha.items() if k != "_aba")
        entradas.append((trecho, f"linha {i}", dados, 1.0))
    _set_meta(imp, mapa=mapa)
    _criar_itens(db, imp, entradas)


# ---------- revisão ----------
def editar_item(db: Session, imp: m.Importacao, item: m.ImportacaoItem, dados: dict) -> None:
    if item.status not in ("pendente", "duplicado"):
        raise HTTPException(409, "Só é possível editar itens pendentes ou duplicados")
    item.dados_extraidos = _normalizar_dados(dados)
    avaliar(db, imp, item, _vistos_de_outros(db, imp, item))


def _resolver_posse(db: Session, dados: dict) -> tuple[int, int | None, int | None]:
    unidade = db.get(m.Unidade, dados["unidade_id"]) if dados["unidade_id"] else None
    if not unidade and dados["unidade"]:
        unidade = achar_unidade(db, dados["unidade"])
        if not unidade:
            unidade = m.Unidade(nome=dados["unidade"][:120])
            db.add(unidade)
            db.flush()
            auditoria.registrar(db, "unidade", unidade.id, "criar", None,
                                {"nome": unidade.nome, "via": "importacao"})
    if not unidade:
        raise ErroValidacao({"unidade": "Escolha a unidade"})

    setor_id = None
    if dados["setor"]:
        alvo = normalizar_texto(dados["setor"])
        setor = next((s for s in unidade.setores if normalizar_texto(s.nome) == alvo), None)
        if not setor:
            setor = m.Setor(unidade_id=unidade.id, nome=dados["setor"][:120])
            db.add(setor)
            db.flush()
            auditoria.registrar(db, "setor", setor.id, "criar", None, {"nome": setor.nome, "via": "importacao"})
        setor_id = setor.id

    pessoa_id = None
    if dados["pessoa"]:
        alvo = normalizar_texto(dados["pessoa"])
        candidatas = [p for p in db.scalars(select(m.Pessoa)).all() if normalizar_texto(p.nome) == alvo]
        if len(candidatas) == 1:
            pessoa = candidatas[0]
        else:
            pessoa = m.Pessoa(nome=dados["pessoa"][:150], unidade_id=unidade.id, setor_id=setor_id)
            db.add(pessoa)
            db.flush()
            auditoria.registrar(db, "pessoa", pessoa.id, "criar", None, {"nome": pessoa.nome, "via": "importacao"})
        pessoa_id = pessoa.id
    return unidade.id, setor_id, pessoa_id


def _nome_padrao(db: Session, dados: dict) -> str | None:
    """Sem nome no arquivo: usa o primeiro campo de texto preenchido (hostname, ramal, modelo…)."""
    if dados.get("nome"):
        return dados["nome"]
    cat = db.get(m.Categoria, dados["categoria_id"])
    for campo in cat.campos if cat else []:
        valor = dados["campos"].get(campo.chave)
        if campo.ativo and campo.tipo in ("texto", "telefone") and not vazio(valor):
            return str(valor).strip()[:150]
    return None


def _concluir_se_pronto(imp: m.Importacao) -> None:
    if imp.status == "revisao" and not any(i.status == "pendente" for i in imp.itens):
        imp.status = "concluida"
        imp.concluido_em = m.agora()


def aprovar_item(db: Session, imp: m.Importacao, item: m.ImportacaoItem) -> m.Ativo:
    if item.status == "duplicado":
        raise HTTPException(409, "Itens duplicados são ignorados. Edite o item se ele for outro objeto.")
    if item.status != "pendente":
        raise HTTPException(409, "Este item já foi revisado")
    avaliar(db, imp, item, _vistos_de_outros(db, imp, item))
    if item.status == "duplicado":
        db.commit()
        raise HTTPException(409, "O item virou duplicado de um objeto já cadastrado e foi ignorado")
    dados = item.dados_extraidos
    sp = db.begin_nested()
    try:
        if not dados["categoria_id"]:
            raise ErroValidacao({"categoria_id": "Escolha a categoria"})
        unidade_id, setor_id, pessoa_id = _resolver_posse(db, dados)
        ativo = svc_ativos.criar(db, AtivoCriar(
            categoria_id=dados["categoria_id"], patrimonio=dados["patrimonio"], nome=_nome_padrao(db, dados),
            status=dados.get("status") or "em_uso", unidade_id=unidade_id, setor_id=setor_id,
            pessoa_id=pessoa_id, observacao=dados["observacao"], valores=dados["campos"],
        ), origem=ORIGEM_POR_METODO.get(imp.metodo, "ia"))
        sp.commit()
    except ErroValidacao as e:
        sp.rollback()
        item.mensagens = [{"tipo": "erro", "texto": t} for t in e.erros.values()]
        raise
    item.status = "aprovado"
    item.ativo_id = ativo.id
    _concluir_se_pronto(imp)
    return ativo


def rejeitar_item(db: Session, imp: m.Importacao, item: m.ImportacaoItem) -> None:
    if item.status not in ("pendente", "duplicado"):
        raise HTTPException(409, "Este item já foi revisado")
    item.status = "rejeitado"
    _concluir_se_pronto(imp)


def aprovar_lote(db: Session, imp: m.Importacao, confianca_minima: float) -> dict:
    aprovados, falhas = 0, []
    for item in list(imp.itens):
        if item.status != "pendente" or item.confianca < confianca_minima:
            continue
        if any(msg.get("tipo") == "erro" for msg in item.mensagens or []):
            falhas.append({"item_id": item.id, "ordem": item.ordem, "erro": "Tem erros a corrigir"})
            continue
        try:
            aprovar_item(db, imp, item)
            aprovados += 1
        except ErroValidacao as e:
            falhas.append({"item_id": item.id, "ordem": item.ordem, "erro": "; ".join(e.erros.values())})
        except HTTPException as e:
            falhas.append({"item_id": item.id, "ordem": item.ordem, "erro": str(e.detail)})
    _concluir_se_pronto(imp)
    return {"aprovados": aprovados, "falhas": falhas}
