// Gráficos em SVG puro: minigráfico, linhas mensais com dica, rosca e número animado.
import { useEffect, useLayoutEffect, useRef, useState } from "react";

const semMovimento = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function useLargura<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [largura, setLargura] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setLargura(el.getBoundingClientRect().width);
    const ro = new ResizeObserver(([e]) => setLargura(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, largura] as const;
}

/** Curva monotônica (não passa abaixo de zero nem cria picos falsos). */
function curva(pts: [number, number][]): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M${pts[0][0]},${pts[0][1]}`;
  const n = pts.length;
  const dx: number[] = [], m: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(pts[i + 1][0] - pts[i][0]);
    m.push((pts[i + 1][1] - pts[i][1]) / dx[i]);
  }
  const t = [m[0]];
  for (let i = 1; i < n - 1; i++) t.push(m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2);
  t.push(m[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
    if (s > 9) { const k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], h = dx[i] / 3;
    d += ` C${x0 + h},${y0 + t[i] * h} ${x1 - h},${y1 - t[i + 1] * h} ${x1},${y1}`;
  }
  return d;
}

function teto(max: number): { topo: number; passos: number[] } {
  if (max <= 0) return { topo: 4, passos: [0, 1, 2, 3, 4] };
  const bruto = max / 4;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((p) => p >= bruto) ?? 10 * mag;
  const passoInt = Math.max(1, Math.ceil(passo));
  const topo = passoInt * Math.ceil(max / passoInt);
  const passos: number[] = [];
  for (let v = 0; v <= topo; v += passoInt) passos.push(v);
  return { topo, passos };
}

export function NumeroAnimado({ valor, duracao = 800 }: { valor: number; duracao?: number }) {
  const [mostrado, setMostrado] = useState(semMovimento() ? valor : 0);
  const anterior = useRef(0);
  useEffect(() => {
    if (semMovimento()) { setMostrado(valor); return; }
    const inicio = performance.now(), de = anterior.current;
    let raf = 0;
    const passo = (agora: number) => {
      const p = Math.min(1, (agora - inicio) / duracao);
      const e = 1 - (1 - p) ** 3;
      setMostrado(Math.round(de + (valor - de) * e));
      if (p < 1) raf = requestAnimationFrame(passo);
      else anterior.current = valor;
    };
    raf = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(raf);
  }, [valor, duracao]);
  return <>{mostrado.toLocaleString("pt-BR")}</>;
}

/** Minigráfico para os indicadores. Desenha na cor do texto (branco no cartão azul). */
export function Minigrafico({ valores, rotulo, altura = 46 }: { valores: number[]; rotulo: string; altura?: number }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  if (valores.length < 2) return null;
  const max = Math.max(...valores), min = Math.min(...valores);
  const amp = max - min || 1;
  const w = largura || 1;
  const pts: [number, number][] = valores.map((v, i) => [(i / (valores.length - 1)) * w, altura - 6 - ((v - min) / amp) * (altura - 14)]);
  const linha = curva(pts);
  return (
    <div ref={ref} style={{ width: "100%", height: altura }}>
      {largura > 0 && (
        <svg width={w} height={altura} role="img" aria-label={rotulo}>
          <path d={`${linha} L${w},${altura} L0,${altura} Z`} fill="currentColor" opacity="0.14" />
          <path d={linha} fill="none" stroke="currentColor" strokeOpacity="0.9" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" pathLength={1} className="tracar" />
        </svg>
      )}
    </div>
  );
}

export interface Serie { chave: string; rotulo: string; cor: string }

/** Linhas mensais com área leve, grade discreta, cursor e dica ao passar o mouse. */
export function GraficoMensal<T extends Record<string, number | string>>({
  dados, series, rotuloX, altura = 270, rotuloDica,
}: {
  dados: T[]; series: Serie[]; rotuloX: (d: T) => string; altura?: number; rotuloDica?: (d: T) => string;
}) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [ativo, setAtivo] = useState<number | null>(null);
  const m = { e: 36, d: 14, t: 14, b: 30 };
  const w = Math.max(0, largura - m.e - m.d);
  const h = altura - m.t - m.b;
  const max = Math.max(0, ...dados.flatMap((d) => series.map((s) => Number(d[s.chave]) || 0)));
  const { topo, passos } = teto(max);
  const x = (i: number) => m.e + (dados.length > 1 ? (i / (dados.length - 1)) * w : w / 2);
  const y = (v: number) => m.t + h - (v / topo) * h;
  const passoX = dados.length > 1 ? w / (dados.length - 1) : w;
  const mostrarCada = passoX < 34 ? 2 : 1;

  function mover(e: React.PointerEvent<SVGRectElement>) {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left) / r.width) * (dados.length - 1));
    setAtivo(Math.max(0, Math.min(dados.length - 1, i)));
  }

  const d = ativo !== null ? dados[ativo] : null;
  const yDica = d ? Math.min(...series.map((s) => y(Number(d[s.chave]) || 0))) : 0;

  return (
    <div className="grafico" ref={ref}>
      {largura > 0 && (
        <svg height={altura} role="img" aria-label={`Gráfico mensal: ${series.map((s) => s.rotulo).join(" e ")}`}>
          {passos.map((v) => (
            <g key={v}>
              <line x1={m.e} x2={m.e + w} y1={y(v)} y2={y(v)} stroke="var(--grid)" strokeWidth="1" />
              <text x={m.e - 10} y={y(v)} dy="0.35em" textAnchor="end">{v}</text>
            </g>
          ))}
          {dados.map((dd, i) => ((i % mostrarCada === 0 && !(mostrarCada > 1 && i === dados.length - 2)) || i === dados.length - 1) && (
            <text key={i} x={x(i)} y={altura - 8} textAnchor="middle" style={ativo === i ? { fill: "var(--fg)", fontWeight: 600 } : undefined}>
              {rotuloX(dd)}
            </text>
          ))}
          {series.map((s) => {
            const pts: [number, number][] = dados.map((dd, i) => [x(i), y(Number(dd[s.chave]) || 0)]);
            const linha = curva(pts);
            return (
              <g key={s.chave}>
                <path d={`${linha} L${x(dados.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={s.cor} opacity="0.1" />
                <path d={linha} fill="none" stroke={s.cor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  pathLength={1} className="tracar" />
              </g>
            );
          })}
          {d && ativo !== null && (
            <g pointerEvents="none">
              <line x1={x(ativo)} x2={x(ativo)} y1={m.t} y2={m.t + h} stroke="var(--muted)" strokeOpacity="0.5" strokeWidth="1" />
              {series.map((s) => (
                <circle key={s.chave} cx={x(ativo)} cy={y(Number(d[s.chave]) || 0)} r="5" fill={s.cor} stroke="var(--surface)" strokeWidth="2" />
              ))}
            </g>
          )}
          <rect x={m.e} y={m.t} width={w} height={h} fill="transparent" onPointerMove={mover} onPointerDown={mover}
            onPointerLeave={() => setAtivo(null)} style={{ cursor: "crosshair" }} />
        </svg>
      )}
      {d && ativo !== null && (
        <div className="dica-grafico" style={{ left: Math.min(Math.max(x(ativo), 90), largura - 90), top: yDica }}>
          <b>{rotuloDica ? rotuloDica(d) : rotuloX(d)}</b>
          {series.map((s) => (
            <div key={s.chave}><i style={{ background: s.cor }} />{s.rotulo}: {Number(d[s.chave]) || 0}</div>
          ))}
        </div>
      )}
      <table className="sr-only">
        <caption>Valores por mês</caption>
        <thead><tr><th>Mês</th>{series.map((s) => <th key={s.chave}>{s.rotulo}</th>)}</tr></thead>
        <tbody>{dados.map((dd, i) => <tr key={i}><td>{rotuloDica ? rotuloDica(dd) : rotuloX(dd)}</td>{series.map((s) => <td key={s.chave}>{dd[s.chave]}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export interface Fatia { chave: string; rotulo: string; valor: number; cor: string }

/** Rosca com 2px de respiro entre as fatias e preenchimento animado. */
export function Rosca({ fatias, centro, sub, ativo, aoPassar }: {
  fatias: Fatia[]; centro: string; sub: string; ativo?: string | null; aoPassar?: (chave: string | null) => void;
}) {
  const [pronto, setPronto] = useState(semMovimento());
  useEffect(() => { const t = requestAnimationFrame(() => setPronto(true)); return () => cancelAnimationFrame(t); }, []);
  const total = fatias.reduce((s, f) => s + f.valor, 0);
  const r = 66, c = 2 * Math.PI * r, folga = total > 0 && fatias.filter((f) => f.valor > 0).length > 1 ? 3 : 0;
  let acumulado = 0;
  return (
    <svg viewBox="0 0 170 170" width="170" height="170" role="img" aria-label={`${centro} ${sub}`}>
      <circle cx="85" cy="85" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="20" />
      {total > 0 && fatias.map((f) => {
        if (f.valor <= 0) return null;
        const comp = (f.valor / total) * c;
        const inicio = acumulado;
        acumulado += comp;
        const visivel = Math.max(0.5, comp - folga);
        const realce = ativo == null || ativo === f.chave;
        return (
          <circle key={f.chave} cx="85" cy="85" r={r} fill="none" stroke={f.cor} strokeWidth={ativo === f.chave ? 24 : 20}
            strokeDasharray={`${pronto ? visivel : 0} ${c}`} strokeDashoffset={-inicio}
            transform="rotate(-90 85 85)" opacity={realce ? 1 : 0.35}
            style={{ transition: "stroke-dasharray 0.9s cubic-bezier(.2,.8,.2,1), opacity 0.2s, stroke-width 0.2s", cursor: "pointer" }}
            onPointerEnter={() => aoPassar?.(f.chave)} onPointerLeave={() => aoPassar?.(null)}>
            <title>{`${f.rotulo}: ${f.valor}`}</title>
          </circle>
        );
      })}
      <text x="85" y="82" textAnchor="middle" style={{ fill: "var(--fg)", fontSize: 30, fontWeight: 600 }}>{centro}</text>
      <text x="85" y="104" textAnchor="middle" style={{ fill: "var(--muted)", fontSize: 12.5 }}>{sub}</text>
    </svg>
  );
}
