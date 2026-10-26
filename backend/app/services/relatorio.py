"""Relatório em PDF da lista de objetos (com os filtros aplicados)."""
from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import models as m
from .ativos import valores_dict

AZUL = colors.HexColor("#0f5e75")
CINZA = colors.HexColor("#d8dfe5")


def gerar_pdf(ativos: list[m.Ativo], filtros: list[str], categoria: m.Categoria | None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title="Relatório de patrimônio")
    estilos = getSampleStyleSheet()
    cel = ParagraphStyle("cel", parent=estilos["BodyText"], fontSize=7.5, leading=9)
    cab = ParagraphStyle("cab", parent=cel, textColor=colors.white, fontName="Helvetica-Bold")
    titulo = ParagraphStyle("tit", parent=estilos["Title"], alignment=0, fontSize=16, textColor=AZUL)

    campos = [c for c in (categoria.campos if categoria else []) if c.ativo][:6]
    colunas = ["Patrimônio", "Nome"] + ([] if categoria else ["Categoria"]) + \
        [c.rotulo for c in campos] + ["Status", "Unidade", "Setor", "Pessoa"]

    linhas = [[Paragraph(escape(c), cab) for c in colunas]]
    for a in ativos:
        vals = valores_dict(a)
        lin = [a.patrimonio or "—", a.nome or "—"]
        if not categoria:
            lin.append(a.categoria.nome)
        for c in campos:
            v = vals.get(c.chave)
            lin.append("Sim" if v is True else "Não" if v is False else ("—" if v in (None, "") else str(v)))
        lin += [m.STATUS_ROTULO.get(a.status, a.status), a.unidade.nome,
                a.setor.nome if a.setor else "—", a.pessoa.nome if a.pessoa else "—"]
        linhas.append([Paragraph(escape(str(x)), cel) for x in lin])

    tabela = Table(linhas, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, CINZA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    resumo = f"{len(ativos)} objeto(s) · gerado em {datetime.now():%d/%m/%Y %H:%M}"
    if filtros:
        resumo += " · filtros: " + "; ".join(filtros)
    historia = [Paragraph("Relatório de patrimônio", titulo),
                Paragraph(escape(resumo), estilos["BodyText"]), Spacer(1, 6 * mm), tabela]
    doc.build(historia)
    return buf.getvalue()
