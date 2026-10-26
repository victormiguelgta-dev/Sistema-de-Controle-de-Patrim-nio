// Tipos e chamadas da API (FastAPI em /api)

export type TipoCampo = "texto" | "numero" | "data" | "bool" | "ip" | "mac" | "telefone" | "lista";
export type Status = "em_estoque" | "em_uso" | "em_manutencao" | "com_defeito" | "arquivado";

export const STATUS_ROTULO: Record<Status, string> = {
  em_estoque: "Em estoque",
  em_uso: "Em uso",
  em_manutencao: "Em manutenção",
  com_defeito: "Com defeito",
  arquivado: "Arquivado",
};
export const STATUS_EDITAVEIS: Status[] = ["em_estoque", "em_uso", "em_manutencao", "com_defeito"];
export const TIPO_ROTULO: Record<TipoCampo, string> = {
  texto: "Texto",
  numero: "Número",
  data: "Data",
  bool: "Sim/Não",
  ip: "Endereço IP",
  mac: "MAC",
  telefone: "Telefone/Ramal",
  lista: "Lista de opções",
};

export interface Ref { id: number; nome: string }

export interface Campo {
  id: number;
  categoria_id: number;
  chave: string;
  rotulo: string;
  tipo: TipoCampo;
  obrigatorio: boolean;
  unico: boolean;
  filtravel: boolean;
  opcoes: string[];
  sinonimos: string[];
  ordem: number;
  ativo: boolean;
}

export interface Categoria {
  id: number;
  nome: string;
  slug: string;
  icone: string | null;
  descricao: string | null;
  ativa: boolean;
  campos: Campo[];
  total_ativos: number;
}

export interface Setor { id: number; unidade_id: number; nome: string; ativo: boolean }
export interface Unidade {
  id: number;
  nome: string;
  sigla: string | null;
  endereco: string | null;
  ativa: boolean;
  setores: Setor[];
  total_ativos: number;
}
export interface Pessoa {
  id: number;
  nome: string;
  matricula: string | null;
  unidade_id: number | null;
  setor_id: number | null;
  email: string | null;
  telefone: string | null;
  ativa: boolean;
  unidade: Ref | null;
  setor: Ref | null;
}

export type Valor = string | number | boolean | null;

export interface Ativo {
  id: number;
  categoria: { id: number; nome: string; slug: string; icone: string | null };
  patrimonio: string | null;
  nome: string | null;
  status: Status;
  unidade: Ref;
  setor: Ref | null;
  pessoa: Ref | null;
  observacao: string | null;
  origem: string;
  criado_em: string;
  atualizado_em: string;
  arquivado_em: string | null;
  motivo_arquivo: string | null;
  valores: Record<string, Valor>;
}

export interface Movimentacao {
  id: number;
  ativo_id: number;
  tipo: string;
  status_anterior: Status | null;
  status_novo: Status | null;
  unidade_origem: Ref | null;
  unidade_destino: Ref | null;
  setor_origem: Ref | null;
  setor_destino: Ref | null;
  pessoa_origem: Ref | null;
  pessoa_destino: Ref | null;
  data: string;
  observacao: string | null;
  ativo?: { id: number; nome: string | null; patrimonio: string | null; categoria: string };
}

export interface Vinculo {
  id: number;
  tipo: string;
  observacao: string | null;
  criado_em: string;
  direcao: "origem" | "destino";
  outro: { id: number; nome: string | null; patrimonio: string | null; categoria: string; status: Status };
}

export interface Auditoria {
  id: number;
  acao: string;
  antes: Record<string, unknown> | null;
  depois: Record<string, unknown> | null;
  criado_em: string;
}

export interface AtivoDetalhe extends Ativo {
  campos: Campo[];
  movimentacoes: Movimentacao[];
  vinculos: Vinculo[];
  auditoria: Auditoria[];
}

export interface AtivoLista { total: number; pagina: number; por_pagina: number; itens: Ativo[] }

export interface Mensagem { tipo: "erro" | "aviso" | "info"; texto: string }

export interface DadosItem {
  categoria_id: number | null;
  patrimonio: string | null;
  nome: string | null;
  unidade_id: number | null;
  unidade: string | null;
  setor: string | null;
  pessoa: string | null;
  observacao: string | null;
  campos: Record<string, string>;
  status?: Status;
}

export interface ImportacaoItem {
  id: number;
  ordem: number;
  trecho_original: string;
  origem_trecho: string | null;
  categoria_sugerida_id: number | null;
  dados_extraidos: DadosItem;
  confianca: number;
  status: "pendente" | "aprovado" | "rejeitado" | "duplicado";
  motivo_duplicado: string | null;
  ativo_id: number | null;
  mensagens: Mensagem[];
}

export interface Importacao {
  id: number;
  arquivo_nome: string;
  formato: string;
  metodo: "ia" | "regras" | "mapeamento";
  categoria_id: number | null;
  unidade_padrao_id: number | null;
  status: "mapeamento" | "processando" | "revisao" | "concluida" | "erro";
  total_itens: number;
  erro: string | null;
  meta: {
    aviso?: string;
    progresso?: string;
    total_blocos?: number;
    colunas?: string[];
    sugestao?: Record<string, string | null>;
    amostra?: Record<string, string>[];
    total_linhas?: number;
  };
  criado_em: string;
  concluido_em: string | null;
  contagem: Record<string, number>;
  itens?: ImportacaoItem[];
}

export interface Dashboard {
  total: number;
  arquivados: number;
  por_status: Record<string, number>;
  por_categoria: { id: number; nome: string; icone: string | null; total: number }[];
  por_unidade: { id: number; nome: string; total: number; com_defeito: number }[];
  itens_pendentes_revisao: number;
  importacoes_abertas: number;
  sem_pessoa: number;
  ultimas_movimentacoes: Movimentacao[];
  serie_mensal: SerieMes[];
}

export interface SerieMes {
  mes: string;
  rotulo: string;
  ano: number;
  ativos: number;
  cadastros: number;
  transferencias: number;
  defeitos: number;
  arquivados: number;
  [k: string]: string | number;
}

export interface Config { gemini_configurado: boolean; gemini_modelo: string; gemini_chave_mascarada: string | null }

// ---------- cliente ----------
export class ErroApi extends Error {
  status: number;
  erros: Record<string, string>;
  constructor(status: number, mensagem: string, erros: Record<string, string> = {}) {
    super(mensagem);
    this.status = status;
    this.erros = erros;
  }
}

async function req<T>(metodo: string, url: string, corpo?: unknown): Promise<T> {
  const init: RequestInit = { method: metodo, headers: {} };
  if (corpo instanceof FormData) init.body = corpo;
  else if (corpo !== undefined) {
    init.body = JSON.stringify(corpo);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let r: Response;
  try {
    r = await fetch("/api" + url, init);
  } catch {
    throw new ErroApi(0, "Não consegui falar com o servidor. Ele está rodando? (uvicorn na porta 8000)");
  }
  if (r.ok) return (r.status === 204 ? undefined : await r.json()) as T;
  let detalhe: unknown = r.statusText;
  try {
    detalhe = (await r.json()).detail;
  } catch { /* corpo vazio */ }
  if (detalhe && typeof detalhe === "object" && !Array.isArray(detalhe) && "erros" in detalhe) {
    const d = detalhe as { mensagem: string; erros: Record<string, string> };
    throw new ErroApi(r.status, Object.values(d.erros).join(" · ") || d.mensagem, d.erros);
  }
  if (Array.isArray(detalhe)) {
    // erro de validação do próprio FastAPI
    const msgs = detalhe.map((e: { loc?: string[]; msg?: string }) => `${(e.loc || []).slice(-1)[0]}: ${e.msg}`);
    throw new ErroApi(r.status, msgs.join(" · "));
  }
  throw new ErroApi(r.status, String(detalhe));
}

export const api = {
  get: <T,>(url: string) => req<T>("GET", url),
  post: <T,>(url: string, corpo?: unknown) => req<T>("POST", url, corpo ?? {}),
  put: <T,>(url: string, corpo: unknown) => req<T>("PUT", url, corpo),
  del: <T,>(url: string) => req<T>("DELETE", url),
};

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "" && v !== false) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? "?" + s : "";
}

export function formatarData(iso: string | null | undefined, comHora = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return comHora
    ? d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("pt-BR");
}

export function formatarValor(v: Valor | undefined, tipo?: TipoCampo): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Sim" : "Não";
  if (tipo === "data" && typeof v === "string") {
    const [a, m, d] = v.split("-");
    return d ? `${d}/${m}/${a}` : v;
  }
  return String(v);
}
