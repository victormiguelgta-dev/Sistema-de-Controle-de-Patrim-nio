import { DragEvent, FormEvent, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Config, formatarData, Importacao } from "../api";
import { ErroBox, StatusPill, useCategorias, useUnidades } from "../components/ui";

const METODOS = [
  { id: "ia", titulo: "IA (Gemini)", texto: "Para textos soltos, conversas de WhatsApp, PDFs e planilhas bagunçadas. Entende unidade, categoria e campos." },
  { id: "regras", titulo: "Regras (sem IA)", texto: "Lê linhas “Rótulo: valor” usando os sinônimos dos campos. Nada sai do computador." },
  { id: "mapeamento", titulo: "Mapear colunas", texto: "Para planilhas organizadas (xlsx, csv): você liga cada coluna a um campo." },
] as const;
const METODO_ROTULO: Record<string, string> = { ia: "IA", regras: "Regras", mapeamento: "Colunas" };

export default function Importar() {
  const categorias = useCategorias();
  const unidades = useUnidades();
  const config = useQuery({ queryKey: ["config"], queryFn: () => api.get<Config>("/config") });
  const lista = useQuery({
    queryKey: ["importacoes"],
    queryFn: () => api.get<Importacao[]>("/importacoes"),
    refetchInterval: (q) => (q.state.data?.some((i) => i.status === "processando") ? 3000 : false),
  });
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [metodo, setMetodo] = useState<"ia" | "regras" | "mapeamento">("ia");
  const [categoriaId, setCategoriaId] = useState("");
  const [unidadeId, setUnidadeId] = useState("");
  const [sobre, setSobre] = useState(false);
  const [erro, setErro] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const ehPlanilha = arquivo ? /\.(xlsx|xlsm|xls|csv)$/i.test(arquivo.name) : true;

  function soltar(e: DragEvent) {
    e.preventDefault();
    setSobre(false);
    if (e.dataTransfer.files[0]) setArquivo(e.dataTransfer.files[0]);
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!arquivo) return;
    setErro(null);
    setEnviando(true);
    const fd = new FormData();
    fd.append("arquivo", arquivo);
    fd.append("metodo", metodo);
    if (categoriaId) fd.append("categoria_id", categoriaId);
    if (unidadeId) fd.append("unidade_padrao_id", unidadeId);
    try {
      const imp = await api.post<Importacao>("/importacoes", fd);
      qc.invalidateQueries({ queryKey: ["importacoes"] });
      navigate(`/importar/${imp.id}`);
    } catch (err) { setErro(err); } finally { setEnviando(false); }
  }

  return (
    <>
      <div className="topo">
        <div><h1>Importar</h1><p className="sub">Transforme planilhas e textos em objetos. Nada entra no patrimônio sem a sua revisão.</p></div>
      </div>

      <form className="card form" onSubmit={enviar}>
        <div
          className={"dropzone" + (sobre ? " sobre" : "")}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setSobre(true); }}
          onDragLeave={() => setSobre(false)}
          onDrop={soltar}
          role="button" tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        >
          <b>{arquivo ? arquivo.name : "Arraste o arquivo aqui ou clique para escolher"}</b>
          <span className="muted">{arquivo ? `${(arquivo.size / 1024 / 1024).toFixed(2)} MB` : "xlsx, csv, txt, pdf ou exportação do WhatsApp (.zip ou .txt)"}</span>
          <input ref={inputRef} type="file" hidden accept=".xlsx,.xlsm,.xls,.csv,.txt,.pdf,.zip"
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
        </div>

        <div className="metodos" role="radiogroup" aria-label="Método">
          {METODOS.map((m) => {
            const desabilitado = m.id === "mapeamento" && !ehPlanilha;
            return (
              <label key={m.id} className={"metodo" + (metodo === m.id ? " sel" : "")} style={desabilitado ? { opacity: 0.5 } : undefined}>
                <span className="check" style={{ color: "var(--fg)" }}>
                  <input type="radio" name="metodo" disabled={desabilitado} checked={metodo === m.id} onChange={() => setMetodo(m.id)} />
                  <b>{m.titulo}</b>
                </span>
                <span>{m.texto}</span>
              </label>
            );
          })}
        </div>
        {metodo === "ia" && config.data && !config.data.gemini_configurado && (
          <div className="aviso atencao">A chave do Gemini não está configurada. <Link to="/configuracoes">Configurar agora</Link> ou use o método Regras.</div>
        )}

        <div className="form-grid">
          <label className="campo" htmlFor="im-cat">
            <span>Categoria {metodo === "mapeamento" ? <span className="obrig">*</span> : <span className="dica">opcional, ajuda a IA</span>}</span>
            <select id="im-cat" value={categoriaId} onChange={(e) => setCategoriaId(e.target.value)}>
              <option value="">{metodo === "mapeamento" ? "Escolha…" : "Detectar automaticamente"}</option>
              {categorias.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </label>
          <label className="campo" htmlFor="im-uni">
            <span>Unidade padrão <span className="dica">usada quando o arquivo não diz</span></span>
            <select id="im-uni" value={unidadeId} onChange={(e) => setUnidadeId(e.target.value)}>
              <option value="">Nenhuma</option>
              {unidades.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>
          </label>
        </div>
        <ErroBox erro={erro} />
        <div className="acoes">
          <button className="primario" disabled={!arquivo || enviando || (metodo === "mapeamento" && (!categoriaId || !ehPlanilha))}>
            {enviando ? "Enviando…" : "Ler arquivo"}
          </button>
        </div>
      </form>

      <section className="card">
        <h2>Importações</h2>
        {!lista.data?.length ? <p className="muted">Nenhuma importação ainda.</p> : (
          <div className="tabela-wrap">
            <table>
              <thead><tr><th>Arquivo</th><th>Método</th><th>Situação</th><th>Itens</th><th>Enviado em</th></tr></thead>
              <tbody>
                {lista.data.map((i) => (
                  <tr key={i.id} className="clicavel" onClick={() => navigate(`/importar/${i.id}`)}>
                    <td><Link to={`/importar/${i.id}`} onClick={(e) => e.stopPropagation()}>{i.arquivo_nome}</Link> <span className="muted">· {i.formato}</span></td>
                    <td>{METODO_ROTULO[i.metodo]}</td>
                    <td><StatusPill status={i.status} /></td>
                    <td className="num">
                      {i.total_itens}
                      {i.contagem.pendente ? <span className="muted"> · {i.contagem.pendente} pendente(s)</span> : null}
                    </td>
                    <td className="muted num">{formatarData(i.criado_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
