import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, Campo, Categoria, Pessoa, STATUS_ROTULO, Unidade, Valor } from "../api";

// ---------- dados compartilhados ----------
export const useCategorias = (incluirInativas = false) =>
  useQuery({
    queryKey: ["categorias", incluirInativas],
    queryFn: () => api.get<Categoria[]>(`/categorias${incluirInativas ? "?incluir_inativas=true" : ""}`),
  });
export const useUnidades = () => useQuery({ queryKey: ["unidades"], queryFn: () => api.get<Unidade[]>("/unidades") });
export const usePessoas = () => useQuery({ queryKey: ["pessoas"], queryFn: () => api.get<Pessoa[]>("/pessoas") });

// ---------- toasts ----------
type Toast = { id: number; texto: string; erro?: boolean };
const ToastCtx = createContext<(texto: string, erro?: boolean) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const mostrar = useCallback((texto: string, erro = false) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, texto, erro }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), erro ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={mostrar}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={"toast" + (t.erro ? " erro" : "")}>{t.texto}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------- modal ----------
export function Modal({ titulo, aoFechar, children, largo }: {
  titulo: string; aoFechar: () => void; children: ReactNode; largo?: boolean;
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [aoFechar]);
  return (
    <div className="fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div className={"modal" + (largo ? " largo" : "")} role="dialog" aria-modal="true" aria-label={titulo}>
        <header className="topo"><h2>{titulo}</h2><button className="pequeno" onClick={aoFechar}>Fechar</button></header>
        {children}
      </div>
    </div>
  );
}

// ---------- pequenos ----------
export function StatusPill({ status }: { status: string }) {
  const rotulos: Record<string, string> = {
    ...STATUS_ROTULO, pendente: "Pendente", aprovado: "Aprovado", rejeitado: "Rejeitado", duplicado: "Duplicado",
    processando: "Processando", mapeamento: "Mapear colunas", revisao: "Em revisão", concluida: "Concluída", erro: "Erro",
  };
  return <span className={`pill st-${status}`}>{rotulos[status] ?? status}</span>;
}

export function Patrimonio({ valor }: { valor: string | null }) {
  if (!valor) return <span className="muted">sem patrimônio</span>;
  return <span className="etiqueta-pat"><span>Patrimônio</span><span>{valor}</span></span>;
}

export function Carregando() {
  return <div className="vazio">Carregando…</div>;
}

export function ErroBox({ erro }: { erro: unknown }) {
  if (!erro) return null;
  return <div className="aviso erro">{erro instanceof Error ? erro.message : String(erro)}</div>;
}

// ---------- input de valor conforme o tipo do campo ----------
export function CampoInput({ campo, valor, onChange, erro, id }: {
  campo: Campo; valor: Valor | undefined; onChange: (v: Valor) => void; erro?: string; id?: string;
}) {
  const cls = erro ? "erro" : undefined;
  const v = valor ?? "";
  const htmlId = id ?? `campo-${campo.chave}`;
  let input: ReactNode;
  switch (campo.tipo) {
    case "lista":
      input = (
        <select id={htmlId} className={cls} value={String(v)} onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {campo.opcoes.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      );
      break;
    case "bool":
      input = (
        <select id={htmlId} className={cls} value={v === true ? "true" : v === false ? "false" : String(v)}
          onChange={(e) => onChange(e.target.value === "" ? "" : e.target.value === "true")}>
          <option value="">—</option><option value="true">Sim</option><option value="false">Não</option>
        </select>
      );
      break;
    case "data":
      input = <input id={htmlId} type="date" className={cls} value={String(v)} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "numero":
      input = <input id={htmlId} inputMode="decimal" className={cls} value={String(v)} onChange={(e) => onChange(e.target.value)} />;
      break;
    default:
      input = (
        <input id={htmlId} className={cls + (["ip", "mac"].includes(campo.tipo) ? " mono" : "")} value={String(v)}
          placeholder={campo.tipo === "ip" ? "10.0.0.1" : campo.tipo === "mac" ? "AA:BB:CC:DD:EE:FF" : ""}
          onChange={(e) => onChange(e.target.value)} />
      );
  }
  return (
    <label className="campo" htmlFor={htmlId}>
      <span>{campo.rotulo}{campo.obrigatorio && <span className="obrig"> *</span>}{campo.unico && <span className="dica"> · único</span>}</span>
      {input}
      {erro && <span className="erro-campo">{erro}</span>}
    </label>
  );
}

// ---------- posse: unidade › setor › pessoa ----------
export interface Posse { unidade_id: number | null; setor_id: number | null; pessoa_id: number | null }

export function PosseSelect({ valor, onChange, erros = {}, prefixo = "posse" }: {
  valor: Posse; onChange: (p: Posse) => void; erros?: Record<string, string>; prefixo?: string;
}) {
  const unidades = useUnidades();
  const pessoas = usePessoas();
  const unidade = unidades.data?.find((u) => u.id === valor.unidade_id);
  const setores = (unidade?.setores ?? []).filter((s) => s.ativo || s.id === valor.setor_id);
  const listaPessoas = (pessoas.data ?? []).filter(
    (p) => p.id === valor.pessoa_id || !valor.unidade_id || p.unidade_id === valor.unidade_id || p.unidade_id === null,
  );
  return (
    <div className="form-grid">
      <label className="campo" htmlFor={`${prefixo}-unidade`}>
        <span>Unidade <span className="obrig">*</span></span>
        <select id={`${prefixo}-unidade`} className={erros.unidade_id ? "erro" : undefined} value={valor.unidade_id ?? ""}
          onChange={(e) => onChange({ unidade_id: e.target.value ? Number(e.target.value) : null, setor_id: null, pessoa_id: valor.pessoa_id })}>
          <option value="">Escolha…</option>
          {unidades.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
        </select>
        {erros.unidade_id && <span className="erro-campo">{erros.unidade_id}</span>}
      </label>
      <label className="campo" htmlFor={`${prefixo}-setor`}>
        <span>Setor <span className="dica">opcional</span></span>
        <select id={`${prefixo}-setor`} className={erros.setor_id ? "erro" : undefined} value={valor.setor_id ?? ""} disabled={!unidade}
          onChange={(e) => onChange({ ...valor, setor_id: e.target.value ? Number(e.target.value) : null })}>
          <option value="">{unidade && setores.length === 0 ? "Unidade sem setores" : "—"}</option>
          {setores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
        </select>
        {erros.setor_id && <span className="erro-campo">{erros.setor_id}</span>}
      </label>
      <label className="campo" htmlFor={`${prefixo}-pessoa`}>
        <span>Pessoa responsável <span className="dica">opcional</span></span>
        <select id={`${prefixo}-pessoa`} value={valor.pessoa_id ?? ""}
          onChange={(e) => onChange({ ...valor, pessoa_id: e.target.value ? Number(e.target.value) : null })}>
          <option value="">—</option>
          {listaPessoas.map((p) => <option key={p.id} value={p.id}>{p.nome}{p.setor ? ` · ${p.setor.nome}` : ""}</option>)}
        </select>
      </label>
    </div>
  );
}
