# Arquitetura — Sistema de Controle de Patrimônio

Painel para cadastrar, buscar e acompanhar equipamentos (impressoras, telefones, computadores…) com
**categorias de campos configuráveis**, posse por **unidade › setor › pessoa**, histórico de
movimentação, vínculos entre objetos, arquivamento de itens quebrados e **importação de planilhas e
textos soltos com IA (Gemini)**, sempre com revisão humana.

> Versão visual desta página: [`docs/arquitetura.html`](arquitetura.html) (abra no navegador).

## Stack

| Camada | Tecnologia |
|---|---|
| Front-end | React + Vite + TypeScript |
| Back-end | Python · FastAPI · SQLAlchemy · Pydantic |
| Banco | SQLite (modo WAL) |
| Importação | pandas/openpyxl (xlsx, csv), pdfplumber (pdf), texto puro (txt, WhatsApp) |
| IA | Google Gemini (plano gratuito) via `google-genai`, saída em JSON validada |
| Relatórios | PDF com ReportLab |
| Execução | Local, sem login (v1) |

## Visão geral

```mermaid
flowchart LR
  U([Usuário]) --> FE
  subgraph FE[Front-end · React]
    D[Dashboard] --- L[Lista + filtros]
    L --- F[Ficha do objeto]
    F --- C[Categorias e campos]
    C --- I[Importar e revisar]
  end
  FE -- REST / JSON --> API
  subgraph API[Back-end · FastAPI]
    R[Rotas + validação Pydantic] --> S[Serviços de domínio]
    S --> ORM[SQLAlchemy]
    S --> P[Parsers: xlsx · csv · txt · WhatsApp · pdf]
  end
  ORM --> DB[(SQLite)]
  S --> FS[/Pasta de uploads · arquivos importados/]
  P --> W[Worker de importação]
  W -- texto + esquema das categorias --> LLM[[Gemini API · plano gratuito]]
  LLM -- JSON estruturado --> W
  W -- itens para revisão --> DB
```

## Fluxo de importação com IA

A IA **nunca** grava direto no patrimônio: ela gera sugestões numa área de revisão. Uma pessoa aprova
(um a um ou em lote), edita ou rejeita. Objetos que já existem (mesmo patrimônio, serial ou IP) são
**marcados como duplicados e ignorados**; o cadastro existente não muda.

```mermaid
flowchart TD
  A[Upload do arquivo] --> B{Formato}
  B -- xlsx / csv organizado --> M[Mapear colunas → campos da categoria]
  B -- txt · WhatsApp · pdf · planilha bagunçada --> T[Extrair texto e quebrar em blocos]
  T --> IA[IA recebe blocos + campos e sinônimos de cada categoria]
  IA --> J[JSON por objeto: categoria, campos, confiança]
  M --> N
  J --> N[Normalizar: IP, número de patrimônio, datas, nomes de local]
  N --> X{Já existe? patrimônio · serial · IP}
  X -- sim --> DU[Avisa como duplicado e ignora · o existente não muda]
  X -- não --> NV[Marca como novo]
  NV --> RV[Tela de revisão · sempre]
  RV -- aprovar / editar / aprovar em lote --> OK[Cria objeto + valores + movimentação + auditoria]
  RV -- rejeitar --> RJ[Item descartado, fica no histórico da importação]
```

Exemplo real — mensagem de WhatsApp de uma visita técnica:

```text
DPDF – TJDFT SIG
Pat: 4386
Hostname: IMPSIGidos-4386
Endereço IP: 10.223.20.238 - IP Fixo
```

vira:

```json
{
  "categoria": "impressora",
  "patrimonio": "4386",
  "unidade": "TJDFT SIG",
  "campos": { "hostname": "IMPSIGidos-4386", "ip": "10.223.20.238" },
  "confianca": 0.97
}
```

Os **sinônimos** de cada campo (ex.: `ip` ← "Endereço IP", "IP") ensinam a IA e o mapeamento de
colunas a reconhecer o dado em arquivos diferentes.

## Ciclo de vida de um objeto

Status: `em_estoque` · `em_uso` · `em_manutencao` · `com_defeito` · `arquivado`.
Quebrou → "com defeito"; sem conserto → arquivado com motivo. Arquivado sai das listas padrão, mas
pode ser consultado e restaurado. Toda mudança de status ou de posse grava uma linha em `movimentacao`.

```mermaid
stateDiagram-v2
  direction LR
  [*] --> Em_estoque: cadastro / importação
  Em_estoque --> Em_uso: atribuir unidade (setor e pessoa opcionais)
  Em_uso --> Em_uso: transferência
  Em_uso --> Em_manutencao: enviado p/ manutenção
  Em_manutencao --> Em_uso: consertado
  Em_uso --> Com_defeito: quebrou
  Com_defeito --> Em_manutencao: enviado p/ conserto
  Com_defeito --> Arquivado: sem conserto (baixa)
  Em_manutencao --> Arquivado: sem conserto (baixa)
  Arquivado --> Em_estoque: restaurar
```

## Modelo de dados

O par `categoria → campo` define as características de cada tipo de objeto. Os valores ficam em
`ativo_valor`, uma linha por campo, com colunas tipadas (texto, número, data) para permitir filtros e
índices.

```mermaid
erDiagram
  CATEGORIA ||--o{ CAMPO : "define"
  CATEGORIA ||--o{ ATIVO : "classifica"
  ATIVO ||--o{ ATIVO_VALOR : "tem"
  CAMPO ||--o{ ATIVO_VALOR : "preenche"
  UNIDADE ||--o{ SETOR : "tem"
  UNIDADE ||--o{ ATIVO : "posse (obrigatória)"
  SETOR |o--o{ ATIVO : "posse (opcional)"
  PESSOA |o--o{ ATIVO : "posse (opcional)"
  SETOR |o--o{ PESSOA : "lotada em"
  UNIDADE ||--o{ PESSOA : "trabalha em"
  ATIVO ||--o{ MOVIMENTACAO : "histórico"
  ATIVO ||--o{ VINCULO : "origem"
  ATIVO ||--o{ VINCULO : "destino"
  IMPORTACAO ||--o{ IMPORTACAO_ITEM : "gera"
  IMPORTACAO_ITEM |o--o| ATIVO : "vira"
  ATIVO ||--o{ AUDITORIA : "alterações"

  CATEGORIA {
    int id PK
    text nome UK
    text slug UK
    text icone
    text descricao
    bool ativa
  }
  CAMPO {
    int id PK
    int categoria_id FK
    text chave
    text rotulo
    text tipo "texto|numero|data|ip|mac|telefone|lista|bool"
    bool obrigatorio
    bool unico
    bool filtravel
    json opcoes
    json sinonimos
    int ordem
  }
  ATIVO {
    int id PK
    int categoria_id FK
    text patrimonio UK "opcional"
    text nome
    text status
    int unidade_id FK "obrigatório"
    int setor_id FK "opcional"
    int pessoa_id FK "opcional"
    text observacao
    text origem "manual|planilha|ia|regras"
    datetime criado_em
    datetime atualizado_em
    datetime arquivado_em
    text motivo_arquivo
  }
  ATIVO_VALOR {
    int id PK
    int ativo_id FK
    int campo_id FK
    text valor_texto
    real valor_numero
    date valor_data
  }
  UNIDADE {
    int id PK
    text nome UK "ex.: Fórum Gama, Sede SIA"
    text sigla
    text endereco
    bool ativa
  }
  SETOR {
    int id PK
    int unidade_id FK
    text nome
    bool ativo
  }
  PESSOA {
    int id PK
    text nome
    text matricula UK
    int unidade_id FK
    int setor_id FK
    text email
    text telefone
    bool ativa
  }
  MOVIMENTACAO {
    int id PK
    int ativo_id FK
    text tipo "cadastro|transferencia|status|arquivamento"
    text status_anterior
    text status_novo
    int unidade_origem_id FK
    int unidade_destino_id FK
    int setor_origem_id FK
    int setor_destino_id FK
    int pessoa_origem_id FK
    int pessoa_destino_id FK
    datetime data
    text observacao
  }
  VINCULO {
    int id PK
    int ativo_origem_id FK
    int ativo_destino_id FK
    text tipo "fila_impressao|ramal|monitor|outro"
    text observacao
    datetime criado_em
  }
  IMPORTACAO {
    int id PK
    text arquivo_nome
    text arquivo_hash
    text metodo "mapeamento|ia"
    text status
    int total_itens
    datetime criado_em
  }
  IMPORTACAO_ITEM {
    int id PK
    int importacao_id FK
    text trecho_original
    int categoria_sugerida_id FK
    json dados_extraidos
    real confianca
    text status "pendente|aprovado|rejeitado|duplicado"
    text motivo_duplicado "patrimonio|serial|ip"
    int ativo_id FK
  }
  AUDITORIA {
    int id PK
    text entidade
    int entidade_id
    text acao
    json antes
    json depois
    datetime criado_em
  }
```

### Regras principais

| Tabela | Regra |
|---|---|
| `campo` | `UNIQUE(categoria_id, chave)`. Flags: obrigatório, único, filtrável. `sinonimos` (JSON) para IA/mapeamento |
| `ativo` | `patrimonio` opcional e único quando existe. `unidade_id` obrigatório; `setor_id` e `pessoa_id` opcionais (setor tem que ser da mesma unidade) |
| `ativo_valor` | `UNIQUE(ativo_id, campo_id)`; índice em `(campo_id, valor_texto)` |
| `setor` | `UNIQUE(unidade_id, nome)` |
| `movimentacao` | Só inserção, nunca editada. Guarda origem → destino de unidade/setor/pessoa e status anterior → novo |
| `vinculo` | Liga dois objetos (impressora ↔ fila, telefone ↔ ramal). `UNIQUE(origem, destino, tipo)` |
| `importacao_item` | `status`: pendente, aprovado, rejeitado, duplicado; `motivo_duplicado`: patrimonio, serial, ip |
| `auditoria` | Antes/depois em JSON de toda criação, edição e arquivamento |

Nada é apagado: objetos são arquivados, e a auditoria guarda cada alteração.

## Telas

| Tela | O que tem |
|---|---|
| Dashboard | Totais por categoria, status e unidade; com defeito; importações aguardando revisão; últimas movimentações |
| Objetos | Busca livre (patrimônio, nome, valores), filtros por categoria, status, unidade, setor, pessoa e campos filtráveis; exportar PDF |
| Ficha do objeto | Campos da categoria, posse, histórico, vínculos, auditoria; transferir, mudar status, vincular, arquivar |
| Categorias | Criar categoria e montar seus campos (tipo, obrigatório, único, filtrável, opções, sinônimos) |
| Importar | Upload (xlsx, csv, txt, WhatsApp, pdf), escolha entre mapeamento de colunas e IA, revisão lado a lado |
| Cadastros | Unidades e setores, pessoas, arquivados, configuração da chave do Gemini |

## Decisões da v1

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Login | Sem login por enquanto |
| 2 | Onde roda | Local |
| 3 | Patrimônio | Opcional; único quando existe |
| 4 | Posse | Unidade obrigatória › setor opcional › pessoa opcional |
| 5 | Vínculo entre objetos | Sim, já na v1 |
| 6 | Quebrou | Passa por "com defeito"; arquiva com motivo quando não tem conserto |
| 7 | Manutenções e fotos | Não registra |
| 8 | Formatos | xlsx, csv, txt, WhatsApp, PDF |
| 9 | IA | Gemini, plano gratuito |
| 10 | Revisão | Sempre revisada, com aprovação em lote |
| 11 | Duplicado | Só avisa e ignora |
| 12 | Exportação | PDF |

> **Atenção (Gemini gratuito):** no plano gratuito o Google pode usar o conteúdo enviado para melhorar
> os produtos. Antes de enviar planilhas reais com IPs internos, confirme com a TI ou use o plano pago.
