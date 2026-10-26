import io
import zipfile

from app.services.importacao import ia


def _impressora(client, cat, unidade, **extra):
    corpo = {"categoria_id": cat["impressora"]["id"], "unidade_id": unidade["id"], "status": "em_uso",
             "valores": {"hostname": "IMP-1", "ip": "10.0.0.5"}}
    corpo.update(extra)
    return client.post("/api/ativos", json=corpo)


# ---------- categorias ----------
def test_categorias_padrao(client, cat):
    assert {"impressora", "telefone_ip", "computador", "monitor"} <= set(cat)
    assert any(c["chave"] == "ip" and c["tipo"] == "ip" for c in cat["impressora"]["campos"])


def test_criar_categoria_com_campos(client):
    r = client.post("/api/categorias", json={"nome": "Nobreak", "campos": [
        {"rotulo": "Potência (VA)", "tipo": "numero", "obrigatorio": True},
        {"rotulo": "Tipo", "tipo": "lista", "opcoes": ["Online", "Interativo"]}]})
    assert r.status_code == 201, r.text
    campos = r.json()["campos"]
    assert [c["chave"] for c in campos] == ["potencia_va", "tipo"]
    assert client.post("/api/categorias", json={"nome": "nobreak"}).status_code == 409
    r = client.post(f"/api/categorias/{r.json()['id']}/campos", json={"rotulo": "Cor", "tipo": "lista"})
    assert r.status_code == 400  # lista sem opções


# ---------- objetos ----------
def test_criar_e_validar_objeto(client, cat, unidade):
    r = _impressora(client, cat, unidade, patrimonio="4386",
                    valores={"hostname": "IMPSIGidos-4386", "ip": "10.223.20.238 - IP Fixo", "tipo_ip": "fixo"})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["valores"]["ip"] == "10.223.20.238"
    assert a["valores"]["tipo_ip"] == "Fixo"

    # patrimônio repetido e IP único repetido
    r = _impressora(client, cat, unidade, patrimonio="4386", valores={"ip": "10.223.20.238"})
    assert r.status_code == 422
    erros = r.json()["detail"]["erros"]
    assert "patrimonio" in erros and "ip" in erros

    # IP inválido e campo inexistente
    r = _impressora(client, cat, unidade, valores={"ip": "abc", "xpto": "1"})
    erros = r.json()["detail"]["erros"]
    assert "ip" in erros and "xpto" in erros


def test_patrimonio_opcional(client, cat, unidade):
    a = _impressora(client, cat, unidade).json()
    b = _impressora(client, cat, unidade, valores={"ip": "10.0.0.6"}).json()
    assert a["patrimonio"] is None and b["patrimonio"] is None


def test_obrigatorio(client, cat, unidade):
    r = client.post("/api/ativos", json={"categoria_id": cat["telefone_ip"]["id"], "unidade_id": unidade["id"],
                                         "valores": {"ip": "10.0.0.9"}})
    assert r.status_code == 422
    assert "ramal" in r.json()["detail"]["erros"]


def test_setor_de_outra_unidade(client, cat, unidade):
    outra = client.post("/api/unidades", json={"nome": "Sede"}).json()
    setor = client.post(f"/api/unidades/{outra['id']}/setores", json={"nome": "Protocolo"}).json()
    r = _impressora(client, cat, unidade, setor_id=setor["id"])
    assert r.status_code == 422
    assert "setor_id" in r.json()["detail"]["erros"]


def test_filtros_e_busca(client, cat, unidade):
    _impressora(client, cat, unidade, patrimonio="1", valores={"hostname": "IMP-A", "ip": "10.0.0.1", "marca": "Samsung"})
    _impressora(client, cat, unidade, patrimonio="2", valores={"hostname": "IMP-B", "ip": "10.0.0.2", "marca": "HP"})
    assert client.get("/api/ativos", params={"q": "10.0.0.2"}).json()["total"] == 1
    assert client.get("/api/ativos", params={"campo_marca": "sams"}).json()["total"] == 1
    assert client.get("/api/ativos", params={"categoria_id": cat["impressora"]["id"]}).json()["total"] == 2
    assert client.get("/api/ativos", params={"categoria_id": cat["monitor"]["id"]}).json()["total"] == 0


def test_ciclo_de_vida(client, cat, unidade):
    a = _impressora(client, cat, unidade, patrimonio="77").json()
    # não arquiva direto
    r = client.post(f"/api/ativos/{a['id']}/arquivar", json={"motivo": "quebrou"})
    assert r.status_code == 409
    assert client.post(f"/api/ativos/{a['id']}/status", json={"status": "com_defeito", "observacao": "não liga"}).status_code == 200
    r = client.post(f"/api/ativos/{a['id']}/arquivar", json={"motivo": "Placa queimada, sem conserto"})
    assert r.status_code == 200 and r.json()["status"] == "arquivado"
    # some da lista padrão, aparece nos arquivados
    assert client.get("/api/ativos").json()["total"] == 0
    assert client.get("/api/ativos", params={"arquivados": True}).json()["total"] == 1
    # IP volta a ficar livre enquanto arquivado
    assert _impressora(client, cat, unidade).status_code == 201
    # restaurar com conflito de IP único
    r = client.post(f"/api/ativos/{a['id']}/restaurar", json={})
    assert r.status_code == 422
    d = client.get(f"/api/ativos/{a['id']}").json()
    assert [mv["tipo"] for mv in d["movimentacoes"]] == ["arquivamento", "status", "cadastro"]
    assert any(x["acao"] == "arquivar" for x in d["auditoria"])


def test_transferencia(client, cat, unidade):
    a = _impressora(client, cat, unidade).json()
    setor = client.post(f"/api/unidades/{unidade['id']}/setores", json={"nome": "Cível"}).json()
    pessoa = client.post("/api/pessoas", json={"nome": "Maria", "unidade_id": unidade["id"], "setor_id": setor["id"]}).json()
    r = client.post(f"/api/ativos/{a['id']}/transferir",
                    json={"unidade_id": unidade["id"], "setor_id": setor["id"], "pessoa_id": pessoa["id"]})
    assert r.status_code == 200
    assert r.json()["setor"]["nome"] == "Cível" and r.json()["pessoa"]["nome"] == "Maria"
    mov = client.get(f"/api/ativos/{a['id']}").json()["movimentacoes"][0]
    assert mov["tipo"] == "transferencia" and mov["setor_destino"]["nome"] == "Cível"


def test_editar_e_auditoria(client, cat, unidade):
    a = _impressora(client, cat, unidade).json()
    r = client.put(f"/api/ativos/{a['id']}", json={"patrimonio": "555", "valores": {"modelo": "M408", "ip": ""}})
    assert r.status_code == 200, r.text
    assert r.json()["patrimonio"] == "555" and "ip" not in r.json()["valores"]
    aud = client.get(f"/api/ativos/{a['id']}").json()["auditoria"]
    assert aud[0]["acao"] == "editar" and aud[0]["depois"]["patrimonio"] == "555"


def test_vinculos(client, cat, unidade):
    pc = client.post("/api/ativos", json={"categoria_id": cat["computador"]["id"], "unidade_id": unidade["id"]}).json()
    mon = client.post("/api/ativos", json={"categoria_id": cat["monitor"]["id"], "unidade_id": unidade["id"]}).json()
    r = client.post(f"/api/ativos/{pc['id']}/vinculos", json={"ativo_destino_id": mon["id"], "tipo": "monitor"})
    assert r.status_code == 201
    assert client.post(f"/api/ativos/{mon['id']}/vinculos", json={"ativo_destino_id": pc["id"], "tipo": "monitor"}).status_code == 409
    v = client.get(f"/api/ativos/{mon['id']}").json()["vinculos"]
    assert v[0]["outro"]["id"] == pc["id"] and v[0]["direcao"] == "destino"
    assert client.delete(f"/api/vinculos/{v[0]['id']}").status_code == 200


def test_relatorio_pdf(client, cat, unidade):
    _impressora(client, cat, unidade, patrimonio="1")
    r = client.get("/api/ativos/relatorio.pdf", params={"categoria_id": cat["impressora"]["id"]})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_dashboard(client, cat, unidade):
    _impressora(client, cat, unidade)
    d = client.get("/api/dashboard").json()
    assert d["total"] == 1 and d["por_status"]["em_uso"] == 1
    assert d["por_unidade"][0]["nome"] == "Fórum Gama"
    serie = d["serie_mensal"]
    assert len(serie) == 12 and serie[-1]["cadastros"] == 1 and serie[-1]["ativos"] == 1


# ---------- importação ----------
WHATS = """[29/09/2026, 13:39:29] Leandro: boa tarde, estamos iniciando as preventivas na sede
[29/09/2026, 15:09:25] ~ Victor: DPDF – SEDE
Pat: 3605
Hostname: IMP-SEDEdie3605
Endereço IP: 10.223.0.64 — IP Fixo <anexado: 00003159-PHOTO.jpg>
[29/09/2026, 15:19:10] ~ Victor: DPDF – SEDE
Pat: 8590
Hostname: IMP-SEDEuni8590
Endereço IP: 10.223.0.62 — IP Fixo
[29/09/2026, 15:20:10] ~ Victor: DPDF – SEDE
Pat: 8590
Hostname: IMP-SEDEuni8590
Endereço IP: 10.223.0.62 — IP Fixo
[29/09/2026, 15:30:00] Gustavo: ok
"""


def _upload(client, nome, conteudo, **form):
    return client.post("/api/importacoes", files={"arquivo": (nome, conteudo)}, data=form)


def test_importar_whatsapp_por_regras(client, cat, unidade):
    r = _upload(client, "conversa.txt", WHATS.encode(), metodo="regras", unidade_padrao_id=str(unidade["id"]))
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["formato"] == "whatsapp" and imp["status"] == "revisao"
    d = client.get(f"/api/importacoes/{imp['id']}").json()
    assert len(d["itens"]) == 3
    primeiro = d["itens"][0]
    assert primeiro["dados_extraidos"]["patrimonio"] == "3605"
    assert primeiro["dados_extraidos"]["campos"]["ip"].startswith("10.223.0.64")
    assert primeiro["dados_extraidos"]["unidade_id"] == unidade["id"]
    assert d["itens"][2]["status"] == "duplicado"  # 8590 repetido no arquivo

    lote = client.post(f"/api/importacoes/{imp['id']}/aprovar-lote", json={"confianca_minima": 0.5}).json()
    assert lote["aprovados"] == 2, lote
    d = client.get(f"/api/importacoes/{imp['id']}").json()
    assert d["status"] == "concluida"
    obj = client.get("/api/ativos", params={"q": "3605"}).json()["itens"][0]
    assert obj["valores"]["ip"] == "10.223.0.64" and obj["origem"] == "regras" and obj["status"] == "em_uso"
    assert obj["nome"] == "IMP-SEDEdie3605"  # sem nome no arquivo: usa o hostname

    # mesmo arquivo de novo: aviso e tudo duplicado
    r = _upload(client, "conversa.txt", WHATS.encode(), metodo="regras", unidade_padrao_id=str(unidade["id"]))
    imp2 = r.json()
    assert "já foi importado" in imp2["meta"]["aviso"]
    assert imp2["contagem"]["duplicado"] == 3


def test_importar_zip_whatsapp(client, cat, unidade):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("_chat.txt", WHATS)
        z.writestr("foto.jpg", b"\xff\xd8")
    r = _upload(client, "WhatsApp Chat.zip", buf.getvalue(), metodo="regras", unidade_padrao_id=str(unidade["id"]))
    assert r.json()["formato"] == "whatsapp" and r.json()["total_itens"] == 3


def test_importar_planilha_com_mapeamento(client, cat, unidade):
    csv = ("Relação de impressoras\n\nPatrimônio;Unidade;Endereço IP;Hostname;Serial\n"
           "4440;TJDFT SIG;10.223.21.132;IMPSIGrec1-4440;088WB07K813DSMN\n"
           "4387;TJDFT SIG;10.223.20.168;IMPSIGcivi-4387;\n"
           "4389;Fórum Gama;999.1.1.1;IMPGAM;\n").encode("utf-8")
    r = _upload(client, "imps.csv", csv, metodo="mapeamento", categoria_id=str(cat["impressora"]["id"]))
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["status"] == "mapeamento"
    sug = imp["meta"]["sugestao"]
    assert sug == {"Patrimônio": "__patrimonio__", "Unidade": "__unidade__", "Endereço IP": "ip",
                   "Hostname": "hostname", "Serial": "serial"}
    d = client.post(f"/api/importacoes/{imp['id']}/mapeamento", json={"mapa": sug}).json()
    assert d["status"] == "revisao" and len(d["itens"]) == 3
    it1, it2, it3 = d["itens"]
    assert any("será criada" in msg["texto"] for msg in it1["mensagens"])
    assert it3["dados_extraidos"]["unidade_id"] == unidade["id"]  # casou “Fórum Gama”
    assert any(msg["tipo"] == "erro" for msg in it3["mensagens"])  # IP inválido

    assert client.post(f"/api/importacoes/{imp['id']}/itens/{it1['id']}/aprovar").status_code == 200
    assert any(u["nome"] == "TJDFT SIG" for u in client.get("/api/unidades").json())
    r = client.post(f"/api/importacoes/{imp['id']}/itens/{it3['id']}/aprovar")
    assert r.status_code == 422
    # corrige e aprova
    dados = it3["dados_extraidos"] | {"campos": {"ip": "10.223.32.9", "hostname": "IMPGAM"}}
    r = client.put(f"/api/importacoes/{imp['id']}/itens/{it3['id']}", json={"dados": dados})
    assert r.status_code == 200 and not any(x["tipo"] == "erro" for x in r.json()["mensagens"])
    assert client.post(f"/api/importacoes/{imp['id']}/itens/{it3['id']}/aprovar").status_code == 200
    assert client.post(f"/api/importacoes/{imp['id']}/itens/{it2['id']}/rejeitar").status_code == 200
    assert client.get(f"/api/importacoes/{imp['id']}").json()["status"] == "concluida"


def test_importar_ia_com_gemini_simulado(client, cat, unidade, monkeypatch):
    from app.config import settings
    settings.gemini_api_key = "teste"

    def falso(prompt):
        assert "impressora" in prompt and "BLOCO 1" in prompt
        return ia.RespostaIA(objetos=[ia.ObjetoExtraido(
            blocos=[1], categoria="impressora", patrimonio="3605", nome="IMP-SEDEdie3605", unidade="Fórum Gama",
            setor="", pessoa="", observacao="", confianca=0.95,
            campos=[ia.CampoExtraido(chave="ip", valor="10.223.0.64"),
                    ia.CampoExtraido(chave="inexistente", valor="x")])])

    monkeypatch.setattr(ia, "_chamar_gemini", falso)
    r = _upload(client, "conversa.txt", WHATS.encode(), metodo="ia")
    assert r.status_code == 201, r.text
    d = client.get(f"/api/importacoes/{r.json()['id']}").json()  # BackgroundTasks roda antes da resposta no TestClient
    assert d["status"] == "revisao", d
    item = d["itens"][0]
    assert item["dados_extraidos"]["unidade_id"] == unidade["id"]
    assert item["dados_extraidos"]["campos"] == {"ip": "10.223.0.64"}
    assert client.post(f"/api/importacoes/{d['id']}/itens/{item['id']}/aprovar").status_code == 200


def test_ia_sem_chave(client):
    r = _upload(client, "conversa.txt", WHATS.encode(), metodo="ia")
    assert r.json()["status"] == "erro" and "Gemini" in r.json()["erro"]


def test_formato_invalido(client):
    assert _upload(client, "foto.png", b"123", metodo="regras").status_code == 400
