# Sistema de Controle de Patrimônio

Painel para cadastrar, buscar e acompanhar equipamentos (impressoras, telefones IP, computadores,
monitores…) com **categorias de campos configuráveis**, posse por **unidade › setor › pessoa**,
histórico de movimentação, vínculos entre objetos, arquivamento de itens sem conserto e
**importação de planilhas, PDFs, textos e conversas do WhatsApp** — com IA (modelo local no Ollama ou
Google Gemini), por regras ou por mapeamento de colunas. Nada entra no patrimônio sem revisão.

- Arquitetura, fluxos e modelo do banco: [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md)
  (versão visual em [`docs/arquitetura.html`](docs/arquitetura.html))
- Stack: React + Vite + TypeScript · Python + FastAPI + SQLAlchemy · SQLite · Ollama / Gemini

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
cp .env.example .env          # opcional: a IA também pode ser configurada pela tela Configurações
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
| **IA** | Textos soltos, conversas do WhatsApp, PDFs, planilhas bagunçadas. Entende unidade, categoria e campos | Com Ollama, não. Com Gemini, sim |
| **Regras** | Linhas no formato `Rótulo: valor` (ex.: `Pat: 4386`, `Endereço IP: 10.0.0.1`), usando os sinônimos dos campos | Não |
| **Mapear colunas** | Planilhas organizadas (xlsx, csv): cada coluna vai para um campo | Não |

Formatos aceitos: `.xlsx`, `.csv`, `.txt`, `.pdf` (com texto selecionável) e a exportação de conversa
do WhatsApp (`.zip` ou `.txt` — só o texto é lido).

Todo item passa pela tela de revisão: dá para corrigir, aprovar um a um ou em lote (por confiança),
ou rejeitar. Objetos que já existem (mesmo patrimônio, serial ou IP) são marcados como **duplicados
e ignorados** — o cadastro existente nunca é alterado por uma importação.

### IA: Ollama (local, padrão) ou Gemini

A escolha fica em **Configurações**, que também mostra se a IA está pronta e o que falta.

**Ollama — o modelo roda no seu computador, nada sai da máquina**

1. Instale o Ollama: https://ollama.com/download (Windows, Mac ou Linux) e deixe ele aberto.
2. Baixe o modelo (uma vez só, ~4,7 GB):
   ```bash
   ollama pull qwen2.5:7b
   ```
3. Em **Configurações**, clique em *Verificar de novo*. Pronto.

Precisa de uns 8 GB de RAM livres. Com placa de vídeo (ou Mac M1+) fica rápido; só no processador,
cada trecho de texto leva de segundos a alguns minutos. Computador fraco: use `qwen2.5:3b`.
Ajustes no `backend/.env`: `OLLAMA_URL`, `OLLAMA_MODELO`, `OLLAMA_TIMEOUT_SEGUNDOS`, `OLLAMA_MAX_CHARS_POR_LOTE`.

**Gemini — nuvem do Google**

1. Crie uma chave gratuita em https://aistudio.google.com/apikey
2. Em **Configurações**, escolha Gemini e cole a chave.

O plano gratuito limita requisições por minuto (o sistema espera entre os lotes) e, pelos termos do
Google, o conteúdo enviado pode ser usado para melhorar os produtos e lido por revisores.
**Use o Gemini só com dados de teste.** Para planilhas reais, use o Ollama ou os métodos sem IA.

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
