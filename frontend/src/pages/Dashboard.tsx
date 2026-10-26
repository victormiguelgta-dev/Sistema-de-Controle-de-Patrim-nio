import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Dashboard as D, formatarData, SerieMes, STATUS_ROTULO, Status } from "../api";
import { Carregando, ErroBox } from "../components/ui";
import { Fatia, GraficoMensal, Minigrafico, NumeroAnimado, Rosca } from "../components/graficos";
import { descreverMovimentacao } from "./ObjetoFicha";

const COR_STATUS: Record<string, string> = {
  em_uso: "var(--ok)", em_estoque: "var(--brand)", em_manutencao: "var(--warn)", com_defeito: "var(--bad)",
};
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const nomeMes = (s: SerieMes) => `${MESES_LONGOS[Number(s.mes.slice(5)) - 1]} de ${s.ano}`;
const soma = (serie: SerieMes[], chave: keyof SerieMes) => serie.reduce((t, s) => t + Number(s[chave]), 0);

function Barras({ itens, link }: { itens: { id: number | string; nome: string; total: number; extra?: string }[]; link: (id: number | string) => string }) {
  const max = Math.max(1, ...itens.map((i) => i.total));
  if (!itens.length) return <p className="muted">Nada cadastrado ainda.</p>;
  return (
    <div className="barras">
      {itens.map((i, n) => (
        <Link key={i.id} to={link(i.id)} className="barra" title={[i.nome, i.extra].filter(Boolean).join(" · ")}>
          <span className="nome">{i.nome}</span>
          <span className="trilho">
            <span className="preenche" style={{ width: `${(i.total / max) * 100}%`, animationDelay: `${n * 50}ms` }} />
          </span>
          <b>{i.total}</b>
        </Link>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<D>("/dashboard") });
  const [meses, setMeses] = useState(12);
  const [statusAtivo, setStatusAtivo] = useState<string | null>(null);
  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;

  const serie = data.serie_mensal.slice(-meses);
  const atual = data.serie_mensal[data.serie_mensal.length - 1];
  const anterior = data.serie_mensal[data.serie_mensal.length - 2];
  const defeitoAgora = data.por_status.com_defeito ?? 0;
  const manutencao = data.por_status.em_manutencao ?? 0;
  const emUso = data.por_status.em_uso ?? 0;
  const fatias: Fatia[] = (["em_uso", "em_estoque", "em_manutencao", "com_defeito"] as Status[]).map((s) => ({
    chave: s, rotulo: STATUS_ROTULO[s], valor: data.por_status[s] ?? 0, cor: COR_STATUS[s],
  }));
  const fatiaAtiva = fatias.find((f) => f.chave === statusAtivo);
  const variacao = atual && anterior ? atual.ativos - anterior.ativos : 0;

  return (
    <>
      <div className="topo">
        <div>
          <h1>Painel</h1>
          <p className="sub">Situação do patrimônio em {atual ? nomeMes(atual) : "—"}</p>
        </div>
        <div className="acoes">
          <Link className="btn" to="/importar">Importar arquivo</Link>
          <Link className="btn primario" to="/objetos/novo">Novo objeto</Link>
        </div>
      </div>

      {data.itens_pendentes_revisao > 0 && (
        <div className="aviso info surge">
          {data.itens_pendentes_revisao} item(ns) importado(s) aguardando revisão. <Link to="/importar">Revisar agora</Link>
        </div>
      )}

      <div className="indicadores">
        <Link className="indicador surge" to="/objetos">
          <span className="titulo">Objetos ativos</span>
          <span className="valor"><NumeroAnimado valor={data.total} /></span>
          <span className="sub">{variacao >= 0 ? "+" : ""}{variacao} desde o mês passado · {emUso} em uso</span>
          <span className="spark"><Minigrafico valores={data.serie_mensal.map((s) => s.ativos)} rotulo="Objetos ativos nos últimos 12 meses" /></span>
        </Link>
        <Link className="indicador surge" style={{ animationDelay: "60ms" }} to="/objetos?ordenar=atualizado_em">
          <span className="titulo">Transferências</span>
          <span className="valor"><NumeroAnimado valor={soma(data.serie_mensal, "transferencias")} /></span>
          <span className="sub">nos últimos 12 meses · {atual?.transferencias ?? 0} neste mês</span>
          <span className="spark"><Minigrafico valores={data.serie_mensal.map((s) => s.transferencias)} rotulo="Transferências por mês" /></span>
        </Link>
        <Link className="indicador surge" style={{ animationDelay: "120ms" }} to="/objetos?status=com_defeito">
          <span className="titulo">Com defeito</span>
          <span className="valor"><NumeroAnimado valor={defeitoAgora} /></span>
          <span className="sub">{manutencao} em manutenção · {soma(data.serie_mensal, "defeitos")} defeitos em 12 meses</span>
          <span className="spark"><Minigrafico valores={data.serie_mensal.map((s) => s.defeitos)} rotulo="Defeitos registrados por mês" /></span>
        </Link>
        <Link className="indicador surge" style={{ animationDelay: "180ms" }} to="/arquivados">
          <span className="titulo">Arquivados</span>
          <span className="valor"><NumeroAnimado valor={data.arquivados} /></span>
          <span className="sub">sem conserto · {soma(data.serie_mensal, "arquivados")} nos últimos 12 meses</span>
          <span className="spark"><Minigrafico valores={data.serie_mensal.map((s) => s.arquivados)} rotulo="Arquivamentos por mês" /></span>
        </Link>
      </div>

      <div className="painel-grid">
        <section className="card surge" style={{ animationDelay: "120ms" }}>
          <header>
            <div>
              <h2>Movimentação mensal</h2>
              <p>Objetos cadastrados e transferidos por mês</p>
            </div>
            <div className="acoes" style={{ alignItems: "flex-start", gap: 18 }}>
              <div className="periodo" role="group" aria-label="Período">
                {[6, 12].map((n) => (
                  <button key={n} className={meses === n ? "ativo" : ""} aria-pressed={meses === n} onClick={() => setMeses(n)}>{n} meses</button>
                ))}
              </div>
              <div className="destaque-num">
                <b><NumeroAnimado valor={soma(serie, "cadastros")} /></b>
                <span>cadastros no período</span>
              </div>
            </div>
          </header>
          <div className="legenda">
            <span><i style={{ background: "var(--serie-1)" }} />Cadastros</span>
            <span><i style={{ background: "var(--serie-2)" }} />Transferências</span>
          </div>
          <GraficoMensal key={meses} dados={serie} rotuloX={(s) => s.rotulo} rotuloDica={nomeMes}
            series={[
              { chave: "cadastros", rotulo: "Cadastros", cor: "var(--serie-1)" },
              { chave: "transferencias", rotulo: "Transferências", cor: "var(--serie-2)" },
            ]} />
        </section>

        <section className="card surge" style={{ animationDelay: "180ms" }}>
          <header><div><h2>Situação</h2><p>Objetos ativos por status</p></div></header>
          <div className="rosca">
            <Rosca fatias={fatias} ativo={statusAtivo} aoPassar={setStatusAtivo}
              centro={(fatiaAtiva?.valor ?? data.total).toLocaleString("pt-BR")}
              sub={fatiaAtiva ? fatiaAtiva.rotulo.toLowerCase() : "objetos"} />
            <div className="itens">
              {fatias.map((f) => (
                <Link key={f.chave} to={`/objetos?status=${f.chave}`} className={"item-rosca" + (statusAtivo === f.chave ? " ativo" : "")}
                  onPointerEnter={() => setStatusAtivo(f.chave)} onPointerLeave={() => setStatusAtivo(null)}
                  onFocus={() => setStatusAtivo(f.chave)} onBlur={() => setStatusAtivo(null)}>
                  <i style={{ background: f.cor }} />
                  <span>{f.rotulo}</span>
                  <b>{f.valor}</b>
                </Link>
              ))}
            </div>
          </div>
          <p className="muted" style={{ fontSize: "0.86rem" }}>
            {data.total ? `${Math.round((emUso / data.total) * 100)}% em uso` : "Sem objetos"} · {data.sem_pessoa} sem pessoa responsável
          </p>
        </section>
      </div>

      <div className="grid g2">
        <section className="card surge" style={{ animationDelay: "240ms" }}>
          <header><div><h2>Por categoria</h2><p>Objetos ativos</p></div><Link to="/categorias" className="muted">Categorias</Link></header>
          <Barras link={(id) => `/objetos?categoria_id=${id}`} itens={data.por_categoria.map((c) => ({ id: c.id, nome: c.nome, total: c.total }))} />
        </section>
        <section className="card surge" style={{ animationDelay: "300ms" }}>
          <header><div><h2>Por unidade</h2><p>As 15 com mais objetos</p></div><Link to="/unidades" className="muted">Unidades</Link></header>
          <Barras link={(id) => `/objetos?unidade_id=${id}`}
            itens={data.por_unidade.map((u) => ({ id: u.id, nome: u.nome, total: u.total, extra: u.com_defeito ? `${u.com_defeito} com defeito` : undefined }))} />
        </section>
      </div>

      <section className="card surge" style={{ animationDelay: "360ms" }}>
        <header><div><h2>Últimas movimentações</h2><p>Cadastros, transferências e mudanças de status</p></div></header>
        {data.ultimas_movimentacoes.length === 0 ? <p className="muted">Nenhuma movimentação ainda.</p> : (
          <div className="linha-tempo">
            {data.ultimas_movimentacoes.map((m) => (
              <div className="evento" key={m.id}>
                <time>{formatarData(m.data)}</time>
                <div>
                  <Link to={`/objetos/${m.ativo?.id}`}><b>{m.ativo?.nome || `Objeto #${m.ativo?.id}`}</b></Link>
                  <span className="muted"> · {m.ativo?.categoria}{m.ativo?.patrimonio ? ` · Pat. ${m.ativo.patrimonio}` : ""}</span>
                  <div className="muted">{descreverMovimentacao(m)}{m.observacao && m.tipo !== "cadastro" ? ` · ${m.observacao}` : ""}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
