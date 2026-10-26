"""Lê os arquivos enviados e transforma em tabelas (planilhas) ou blocos de texto."""
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

FORMATOS = ["xlsx", "csv", "txt", "whatsapp", "pdf"]
EXTENSOES = {".xlsx": "xlsx", ".xlsm": "xlsx", ".xls": "xlsx", ".csv": "csv",
             ".txt": "txt", ".zip": "whatsapp", ".pdf": "pdf"}
MAX_BLOCO = 1500
MAX_ZIP_TXT = 20 * 1024 * 1024

# [21/07/2026, 10:28:15] Nome: msg   (iPhone)
# 21/07/2026 10:28 - Nome: msg       (Android)
WA_IOS = re.compile(r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),? (\d{1,2}:\d{2}(?::\d{2})?)\] ([^:]{1,60}): ?(.*)$")
WA_ANDROID = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),? (\d{1,2}:\d{2}) - ([^:]{1,60}): ?(.*)$")
WA_SISTEMA = re.compile(r"^\[?\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}")
ANEXO = re.compile(r"<(anexado|attached):[^>]*>|<M[ií]dia oculta>|<Media omitted>", re.I)
INVISIVEIS = dict.fromkeys(map(ord, "‎‏‪‫‬ ﻿"), None)


class ErroArquivo(Exception):
    pass


@dataclass
class Bloco:
    texto: str
    origem: str


@dataclass
class Tabela:
    colunas: list[str]
    linhas: list[dict[str, str]] = field(default_factory=list)


def detectar_formato(nome: str, conteudo: bytes) -> str:
    ext = Path(nome).suffix.lower()
    formato = EXTENSOES.get(ext)
    if not formato:
        raise ErroArquivo(
            f"Formato “{ext or nome}” não suportado. Use xlsx, csv, txt, pdf ou a exportação do WhatsApp (.zip/.txt)."
        )
    if formato == "txt" and _parece_whatsapp(_decodificar(conteudo)):
        return "whatsapp"
    return formato


def _decodificar(conteudo: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return conteudo.decode(enc)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("utf-8", errors="replace")


def _parece_whatsapp(texto: str) -> bool:
    linhas = [l.translate(INVISIVEIS) for l in texto.splitlines()[:200] if l.strip()]
    if not linhas:
        return False
    hits = sum(1 for l in linhas if WA_IOS.match(l) or WA_ANDROID.match(l))
    return hits >= max(3, len(linhas) * 0.3)


# ---------- planilhas ----------
def _achar_cabecalho(df: pd.DataFrame) -> int:
    """Primeira linha com pelo menos metade das colunas preenchidas vira cabeçalho."""
    if df.empty:
        return 0
    preenchidas = df.notna().sum(axis=1)
    limite = max(2, int(preenchidas.max() * 0.5))
    for idx, n in preenchidas.items():
        if n >= limite:
            return int(idx)
    return 0


def _df_para_tabela(df: pd.DataFrame, aba: str | None = None) -> Tabela:
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        return Tabela(colunas=[])
    df = df.reset_index(drop=True)
    h = _achar_cabecalho(df)
    cab = []
    vistos: dict[str, int] = {}
    for i, c in enumerate(df.iloc[h].tolist()):
        nome = str(c).strip() if pd.notna(c) and str(c).strip() else f"Coluna {i + 1}"
        if nome in vistos:
            vistos[nome] += 1
            nome = f"{nome} ({vistos[nome]})"
        else:
            vistos[nome] = 1
        cab.append(nome)
    corpo = df.iloc[h + 1:]
    linhas = []
    for _, row in corpo.iterrows():
        linha = {}
        for col, val in zip(cab, row.tolist()):
            if pd.isna(val):
                continue
            s = str(val).strip()
            if s.endswith(".0") and s[:-2].isdigit():
                s = s[:-2]
            if s:
                linha[col] = s
        if linha:
            if aba:
                linha["_aba"] = aba
            linhas.append(linha)
    return Tabela(colunas=cab, linhas=linhas)


def ler_tabela(conteudo: bytes, formato: str) -> Tabela:
    try:
        if formato == "csv":
            texto = _decodificar(conteudo).translate(INVISIVEIS)
            sep = max([";", ",", "\t", "|"], key=texto.count)
            linhas_csv = [l for l in csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in l)]
            largura = max((len(l) for l in linhas_csv), default=0)
            df = pd.DataFrame([[(c.strip() or None) for c in l] + [None] * (largura - len(l)) for l in linhas_csv])
            return _df_para_tabela(df)
        if formato == "xlsx":
            abas = pd.read_excel(io.BytesIO(conteudo), sheet_name=None, header=None, dtype=object)
            tabelas = [_df_para_tabela(df, nome if len(abas) > 1 else None) for nome, df in abas.items()]
            colunas: list[str] = []
            linhas: list[dict] = []
            for t in tabelas:
                for c in t.colunas:
                    if c not in colunas:
                        colunas.append(c)
                linhas.extend(t.linhas)
            return Tabela(colunas=colunas, linhas=linhas)
    except Exception as e:  # pandas lança vários tipos
        raise ErroArquivo(f"Não consegui ler a planilha: {e}") from e
    raise ErroArquivo("Esse formato não é uma planilha")


def tabela_para_blocos(t: Tabela) -> list[Bloco]:
    blocos = []
    for i, linha in enumerate(t.linhas, start=1):
        partes = [f"{k}: {v}" for k, v in linha.items() if k != "_aba"]
        origem = f"linha {i}" + (f" (aba {linha['_aba']})" if "_aba" in linha else "")
        blocos.append(Bloco(texto="\n".join(partes), origem=origem))
    return blocos


# ---------- textos ----------
def _quebrar(texto: str, origem: str) -> list[Bloco]:
    texto = texto.strip()
    if not texto:
        return []
    if len(texto) <= MAX_BLOCO:
        return [Bloco(texto, origem)]
    blocos, atual = [], []
    tamanho = 0
    for linha in texto.splitlines():
        if tamanho + len(linha) > MAX_BLOCO and atual:
            blocos.append(Bloco("\n".join(atual), origem))
            atual, tamanho = [], 0
        atual.append(linha)
        tamanho += len(linha) + 1
    if atual:
        blocos.append(Bloco("\n".join(atual), origem))
    return blocos


def blocos_texto(texto: str) -> list[Bloco]:
    texto = texto.translate(INVISIVEIS).replace("\r\n", "\n")
    paragrafos = re.split(r"\n\s*\n", texto)
    blocos: list[Bloco] = []
    for i, p in enumerate(paragrafos, start=1):
        blocos.extend(_quebrar(p, f"parágrafo {i}"))
    return blocos


def blocos_whatsapp(texto: str) -> list[Bloco]:
    """Uma mensagem = um bloco. Ignora mensagens de sistema, apagadas e sem números."""
    texto = texto.translate(INVISIVEIS).replace("\r\n", "\n")
    mensagens: list[dict] = []
    for linha in texto.split("\n"):
        mt = WA_IOS.match(linha) or WA_ANDROID.match(linha)
        if mt:
            data, hora, autor, corpo = mt.groups()
            mensagens.append({"data": data, "hora": hora, "autor": autor.strip(" ~"), "linhas": [corpo]})
        elif WA_SISTEMA.match(linha):
            mensagens.append({"sistema": True, "linhas": []})
        elif mensagens:
            mensagens[-1]["linhas"].append(linha)
    blocos = []
    for i, msg in enumerate(mensagens, start=1):
        if msg.get("sistema"):
            continue
        corpo = ANEXO.sub("", "\n".join(msg["linhas"])).strip()
        if not corpo or "mensagem apagada" in corpo.lower() or "message deleted" in corpo.lower():
            continue
        if len(corpo) < 12 or not re.search(r"\d", corpo):
            continue
        origem = f"mensagem {i} · {msg['autor']} · {msg['data']} {msg['hora']}"
        blocos.extend(_quebrar(corpo, origem[:120]))
    return blocos


def _texto_do_zip(conteudo: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            txts = [i for i in z.infolist() if i.filename.lower().endswith(".txt") and not i.is_dir()]
            if not txts:
                raise ErroArquivo("O .zip não tem nenhum .txt (esperado: exportação de conversa do WhatsApp)")
            escolhido = next((i for i in txts if Path(i.filename).name.lower() == "_chat.txt"), txts[0])
            if escolhido.file_size > MAX_ZIP_TXT:
                raise ErroArquivo("O texto da conversa é grande demais")
            return _decodificar(z.read(escolhido))
    except zipfile.BadZipFile as e:
        raise ErroArquivo("Arquivo .zip inválido") from e


def blocos_pdf(conteudo: bytes) -> list[Bloco]:
    import pdfplumber

    blocos: list[Bloco] = []
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            for n, pagina in enumerate(pdf.pages, start=1):
                tabelas = [t for t in (pagina.extract_tables() or []) if t and len(t) > 1]
                if tabelas:
                    for t in tabelas:
                        cab = [str(c or f"Coluna {i + 1}").strip() for i, c in enumerate(t[0])]
                        for j, row in enumerate(t[1:], start=1):
                            partes = [f"{c}: {str(v).strip()}" for c, v in zip(cab, row) if v and str(v).strip()]
                            if partes:
                                blocos.append(Bloco("\n".join(partes), f"página {n}, linha {j}"))
                    continue
                texto = pagina.extract_text() or ""
                for b in blocos_texto(texto):
                    blocos.append(Bloco(b.texto, f"página {n}"))
    except Exception as e:
        raise ErroArquivo(f"Não consegui ler o PDF: {e}") from e
    if not blocos:
        raise ErroArquivo("O PDF não tem texto selecionável (PDF escaneado não é suportado)")
    return blocos


def ler_blocos(conteudo: bytes, formato: str) -> list[Bloco]:
    if formato in ("xlsx", "csv"):
        return tabela_para_blocos(ler_tabela(conteudo, formato))
    if formato == "pdf":
        return blocos_pdf(conteudo)
    if formato == "whatsapp":
        texto = _texto_do_zip(conteudo) if conteudo[:2] == b"PK" else _decodificar(conteudo)
        return blocos_whatsapp(texto)
    if formato == "txt":
        return blocos_texto(_decodificar(conteudo))
    raise ErroArquivo(f"Formato {formato} não suportado")
