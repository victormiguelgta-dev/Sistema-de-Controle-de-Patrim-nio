import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api, AtivoDetalhe, AtivoLista, Auditoria, formatarData, formatarValor, Movimentacao, qs,
  STATUS_EDITAVEIS, STATUS_ROTULO, Status,
} from "../api";
import { Carregando, ErroBox, Modal, Patrimonio, PosseSelect, Posse, StatusPill, useToast } from "../components/ui";

const ACAO_ROTULO: Record<string, string> = {
  criar: "Cadastro", editar: "Edição", transferir: "Transferência", status: "Mudança de status",
  arquivar: "Arquivamento", restaurar: "Restauração", vincular: "Vínculo criado", desvincular: "Vínculo removido",
};
const TIPOS_VINCULO = ["fila_impressao", "ramal", "monitor", "periferico", "outro"];

export function descreverMovimentacao(m: Movimentacao): string {
  const posse = (u: Movimentacao["unidade_destino"], s: Movimentacao["setor_destino"], p: Movimentacao["pessoa_destino"]) =>
    [u?.nome, s?.nome, p?.nome].filter(Boolean).join(" › ") || "—";
  switch (m.tipo) {
    case "cadastro": return `Cadastrado em ${posse(m.unidade_destino, m.setor_destino, m.pessoa_destino)}`;
    case "transferencia": return `Transferido: ${posse(m.unidade_origem, m.setor_origem, m.pessoa_origem)} → ${posse(m.unidade_destino, m.setor_destino, m.pessoa_destino)}`;
    case "status": return `Status: ${STATUS_ROTULO[m.status_anterior as Status] ?? "—"} → ${STATUS_ROTULO[m.status_novo as Status] ?? "—"}`;
    case "arquivamento": return "Arquivado";
    case "restauracao": return "Restaurado do arquivo";
    default: return m.tipo;
  }
}

function Diff({ a }: { a: Auditoria }) {
  const antes = (a.antes ?? {}) as Record<string, unknown>;
  const depois = (a.depois ?? {}) as Record<string, unknown>;
  const linhas: string[][] = [];
  const chaves = new Set([...Object.keys(antes), ...Object.keys(depois)]);
  for (const k of chaves) {
    if (k === "valores") {
      const va = (antes.valores ?? {}) as Record<string, unknown>;
      const vd = (depois.valores ?? {}) as Record<string, unknown>;
      for (const c of new Set([...Object.keys(va), ...Object.keys(vd)])) {
        if (JSON.stringify(va[c]) !== JSON.stringify(vd[c])) linhas.push([c, String(va[c] ?? "—"), String(vd[c] ?? "—")]);
      }
    } else if (JSON.stringify(antes[k]) !== JSON.stringify(depois[k])) {
      linhas.push([k, a.antes ? String(antes[k] ?? "—") : "", a.depois ? String(depois[k] ?? "—") : ""]);
    }
  }
  if (!linhas.length) return null;
  return (
    <div className="diff">
      {linhas.slice(0, 12).map(([k, x, y]) => (
        <div key={k}>{k}: {x && <del>{x}</del>}{x && y && " → "}{y && <ins>{y}</ins>}</div>
      ))}
    </div>
  );
}

type Acao = "transferir" | "status" | "arquivar" | "restaurar" | "vincular" | null;

export default function ObjetoFicha() {
  const { id } = useParams();
  const qc = useQueryClient();
  const toast = useToast();
  const { data: a, isLoading, error } = useQuery({ queryKey: ["ativo", id], queryFn: () => api.get<AtivoDetalhe>(`/ativos/${id}`) });
  const [aba, setAba] = useState<"historico" | "vinculos" | "auditoria">("historico");
  const [acao, setAcao] = useState<Acao>(null);

  if (isLoading) return <Carregando />;
  if (error || !a) return <ErroBox erro={error ?? "Objeto não encontrado"} />;
  const arquivado = Boolean(a.arquivado_em);
  const fechar = () => setAcao(null);
  const pronto = (msg: string) => { qc.invalidateQueries(); toast(msg); fechar(); };

  return (
    <>
      <div className="topo">
        <div style={{ display: "grid", gap: 8 }}>
          <Link to={arquivado ? "/arquivados" : "/objetos"} className="muted">← {arquivado ? "Arquivados" : "Objetos"}</Link>
          <h1>{a.nome || `${a.categoria.nome} #${a.id}`}</h1>
          <div className="acoes"><Patrimonio valor={a.patrimonio} /><StatusPill status={a.status} /><span className="chip">{a.categoria.nome}</span></div>
        </div>
        <div className="acoes">
          {arquivado ? (
            <button className="primario" onClick={() => setAcao("restaurar")}>Restaurar</button>
          ) : (
            <>
              <Link className="btn" to={`/objetos/${a.id}/editar`}>Editar</Link>
              <button onClick={() => setAcao("transferir")}>Transferir</button>
              <button onClick={() => setAcao("status")}>Mudar status</button>
              <button onClick={() => setAcao("vincular")}>Vincular</button>
              <button className="perigo" onClick={() => setAcao("arquivar")}>Arquivar</button>
            </>
          )}
        </div>
      </div>

      {arquivado && (
        <div className="aviso atencao">Arquivado em {formatarData(a.arquivado_em)}. Motivo: {a.motivo_arquivo}</div>
      )}

      <div className="grid g2">
        <section className="card">
          <h2>Características</h2>
          <dl className="dados">
            {a.campos.filter((c) => c.ativo || a.valores[c.chave] != null).map((c) => (
              <div className="dado" key={c.id}>
                <dt>{c.rotulo}</dt>
                <dd className={["ip", "mac"].includes(c.tipo) ? "mono" : undefined}>{formatarValor(a.valores[c.chave], c.tipo)}</dd>
              </div>
            ))}
          </dl>
          {a.observacao && <p><span className="muted">Observação:</span> {a.observacao}</p>}
        </section>
        <section className="card">
          <h2>Posse</h2>
          <dl className="dados">
            <div className="dado"><dt>Unidade</dt><dd>{a.unidade.nome}</dd></div>
            <div className="dado"><dt>Setor</dt><dd>{a.setor?.nome ?? "—"}</dd></div>
            <div className="dado"><dt>Pessoa</dt><dd>{a.pessoa?.nome ?? "—"}</dd></div>
            <div className="dado"><dt>Origem do cadastro</dt><dd>{{ manual: "Manual", planilha: "Planilha", ia: "IA (Gemini)", regras: "Importação por regras" }[a.origem] ?? a.origem}</dd></div>
            <div className="dado"><dt>Cadastrado em</dt><dd className="num">{formatarData(a.criado_em)}</dd></div>
            <div className="dado"><dt>Atualizado em</dt><dd className="num">{formatarData(a.atualizado_em)}</dd></div>
          </dl>
        </section>
      </div>

      <section className="card">
        <div className="abas" role="tablist">
          <button role="tab" aria-selected={aba === "historico"} className={aba === "historico" ? "ativa" : ""} onClick={() => setAba("historico")}>Histórico ({a.movimentacoes.length})</button>
          <button role="tab" aria-selected={aba === "vinculos"} className={aba === "vinculos" ? "ativa" : ""} onClick={() => setAba("vinculos")}>Ligado a ({a.vinculos.length})</button>
          <button role="tab" aria-selected={aba === "auditoria"} className={aba === "auditoria" ? "ativa" : ""} onClick={() => setAba("auditoria")}>Auditoria</button>
        </div>
        {aba === "historico" && (
          <div className="linha-tempo">
            {a.movimentacoes.map((m) => (
              <div className="evento" key={m.id}>
                <time>{formatarData(m.data)}</time>
                <div><span className="tipo">{descreverMovimentacao(m)}</span>{m.observacao && <p className="muted">{m.observacao}</p>}</div>
              </div>
            ))}
          </div>
        )}
        {aba === "vinculos" && (
          a.vinculos.length === 0 ? <p className="muted">Nenhum vínculo. Use “Vincular” para ligar este objeto a outro (ex.: impressora ↔ fila, telefone ↔ ramal).</p> : (
            <div className="linha-tempo">
              {a.vinculos.map((v) => (
                <div className="evento" key={v.id}>
                  <span className="chip">{v.tipo.replace("_", " ")}</span>
                  <div className="topo">
                    <div>
                      <Link to={`/objetos/${v.outro.id}`}><b>{v.outro.nome || `Objeto #${v.outro.id}`}</b></Link>
                      <span className="muted"> · {v.outro.categoria}{v.outro.patrimonio ? ` · PAT ${v.outro.patrimonio}` : ""}</span>
                      {v.observacao && <p className="muted">{v.observacao}</p>}
                    </div>
                    {!arquivado && (
                      <button className="pequeno perigo" onClick={async () => {
                        try { await api.del(`/vinculos/${v.id}`); pronto("Vínculo removido"); } catch (e) { toast(String((e as Error).message), true); }
                      }}>Remover</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )
        )}
        {aba === "auditoria" && (
          <div className="linha-tempo">
            {a.auditoria.map((x) => (
              <div className="evento" key={x.id}>
                <time>{formatarData(x.criado_em)}</time>
                <div><span className="tipo">{ACAO_ROTULO[x.acao] ?? x.acao}</span><Diff a={x} /></div>
              </div>
            ))}
          </div>
        )}
      </section>

      {acao === "transferir" && <Transferir ativo={a} aoFechar={fechar} aoConcluir={pronto} />}
      {acao === "status" && <MudarStatus ativo={a} aoFechar={fechar} aoConcluir={pronto} />}
      {acao === "arquivar" && <Arquivar ativo={a} aoFechar={fechar} aoConcluir={pronto} abrirStatus={() => setAcao("status")} />}
      {acao === "restaurar" && <Restaurar ativo={a} aoFechar={fechar} aoConcluir={pronto} />}
      {acao === "vincular" && <Vincular ativo={a} aoFechar={fechar} aoConcluir={pronto} />}
    </>
  );
}

interface PropsAcao { ativo: AtivoDetalhe; aoFechar: () => void; aoConcluir: (msg: string) => void }

function useEnvio(aoConcluir: (msg: string) => void) {
  const [erro, setErro] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  async function enviar(fn: () => Promise<unknown>, msg: string) {
    setErro(null);
    setEnviando(true);
    try { await fn(); aoConcluir(msg); } catch (e) { setErro(e); } finally { setEnviando(false); }
  }
  return { erro, enviando, enviar };
}

function Transferir({ ativo, aoFechar, aoConcluir }: PropsAcao) {
  const [posse, setPosse] = useState<Posse>({ unidade_id: ativo.unidade.id, setor_id: ativo.setor?.id ?? null, pessoa_id: ativo.pessoa?.id ?? null });
  const [obs, setObs] = useState("");
  const { erro, enviando, enviar } = useEnvio(aoConcluir);
  const submit = (e: FormEvent) => { e.preventDefault(); enviar(() => api.post(`/ativos/${ativo.id}/transferir`, { ...posse, observacao: obs }), "Objeto transferido"); };
  return (
    <Modal titulo="Transferir objeto" aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <PosseSelect valor={posse} onChange={setPosse} prefixo="tr" />
        <label className="campo" htmlFor="tr-obs"><span>Observação</span><textarea id="tr-obs" value={obs} onChange={(e) => setObs(e.target.value)} /></label>
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={enviando || !posse.unidade_id}>Transferir</button></footer>
      </form>
    </Modal>
  );
}

function MudarStatus({ ativo, aoFechar, aoConcluir }: PropsAcao) {
  const [status, setStatus] = useState<Status>(ativo.status === "com_defeito" ? "em_manutencao" : "com_defeito");
  const [obs, setObs] = useState("");
  const { erro, enviando, enviar } = useEnvio(aoConcluir);
  const submit = (e: FormEvent) => { e.preventDefault(); enviar(() => api.post(`/ativos/${ativo.id}/status`, { status, observacao: obs }), "Status atualizado"); };
  return (
    <Modal titulo="Mudar status" aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <p>Atual: <StatusPill status={ativo.status} /></p>
        <label className="campo" htmlFor="st-novo"><span>Novo status</span>
          <select id="st-novo" value={status} onChange={(e) => setStatus(e.target.value as Status)}>
            {STATUS_EDITAVEIS.filter((s) => s !== ativo.status).map((s) => <option key={s} value={s}>{STATUS_ROTULO[s]}</option>)}
          </select>
        </label>
        <label className="campo" htmlFor="st-obs"><span>O que aconteceu? <span className="dica">fica no histórico</span></span>
          <textarea id="st-obs" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="ex.: não liga, painel apagado" />
        </label>
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={enviando}>Salvar</button></footer>
      </form>
    </Modal>
  );
}

function Arquivar({ ativo, aoFechar, aoConcluir, abrirStatus }: PropsAcao & { abrirStatus: () => void }) {
  const [motivo, setMotivo] = useState("");
  const { erro, enviando, enviar } = useEnvio(aoConcluir);
  const pode = ativo.status === "com_defeito" || ativo.status === "em_manutencao";
  const submit = (e: FormEvent) => { e.preventDefault(); enviar(() => api.post(`/ativos/${ativo.id}/arquivar`, { motivo }), "Objeto arquivado"); };
  return (
    <Modal titulo="Arquivar objeto" aoFechar={aoFechar}>
      {!pode ? (
        <>
          <p>Só objetos <b>com defeito</b> ou <b>em manutenção</b> podem ser arquivados. Primeiro registre o defeito.</p>
          <footer><button onClick={aoFechar}>Cancelar</button><button className="primario" onClick={abrirStatus}>Marcar como com defeito</button></footer>
        </>
      ) : (
        <form className="form" onSubmit={submit}>
          <p>O objeto sai das listas e do painel, mas continua consultável em Arquivados e pode ser restaurado.</p>
          <label className="campo" htmlFor="arq-motivo"><span>Motivo <span className="obrig">*</span></span>
            <textarea id="arq-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="ex.: placa queimada, sem conserto" />
          </label>
          <ErroBox erro={erro} />
          <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="perigo cheio" disabled={enviando || motivo.trim().length < 3}>Arquivar</button></footer>
        </form>
      )}
    </Modal>
  );
}

function Restaurar({ ativo, aoFechar, aoConcluir }: PropsAcao) {
  const [obs, setObs] = useState("");
  const { erro, enviando, enviar } = useEnvio(aoConcluir);
  const submit = (e: FormEvent) => { e.preventDefault(); enviar(() => api.post(`/ativos/${ativo.id}/restaurar`, { observacao: obs }), "Objeto restaurado"); };
  return (
    <Modal titulo="Restaurar objeto" aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <p>O objeto volta como <b>Em estoque</b> na mesma unidade.</p>
        <label className="campo" htmlFor="rs-obs"><span>Observação</span><textarea id="rs-obs" value={obs} onChange={(e) => setObs(e.target.value)} /></label>
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={enviando}>Restaurar</button></footer>
      </form>
    </Modal>
  );
}

function Vincular({ ativo, aoFechar, aoConcluir }: PropsAcao) {
  const [busca, setBusca] = useState("");
  const [destino, setDestino] = useState<number | null>(null);
  const [tipo, setTipo] = useState("outro");
  const [obs, setObs] = useState("");
  const { erro, enviando, enviar } = useEnvio(aoConcluir);
  const resultados = useQuery({
    queryKey: ["busca-vinculo", busca],
    queryFn: () => api.get<AtivoLista>(`/ativos${qs({ q: busca, por_pagina: 8 })}`),
    enabled: busca.trim().length >= 2,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (destino) enviar(() => api.post(`/ativos/${ativo.id}/vinculos`, { ativo_destino_id: destino, tipo, observacao: obs }), "Vínculo criado");
  };
  return (
    <Modal titulo="Vincular a outro objeto" aoFechar={aoFechar}>
      <form className="form" onSubmit={submit}>
        <label className="campo" htmlFor="vc-busca"><span>Buscar objeto</span>
          <input id="vc-busca" autoFocus value={busca} onChange={(e) => { setBusca(e.target.value); setDestino(null); }} placeholder="Patrimônio, nome, IP…" />
        </label>
        <div className="linha-tempo">
          {resultados.data?.itens.filter((x) => x.id !== ativo.id).map((x) => (
            <label key={x.id} className="check" style={{ padding: "6px 0" }}>
              <input type="radio" name="vc-destino" checked={destino === x.id} onChange={() => setDestino(x.id)} />
              <span><b>{x.nome || `Objeto #${x.id}`}</b> <span className="muted">· {x.categoria.nome}{x.patrimonio ? ` · PAT ${x.patrimonio}` : ""} · {x.unidade.nome}</span></span>
            </label>
          ))}
          {resultados.data && resultados.data.itens.length === 0 && <p className="muted">Nada encontrado.</p>}
        </div>
        <div className="form-grid">
          <label className="campo" htmlFor="vc-tipo"><span>Tipo de vínculo</span>
            <select id="vc-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {TIPOS_VINCULO.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
            </select>
          </label>
          <label className="campo" htmlFor="vc-obs"><span>Observação</span><input id="vc-obs" value={obs} onChange={(e) => setObs(e.target.value)} /></label>
        </div>
        <ErroBox erro={erro} />
        <footer><button type="button" onClick={aoFechar}>Cancelar</button><button className="primario" disabled={enviando || !destino}>Vincular</button></footer>
      </form>
    </Modal>
  );
}
