import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, Pessoa } from "../api";
import { Carregando, ErroBox, Modal, usePessoas, useToast, useUnidades } from "../components/ui";

export default function Pessoas() {
  const { data, isLoading, error } = usePessoas();
  const [edit, setEdit] = useState<Pessoa | "nova" | null>(null);
  const [busca, setBusca] = useState("");
  const qc = useQueryClient();
  const toast = useToast();

  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;
  const termo = busca.trim().toLowerCase();
  const lista = data.filter((p) => !termo || p.nome.toLowerCase().includes(termo) || (p.matricula ?? "").toLowerCase().includes(termo));
  return (
    <>
      <div className="topo">
        <div><h1>Pessoas</h1><p className="sub">Responsáveis pelos objetos. Não precisam ter acesso ao sistema.</p></div>
        <button className="primario" onClick={() => setEdit("nova")}>Nova pessoa</button>
      </div>
      <input aria-label="Buscar pessoa" placeholder="Buscar por nome ou matrícula" value={busca} onChange={(e) => setBusca(e.target.value)} style={{ maxWidth: 360 }} />
      {lista.length === 0 ? <div className="card vazio"><p>{data.length ? "Ninguém encontrado." : "Nenhuma pessoa cadastrada."}</p></div> : (
        <div className="tabela-wrap">
          <table>
            <thead><tr><th>Nome</th><th>Matrícula</th><th>Unidade › Setor</th><th>Contato</th><th></th></tr></thead>
            <tbody>
              {lista.map((p) => (
                <tr key={p.id}>
                  <td><b>{p.nome}</b></td>
                  <td className="mono">{p.matricula ?? "—"}</td>
                  <td>{p.unidade?.nome ?? "—"}{p.setor && <span className="muted"> › {p.setor.nome}</span>}</td>
                  <td className="muted">{[p.email, p.telefone].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="acoes" style={{ justifyContent: "flex-end" }}>
                    <Link className="btn pequeno" to={`/objetos?pessoa_id=${p.id}`}>Objetos</Link>
                    <button className="pequeno" onClick={() => setEdit(p)}>Editar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {edit && <PessoaModal pessoa={edit === "nova" ? null : edit} aoFechar={() => setEdit(null)}
        aoSalvar={() => { setEdit(null); qc.invalidateQueries({ queryKey: ["pessoas"] }); toast("Pessoa salva"); }} />}
    </>
  );
}

function PessoaModal({ pessoa, aoFechar, aoSalvar }: { pessoa: Pessoa | null; aoFechar: () => void; aoSalvar: () => void }) {
  const unidades = useUnidades();
  const [f, setF] = useState({
    nome: pessoa?.nome ?? "", matricula: pessoa?.matricula ?? "", email: pessoa?.email ?? "", telefone: pessoa?.telefone ?? "",
    unidade_id: pessoa?.unidade_id ?? null as number | null, setor_id: pessoa?.setor_id ?? null as number | null,
  });
  const [ativa, setAtiva] = useState(pessoa?.ativa ?? true);
  const [erro, setErro] = useState<unknown>(null);
  const unidade = unidades.data?.find((u) => u.id === f.unidade_id);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (pessoa) await api.put(`/pessoas/${pessoa.id}`, { ...f, ativa });
      else await api.post("/pessoas", f);
      aoSalvar();
    } catch (err) { setErro(err); }
  }
  return (
    <Modal titulo={pessoa ? "Editar pessoa" : "Nova pessoa"} aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <label className="campo" htmlFor="pe-nome"><span>Nome <span className="obrig">*</span></span><input id="pe-nome" autoFocus value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} /></label>
          <label className="campo" htmlFor="pe-mat"><span>Matrícula</span><input id="pe-mat" value={f.matricula} onChange={(e) => setF({ ...f, matricula: e.target.value })} /></label>
          <label className="campo" htmlFor="pe-uni"><span>Unidade</span>
            <select id="pe-uni" value={f.unidade_id ?? ""} onChange={(e) => setF({ ...f, unidade_id: e.target.value ? Number(e.target.value) : null, setor_id: null })}>
              <option value="">—</option>{unidades.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>
          </label>
          <label className="campo" htmlFor="pe-set"><span>Setor</span>
            <select id="pe-set" value={f.setor_id ?? ""} disabled={!unidade} onChange={(e) => setF({ ...f, setor_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">—</option>{unidade?.setores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          </label>
          <label className="campo" htmlFor="pe-email"><span>E-mail</span><input id="pe-email" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
          <label className="campo" htmlFor="pe-tel"><span>Telefone</span><input id="pe-tel" value={f.telefone} onChange={(e) => setF({ ...f, telefone: e.target.value })} /></label>
        </div>
        {pessoa && <label className="check"><input type="checkbox" checked={ativa} onChange={(e) => setAtiva(e.target.checked)} /> Pessoa ativa</label>}
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={!f.nome.trim()}>Salvar</button></footer>
      </form>
    </Modal>
  );
}
