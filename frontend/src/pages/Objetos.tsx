import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, AtivoLista, formatarData, formatarValor, qs, STATUS_EDITAVEIS, STATUS_ROTULO } from "../api";
import { Carregando, ErroBox, StatusPill, useCategorias, usePessoas, useUnidades } from "../components/ui";

const POR_PAGINA = 50;

export default function Objetos({ arquivados = false }: { arquivados?: boolean }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const categorias = useCategorias();
  const unidades = useUnidades();
  const pessoas = usePessoas();
  const [busca, setBusca] = useState(params.get("q") ?? "");

  const filtros = Object.fromEntries(params.entries());
  const categoriaId = params.get("categoria_id") ? Number(params.get("categoria_id")) : null;
  const categoria = categorias.data?.find((c) => c.id === categoriaId);
  const unidade = unidades.data?.find((u) => u.id === Number(params.get("unidade_id")));
  const pagina = Number(params.get("pagina") ?? 1);
  const ordenar = params.get("ordenar") ?? (arquivados ? "arquivado_em" : "atualizado_em");
  const direcao = params.get("direcao") ?? "desc";

  const consulta = qs({ ...filtros, arquivados, por_pagina: POR_PAGINA, ordenar, direcao });
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["ativos", consulta],
    queryFn: () => api.get<AtivoLista>(`/ativos${consulta}`),
    placeholderData: keepPreviousData,
  });

  // busca com atraso para não consultar a cada tecla
  useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("q") ?? "") !== busca) definir({ q: busca });
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busca]);

  function definir(novos: Record<string, string | number | null>) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(novos)) {
      if (v === null || v === "") p.delete(k);
      else p.set(k, String(v));
    }
    if (!("pagina" in novos)) p.delete("pagina");
    setParams(p, { replace: true });
  }

  function trocarCategoria(id: string) {
    const p = new URLSearchParams(params);
    [...p.keys()].filter((k) => k.startsWith("campo_")).forEach((k) => p.delete(k));
    if (id) p.set("categoria_id", id); else p.delete("categoria_id");
    p.delete("pagina");
    setParams(p, { replace: true });
  }

  function ordenarPor(col: string) {
    definir({ ordenar: col, direcao: ordenar === col && direcao === "asc" ? "desc" : "asc" });
  }

  const colunasCampos = useMemo(
    () => (categoria ? categoria.campos.filter((c) => c.ativo).slice(0, 5) : []),
    [categoria],
  );
  const temFiltro = [...params.keys()].some((k) => !["ordenar", "direcao", "pagina"].includes(k));
  const totalPaginas = data ? Math.max(1, Math.ceil(data.total / POR_PAGINA)) : 1;
  const Seta = ({ col }: { col: string }) => (ordenar === col ? <span aria-hidden>{direcao === "asc" ? " ↑" : " ↓"}</span> : null);

  return (
    <>
      <div className="topo">
        <div>
          <h1>{arquivados ? "Arquivados" : "Objetos"}</h1>
          <p className="sub">
            {arquivados ? "Objetos dados como sem conserto. Continuam consultáveis e podem ser restaurados." : "Busque, filtre e abra a ficha de cada objeto"}
          </p>
        </div>
        <div className="acoes">
          <a className="btn" href={`/api/ativos/relatorio.pdf${qs({ ...filtros, arquivados, pagina: null, ordenar: null, direcao: null })}`}>Exportar PDF</a>
          {!arquivados && <Link className="btn primario" to="/objetos/novo">Novo objeto</Link>}
        </div>
      </div>

      <section className="card">
        <div className="filtros">
          <label className="campo busca" htmlFor="f-busca">
            <span>Buscar</span>
            <input id="f-busca" placeholder="Patrimônio, nome, IP, serial, hostname…" value={busca} onChange={(e) => setBusca(e.target.value)} />
          </label>
          <label className="campo" htmlFor="f-cat">
            <span>Categoria</span>
            <select id="f-cat" value={categoriaId ?? ""} onChange={(e) => trocarCategoria(e.target.value)}>
              <option value="">Todas</option>
              {categorias.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </label>
          {!arquivados && (
            <label className="campo" htmlFor="f-status">
              <span>Status</span>
              <select id="f-status" value={params.get("status") ?? ""} onChange={(e) => definir({ status: e.target.value })}>
                <option value="">Todos</option>
                {STATUS_EDITAVEIS.map((s) => <option key={s} value={s}>{STATUS_ROTULO[s]}</option>)}
              </select>
            </label>
          )}
          <label className="campo" htmlFor="f-unidade">
            <span>Unidade</span>
            <select id="f-unidade" value={params.get("unidade_id") ?? ""} onChange={(e) => definir({ unidade_id: e.target.value, setor_id: null })}>
              <option value="">Todas</option>
              {unidades.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>
          </label>
          <label className="campo" htmlFor="f-setor">
            <span>Setor</span>
            <select id="f-setor" value={params.get("setor_id") ?? ""} disabled={!unidade} onChange={(e) => definir({ setor_id: e.target.value })}>
              <option value="">{unidade ? "Todos" : "Escolha a unidade"}</option>
              {unidade?.setores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          </label>
          <label className="campo" htmlFor="f-pessoa">
            <span>Pessoa</span>
            <select id="f-pessoa" value={params.get("pessoa_id") ?? ""} onChange={(e) => definir({ pessoa_id: e.target.value })}>
              <option value="">Todas</option>
              {pessoas.data?.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </select>
          </label>
          {categoria?.campos.filter((c) => c.filtravel && c.ativo).map((c) => (
            <label className="campo" key={c.id} htmlFor={`f-${c.chave}`}>
              <span>{c.rotulo}</span>
              {c.tipo === "lista" ? (
                <select id={`f-${c.chave}`} value={params.get(`campo_${c.chave}`) ?? ""} onChange={(e) => definir({ [`campo_${c.chave}`]: e.target.value })}>
                  <option value="">Todos</option>
                  {c.opcoes.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input id={`f-${c.chave}`} defaultValue={params.get(`campo_${c.chave}`) ?? ""}
                  onBlur={(e) => definir({ [`campo_${c.chave}`]: e.target.value })}
                  onKeyDown={(e) => e.key === "Enter" && definir({ [`campo_${c.chave}`]: (e.target as HTMLInputElement).value })} />
              )}
            </label>
          ))}
          {temFiltro && <button className="link" onClick={() => { setBusca(""); setParams(new URLSearchParams(), { replace: true }); }}>Limpar filtros</button>}
        </div>
      </section>

      <ErroBox erro={error} />
      {isLoading ? <Carregando /> : data && (
        <>
          <p className="muted num">{data.total} objeto(s){isFetching ? " · atualizando…" : ""}</p>
          {data.itens.length === 0 ? (
            <div className="card vazio">
              <p>{temFiltro ? "Nenhum objeto com esses filtros." : arquivados ? "Nenhum objeto arquivado." : "Nenhum objeto cadastrado ainda."}</p>
              {!temFiltro && !arquivados && <div className="acoes"><Link className="btn" to="/importar">Importar um arquivo</Link><Link className="btn primario" to="/objetos/novo">Cadastrar o primeiro</Link></div>}
            </div>
          ) : (
            <div className="tabela-wrap">
              <table>
                <thead>
                  <tr>
                    <th><button className="ordem" onClick={() => ordenarPor("patrimonio")}>Patrimônio<Seta col="patrimonio" /></button></th>
                    <th><button className="ordem" onClick={() => ordenarPor("nome")}>Nome<Seta col="nome" /></button></th>
                    {!categoria && <th>Categoria</th>}
                    {colunasCampos.map((c) => <th key={c.id}>{c.rotulo}</th>)}
                    <th><button className="ordem" onClick={() => ordenarPor("status")}>Status<Seta col="status" /></button></th>
                    <th>Unidade › Setor</th>
                    <th>Pessoa</th>
                    <th>
                      {arquivados
                        ? <button className="ordem" onClick={() => ordenarPor("arquivado_em")}>Arquivado em<Seta col="arquivado_em" /></button>
                        : <button className="ordem" onClick={() => ordenarPor("atualizado_em")}>Atualizado<Seta col="atualizado_em" /></button>}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.itens.map((a) => (
                    <tr key={a.id} className="clicavel" onClick={() => navigate(`/objetos/${a.id}`)}>
                      <td className="pat">{a.patrimonio ?? <span className="muted">—</span>}</td>
                      <td><Link to={`/objetos/${a.id}`} onClick={(e) => e.stopPropagation()}>{a.nome || `Objeto #${a.id}`}</Link></td>
                      {!categoria && <td>{a.categoria.nome}</td>}
                      {colunasCampos.map((c) => <td key={c.id} className={["ip", "mac"].includes(c.tipo) ? "mono" : undefined}>{formatarValor(a.valores[c.chave], c.tipo)}</td>)}
                      <td><StatusPill status={a.status} /></td>
                      <td>{a.unidade.nome}{a.setor && <span className="muted"> › {a.setor.nome}</span>}</td>
                      <td>{a.pessoa?.nome ?? <span className="muted">—</span>}</td>
                      <td className="muted num">{formatarData(arquivados ? a.arquivado_em : a.atualizado_em, false)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {totalPaginas > 1 && (
            <div className="paginacao">
              <button disabled={pagina <= 1} onClick={() => definir({ pagina: pagina - 1 })}>Anterior</button>
              <span className="num">Página {pagina} de {totalPaginas}</span>
              <button disabled={pagina >= totalPaginas} onClick={() => definir({ pagina: pagina + 1 })}>Próxima</button>
            </div>
          )}
        </>
      )}
    </>
  );
}
