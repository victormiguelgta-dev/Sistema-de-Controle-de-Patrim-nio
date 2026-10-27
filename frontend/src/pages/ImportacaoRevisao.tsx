import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Categoria, DadosItem, ErroApi, formatarData, Importacao, ImportacaoItem } from "../api";
import { CampoInput, Carregando, ErroBox, StatusPill, useCategorias, useToast, useUnidades } from "../components/ui";

const DESTINOS_BASE: Record<string, string> = {
  __patrimonio__: "Patrimônio", __nome__: "Nome", __unidade__: "Unidade", __setor__: "Setor",
  __pessoa__: "Pessoa", __observacao__: "Observação",
};
const FILTROS = [
  { id: "pendente", rotulo: "Pendentes" }, { id: "duplicado", rotulo: "Duplicados" },
  { id: "aprovado", rotulo: "Aprovados" }, { id: "rejeitado", rotulo: "Rejeitados" }, { id: "todos", rotulo: "Todos" },
];
const POR_PAGINA = 20;

export default function ImportacaoRevisao() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: imp, isLoading, error } = useQuery({
    queryKey: ["importacao", id],
    queryFn: () => api.get<Importacao>(`/importacoes/${id}`),
    refetchInterval: (q) => (q.state.data?.status === "processando" ? 2500 : false),
  });
  const categorias = useCategorias();
  const [filtro, setFiltro] = useState("pendente");
  const [pagina, setPagina] = useState(1);
  const atualizar = () => {
    qc.invalidateQueries({ queryKey: ["importacao", id] });
    qc.invalidateQueries({ queryKey: ["importacoes"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  useEffect(() => setPagina(1), [filtro]);
  useEffect(() => {
    // depois que tudo foi revisado, mostra todos
    if (imp?.status === "concluida" && filtro === "pendente") setFiltro("todos");
  }, [imp?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) return <Carregando />;
  if (error || !imp) return <ErroBox erro={error} />;
  const itens = (imp.itens ?? []).filter((i) => filtro === "todos" || i.status === filtro);
  const paginas = Math.max(1, Math.ceil(itens.length / POR_PAGINA));
  const visiveis = itens.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);

  return (
    <>
      <div className="topo">
        <div style={{ display: "grid", gap: 6 }}>
          <Link to="/importar" className="muted">← Importações</Link>
          <h1>{imp.arquivo_nome}</h1>
          <p className="sub">
            {imp.metodo === "ia" ? `IA · ${imp.meta.provedor === "gemini" ? "Gemini" : "Ollama"}${imp.meta.modelo ? ` (${imp.meta.modelo})` : ""}` : { regras: "Regras", mapeamento: "Mapeamento de colunas" }[imp.metodo]} · {imp.formato} · {formatarData(imp.criado_em)}
          </p>
        </div>
        <StatusPill status={imp.status} />
      </div>
      {imp.meta.aviso && <div className="aviso atencao">{imp.meta.aviso}</div>}
      {imp.erro && <div className={"aviso " + (imp.status === "erro" ? "erro" : "info")}>{imp.erro}</div>}

      {imp.status === "processando" && (
        <section className="card vazio">
          <h2>Lendo o arquivo com {imp.meta.provedor === "gemini" ? "o Gemini" : "o modelo local"}…</h2>
          <p>{imp.meta.progresso ?? "Na fila"} · {imp.meta.total_blocos ?? "?"} trecho(s) de texto</p>
          <p className="muted">
            {imp.meta.provedor === "gemini"
              ? "O plano gratuito tem limite por minuto, então arquivos grandes demoram."
              : "O modelo roda neste computador; sem placa de vídeo, cada trecho pode levar alguns minutos."}{" "}
            Pode sair desta tela; o processamento continua.
          </p>
        </section>
      )}

      {imp.status === "mapeamento" && categorias.data && (
        <Mapeamento imp={imp} categoria={categorias.data.find((c) => c.id === imp.categoria_id)} aoConcluir={atualizar} />
      )}

      {(imp.status === "revisao" || imp.status === "concluida") && (
        <>
          <Resumo imp={imp} aoConcluir={atualizar} />
          <div className="abas" role="tablist">
            {FILTROS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filtro === f.id} className={filtro === f.id ? "ativa" : ""} onClick={() => setFiltro(f.id)}>
                {f.rotulo} ({f.id === "todos" ? imp.itens?.length ?? 0 : imp.contagem[f.id] ?? 0})
              </button>
            ))}
          </div>
          {visiveis.length === 0 ? <div className="card vazio"><p>Nenhum item aqui.</p></div> : (
            <div className="grid">
              {visiveis.map((it) => (
                <ItemCard key={`${it.id}-${it.status}-${JSON.stringify(it.dados_extraidos)}`} imp={imp} item={it} categorias={categorias.data ?? []} aoConcluir={atualizar} />
              ))}
            </div>
          )}
          {paginas > 1 && (
            <div className="paginacao">
              <button disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
              <span className="num">Página {pagina} de {paginas}</span>
              <button disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>Próxima</button>
            </div>
          )}
        </>
      )}
    </>
  );
}

function Resumo({ imp, aoConcluir }: { imp: Importacao; aoConcluir: () => void }) {
  const [minimo, setMinimo] = useState(0.9);
  const [resultado, setResultado] = useState<{ aprovados: number; falhas: { ordem: number; erro: string }[] } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<unknown>(null);
  const elegiveis = (imp.itens ?? []).filter((i) => i.status === "pendente" && i.confianca >= minimo
    && !i.mensagens.some((m) => m.tipo === "erro")).length;

  async function lote() {
    setEnviando(true); setErro(null);
    try {
      setResultado(await api.post(`/importacoes/${imp.id}/aprovar-lote`, { confianca_minima: minimo }));
      aoConcluir();
    } catch (e) { setErro(e); } finally { setEnviando(false); }
  }

  return (
    <section className="card">
      <div className="kpis">
        <div className="kpi"><b>{imp.total_itens}</b><span>objetos encontrados</span></div>
        <div className="kpi"><b>{imp.contagem.pendente ?? 0}</b><span>pendentes</span></div>
        <div className="kpi"><b>{imp.contagem.aprovado ?? 0}</b><span>aprovados</span></div>
        <div className={"kpi" + (imp.contagem.duplicado ? " atencao" : "")}><b>{imp.contagem.duplicado ?? 0}</b><span>duplicados (ignorados)</span></div>
      </div>
      {imp.status === "revisao" && (
        <div className="acoes">
          <label className="check" htmlFor="lote-min">Aprovar de uma vez os pendentes sem erro com confiança ≥
            <select id="lote-min" value={minimo} onChange={(e) => setMinimo(Number(e.target.value))} style={{ width: "auto" }}>
              {[0.95, 0.9, 0.8, 0.7, 0.5, 0].map((v) => <option key={v} value={v}>{Math.round(v * 100)}%</option>)}
            </select>
          </label>
          <button className="primario" disabled={enviando || elegiveis === 0} onClick={lote}>
            {enviando ? "Aprovando…" : `Aprovar ${elegiveis} item(ns)`}
          </button>
        </div>
      )}
      {resultado && (
        <div className={"aviso " + (resultado.falhas.length ? "atencao" : "info")}>
          {resultado.aprovados} aprovado(s).
          {resultado.falhas.length > 0 && ` ${resultado.falhas.length} não puderam ser aprovados: ` +
            resultado.falhas.slice(0, 5).map((f) => `item ${f.ordem} (${f.erro})`).join("; ")}
        </div>
      )}
      <ErroBox erro={erro} />
    </section>
  );
}

function Mapeamento({ imp, categoria, aoConcluir }: { imp: Importacao; categoria?: Categoria; aoConcluir: () => void }) {
  const [mapa, setMapa] = useState<Record<string, string | null>>(imp.meta.sugestao ?? {});
  const [erro, setErro] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const destinos = useMemo(() => [
    ...Object.entries(DESTINOS_BASE).map(([k, v]) => ({ k, v })),
    ...(categoria?.campos.filter((c) => c.ativo).map((c) => ({ k: c.chave, v: `${c.rotulo} (${categoria.nome})` })) ?? []),
  ], [categoria]);
  const usados = new Set(Object.values(mapa).filter(Boolean));

  async function aplicar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true); setErro(null);
    try { await api.post(`/importacoes/${imp.id}/mapeamento`, { mapa }); aoConcluir(); }
    catch (err) { setErro(err); } finally { setEnviando(false); }
  }

  return (
    <form className="card form" onSubmit={aplicar}>
      <header><div><h2>Ligue cada coluna a um campo</h2><p className="muted">{imp.meta.total_linhas} linha(s) · categoria {categoria?.nome}. Já sugeri o que reconheci pelos nomes e sinônimos.</p></div></header>
      <div className="mapa">
        {(imp.meta.colunas ?? []).map((col) => {
          const exemplo = (imp.meta.amostra ?? []).map((l) => l[col]).filter(Boolean).slice(0, 3).join(" · ");
          return (
            <div className="mapa-linha" key={col}>
              <b>{col}</b>
              <span aria-hidden className="muted">→</span>
              <select aria-label={`Destino da coluna ${col}`} value={mapa[col] ?? ""} onChange={(e) => setMapa({ ...mapa, [col]: e.target.value || null })}>
                <option value="">Ignorar coluna</option>
                {destinos.map((d) => <option key={d.k} value={d.k} disabled={usados.has(d.k) && mapa[col] !== d.k}>{d.v}</option>)}
              </select>
              <span className="exemplo" title={exemplo}>{exemplo || "vazio nas primeiras linhas"}</span>
            </div>
          );
        })}
      </div>
      <ErroBox erro={erro} />
      <div className="acoes"><button className="primario" disabled={enviando || usados.size === 0}>{enviando ? "Gerando…" : "Gerar itens para revisão"}</button></div>
    </form>
  );
}

function ItemCard({ imp, item, categorias, aoConcluir }: { imp: Importacao; item: ImportacaoItem; categorias: Categoria[]; aoConcluir: () => void }) {
  const unidades = useUnidades();
  const toast = useToast();
  const [dados, setDados] = useState<DadosItem>(item.dados_extraidos);
  const [sujo, setSujo] = useState(false);
  const [editandoDup, setEditandoDup] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<unknown>(null);
  const editavel = item.status === "pendente" || (item.status === "duplicado" && editandoDup);
  const categoria = categorias.find((c) => c.id === dados.categoria_id);
  const outraUnidade = !dados.unidade_id;

  const set = (patch: Partial<DadosItem>) => { setDados((d) => ({ ...d, ...patch })); setSujo(true); };
  const url = `/importacoes/${imp.id}/itens/${item.id}`;

  async function executar(acao: "salvar" | "aprovar" | "rejeitar") {
    setEnviando(true); setErro(null);
    try {
      if (sujo && acao !== "rejeitar") await api.put(url, { dados });
      if (acao === "aprovar") { await api.post(`${url}/aprovar`); toast("Objeto cadastrado"); }
      if (acao === "rejeitar") await api.post(`${url}/rejeitar`);
      if (acao === "salvar") toast("Item atualizado");
      aoConcluir();
    } catch (e) {
      setErro(e);
      if (e instanceof ErroApi) aoConcluir();
    } finally { setEnviando(false); }
  }

  return (
    <article className={"card item" + (["aprovado", "rejeitado"].includes(item.status) ? " feito" : "")}>
      <div className="original">
        <div className="acoes" style={{ justifyContent: "space-between" }}>
          <span className="muted">#{item.ordem} · {item.origem_trecho}</span>
          <span className="conf" title="Confiança">{Math.round(item.confianca * 100)}%</span>
        </div>
        <pre>{item.trecho_original}</pre>
      </div>
      <div className="sugestao">
        <div className="acoes" style={{ justifyContent: "space-between" }}>
          <StatusPill status={item.status} />
          {item.ativo_id && <Link to={`/objetos/${item.ativo_id}`}>{item.status === "aprovado" ? "Abrir objeto criado" : "Ver objeto existente"}</Link>}
        </div>
        {item.mensagens.length > 0 && (
          <ul className="msgs">
            {item.mensagens.map((m, i) => <li key={i} className={m.tipo === "aviso" ? "aviso-t" : m.tipo}>{m.texto}</li>)}
          </ul>
        )}
        <fieldset disabled={!editavel || enviando} style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 12 }}>
          <div className="form-grid">
            <label className="campo" htmlFor={`it${item.id}-cat`}><span>Categoria</span>
              <select id={`it${item.id}-cat`} value={dados.categoria_id ?? ""} onChange={(e) => set({ categoria_id: e.target.value ? Number(e.target.value) : null })}>
                <option value="">Escolha…</option>
                {categorias.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            </label>
            <label className="campo" htmlFor={`it${item.id}-pat`}><span>Patrimônio</span>
              <input id={`it${item.id}-pat`} className="mono" value={dados.patrimonio ?? ""} onChange={(e) => set({ patrimonio: e.target.value })} />
            </label>
            <label className="campo" htmlFor={`it${item.id}-nome`}><span>Nome</span>
              <input id={`it${item.id}-nome`} value={dados.nome ?? ""} onChange={(e) => set({ nome: e.target.value })} />
            </label>
            <label className="campo" htmlFor={`it${item.id}-uni`}><span>Unidade</span>
              <select id={`it${item.id}-uni`} value={dados.unidade_id ?? "__outra__"}
                onChange={(e) => e.target.value === "__outra__" ? set({ unidade_id: null }) : set({ unidade_id: Number(e.target.value), unidade: null })}>
                {unidades.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
                <option value="__outra__">{dados.unidade ? `Nova: ${dados.unidade}` : "Outra (digitar)"}</option>
              </select>
            </label>
            {outraUnidade && (
              <label className="campo" htmlFor={`it${item.id}-uni-nome`}><span>Nome da nova unidade</span>
                <input id={`it${item.id}-uni-nome`} value={dados.unidade ?? ""} onChange={(e) => set({ unidade: e.target.value })} />
              </label>
            )}
            <label className="campo" htmlFor={`it${item.id}-setor`}><span>Setor <span className="dica">criado se não existir</span></span>
              <input id={`it${item.id}-setor`} value={dados.setor ?? ""} onChange={(e) => set({ setor: e.target.value })} />
            </label>
            <label className="campo" htmlFor={`it${item.id}-pessoa`}><span>Pessoa</span>
              <input id={`it${item.id}-pessoa`} value={dados.pessoa ?? ""} onChange={(e) => set({ pessoa: e.target.value })} />
            </label>
          </div>
          {categoria && (
            <div className="form-grid">
              {categoria.campos.filter((c) => c.ativo).map((c) => (
                <CampoInput key={c.id} id={`it${item.id}-${c.chave}`} campo={c} valor={dados.campos[c.chave] ?? ""}
                  onChange={(v) => set({ campos: { ...dados.campos, [c.chave]: v === null ? "" : String(v) } })} />
              ))}
            </div>
          )}
          <label className="campo" htmlFor={`it${item.id}-obs`}><span>Observação</span>
            <input id={`it${item.id}-obs`} value={dados.observacao ?? ""} onChange={(e) => set({ observacao: e.target.value })} />
          </label>
        </fieldset>
        <ErroBox erro={erro} />
        <div className="acoes">
          {item.status === "pendente" && (
            <>
              <button className="primario" disabled={enviando} onClick={() => executar("aprovar")}>Aprovar</button>
              {sujo && <button disabled={enviando} onClick={() => executar("salvar")}>Salvar alterações</button>}
              <button className="perigo" disabled={enviando} onClick={() => executar("rejeitar")}>Rejeitar</button>
            </>
          )}
          {item.status === "duplicado" && (
            editandoDup
              ? <button className="primario" disabled={enviando || !sujo} onClick={() => executar("salvar")}>Salvar e verificar de novo</button>
              : <>
                  <button onClick={() => setEditandoDup(true)}>Não é duplicado, corrigir dados</button>
                  <button className="perigo" disabled={enviando} onClick={() => executar("rejeitar")}>Descartar</button>
                </>
          )}
        </div>
      </div>
    </article>
  );
}
