import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Ativo, AtivoDetalhe, ErroApi, STATUS_EDITAVEIS, STATUS_ROTULO, Status, Valor } from "../api";
import { CampoInput, Carregando, ErroBox, Posse, PosseSelect, useCategorias, useToast } from "../components/ui";

export default function ObjetoForm() {
  const { id } = useParams();
  const editando = Boolean(id);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const categorias = useCategorias();
  const existente = useQuery({
    queryKey: ["ativo", id],
    queryFn: () => api.get<AtivoDetalhe>(`/ativos/${id}`),
    enabled: editando,
  });

  const [categoriaId, setCategoriaId] = useState<number | null>(params.get("categoria_id") ? Number(params.get("categoria_id")) : null);
  const [patrimonio, setPatrimonio] = useState("");
  const [nome, setNome] = useState("");
  const [status, setStatus] = useState<Status>("em_uso");
  const [observacao, setObservacao] = useState("");
  const [posse, setPosse] = useState<Posse>({ unidade_id: null, setor_id: null, pessoa_id: null });
  const [valores, setValores] = useState<Record<string, Valor>>({});
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<unknown>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    const a = existente.data;
    if (!a) return;
    setCategoriaId(a.categoria.id);
    setPatrimonio(a.patrimonio ?? "");
    setNome(a.nome ?? "");
    setObservacao(a.observacao ?? "");
    setValores(a.valores);
  }, [existente.data]);

  const categoria = categorias.data?.find((c) => c.id === categoriaId)
    ?? (existente.data ? { ...existente.data.categoria, campos: existente.data.campos } : undefined);
  const campos = (categoria?.campos ?? []).filter((c) => c.ativo || valores[c.chave] != null);

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setErros({});
    setErroGeral(null);
    if (!categoriaId) return setErros({ categoria_id: "Escolha a categoria" });
    if (!editando && !posse.unidade_id) return setErros({ unidade_id: "Escolha a unidade" });
    const vals: Record<string, Valor> = {};
    for (const c of campos) vals[c.chave] = valores[c.chave] ?? "";
    setSalvando(true);
    try {
      let ativo: Ativo;
      if (editando) {
        ativo = await api.put<Ativo>(`/ativos/${id}`, { patrimonio, nome, observacao, valores: vals });
      } else {
        ativo = await api.post<Ativo>("/ativos", {
          categoria_id: categoriaId, patrimonio, nome, status, observacao, valores: vals, ...posse,
        });
      }
      qc.invalidateQueries();
      toast(editando ? "Alterações salvas" : "Objeto cadastrado");
      navigate(`/objetos/${ativo.id}`);
    } catch (err) {
      if (err instanceof ErroApi && Object.keys(err.erros).length) setErros(err.erros);
      else setErroGeral(err);
    } finally {
      setSalvando(false);
    }
  }

  if (editando && existente.isLoading) return <Carregando />;
  if (editando && existente.data?.arquivado_em) {
    return <div className="aviso atencao">Este objeto está arquivado. Restaure na ficha antes de editar.</div>;
  }

  return (
    <form className="form" onSubmit={salvar}>
      <div className="topo">
        <div>
          <h1>{editando ? "Editar objeto" : "Novo objeto"}</h1>
          <p className="sub">{editando ? "Posse e status mudam pelas ações da ficha, para ficar no histórico." : "Os campos mudam conforme a categoria."}</p>
        </div>
        <div className="acoes">
          <Link className="btn" to={editando ? `/objetos/${id}` : "/objetos"}>Cancelar</Link>
          <button className="primario" type="submit" disabled={salvando}>{salvando ? "Salvando…" : "Salvar"}</button>
        </div>
      </div>
      <ErroBox erro={erroGeral} />
      {Object.keys(erros).length > 0 && <div className="aviso erro">Confira os campos destacados.</div>}

      <section className="card">
        <h2>Identificação</h2>
        <div className="form-grid">
          <label className="campo" htmlFor="o-cat">
            <span>Categoria <span className="obrig">*</span></span>
            <select id="o-cat" className={erros.categoria_id ? "erro" : undefined} value={categoriaId ?? ""} disabled={editando}
              onChange={(e) => { setCategoriaId(e.target.value ? Number(e.target.value) : null); setValores({}); }}>
              <option value="">Escolha…</option>
              {categorias.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
            {erros.categoria_id && <span className="erro-campo">{erros.categoria_id}</span>}
          </label>
          <label className="campo" htmlFor="o-pat">
            <span>Patrimônio <span className="dica">opcional · único</span></span>
            <input id="o-pat" className={"mono" + (erros.patrimonio ? " erro" : "")} value={patrimonio} onChange={(e) => setPatrimonio(e.target.value)} placeholder="ex.: 4386" />
            {erros.patrimonio && <span className="erro-campo">{erros.patrimonio}</span>}
          </label>
          <label className="campo" htmlFor="o-nome">
            <span>Nome <span className="dica">como as pessoas reconhecem</span></span>
            <input id="o-nome" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="ex.: Impressora do protocolo" />
          </label>
          {!editando && (
            <label className="campo" htmlFor="o-status">
              <span>Status</span>
              <select id="o-status" value={status} onChange={(e) => setStatus(e.target.value as Status)}>
                {STATUS_EDITAVEIS.map((s) => <option key={s} value={s}>{STATUS_ROTULO[s]}</option>)}
              </select>
            </label>
          )}
        </div>
      </section>

      {categoria && (
        <section className="card">
          <h2>Características · {categoria.nome}</h2>
          {campos.length === 0 ? <p className="muted">Esta categoria ainda não tem campos. <Link to="/categorias">Adicionar campos</Link></p> : (
            <div className="form-grid">
              {campos.map((c) => (
                <CampoInput key={c.id} campo={c} valor={valores[c.chave]} erro={erros[c.chave]}
                  onChange={(v) => setValores((x) => ({ ...x, [c.chave]: v }))} />
              ))}
            </div>
          )}
        </section>
      )}

      {!editando && (
        <section className="card">
          <h2>Posse</h2>
          <PosseSelect valor={posse} onChange={setPosse} erros={erros} />
        </section>
      )}

      <section className="card">
        <label className="campo" htmlFor="o-obs">
          <span>Observação</span>
          <textarea id="o-obs" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
        </label>
      </section>
    </form>
  );
}
