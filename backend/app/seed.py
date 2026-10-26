"""Categorias iniciais e, opcionalmente, dados de exemplo.

Uso:
    python -m app.seed             # cria as categorias padrão (se o banco estiver vazio)
    python -m app.seed --exemplos  # também cria unidades e objetos FICTÍCIOS para testar
"""
from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .schemas import AtivoCriar
from .services import ativos as svc
from .services.validacao import slugificar

C = dict  # atalho para definir campos

CATEGORIAS = [
    {
        "nome": "Impressora", "icone": "printer",
        "descricao": "Impressoras e multifuncionais de rede",
        "campos": [
            C(chave="hostname", rotulo="Hostname", filtravel=True, sinonimos=["Host", "Nome de rede", "Nome na rede"]),
            C(chave="ip", rotulo="Endereço IP", tipo="ip", unico=True, filtravel=True,
              sinonimos=["IP", "End. IP", "Endereço de IP", "IP da impressora"]),
            C(chave="tipo_ip", rotulo="Tipo de IP", tipo="lista", opcoes=["Fixo", "DHCP"], filtravel=True,
              sinonimos=["IP fixo", "Configuração de IP"]),
            C(chave="serial", rotulo="Número de série", unico=True,
              sinonimos=["Serial", "N/S", "SN", "Nº de série", "Série"]),
            C(chave="marca", rotulo="Marca", filtravel=True, sinonimos=["Fabricante"]),
            C(chave="modelo", rotulo="Modelo", filtravel=True),
            C(chave="cor", rotulo="Impressão", tipo="lista", opcoes=["Monocromática", "Colorida"], filtravel=True,
              sinonimos=["Mono/Color", "Tipo de impressão"]),
            C(chave="fila", rotulo="Fila no servidor", sinonimos=["Fila", "Nome da fila", "Fila de impressão"]),
        ],
    },
    {
        "nome": "Telefone IP", "icone": "phone",
        "descricao": "Aparelhos de telefonia IP",
        "campos": [
            C(chave="ramal", rotulo="Ramal", tipo="telefone", obrigatorio=True, unico=True, filtravel=True,
              sinonimos=["Extensão", "Número do ramal"]),
            C(chave="ip", rotulo="Endereço IP", tipo="ip", unico=True, filtravel=True, sinonimos=["IP"]),
            C(chave="mac", rotulo="MAC", tipo="mac", unico=True, sinonimos=["Endereço MAC", "MAC address"]),
            C(chave="marca", rotulo="Marca", filtravel=True, sinonimos=["Fabricante"]),
            C(chave="modelo", rotulo="Modelo", filtravel=True),
        ],
    },
    {
        "nome": "Computador", "icone": "monitor",
        "descricao": "Desktops e notebooks",
        "campos": [
            C(chave="hostname", rotulo="Hostname", filtravel=True, sinonimos=["Nome do computador", "Host"]),
            C(chave="ip", rotulo="Endereço IP", tipo="ip", filtravel=True, sinonimos=["IP"]),
            C(chave="mac", rotulo="MAC", tipo="mac", sinonimos=["Endereço MAC"]),
            C(chave="serial", rotulo="Número de série", unico=True, sinonimos=["Serial", "Service tag", "N/S"]),
            C(chave="modelo", rotulo="Modelo", filtravel=True),
            C(chave="sistema", rotulo="Sistema operacional", tipo="lista", filtravel=True,
              opcoes=["Windows 10", "Windows 11", "Linux", "Outro"], sinonimos=["SO", "Sistema"]),
            C(chave="memoria_gb", rotulo="Memória (GB)", tipo="numero", sinonimos=["RAM", "Memória"]),
        ],
    },
    {
        "nome": "Monitor", "icone": "display",
        "descricao": "Monitores de vídeo",
        "campos": [
            C(chave="serial", rotulo="Número de série", unico=True, sinonimos=["Serial", "N/S"]),
            C(chave="marca", rotulo="Marca", filtravel=True),
            C(chave="modelo", rotulo="Modelo", filtravel=True),
            C(chave="polegadas", rotulo="Polegadas", tipo="numero", filtravel=True, sinonimos=["Tamanho", "Pol"]),
        ],
    },
]


def criar_categorias(db: Session) -> int:
    if db.scalar(select(m.Categoria.id).limit(1)):
        return 0
    for cat in CATEGORIAS:
        c = m.Categoria(nome=cat["nome"], slug=slugificar(cat["nome"]), icone=cat["icone"],
                        descricao=cat["descricao"])
        for i, campo in enumerate(cat["campos"]):
            dados = dict(campo)
            c.campos.append(m.Campo(ordem=i, tipo=dados.pop("tipo", "texto"), **dados))
        db.add(c)
    db.flush()
    return len(CATEGORIAS)


def criar_exemplos(db: Session) -> None:
    """Dados fictícios (IPs de rede privada de exemplo) para conhecer o sistema."""
    if db.scalar(select(m.Ativo.id).limit(1)):
        print("Já existem objetos; exemplos não criados.")
        return
    cats = {c.slug: c for c in db.scalars(select(m.Categoria)).all()}
    centro = m.Unidade(nome="Unidade Exemplo Centro", sigla="UEC")
    norte = m.Unidade(nome="Unidade Exemplo Norte", sigla="UEN")
    db.add_all([centro, norte])
    db.flush()
    protocolo = m.Setor(unidade_id=centro.id, nome="Protocolo")
    gabinete = m.Setor(unidade_id=centro.id, nome="Gabinete")
    db.add_all([protocolo, gabinete])
    db.flush()
    ana = m.Pessoa(nome="Ana Exemplo", matricula="EX-001", unidade_id=centro.id, setor_id=gabinete.id)
    db.add(ana)
    db.flush()

    exemplos = [
        ("impressora", "9001", "IMP-UEC-PROT-9001", centro, protocolo, None, "em_uso",
         {"hostname": "IMP-UEC-PROT-9001", "ip": "192.168.10.21", "tipo_ip": "Fixo",
          "serial": "EXEMPLO0001", "marca": "Marca A", "modelo": "M408", "cor": "Monocromática"}),
        ("impressora", "9002", "IMP-UEC-GAB-9002", centro, gabinete, None, "em_uso",
         {"hostname": "IMP-UEC-GAB-9002", "ip": "192.168.10.22", "tipo_ip": "Fixo",
          "serial": "EXEMPLO0002", "marca": "Marca A", "modelo": "C406", "cor": "Colorida"}),
        ("impressora", "9003", "IMP-UEN-9003", norte, None, None, "com_defeito",
         {"hostname": "IMP-UEN-9003", "ip": "192.168.20.21", "tipo_ip": "Fixo", "marca": "Marca A",
          "modelo": "M408", "cor": "Monocromática"}),
        ("telefone_ip", None, "Ramal 4410", centro, gabinete, ana, "em_uso",
         {"ramal": "4410", "ip": "192.168.30.10", "mac": "00:11:22:33:44:55", "marca": "Marca B"}),
        ("computador", "9010", "PC-UEC-GAB-01", centro, gabinete, ana, "em_uso",
         {"hostname": "PC-UEC-GAB-01", "ip": "192.168.10.50", "sistema": "Windows 11", "memoria_gb": 16}),
        ("monitor", "9011", "Monitor 24\"", centro, gabinete, ana, "em_uso",
         {"marca": "Marca C", "polegadas": 24}),
        ("computador", "9012", "PC-UEN-ESTOQUE", norte, None, None, "em_estoque",
         {"hostname": "PC-UEN-ESTOQUE", "sistema": "Linux", "memoria_gb": 8}),
    ]
    criados = {}
    for slug, pat, nome, uni, setor, pessoa, status, valores in exemplos:
        a = svc.criar(db, AtivoCriar(categoria_id=cats[slug].id, patrimonio=pat, nome=nome, status=status,
                                     unidade_id=uni.id, setor_id=setor.id if setor else None,
                                     pessoa_id=pessoa.id if pessoa else None, valores=valores,
                                     observacao="Dado de exemplo"))
        criados[nome] = a
    db.add(m.Vinculo(ativo_origem_id=criados["PC-UEC-GAB-01"].id,
                     ativo_destino_id=criados['Monitor 24"'].id, tipo="monitor"))
    db.flush()


def main() -> None:
    from .database import Base, engine, nova_sessao
    from .config import settings

    settings.preparar_pastas()
    Base.metadata.create_all(engine)
    db = nova_sessao()
    try:
        n = criar_categorias(db)
        print(f"{n} categoria(s) criada(s)." if n else "Categorias já existiam.")
        if "--exemplos" in sys.argv:
            criar_exemplos(db)
            print("Dados de exemplo criados.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
