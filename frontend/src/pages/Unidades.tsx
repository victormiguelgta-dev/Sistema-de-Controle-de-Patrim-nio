import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, Setor, Unidade } from "../api";
import { Carregando, ErroBox, Modal, useToast, useUnidades } from "../components/ui";

export default function Unidades() {
  const { data, isLoading, error } = useUnidades();
  const [edit, setEdit] = useState<Unidade | "nova" | null>(null);
  const [novoSetor, setNovoSetor] = useState<Record<number, string>>({});
  const [setorEdit, setSetorEdit] = useState<Setor | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const atualizar = () => { qc.invalidateQueries({ queryKey: ["unidades"] }); qc.invalidateQueries({ queryKey: ["ativos"] }); };

  async function addSetor(u: Unidade, e: FormEvent) {
    e.preventDefault();
    const nome = (novoSetor[u.id] ?? "").trim();
    if (!nome) return;
    try {
      await api.post(`/unidades/${u.id}/setores`, { nome });
      setNovoSetor((s) => ({ ...s, [u.id]: "" }));
      atualizar(); toast("Setor criado");
    } catch (err) { toast((err as Error).message, true); }
  }

  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;
  return (
    <>
      <div className="topo">
        <div><h1>Unidades e setores</h1><p className="sub">Cada objeto pertence a uma unidade (Defensoria). Setor e pessoa são opcionais.</p></div>
        <button className="primario" onClick={() => setEdit("nova")}>Nova unidade</button>
      </div>
      {data.length === 0 ? (
        <div className="card vazio"><p>Nenhuma unidade cadastrada. Crie a primeira, ou importe um arquivo: unidades citadas nele podem ser criadas na revisão.</p></div>
      ) : (
        <div className="grid g3">
          {data.map((u) => (
            <section className="card" key={u.id}>
              <header>
                <div><h2>{u.nome}</h2><p className="muted">{[u.sigla, u.endereco].filter(Boolean).join(" · ") || "—"}</p></div>
                <button className="pequeno" onClick={() => setEdit(u)}>Editar</button>
              </header>
              <Link to={`/objetos?unidade_id=${u.id}`} className="muted num">{u.total_ativos} objeto(s)</Link>
              <div className="chips">
                {u.setores.length === 0 && <span className="muted">Sem setores</span>}
                {u.setores.map((s) => (
                  <button key={s.id} className={"chip" + (s.ativo ? "" : " muted")} style={{ border: 0 }} onClick={() => setSetorEdit(s)} title="Editar setor">
                    {s.nome}{!s.ativo && " (inativo)"}
                  </button>
                ))}
              </div>
              <form className="acoes" onSubmit={(e) => addSetor(u, e)}>
                <input aria-label={`Novo setor em ${u.nome}`} placeholder="Novo setor" value={novoSetor[u.id] ?? ""} style={{ flex: 1 }}
                  onChange={(e) => setNovoSetor((s) => ({ ...s, [u.id]: e.target.value }))} />
                <button className="pequeno">Adicionar</button>
              </form>
            </section>
          ))}
        </div>
      )}
      {edit && <UnidadeModal unidade={edit === "nova" ? null : edit} aoFechar={() => setEdit(null)} aoSalvar={() => { setEdit(null); atualizar(); toast("Unidade salva"); }} />}
      {setorEdit && <SetorModal setor={setorEdit} aoFechar={() => setSetorEdit(null)} aoSalvar={() => { setSetorEdit(null); atualizar(); toast("Setor salvo"); }} />}
    </>
  );
}

function UnidadeModal({ unidade, aoFechar, aoSalvar }: { unidade: Unidade | null; aoFechar: () => void; aoSalvar: () => void }) {
  const [nome, setNome] = useState(unidade?.nome ?? "");
  const [sigla, setSigla] = useState(unidade?.sigla ?? "");
  const [endereco, setEndereco] = useState(unidade?.endereco ?? "");
  const [ativa, setAtiva] = useState(unidade?.ativa ?? true);
  const [erro, setErro] = useState<unknown>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (unidade) await api.put(`/unidades/${unidade.id}`, { nome, sigla, endereco, ativa });
      else await api.post("/unidades", { nome, sigla, endereco });
      aoSalvar();
    } catch (err) { setErro(err); }
  }
  return (
    <Modal titulo={unidade ? "Editar unidade" : "Nova unidade"} aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <label className="campo" htmlFor="un-nome"><span>Nome <span className="obrig">*</span></span><input id="un-nome" autoFocus value={nome} onChange={(e) => setNome(e.target.value)} placeholder="ex.: Fórum Gama" /></label>
        <div className="form-grid">
          <label className="campo" htmlFor="un-sigla"><span>Sigla</span><input id="un-sigla" value={sigla} onChange={(e) => setSigla(e.target.value)} /></label>
          <label className="campo" htmlFor="un-end"><span>Endereço</span><input id="un-end" value={endereco} onChange={(e) => setEndereco(e.target.value)} /></label>
        </div>
        {unidade && <label className="check"><input type="checkbox" checked={ativa} onChange={(e) => setAtiva(e.target.checked)} /> Unidade ativa</label>}
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={!nome.trim()}>Salvar</button></footer>
      </form>
    </Modal>
  );
}

function SetorModal({ setor, aoFechar, aoSalvar }: { setor: Setor; aoFechar: () => void; aoSalvar: () => void }) {
  const [nome, setNome] = useState(setor.nome);
  const [ativo, setAtivo] = useState(setor.ativo);
  const [erro, setErro] = useState<unknown>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try { await api.put(`/setores/${setor.id}`, { nome, ativo }); aoSalvar(); } catch (err) { setErro(err); }
  }
  return (
    <Modal titulo="Editar setor" aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <label className="campo" htmlFor="se-nome"><span>Nome</span><input id="se-nome" autoFocus value={nome} onChange={(e) => setNome(e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} /> Setor ativo</label>
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={!nome.trim()}>Salvar</button></footer>
      </form>
    </Modal>
  );
}
