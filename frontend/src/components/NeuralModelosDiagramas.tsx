"use client";

// Diagramas interactivos de las arquitecturas reales de DAI Neural (SVG; sin dependencias nuevas).
// Los tamaños vienen del código de los modelos y de la configuración registrada en los benchmarks (tabla de
// arquitectura). Las alturas de las barras de vectores son ilustrativas: no son datos de personas ni de cursos.
import { useEffect, useId, useMemo, useState, type ReactNode } from "react";

import type { MallaEjemplo } from "../lib/neural";
import { PALETA } from "../lib/paleta";
import { BOTON } from "./NeuralUI";

const FUENTE = { fontFamily: "inherit" } as const;

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
function useMovimientoReducido(): boolean {
  const [reducido, setReducido] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducido(mq.matches);
    const al = (e: MediaQueryListEvent) => setReducido(e.matches);
    mq.addEventListener("change", al);
    return () => mq.removeEventListener("change", al);
  }, []);
  return reducido;
}

/** Paso a paso con reproducción automática (desactivada si la persona pidió menos movimiento). */
function usePasos(total: number, intervaloMs = 1700) {
  const [paso, setPaso] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(false);
  const reducido = useMovimientoReducido();
  useEffect(() => {
    if (!reproduciendo) return;
    const t = window.setInterval(() => {
      setPaso((p) => {
        if (p >= total - 1) {
          setReproduciendo(false);
          return p;
        }
        return p + 1;
      });
    }, intervaloMs);
    return () => window.clearInterval(t);
  }, [reproduciendo, total, intervaloMs]);
  const alternar = () => {
    if (reproduciendo) return setReproduciendo(false);
    if (paso >= total - 1) setPaso(0);
    setReproduciendo(true);
  };
  return { paso, setPaso: (p: number) => { setReproduciendo(false); setPaso(Math.max(0, Math.min(total - 1, p))); }, reproduciendo, alternar, reducido };
}

function Controles({
  paso, total, onPaso, reproduciendo, onAlternar, titulos,
}: {
  paso: number; total: number; onPaso: (p: number) => void; reproduciendo: boolean; onAlternar: () => void; titulos: readonly string[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className={BOTON} onClick={() => onPaso(paso - 1)} disabled={paso === 0}>Anterior</button>
      <button type="button" className={BOTON} onClick={() => onPaso(paso + 1)} disabled={paso >= total - 1}>Siguiente</button>
      <button type="button" className={BOTON} onClick={onAlternar} aria-pressed={reproduciendo}>
        {reproduciendo ? "Pausar" : paso >= total - 1 ? "Repetir" : "Reproducir"}
      </button>
      <span className="text-sm text-[var(--portal-muted)]" aria-live="polite">
        Paso {paso + 1} de {total}: <strong className="text-[var(--portal-fg)]">{titulos[paso]}</strong>
      </span>
    </div>
  );
}

function Marco({ children, minAncho, etiqueta }: { children: ReactNode; minAncho: number; etiqueta: string }) {
  return (
    <div className="overflow-x-auto rounded-md border border-[var(--boveda-linea)] bg-black/10" role="region" aria-label={etiqueta} tabIndex={0}>
      <div style={{ minWidth: minAncho }}>{children}</div>
    </div>
  );
}

function Defs({ id }: { id: string }) {
  return (
    <defs>
      <marker id={`${id}-fl`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill={PALETA.subtle} />
      </marker>
      <marker id={`${id}-fa`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill={PALETA.azulClaro} />
      </marker>
      <marker id={`${id}-fs`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill={PALETA.serie3} />
      </marker>
    </defs>
  );
}

/** Altura pseudoaleatoria estable (0..1) a partir de un texto: solo para dibujar vectores ilustrativos. */
function altura(semilla: string, i: number): number {
  let h = 2166136261;
  const s = `${semilla}:${i}`;
  for (let j = 0; j < s.length; j++) h = Math.imul(h ^ s.charCodeAt(j), 16777619);
  return 0.2 + ((h >>> 0) % 1000) / 1250;
}

function Vector({ x, y, n, semilla, color, ancho = 6, alto = 26, max = 16 }: { x: number; y: number; n: number; semilla: string; color: string; ancho?: number; alto?: number; max?: number }) {
  const visibles = Math.min(n, max);
  return (
    <g aria-hidden="true">
      {Array.from({ length: visibles }, (_, i) => (
        <rect key={i} x={x + i * (ancho + 2)} y={y + alto - alto * altura(semilla, i)} width={ancho} height={alto * altura(semilla, i)} rx={1} fill={color} opacity={0.85} />
      ))}
      {n > max ? <text x={x + visibles * (ancho + 2) + 2} y={y + alto - 2} fontSize={10} fill={PALETA.subtle} style={FUENTE}>…</text> : null}
    </g>
  );
}

function Caja({
  x, y, w, h, titulo, sub, activo = false, color = PALETA.azul, children,
}: {
  x: number; y: number; w: number; h: number; titulo: string; sub?: string; activo?: boolean; color?: string; children?: ReactNode;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={6} fill={activo ? "rgba(117,156,192,0.18)" : "rgba(255,255,255,0.03)"}
        stroke={activo ? color : "rgba(237,237,239,0.22)"} strokeWidth={activo ? 2 : 1} style={{ transition: "all .25s" }} />
      <text x={x + w / 2} y={y + (sub ? h / 2 - 3 : h / 2 + 4)} textAnchor="middle" fontSize={12} fontWeight={600} fill={PALETA.fg} style={FUENTE}>{titulo}</text>
      {sub ? <text x={x + w / 2} y={y + h / 2 + 12} textAnchor="middle" fontSize={10.5} fill={PALETA.muted} style={FUENTE}>{sub}</text> : null}
      {children}
    </g>
  );
}

function Flecha({ d, id, tipo = "fl", activa = false, animada = false, color }: { d: string; id: string; tipo?: "fl" | "fa" | "fs"; activa?: boolean; animada?: boolean; color?: string }) {
  return (
    <path d={d} fill="none" stroke={color ?? (activa ? (tipo === "fs" ? PALETA.serie3 : PALETA.azulClaro) : "rgba(237,237,239,0.35)")}
      strokeWidth={activa ? 2.2 : 1.4} markerEnd={`url(#${id}-${activa ? tipo : "fl"})`}
      strokeDasharray={animada ? "6 5" : undefined} style={animada ? { animation: "neural-flujo 1s linear infinite" } : { transition: "stroke .25s" }} />
  );
}

/** Define la animación de flujo una sola vez por diagrama (se apaga con prefers-reduced-motion). */
function EstiloAnimacion() {
  return (
    <style>{`@keyframes neural-flujo { to { stroke-dashoffset: -22; } } @media (prefers-reduced-motion: reduce) { [style*="neural-flujo"] { animation: none !important; } }`}</style>
  );
}

function PanelPaso({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)] px-4 py-3 text-sm leading-6 text-[var(--portal-fg)]" aria-live="polite">{children}</div>;
}

// ---------------------------------------------------------------------------
// GRU desenrollada sobre los semestres (T1 y T3)
// ---------------------------------------------------------------------------
export interface ParamsGRU {
  tarea: "t1" | "t3";
  k: number;
  dSeq: number;
  hidden: number;
  /** Capa estática: tamaño de salida de la rama del perfil de ingreso. */
  estatica: number;
  cabeza: number;
  variables: readonly string[];
}

export function DiagramaGRU({ p }: { p: ParamsGRU }) {
  const id = useId().replace(/:/g, "");
  const k = p.k;
  const total = k + 2;
  const { paso, setPaso, reproduciendo, alternar } = usePasos(total);
  const dx = k <= 2 ? 150 : 118;
  const x0 = 120;
  const xs = Array.from({ length: k }, (_, i) => x0 + i * dx);
  const concatX = Math.max(xs[k - 1] + 110, 560);
  const concat = p.hidden + p.estatica;
  const esT3 = p.tarea === "t3";
  const W = concatX + 330;
  const titulos = [...xs.map((_, i) => `Semestre ${i + 1}`), "Unir con el perfil de ingreso", esT3 ? "Riesgos por semestre" : "Probabilidad"];
  const enSem = (i: number) => paso === i;
  const pasado = (i: number) => paso >= i;
  const headX = concatX + 70;

  return (
    <div className="space-y-3">
      <Marco minAncho={W} etiqueta="Diagrama de la red GRU desenrollada sobre los semestres">
        <svg viewBox={`0 190 ${W} 280`} width="100%" role="img" aria-label={`GRU sobre ${k} semestres con vector de ${p.dSeq} variables y memoria de ${p.hidden} números`}>
          <Defs id={id} /><EstiloAnimacion />
          <text x={x0 - 80} y={206} fontSize={11} fill={PALETA.subtle} style={FUENTE}>Tiempo →</text>
          {/* memoria inicial */}
          <Caja x={x0 - 98} y={232} w={52} h={32} titulo="h₀" sub="ceros" />
          <Flecha d={`M${x0 - 46} 248 L${xs[0] - 42} 248`} id={id} activa={pasado(0)} />
          {xs.map((x, i) => (
            <g key={i}>
              {/* entrada */}
              <Caja x={x - 50} y={346} w={100} h={62} titulo={`x${i + 1}`} sub={`${p.dSeq} variables`} activo={enSem(i)}>
                <Vector x={x - 45} y={384} n={p.dSeq} semilla={`x${i}`} color={PALETA.azulClaro} ancho={4} alto={18} max={13} />
              </Caja>
              <text x={x} y={430} textAnchor="middle" fontSize={11} fill={PALETA.muted} style={FUENTE}>Semestre {i + 1}</text>
              <Flecha d={`M${x} 346 L${x} 278`} id={id} activa={enSem(i)} animada={enSem(i)} />
              {/* celda GRU */}
              <Caja x={x - 42} y={218} w={84} h={60} titulo="GRU" sub={`${p.hidden} unidades`} activo={enSem(i)} />
              {/* memoria que pasa al siguiente semestre */}
              {i < k - 1 ? (
                <>
                  <Flecha d={`M${x + 42} 248 L${xs[i + 1] - 42} 248`} id={id} activa={pasado(i + 1) || enSem(i)} animada={enSem(i)} />
                  <text x={(x + xs[i + 1]) / 2} y={238} textAnchor="middle" fontSize={11} fill={PALETA.muted} style={FUENTE}>h{i + 1}</text>
                </>
              ) : (
                <>
                  <Flecha d={`M${x + 42} 248 L${concatX - 4} 248`} id={id} activa={pasado(k)} animada={paso === k} />
                  <text x={(x + concatX) / 2} y={238} textAnchor="middle" fontSize={11} fill={PALETA.muted} style={FUENTE}>h{k} ({p.hidden})</text>
                </>
              )}
            </g>
          ))}
          {/* rama estática */}
          <Caja x={concatX} y={312} w={140} h={64} titulo="Perfil de ingreso" sub={`capa → ${p.estatica}`} activo={paso === k} color={PALETA.serie3}>
            <Vector x={concatX + 12} y={346} n={p.estatica} semilla="static" color={PALETA.serie3} ancho={3} alto={14} max={24} />
          </Caja>
          <text x={concatX + 70} y={396} textAnchor="middle" fontSize={11} fill={PALETA.muted} style={FUENTE}>solo datos previos al ingreso</text>
          <Flecha d={`M${concatX + 70} 312 L${concatX + 70} 282`} id={id} tipo="fs" activa={paso === k} animada={paso === k} />
          <Caja x={concatX} y={218} w={140} h={60} titulo="Unir" sub={`${p.hidden} + ${p.estatica} = ${concat}`} activo={paso === k} />
          <Flecha d={`M${concatX + 140} 248 L${headX + 80} 248`} id={id} activa={paso > k} />
          {/* cabeza */}
          <Caja x={headX + 82} y={196} w={170} h={104} titulo="Cabeza" activo={paso > k}>
            <text x={headX + 167} y={236} textAnchor="middle" fontSize={10.5} fill={PALETA.muted} style={FUENTE}>{`Linear ${concat} → ${p.cabeza}`}</text>
            <text x={headX + 167} y={252} textAnchor="middle" fontSize={10.5} fill={PALETA.muted} style={FUENTE}>ReLU + dropout</text>
            <text x={headX + 167} y={268} textAnchor="middle" fontSize={10.5} fill={PALETA.muted} style={FUENTE}>{esT3 ? `Linear ${p.cabeza} → U × 3` : `Linear ${p.cabeza} → 1`}</text>
            <text x={headX + 167} y={284} textAnchor="middle" fontSize={10.5} fill={PALETA.muted} style={FUENTE}>{esT3 ? "softmax por semestre" : "sigmoide"}</text>
          </Caja>
          <Flecha d={`M${headX + 167} 300 L${headX + 167} 336`} id={id} activa={paso > k} animada={paso === k + 1} />
          {esT3 ? <SalidaRiesgos x={headX + 82} y={338} activo={paso === k + 1} /> : (
            <Caja x={headX + 82} y={338} w={170} h={52} titulo="Probabilidad" sub="de no continuar (0 a 1)" activo={paso === k + 1} color={PALETA.adverso} />
          )}
        </svg>
      </Marco>
      <Controles paso={paso} total={total} onPaso={setPaso} reproduciendo={reproduciendo} onAlternar={alternar} titulos={titulos} />
      <PanelPaso>
        {paso < k ? (
          <>
            <strong>Semestre {paso + 1}.</strong> La red recibe el vector del semestre ({p.dSeq} números: {p.variables.join(", ")}) y la memoria del semestre anterior
            (h{paso}). Con ambos calcula la memoria nueva h{paso + 1}, de {p.hidden} números. Así lee la historia en orden, un semestre a la vez.
          </>
        ) : paso === k ? (
          <>
            <strong>Unir.</strong> La memoria final h{k} resume la historia hasta el corte. Se une a la rama del perfil de ingreso (datos previos a entrar a la universidad,
            que pasan por una capa de {p.estatica} números). Resultan {concat} números.
          </>
        ) : esT3 ? (
          <>
            <strong>Riesgos por semestre.</strong> La cabeza devuelve, para cada semestre u después del corte, tres números: sigue, egresa o sale. El softmax los convierte en
            riesgos de un semestre; encadenados dan la probabilidad acumulada de egresar y la de salir del programa. Egreso y salida compiten: quien sale ya no egresa.
          </>
        ) : (
          <>
            <strong>Probabilidad.</strong> La cabeza reduce los {concat} números a uno; el sigmoide lo convierte en una probabilidad entre 0 y 1 de no continuar matriculado.
            Es lo que el benchmark evalúa en conjunto; las predicciones individuales no están habilitadas.
          </>
        )}
      </PanelPaso>
    </div>
  );
}

function SalidaRiesgos({ x, y, activo }: { x: number; y: number; activo: boolean }) {
  // Forma de la salida: para cada semestre u, tres porciones (sigue, egresa, sale). Alturas ilustrativas.
  const cols = 6;
  const sigue = [0.9, 0.78, 0.62, 0.48, 0.36, 0.28];
  const egreso = [0.02, 0.06, 0.16, 0.28, 0.38, 0.44];
  return (
    <g>
      <rect x={x} y={y} width={170} height={104} rx={6} fill="rgba(255,255,255,0.03)" stroke={activo ? PALETA.adverso : "rgba(237,237,239,0.22)"} strokeWidth={activo ? 2 : 1} />
      <text x={x + 85} y={y + 16} textAnchor="middle" fontSize={11} fontWeight={600} fill={PALETA.fg} style={FUENTE}>Riesgos por semestre u</text>
      {Array.from({ length: cols }, (_, i) => {
        const bx = x + 14 + i * 24;
        const base = y + 90;
        const h = 56;
        const hs = h * sigue[i], he = h * egreso[i], hx = h - hs - he;
        return (
          <g key={i} aria-hidden="true">
            <rect x={bx} y={base - h} width={16} height={hx} fill={PALETA.adverso} opacity={0.9} />
            <rect x={bx} y={base - h + hx} width={16} height={he} fill={PALETA.azul} opacity={0.9} />
            <rect x={bx} y={base - hs} width={16} height={hs} fill="rgba(237,237,239,0.16)" />
            <text x={bx + 8} y={base + 10} textAnchor="middle" fontSize={9} fill={PALETA.subtle} style={FUENTE}>{i + 1}</text>
          </g>
        );
      })}
      <text x={x + 85} y={y + 118} textAnchor="middle" fontSize={9.5} fill={PALETA.subtle} style={FUENTE}>Forma ilustrativa, no son datos</text>
      <g transform={`translate(${x + 4},${y + 126})`} fontSize={10} style={FUENTE}>
        <rect width={9} height={9} fill={PALETA.azul} /><text x={13} y={8} fill={PALETA.muted}>egresa</text>
        <rect x={56} width={9} height={9} fill={PALETA.adverso} /><text x={69} y={8} fill={PALETA.muted}>sale</text>
        <rect x={104} width={9} height={9} fill="rgba(237,237,239,0.3)" /><text x={117} y={8} fill={PALETA.muted}>sigue</text>
      </g>
    </g>
  );
}

// ---------------------------------------------------------------------------
// Perceptrón multicapa (capas de nodos) de los riesgos discretos de T3
// ---------------------------------------------------------------------------
export interface ParamsMLP { entrada: string; capas: readonly number[]; salidaTexto: string }

export function DiagramaMLP({ p }: { p: ParamsMLP }) {
  const [activo, setActivo] = useState<{ capa: number; nodo: number } | null>(null);
  const columnas = [
    { titulo: "Entrada", sub: p.entrada, n: 7, etiqueta: "variables" },
    ...p.capas.map((c) => ({ titulo: `${c} neuronas`, sub: "ReLU + dropout", n: Math.min(8, Math.max(4, Math.round(c / 18))), etiqueta: `${c}` })),
    { titulo: "Salida", sub: p.salidaTexto, n: 3, etiqueta: "" },
  ];
  const W = 760, H = 330, gx = (W - 140) / (columnas.length - 1);
  const pos = (c: number, i: number) => {
    const n = columnas[c].n;
    const alto = 210, y0 = 58 + (alto - (n - 1) * 30) / 2;
    return { x: 70 + c * gx, y: y0 + i * 30 };
  };
  const etiquetasSalida = ["sigue", "egresa", "sale"];
  return (
    <div className="space-y-3">
      <Marco minAncho={W} etiqueta="Diagrama de capas del perceptrón multicapa">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Red de capas: entrada, ${p.capas.join(" y ")} neuronas, salida`}>
          {columnas.slice(0, -1).map((col, c) =>
            Array.from({ length: col.n }, (_, i) =>
              Array.from({ length: columnas[c + 1].n }, (_, j) => {
                const a = pos(c, i), b = pos(c + 1, j);
                const resaltada = activo && ((activo.capa === c && activo.nodo === i) || (activo.capa === c + 1 && activo.nodo === j));
                return <line key={`${c}-${i}-${j}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={resaltada ? PALETA.azulClaro : "rgba(237,237,239,0.12)"} strokeWidth={resaltada ? 1.6 : 0.8} />;
              }),
            ),
          )}
          {columnas.map((col, c) => (
            <g key={c}>
              <text x={70 + c * gx} y={26} textAnchor="middle" fontSize={12} fontWeight={600} fill={PALETA.fg} style={FUENTE}>{col.titulo}</text>
              <text x={70 + c * gx} y={42} textAnchor="middle" fontSize={10.5} fill={PALETA.muted} style={FUENTE}>{col.sub}</text>
              {Array.from({ length: col.n }, (_, i) => {
                const q = pos(c, i);
                const sel = activo?.capa === c && activo.nodo === i;
                const color = c === 0 ? PALETA.serie3 : c === columnas.length - 1 ? PALETA.adverso : PALETA.azul;
                return (
                  <g key={i}>
                    <circle cx={q.x} cy={q.y} r={sel ? 11 : 9} fill={color} opacity={sel ? 1 : 0.85} stroke="#121314" strokeWidth={1.5} tabIndex={0}
                      onMouseEnter={() => setActivo({ capa: c, nodo: i })} onMouseLeave={() => setActivo(null)}
                      onFocus={() => setActivo({ capa: c, nodo: i })} onBlur={() => setActivo(null)} style={{ cursor: "pointer", transition: "r .15s" }}>
                      <title>{c === columnas.length - 1 ? `Salida: ${etiquetasSalida[i]}` : `Neurona ${i + 1} de la capa`}</title>
                    </circle>
                    {c === columnas.length - 1 ? <text x={q.x + 16} y={q.y + 4} fontSize={11} fill={PALETA.muted} style={FUENTE}>{etiquetasSalida[i]}</text> : null}
                  </g>
                );
              })}
              {col.n < 8 && c > 0 && c < columnas.length - 1 ? <text x={70 + c * gx} y={pos(c, col.n - 1).y + 24} textAnchor="middle" fontSize={14} fill={PALETA.subtle}>⋮</text> : null}
              {c === 0 ? <text x={70} y={pos(0, 6).y + 24} textAnchor="middle" fontSize={14} fill={PALETA.subtle}>⋮</text> : null}
            </g>
          ))}
        </svg>
      </Marco>
      <PanelPaso>
        Cada círculo es una neurona: suma sus entradas con pesos aprendidos y aplica una función (ReLU). Se muestran solo algunas neuronas por capa; los tamaños reales
        son los indicados arriba. Pasa el cursor por una neurona para ver con qué se conecta. A la salida, para cada semestre posterior al corte, la red entrega tres
        valores (sigue, egresa, sale) que el softmax vuelve riesgos del semestre.
      </PanelPaso>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CatBoost: conjunto de árboles
// ---------------------------------------------------------------------------
export interface ParamsCatBoost { iteraciones: number | null; profundidad: number | null; tasa: number | null; variables: number | null }

export function DiagramaCatBoost({ p }: { p: ParamsCatBoost }) {
  const [n, setN] = useState(1);
  const W = 780;
  const condiciones = ["créditos aprobados < x₁", "promedio acumulado ≥ x₂", "semestres sin notas > x₃"];
  const arbol = (cx: number, etiqueta: string, i: number) => {
    const nivel = (d: number) => 70 + d * 58;
    const hojas = [0, 1, 2, 3, 4, 5, 6, 7];
    return (
      <g key={i} opacity={i < n ? 1 : 0.18} style={{ transition: "opacity .3s" }}>
        <text x={cx} y={28} textAnchor="middle" fontSize={12} fontWeight={600} fill={PALETA.fg} style={FUENTE}>{etiqueta}</text>
        {[0, 1, 2].map((d) => (
          <g key={d}>
            {Array.from({ length: 2 ** d }, (_, j) => {
              const ancho = 150 / 2 ** d;
              const x = cx - 75 + ancho * (j + 0.5);
              return (
                <g key={j}>
                  <rect x={x - 9} y={nivel(d) - 11} width={18} height={18} rx={4} fill={PALETA.azul} opacity={0.85} />
                  {d < 2 ? (
                    <>
                      <line x1={x} y1={nivel(d) + 7} x2={x - ancho / 4} y2={nivel(d + 1) - 11} stroke="rgba(237,237,239,0.3)" />
                      <line x1={x} y1={nivel(d) + 7} x2={x + ancho / 4} y2={nivel(d + 1) - 11} stroke="rgba(237,237,239,0.3)" />
                    </>
                  ) : null}
                </g>
              );
            })}
            <text x={cx + 82} y={nivel(d) + 3} fontSize={9.5} fill={PALETA.subtle} style={FUENTE}>{d === 0 ? condiciones[(i + d) % 3] : ""}</text>
          </g>
        ))}
        {hojas.slice(0, 4).map((_, j) => {
          const x = cx - 75 + (150 / 4) * (j + 0.5);
          const v = altura(`hoja${i}`, j) - 0.5;
          return <rect key={j} x={x - 7} y={nivel(3) - 4 - Math.max(0, v) * 30} width={14} height={Math.abs(v) * 30 + 3} fill={v >= 0 ? PALETA.azulClaro : PALETA.adverso} opacity={0.9} />;
        })}
        <text x={cx} y={nivel(3) + 26} textAnchor="middle" fontSize={10} fill={PALETA.subtle} style={FUENTE}>valores de hojas</text>
      </g>
    );
  };
  return (
    <div className="space-y-3">
      <Marco minAncho={W} etiqueta="Diagrama de un conjunto de árboles de decisión">
        <svg viewBox={`0 0 ${W} 300`} width="100%" role="img" aria-label="Tres árboles de decisión que se suman">
          {[0, 1, 2].map((i) => arbol(110 + i * 215, `Árbol ${i + 1}`, i))}
          {[0, 1].map((i) => <text key={i} x={217 + i * 215} y={110} textAnchor="middle" fontSize={22} fill={PALETA.muted}>+</text>)}
          <text x={744} y={110} textAnchor="middle" fontSize={22} fill={PALETA.muted}>…</text>
          <text x={390} y={286} textAnchor="middle" fontSize={12} fill={PALETA.fg} style={FUENTE}>
            {`suma de ${p.iteraciones ?? "N"} árboles de profundidad ${p.profundidad ?? "d"} → sigmoide → probabilidad`}
          </text>
        </svg>
      </Marco>
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="cb-n" className="text-sm text-[var(--portal-muted)]">Árboles sumados: <strong className="text-[var(--portal-fg)]">{n}</strong> de 3 mostrados</label>
        <input id="cb-n" type="range" min={1} max={3} value={n} onChange={(e) => setN(Number(e.target.value))} className="w-40 accent-[var(--ucn-azul)]" />
      </div>
      <PanelPaso>
        Cada árbol hace preguntas sobre las variables (por ejemplo «¿créditos aprobados menores que x?») y termina en una hoja con un número pequeño. CatBoost agrega árboles uno
        tras otro; cada árbol nuevo corrige lo que los anteriores dejaron mal. La predicción es la suma de las hojas, pasada por un sigmoide. Aquí cada árbol es simétrico: usa la misma
        pregunta en todo un nivel. {p.iteraciones != null ? `Con parada temprana, el modelo conserva en promedio ${Math.round(p.iteraciones)} árboles` : ""}
        {p.variables != null ? ` sobre ${Math.round(p.variables)} variables` : ""}{p.tasa != null ? ` y una tasa de aprendizaje de ${p.tasa.toLocaleString("es-CL")}` : ""}.
        Los valores y condiciones dibujados son ilustrativos.
      </PanelPaso>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GraphSAGE sobre el grafo de prerrequisitos de una malla real
// ---------------------------------------------------------------------------
export interface ParamsSage { dHid: number; dOut: number; capas: number; relaciones: number; cabeza: string }

interface NodoPos { codigo: string; nombre: string | null; semestre: number; creditos: number | null; x: number; y: number }

const TITULOS_SAGE = [
  "Cada ramo es un nodo", "Elegir un ramo", "Mirar a los vecinos", "Agregar los mensajes", "Combinar", "Repetir en 2 capas", "Entrar al predictor",
] as const;

export function DiagramaGraphSAGE({ malla, p }: { malla: MallaEjemplo; p: ParamsSage }) {
  const id = useId().replace(/:/g, "");
  const total = TITULOS_SAGE.length;
  const { paso, setPaso, reproduciendo, alternar } = usePasos(total, 2000);

  const { nodos, porCodigo, W, H } = useMemo(() => {
    const columnas = new Map<number, typeof malla.nodos>();
    for (const n of malla.nodos) columnas.set(n.semestre, [...(columnas.get(n.semestre) ?? []), n]);
    const sems = [...columnas.keys()].sort((a, b) => a - b);
    const filasMax = Math.max(1, ...[...columnas.values()].map((l) => l.length));
    const anchoCol = 190, rowH = 46;
    const lista: NodoPos[] = [];
    sems.forEach((s, ci) => {
      (columnas.get(s) ?? []).slice().sort((a, b) => a.codigo.localeCompare(b.codigo)).forEach((n, ri) =>
        lista.push({ ...n, x: 30 + ci * anchoCol, y: 54 + ri * rowH }));
    });
    return { nodos: lista, porCodigo: new Map(lista.map((n) => [n.codigo, n])), W: 60 + Math.max(1, sems.length) * anchoCol + 280, H: Math.max(260, 70 + filasMax * rowH) };
  }, [malla]);

  const grados = useMemo(() => {
    const g = new Map<string, number>();
    for (const a of malla.aristas) {
      g.set(a.desde, (g.get(a.desde) ?? 0) + 1);
      g.set(a.hacia, (g.get(a.hacia) ?? 0) + 1);
    }
    return g;
  }, [malla.aristas]);
  const [objetivoElegido, setObjetivo] = useState<string | null>(null);
  const objetivo = objetivoElegido && porCodigo.has(objetivoElegido)
    ? objetivoElegido
    : ([...nodos].sort((a, b) => (grados.get(b.codigo) ?? 0) - (grados.get(a.codigo) ?? 0))[0]?.codigo ?? null);

  const previos = useMemo(() => new Set(malla.aristas.filter((a) => a.hacia === objetivo).map((a) => a.desde)), [malla.aristas, objetivo]);
  const posteriores = useMemo(() => new Set(malla.aristas.filter((a) => a.desde === objetivo).map((a) => a.hacia)), [malla.aristas, objetivo]);
  const segundo = useMemo(() => {
    const primero = new Set([...previos, ...posteriores, objetivo ?? ""]);
    const s = new Set<string>();
    for (const a of malla.aristas) {
      if (primero.has(a.desde) && !primero.has(a.hacia)) s.add(a.hacia);
      if (primero.has(a.hacia) && !primero.has(a.desde)) s.add(a.desde);
    }
    return s;
  }, [malla.aristas, previos, posteriores, objetivo]);

  if (nodos.length === 0) {
    return <p className="rounded-md border border-dashed border-[var(--boveda-linea-fuerte)] px-4 py-6 text-center text-sm text-[var(--portal-muted)]">No hay una malla con prerrequisitos para dibujar el grafo.</p>;
  }
  const t = objetivo ? porCodigo.get(objetivo) : undefined;
  const colorNodo = (c: string) => {
    if (c === objetivo && paso >= 1) return PALETA.adverso;
    if (paso >= 2 && previos.has(c)) return PALETA.azulClaro;
    if (paso >= 2 && posteriores.has(c)) return PALETA.serie3;
    if (paso >= 5 && segundo.has(c)) return PALETA.tierraClara;
    return PALETA.neutro;
  };
  const opaco = (c: string) => (paso < 2 || c === objetivo || previos.has(c) || posteriores.has(c) || (paso >= 5 && segundo.has(c)) ? 1 : 0.35);
  const panelX = W - 270;

  return (
    <div className="space-y-3">
      <Marco minAncho={Math.min(W, 920)} etiqueta="Grafo de prerrequisitos de una malla con el paso de mensajes de GraphSAGE">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Grafo de ${nodos.length} ramos y ${malla.aristas.length} prerrequisitos de ${malla.nombre_programa ?? "un programa"}`}>
          <Defs id={id} /><EstiloAnimacion />
          {[...new Set(nodos.map((n) => n.semestre))].map((s) => {
            const n = nodos.find((q) => q.semestre === s);
            return n ? <text key={s} x={n.x + 74} y={26} textAnchor="middle" fontSize={11.5} fontWeight={600} fill={PALETA.serie3} style={FUENTE}>Semestre {s}</text> : null;
          })}
          {malla.aristas.map((a, i) => {
            const o = porCodigo.get(a.desde), d = porCodigo.get(a.hacia);
            if (!o || !d) return null;
            const entraAlObjetivo = a.hacia === objetivo, saleDelObjetivo = a.desde === objetivo;
            const activa = paso >= 2 && (entraAlObjetivo || saleDelObjetivo);
            const x1 = o.x + 148, y1 = o.y + 13, x2 = d.x, y2 = d.y + 13;
            const mx = (x1 + x2) / 2;
            return (
              <Flecha key={i} id={id} d={`M${x1} ${y1} C${mx} ${y1}, ${mx} ${y2}, ${x2 - 2} ${y2}`}
                tipo={entraAlObjetivo ? "fa" : "fs"} activa={activa} animada={activa && paso === 2} />
            );
          })}
          {nodos.map((n) => (
            <g key={n.codigo} opacity={opaco(n.codigo)} style={{ transition: "opacity .3s", cursor: "pointer" }} tabIndex={0} role="button"
              aria-label={`${n.codigo} ${n.nombre ?? ""}: elegir como ramo objetivo`}
              onClick={() => { setObjetivo(n.codigo); if (paso < 1) setPaso(1); }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setObjetivo(n.codigo); if (paso < 1) setPaso(1); } }}>
              <title>{`${n.codigo}${n.nombre ? ` · ${n.nombre}` : ""}${n.creditos != null ? ` · ${n.creditos} créditos` : ""}`}</title>
              <rect x={n.x} y={n.y} width={148} height={26} rx={5} fill="rgba(255,255,255,0.04)" stroke={colorNodo(n.codigo)} strokeWidth={n.codigo === objetivo && paso >= 1 ? 2.5 : 1.4} />
              <circle cx={n.x + 10} cy={n.y + 13} r={4} fill={colorNodo(n.codigo)} />
              <text x={n.x + 20} y={n.y + 11} fontSize={9} fill={PALETA.subtle} style={FUENTE}>{n.codigo}</text>
              <text x={n.x + 20} y={n.y + 22} fontSize={9.5} fill={PALETA.fg} style={FUENTE}>{(n.nombre ?? "").slice(0, 24)}</text>
            </g>
          ))}
          {/* panel lateral del paso */}
          <g transform={`translate(${panelX},46)`}>
            <PanelLateral paso={paso} t={t} nPrev={previos.size} nPost={posteriores.size} nSeg={segundo.size} p={p} />
          </g>
        </svg>
      </Marco>
      <Controles paso={paso} total={total} onPaso={setPaso} reproduciendo={reproduciendo} onAlternar={alternar} titulos={TITULOS_SAGE} />
      <PanelPaso>
        {paso === 0 ? (<><strong>Un grafo de cursos.</strong> Cada ramo de la malla de {malla.nombre_programa ?? "un programa"} (catálogo {malla.catalogo ?? "—"}, primeros {malla.semestre_max} semestres) es un nodo; cada prerrequisito, una flecha. Cada nodo parte con atributos propios: créditos, semestre de la malla, departamento y área de formación, y la tasa histórica de aprobación anterior a 2015. Haz clic en un ramo para elegirlo.</>)
          : paso === 1 ? (<><strong>Ramo objetivo: {t?.codigo}.</strong> {t?.nombre ?? ""}. GraphSAGE calcula una representación (embedding) para cada ramo; veamos cómo se construye la de este.</>)
          : paso === 2 ? (<><strong>Mensajes de los vecinos.</strong> {previos.size} ramo(s) previo(s) (azul, los prerrequisitos) y {posteriores.size} ramo(s) posterior(es) (dorado, los que lo exigen) le envían sus vectores. Con coinscripción habría una tercera relación: ramos que se toman juntos.</>)
          : paso === 3 ? (<><strong>Agregar.</strong> Los mensajes de cada relación se promedian (agregador de media): un vector para los previos y otro para los posteriores, del mismo tamaño que el propio ({p.dHid}). Así el número de vecinos no cambia el tamaño.</>)
          : paso === 4 ? (<><strong>Combinar.</strong> El vector nuevo es h′ = W<sub>propio</sub>·h + W<sub>previos</sub>·promedio(previos) + W<sub>posteriores</sub>·promedio(posteriores), con una matriz de pesos aprendida por cada relación. Después se aplica ReLU.</>)
          : paso === 5 ? (<><strong>Dos capas.</strong> Se repite el proceso {p.capas} veces ({p.dHid} → {p.dHid} → {p.dOut}). Con la segunda capa el ramo recibe información de los vecinos de sus vecinos (marcados en tierra clara): hasta dos prerrequisitos de distancia.</>)
          : (<><strong>Al predictor.</strong> El embedding de {p.dOut} números del curso se une a los datos del estudiante y su carga, y entra a la red de {p.cabeza} que estima la probabilidad de reprobar. En los resultados medidos, este grafo no agregó señal frente a las mismas variables sin aristas.</>)}
      </PanelPaso>
    </div>
  );
}

function PanelLateral({ paso, t, nPrev, nPost, nSeg, p }: { paso: number; t: NodoPos | undefined; nPrev: number; nPost: number; nSeg: number; p: ParamsSage }) {
  const sem = t ? `${t.codigo}` : "ramo";
  const caja = (y: number, alto: number, titulo: string, lineas: string[], color: string) => (
    <g>
      <rect x={0} y={y} width={252} height={alto} rx={6} fill="rgba(255,255,255,0.03)" stroke={color} />
      <text x={10} y={y + 17} fontSize={11.5} fontWeight={600} fill={PALETA.fg} style={FUENTE}>{titulo}</text>
      {lineas.map((l, i) => <text key={i} x={10} y={y + 34 + i * 14} fontSize={10.5} fill={PALETA.muted} style={FUENTE}>{l}</text>)}
    </g>
  );
  if (paso === 0) return caja(0, 130, "Atributos de cada nodo", ["créditos del ramo", "semestre de la malla (mín., media, máx.)", "número de programas donde aparece", "departamento y formación (categorías)", "tasa de aprobación previa a 2015"], PALETA.neutro);
  if (paso === 1) return caja(0, 70, `Objetivo: ${sem}`, [t?.nombre ?? "", `${t?.creditos ?? "—"} créditos · semestre ${t?.semestre ?? "—"}`], PALETA.adverso);
  if (paso === 2) return (
    <g>{caja(0, 52, `Previos: ${nPrev}`, ["prerrequisitos del ramo (azul)"], PALETA.azulClaro)}{caja(64, 52, `Posteriores: ${nPost}`, ["ramos que lo exigen (dorado)"], PALETA.serie3)}</g>
  );
  if (paso === 3) return (
    <g>
      {caja(0, 64, "promedio(previos)", [`1 vector de ${p.dHid} números`, `de ${nPrev} mensaje(s)`], PALETA.azulClaro)}
      <Vector x={150} y={26} n={p.dHid} semilla={`prev${sem}`} color={PALETA.azulClaro} ancho={2} alto={24} max={40} />
      {caja(76, 64, "promedio(posteriores)", [`1 vector de ${p.dHid} números`, `de ${nPost} mensaje(s)`], PALETA.serie3)}
      <Vector x={150} y={102} n={p.dHid} semilla={`post${sem}`} color={PALETA.serie3} ancho={2} alto={24} max={40} />
    </g>
  );
  if (paso === 4) return (
    <g>
      {caja(0, 108, "h′ = W·h + W·prom(previos)", ["+ W·prom(posteriores)", "ReLU", `resultado: ${p.dHid} números`], PALETA.adverso)}
      <Vector x={14} y={84} n={p.dHid} semilla={`h${sem}`} color={PALETA.adverso} ancho={2} alto={16} max={40} />
    </g>
  );
  if (paso === 5) return caja(0, 100, `Capa 1: ${p.dHid} → ${p.dHid}`, [`Capa 2: ${p.dHid} → ${p.dOut}`, `${nSeg} ramo(s) a distancia 2`, "(tierra clara)"], PALETA.tierraClara);
  return (
    <g>
      {caja(0, 64, `Embedding: ${p.dOut} números`, ["resumen del ramo y de su entorno"], PALETA.adverso)}
      <Vector x={150} y={26} n={p.dOut} semilla={`e${sem}`} color={PALETA.adverso} ancho={3} alto={24} max={32} />
      {caja(78, 64, "Predictor (red densa)", [p.cabeza, "estudiante + carga + embedding"], PALETA.azul)}
    </g>
  );
}
