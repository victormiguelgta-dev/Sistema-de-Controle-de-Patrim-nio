import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Dashboard as D, formatarData, STATUS_ROTULO, Status } from "../api";
import { Carregando, ErroBox, StatusPill } from "../components/ui";
import { descreverMovimentacao } from "./ObjetoFicha";

function Barras({ itens, link }: { itens: { id: number | string; nome: string; total: number; extra?: string }[]; link: (id: number | string) => string }) {
  const max = Math.max(1, ...itens.map((i) => i.total));
  if (!itens.length) return <p className="muted">Nada cadastrado ainda.</p>;
  return (
    <div className="barras">
      {itens.map((i) => (
        <Link key={i.id} to={link(i.id)} className="barra" title={[i.nome, i.extra].filter(Boolean).join(" · ")}>
          <span className="nome">{i.nome}</span>
          <span className="trilho"><span className="preenche" style={{ width: `${(i.total / max) * 100}%`, display: "block" }} /></span>
          <b>{i.total}</b>
        </Link>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<D>("/dashboard") });
  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;
  const defeito = data.por_status.com_defeito ?? 0;
  const manutencao = data.por_status.em_manutencao ?? 0;
  return (
    <>
      <div className="topo">
        <div><h1>Painel</h1><p className="sub">Visão geral do patrimônio cadastrado</p></div>
        <div className="acoes">
          <Link className="btn" to="/importar">Importar arquivo</Link>
          <Link className="btn primario" to="/objetos/novo">Novo objeto</Link>
        </div>
      </div>

      <div className="kpis">
        <Link className="kpi" to="/objetos"><b>{data.total}</b><span>objetos ativos</span></Link>
        <Link className={"kpi" + (defeito ? " alerta" : "")} to="/objetos?status=com_defeito"><b>{defeito}</b><span>com defeito</span></Link>
        <Link className={"kpi" + (manutencao ? " atencao" : "")} to="/objetos?status=em_manutencao"><b>{manutencao}</b><span>em manutenção</span></Link>
        <Link className={"kpi" + (data.itens_pendentes_revisao ? " atencao" : "")} to="/importar"><b>{data.itens_pendentes_revisao}</b><span>itens aguardando revisão</span></Link>
        <Link className="kpi" to="/arquivados"><b>{data.arquivados}</b><span>arquivados</span></Link>
      </div>

      <div className="grid g3">
        <section className="card">
          <h2>Por status</h2>
          <Barras link={(id) => `/objetos?status=${id}`}
            itens={Object.entries(data.por_status).map(([s, n]) => ({ id: s, nome: STATUS_ROTULO[s as Status], total: n }))} />
        </section>
        <section className="card">
          <h2>Por categoria</h2>
          <Barras link={(id) => `/objetos?categoria_id=${id}`}
            itens={data.por_categoria.map((c) => ({ id: c.id, nome: c.nome, total: c.total }))} />
        </section>
        <section className="card">
          <h2>Por unidade</h2>
          <Barras link={(id) => `/objetos?unidade_id=${id}`}
            itens={data.por_unidade.map((u) => ({ id: u.id, nome: u.nome, total: u.total,
              extra: u.com_defeito ? `${u.com_defeito} com defeito` : undefined }))} />
        </section>
      </div>

      <section className="card">
        <header><h2>Últimas movimentações</h2></header>
        {data.ultimas_movimentacoes.length === 0 ? <p className="muted">Nenhuma movimentação ainda.</p> : (
          <div className="linha-tempo">
            {data.ultimas_movimentacoes.map((m) => (
              <div className="evento" key={m.id}>
                <time>{formatarData(m.data)}</time>
                <div>
                  <Link to={`/objetos/${m.ativo?.id}`}><b>{m.ativo?.nome || `Objeto #${m.ativo?.id}`}</b></Link>
                  <span className="muted"> · {m.ativo?.categoria}{m.ativo?.patrimonio ? ` · PAT ${m.ativo.patrimonio}` : ""}</span>
                  <div>{descreverMovimentacao(m)} {m.status_novo && m.tipo !== "transferencia" && <StatusPill status={m.status_novo} />}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
