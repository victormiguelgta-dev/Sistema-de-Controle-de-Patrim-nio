"""Converte e valida valores de campo conforme o tipo definido na categoria."""
from __future__ import annotations

import ipaddress
import re
import unicodedata
from datetime import date, datetime

IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_RE = re.compile(r"([0-9A-Fa-f]{2})[:\-.]?([0-9A-Fa-f]{2})[:\-.]?([0-9A-Fa-f]{2})[:\-.]?"
                    r"([0-9A-Fa-f]{2})[:\-.]?([0-9A-Fa-f]{2})[:\-.]?([0-9A-Fa-f]{2})")
VERDADEIRO = {"sim", "s", "true", "1", "yes", "verdadeiro", "x"}
FALSO = {"nao", "não", "n", "false", "0", "no", "falso"}


class ErroValidacao(Exception):
    def __init__(self, erros: dict[str, str], mensagem: str = "Dados inválidos"):
        super().__init__(mensagem)
        self.erros = erros
        self.mensagem = mensagem


def normalizar_texto(s: str | None) -> str:
    """minúsculas, sem acento, só letras/números separados por espaço."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def slugificar(s: str) -> str:
    return normalizar_texto(s).replace(" ", "_")[:80] or "item"


def vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def converter(tipo: str, valor, opcoes: list | None = None) -> tuple[str, float | None, date | None]:
    """Devolve (valor_texto, valor_numero, valor_data). Lança ValueError com mensagem amigável."""
    if isinstance(valor, bool):
        texto = "true" if valor else "false"
    else:
        texto = str(valor).strip()

    if tipo == "texto":
        return texto, None, None

    if tipo == "numero":
        bruto = texto.replace(" ", "")
        if "," in bruto and "." in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")
        else:
            bruto = bruto.replace(",", ".")
        try:
            n = float(bruto)
        except ValueError:
            raise ValueError(f"“{texto}” não é um número")
        return (str(int(n)) if n.is_integer() else str(n)), n, None

    if tipo == "data":
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                d = datetime.strptime(texto, fmt).date()
                return d.isoformat(), None, d
            except ValueError:
                continue
        raise ValueError(f"“{texto}” não é uma data (use dd/mm/aaaa)")

    if tipo == "bool":
        t = texto.lower()
        if t in VERDADEIRO:
            return "true", None, None
        if t in FALSO:
            return "false", None, None
        raise ValueError(f"“{texto}” não é sim/não")

    if tipo == "ip":
        m = IPV4_RE.search(texto)
        if not m:
            raise ValueError(f"“{texto}” não tem um IPv4 válido")
        try:
            ip = ipaddress.IPv4Address(m.group(0))
        except ipaddress.AddressValueError:
            raise ValueError(f"“{m.group(0)}” não é um IPv4 válido")
        return str(ip), None, None

    if tipo == "mac":
        m = MAC_RE.search(texto)
        if not m:
            raise ValueError(f"“{texto}” não é um endereço MAC")
        return ":".join(g.upper() for g in m.groups()), None, None

    if tipo == "telefone":
        limpo = re.sub(r"[^\d+]", "", texto)
        if not re.search(r"\d", limpo):
            raise ValueError(f"“{texto}” não é um telefone/ramal")
        return limpo, None, None

    if tipo == "lista":
        opcoes = opcoes or []
        for op in opcoes:
            if normalizar_texto(op) == normalizar_texto(texto):
                return op, None, None
        raise ValueError(f"“{texto}” não está entre as opções: {', '.join(opcoes)}")

    return texto, None, None


def valor_para_saida(tipo: str, texto: str | None, numero: float | None):
    if texto is None:
        return None
    if tipo == "numero" and numero is not None:
        return int(numero) if float(numero).is_integer() else numero
    if tipo == "bool":
        return texto == "true"
    return texto
