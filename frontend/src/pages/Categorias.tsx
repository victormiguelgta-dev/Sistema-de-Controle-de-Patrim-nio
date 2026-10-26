import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, Campo, Categoria, TIPO_ROTULO, TipoCampo } from "../api";
import { Carregando, ErroBox, Modal, useCategorias, useToast } from "../components/ui";

const separar = (t: string) => t.split(/[\n,;]/).map((x) => x.trim()).filter(Boolean);

export default function Categorias() {
  const { data, isLoading, error } = useCategorias(true);
  const [selId, setSelId] = useState<number | null>(null);
  const [novaCat, setNovaCat] = useState(false);
  const [editCat, setEditCat] = useState(false);
  const [campoEdit, setCampoEdit] = useState<Campo | "novo" | null>(null);
  const qc = useQueryClient();
  const toast = useToast();

  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;
  const sel = data.find((c) => c.id === selId) ?? data[0];
  const atualizar = () => qc.invalidateQueries({ queryKey: ["categorias"] });

  async function mover(campo: Campo, delta: number) {
    if (!sel) return;
    const ids = sel.campos.map((c) => c.id);
    const i = ids.indexOf(campo.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    try { await api.put(`/categorias/${sel.id}/ordem`, { campo_ids: ids }); atualizar(); }
    catch (e) { toast((e as Error).message, true); }
  }

  async function remover(campo: Campo) {
    try {
      const r = await api.del<{ mensagem: string }>(`/campos/${campo.id}`);
      toast(r.mensagem); atualizar();
    } catch (e) { toast((e as Error).message, true); }
  }

  async function reativar(campo: Campo) {
    try { await api.put(`/campos/${campo.id}`, { ativo: true }); atualizar(); toast("Campo reativado"); }
    catch (e) { toast((e as Error).message, true); }
  }

  return (
    <>
      <div className="topo">
        <div><h1>Categorias</h1><p className="sub">Cada categoria define as características dos seus objetos. A IA e a importação usam os campos e sinônimos daqui.</p></div>
        <button className="primario" onClick={() => setNovaCat(true)}>Nova categoria</button>
      </div>
      <div className="layout-cat">
        <nav className="lista-cat card" aria-label="Categorias">
          {data.map((c) => (
            <button key={c.id} className={c.id === sel?.id ? "sel" : ""} onClick={() => setSelId(c.id)}>
              <span>{c.nome}{!c.ativa && <span className="muted"> (inativa)</span>}</span><span className="muted num">{c.total_ativos}</span>
            </button>
          ))}
        </nav>
        {sel && (
          <section className="card">
            <header>
              <div>
                <h2>{sel.nome}</h2>
                <p className="muted">{sel.descricao || "Sem descrição"} · slug <code>{sel.slug}</code> · <Link to={`/objetos?categoria_id=${sel.id}`}>{sel.total_ativos} objeto(s)</Link></p>
              </div>
              <div className="acoes">
                <button onClick={() => setEditCat(true)}>Editar categoria</button>
                <button className="primario" onClick={() => setCampoEdit("novo")}>Adicionar campo</button>
              </div>
            </header>
            {sel.campos.length === 0 ? <p className="muted">Sem campos ainda.</p> : sel.campos.map((c, i) => (
              <div className={"campo-linha" + (c.ativo ? "" : " inativo")} key={c.id}>
                <div className="setas">
                  <button aria-label="Subir" disabled={i === 0} onClick={() => mover(c, -1)}>▲</button>
                  <button aria-label="Descer" disabled={i === sel.campos.length - 1} onClick={() => mover(c, 1)}>▼</button>
                </div>
                <div style={{ display: "grid", gap: 4, minWidth: 0 }}>
                  <div><b>{c.rotulo}</b> <code className="muted">{c.chave}</code>{!c.ativo && <span className="muted"> · desativado</span>}</div>
                  <div className="chips">
                    <span className="chip">{TIPO_ROTULO[c.tipo]}</span>
                    {c.obrigatorio && <span className="chip">obrigatório</span>}
                    {c.unico && <span className="chip">único</span>}
                    {c.filtravel && <span className="chip">filtro</span>}
                    {c.opcoes.length > 0 && <span className="muted">opções: {c.opcoes.join(", ")}</span>}
                  </div>
                  {c.sinonimos.length > 0 && <div className="muted" style={{ fontSize: "0.8rem" }}>também aparece como: {c.sinonimos.join(", ")}</div>}
                </div>
                <div className="acoes">
                  <button className="pequeno" onClick={() => setCampoEdit(c)}>Editar</button>
                  {c.ativo ? <button className="pequeno perigo" onClick={() => remover(c)}>Remover</button>
                    : <button className="pequeno" onClick={() => reativar(c)}>Reativar</button>}
                </div>
              </div>
            ))}
          </section>
        )}
      </div>
      {novaCat && <CategoriaModal aoFechar={() => setNovaCat(false)} aoSalvar={(c) => { setNovaCat(false); atualizar(); setSelId(c.id); toast("Categoria criada"); }} />}
      {editCat && sel && <CategoriaModal categoria={sel} aoFechar={() => setEditCat(false)} aoSalvar={() => { setEditCat(false); atualizar(); toast("Categoria salva"); }} />}
      {campoEdit && sel && <CampoModal categoria={sel} campo={campoEdit === "novo" ? null : campoEdit}
        aoFechar={() => setCampoEdit(null)} aoSalvar={() => { setCampoEdit(null); atualizar(); toast("Campo salvo"); }} />}
    </>
  );
}

function CategoriaModal({ categoria, aoFechar, aoSalvar }: { categoria?: Categoria; aoFechar: () => void; aoSalvar: (c: Categoria) => void }) {
  const [nome, setNome] = useState(categoria?.nome ?? "");
  const [descricao, setDescricao] = useState(categoria?.descricao ?? "");
  const [ativa, setAtiva] = useState(categoria?.ativa ?? true);
  const [erro, setErro] = useState<unknown>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const c = categoria
        ? await api.put<Categoria>(`/categorias/${categoria.id}`, { nome, descricao, ativa })
        : await api.post<Categoria>("/categorias", { nome, descricao, campos: [] });
      aoSalvar(c);
    } catch (err) { setErro(err); }
  }
  return (
    <Modal titulo={categoria ? "Editar categoria" : "Nova categoria"} aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <label className="campo" htmlFor="cat-nome"><span>Nome <span className="obrig">*</span></span><input id="cat-nome" autoFocus value={nome} onChange={(e) => setNome(e.target.value)} placeholder="ex.: Nobreak" /></label>
        <label className="campo" htmlFor="cat-desc"><span>Descrição <span className="dica">ajuda a IA a reconhecer a categoria</span></span><textarea id="cat-desc" value={descricao} onChange={(e) => setDescricao(e.target.value)} /></label>
        {categoria && <label className="check"><input type="checkbox" checked={ativa} onChange={(e) => setAtiva(e.target.checked)} /> Categoria ativa (inativas não aparecem no cadastro)</label>}
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={!nome.trim()}>Salvar</button></footer>
      </form>
    </Modal>
  );
}

function CampoModal({ categoria, campo, aoFechar, aoSalvar }: { categoria: Categoria; campo: Campo | null; aoFechar: () => void; aoSalvar: () => void }) {
  const [rotulo, setRotulo] = useState(campo?.rotulo ?? "");
  const [chave, setChave] = useState(campo?.chave ?? "");
  const [tipo, setTipo] = useState<TipoCampo>(campo?.tipo ?? "texto");
  const [obrigatorio, setObrigatorio] = useState(campo?.obrigatorio ?? false);
  const [unico, setUnico] = useState(campo?.unico ?? false);
  const [filtravel, setFiltravel] = useState(campo?.filtravel ?? false);
  const [opcoes, setOpcoes] = useState((campo?.opcoes ?? []).join(", "));
  const [sinonimos, setSinonimos] = useState((campo?.sinonimos ?? []).join(", "));
  const [erro, setErro] = useState<unknown>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    const corpo = { rotulo, tipo, obrigatorio, unico, filtravel, opcoes: separar(opcoes), sinonimos: separar(sinonimos) };
    try {
      if (campo) await api.put(`/campos/${campo.id}`, corpo);
      else await api.post(`/categorias/${categoria.id}/campos`, { ...corpo, chave: chave || null });
      aoSalvar();
    } catch (err) { setErro(err); }
  }
  return (
    <Modal titulo={campo ? `Editar campo · ${categoria.nome}` : `Novo campo · ${categoria.nome}`} aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <label className="campo" htmlFor="cp-rotulo"><span>Rótulo <span className="obrig">*</span></span><input id="cp-rotulo" autoFocus value={rotulo} onChange={(e) => setRotulo(e.target.value)} placeholder="ex.: Ramal" /></label>
          <label className="campo" htmlFor="cp-chave"><span>Chave <span className="dica">{campo ? "não muda" : "gerada do rótulo se vazio"}</span></span>
            <input id="cp-chave" className="mono" value={chave} disabled={Boolean(campo)} onChange={(e) => setChave(e.target.value)} placeholder="ramal" /></label>
          <label className="campo" htmlFor="cp-tipo"><span>Tipo</span>
            <select id="cp-tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoCampo)}>
              {(Object.keys(TIPO_ROTULO) as TipoCampo[]).map((t) => <option key={t} value={t}>{TIPO_ROTULO[t]}</option>)}
            </select>
          </label>
        </div>
        {tipo === "lista" && (
          <label className="campo" htmlFor="cp-opcoes"><span>Opções <span className="obrig">*</span> <span className="dica">separadas por vírgula</span></span>
            <input id="cp-opcoes" value={opcoes} onChange={(e) => setOpcoes(e.target.value)} placeholder="Fixo, DHCP" /></label>
        )}
        <label className="campo" htmlFor="cp-sin"><span>Sinônimos <span className="dica">como esse dado aparece em planilhas e textos; separados por vírgula</span></span>
          <input id="cp-sin" value={sinonimos} onChange={(e) => setSinonimos(e.target.value)} placeholder="Endereço IP, IP, End. IP" /></label>
        <div className="acoes">
          <label className="check"><input type="checkbox" checked={obrigatorio} onChange={(e) => setObrigatorio(e.target.checked)} /> Obrigatório</label>
          <label className="check"><input type="checkbox" checked={unico} onChange={(e) => setUnico(e.target.checked)} /> Valor único</label>
          <label className="check"><input type="checkbox" checked={filtravel} onChange={(e) => setFiltravel(e.target.checked)} /> Aparece nos filtros</label>
        </div>
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={!rotulo.trim()}>Salvar</button></footer>
      </form>
    </Modal>
  );
}
