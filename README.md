# Sistema de Controle de Patrimônio

Painel para cadastrar, buscar e acompanhar equipamentos (impressoras, telefones IP, computadores,
monitores…) com **categorias de campos configuráveis**, posse por **unidade › setor › pessoa**,
histórico de movimentação, vínculos entre objetos, arquivamento de itens sem conserto e
**importação de planilhas, PDFs, textos e conversas do WhatsApp** — com IA (Google Gemini), por
regras ou por mapeamento de colunas. Nada entra no patrimônio sem revisão.

- Arquitetura, fluxos e modelo do banco: [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md)
  (versão visual em [`docs/arquitetura.html`](docs/arquitetura.html))
- Stack: React + Vite + TypeScript · Python + FastAPI + SQLAlchemy · SQLite · Gemini

## Como rodar (local)

Pré-requisitos: **Python 3.11+** e **Node.js 18+**.

### 1. Back-end (API)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # opcional: a chave do Gemini também pode ser salva pela tela Configurações
python -m app.seed --exemplos # opcional: cria unidades e objetos FICTÍCIOS para conhecer o sistema
uvicorn app.main:app --reload
```

A API sobe em http://localhost:8000 (documentação interativa em http://localhost:8000/docs).
O banco fica em `backend/data/patrimonio.db` e é criado sozinho na primeira execução, já com as
categorias Impressora, Telefone IP, Computador e Monitor.

### 2. Front-end (telas)

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173.

> Para usar sem o Vite: rode `npm run build` uma vez. A API passa a servir as telas em
> http://localhost:8000.

## Importação

| Método | Para quê | Sai do computador? |
|---|---|---|
| **IA (Gemini)** | Textos soltos, conversas do WhatsApp, PDFs, planilhas bagunçadas. Entende unidade, categoria e campos | Sim, o texto vai para o Gemini |
| **Regras** | Linhas no formato `Rótulo: valor` (ex.: `Pat: 4386`, `Endereço IP: 10.0.0.1`), usando os sinônimos dos campos | Não |
| **Mapear colunas** | Planilhas organizadas (xlsx, csv): cada coluna vai para um campo | Não |

Formatos aceitos: `.xlsx`, `.csv`, `.txt`, `.pdf` (com texto selecionável) e a exportação de conversa
do WhatsApp (`.zip` ou `.txt` — só o texto é lido).

Todo item passa pela tela de revisão: dá para corrigir, aprovar um a um ou em lote (por confiança),
ou rejeitar. Objetos que já existem (mesmo patrimônio, serial ou IP) são marcados como **duplicados
e ignorados** — o cadastro existente nunca é alterado por uma importação.

### Chave do Gemini

1. Crie uma chave gratuita em https://aistudio.google.com/apikey
2. Cole em **Configurações** no sistema (ou em `GEMINI_API_KEY` no `backend/.env`)

O plano gratuito tem limite de requisições por minuto, então o sistema manda o texto em lotes e
espera entre eles (`GEMINI_INTERVALO_SEGUNDOS`). O modelo padrão é `gemini-2.5-flash`; troque em
Configurações se o Google lançar outro.

> **Atenção:** no plano gratuito o Google pode usar o conteúdo enviado para melhorar os produtos.
> Antes de enviar planilhas reais com IPs internos, confirme com a TI ou use o método **Regras**.

## Regras principais

- **Patrimônio** é opcional; quando existe, não pode repetir.
- **Unidade** é obrigatória; **setor** e **pessoa** são opcionais (o setor tem que ser da unidade).
- Campos marcados como **únicos** (ex.: IP de impressora) não repetem entre objetos ativos.
- Quebrou: mude o status para **Com defeito**. Só objetos com defeito ou em manutenção podem ser
  **arquivados**, sempre com motivo. Arquivados saem das listas, mas podem ser consultados e restaurados.
- Nada é apagado: toda alteração fica no **histórico** e na **auditoria** do objeto.
- Sem login nesta versão (uso local).

## Testes

```bash
cd backend
pytest
```

## Estrutura

```
backend/
  app/
    main.py            # FastAPI, rotas em /api
    models.py          # tabelas (SQLAlchemy)
    schemas.py         # entrada/saída (Pydantic)
    seed.py            # categorias padrão e dados de exemplo
    routers/           # categorias, cadastros, ativos, importações, painel
    services/
      ativos.py        # regras de cadastro, posse, status, arquivamento
      validacao.py     # tipos de campo (IP, MAC, data, lista…)
      relatorio.py     # PDF
      importacao/      # leitores de arquivo, regras, Gemini, revisão
  tests/
frontend/
  src/
    pages/             # Painel, Objetos, Ficha, Categorias, Unidades, Pessoas, Importar, Revisão
    components/ui.tsx  # componentes compartilhados
docs/                  # arquitetura e modelagem
```
