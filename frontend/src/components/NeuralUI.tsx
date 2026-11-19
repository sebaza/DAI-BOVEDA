"use client";

// Primitivas compartidas de DAI Neural: carga con estados, pestañas accesibles, formato y avisos.
import { createContext, useContext, useEffect, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from "react";

import { AceptacionRequerida, NeuralError, esCancelacion } from "../lib/neural";
import { POCOS_CASOS_TEXTOS, limpiarCodigos } from "../lib/neuralLenguaSimple";
import { HayTablaContext } from "./EChartsChart";

export { CARD, SELECT } from "./PercepcionUI";

export const INPUT =
  "h-9 w-full min-w-0 rounded border border-[var(--boveda-linea-fuerte)] bg-[var(--boveda-madera)] px-3 " +
  "text-sm text-slate-100 outline-none transition focus:border-[var(--portal-cyan)] hover:border-white/20";

export const BOTON =
  "inline-flex h-9 items-center justify-center rounded border border-[var(--boveda-linea-fuerte)] px-4 text-sm " +
  "font-semibold text-[var(--portal-fg)] transition hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-50 " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]";

// ---------------------------------------------------------------------------
// Carga de datos con cancelación
// ---------------------------------------------------------------------------
export type EstadoCarga<T> =
  | { fase: "cargando" }
  | { fase: "ok"; datos: T }
  | { fase: "error"; mensaje: string; status: number | null; reintentar: () => void };

/** Aviso al panel cuando cualquier consulta responde «aceptación requerida»: el panel vuelve a la puerta de aceptación. */
export const AceptacionRevocadaContext = createContext<() => void>(() => {});

/** Ejecuta `fetcher` al cambiar `deps` (cancela la anterior). Con `activo = false` no consulta. */
export function useCarga<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
  activo = true,
): EstadoCarga<T> {
  const [estado, setEstado] = useState<EstadoCarga<T>>({ fase: "cargando" });
  const [intento, setIntento] = useState(0);
  const alRevocarse = useContext(AceptacionRevocadaContext);
  useEffect(() => {
    if (!activo) return;
    const ctrl = new AbortController();
    setEstado({ fase: "cargando" });
    fetcher(ctrl.signal)
      .then((datos) => {
        if (!ctrl.signal.aborted) setEstado({ fase: "ok", datos });
      })
      .catch((e: unknown) => {
        if (esCancelacion(e) || ctrl.signal.aborted) return;
        if (e instanceof AceptacionRequerida) {
          alRevocarse();
          return;
        }
        const reintentar = () => setIntento((n) => n + 1);
        if (e instanceof NeuralError) setEstado({ fase: "error", mensaje: e.message, status: e.status, reintentar });
        else setEstado({ fase: "error", mensaje: "No se pudo conectar con el servidor.", status: null, reintentar });
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, activo, intento]);
  return estado;
}

/** Ancho del contenedor en px (0 antes de medir). Sirve para dimensionar etiquetas de gráficos en pantallas angostas. */
export function useAncho<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const medir = () => setAncho(Math.round(el.getBoundingClientRect().width));
    medir();
    if (typeof ResizeObserver === "undefined") return;
    const obs = new ResizeObserver(medir);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return [ref, ancho];
}

export function Esqueleto({ filas = 4, alto = "h-6" }: { filas?: number; alto?: string }) {
  return (
    <div className="space-y-2" role="status" aria-live="polite" aria-label="Cargando">
      {Array.from({ length: filas }, (_, i) => (
        <div key={i} className={`portal-esqueleto ${alto} rounded`} style={{ width: `${100 - (i % 3) * 12}%` }} />
      ))}
      <span className="sr-only">Cargando…</span>
    </div>
  );
}

export function ErrorCarga({ mensaje, status, onReintentar }: { mensaje: string; status: number | null; onReintentar?: () => void }) {
  const titulo =
    status === 503 ? "Módulo sin configurar o sin datos"
    : status === 403 ? "Sin acceso"
    : status === 404 ? "No encontrado"
    : "No se pudo cargar";
  return (
    <div role="alert" className="rounded-md border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-4 py-3 text-sm">
      <p className="font-semibold text-ucn-tierra-clara">{titulo}</p>
      <p className="mt-1 text-[var(--portal-muted)]">{mensaje}</p>
      {onReintentar && status !== 403 && status !== 404 ? (
        <button type="button" onClick={onReintentar} className={`${BOTON} mt-3 h-8 px-3 text-xs`}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export function Vacio({ children, titulo }: { children: ReactNode; titulo?: string }) {
  return (
    <div className="rounded-md border border-dashed border-[var(--boveda-linea-fuerte)] px-4 py-6 text-center text-sm text-[var(--portal-muted)]">
      {titulo ? <p className="mb-1 font-semibold text-[var(--portal-fg)]">{titulo}</p> : null}
      <p>{children}</p>
    </div>
  );
}

/** Pinta el estado de una carga: esqueleto, error o el contenido. */
export function Carga<T>({
  estado, children, filas, alto,
}: {
  estado: EstadoCarga<T>;
  children: (datos: T) => ReactNode;
  filas?: number;
  alto?: string;
}) {
  if (estado.fase === "cargando") return <Esqueleto filas={filas} alto={alto} />;
  if (estado.fase === "error") return <ErrorCarga mensaje={estado.mensaje} status={estado.status} onReintentar={estado.reintentar} />;
  return <>{children(estado.datos)}</>;
}

// ---------------------------------------------------------------------------
// Pestañas
// ---------------------------------------------------------------------------
export interface PestanaDef<Id extends string> {
  id: Id;
  label: string;
  /** Nombre del grupo al que pertenece. Las pestañas contiguas con el mismo grupo se muestran juntas, bajo su nombre. */
  grupo?: string;
}

/** Pestañas contiguas con el mismo grupo (sin grupo: un solo tramo sin nombre). `inicio` es el índice de la primera en la lista. */
function agruparPestanas<Id extends string>(pestanas: readonly PestanaDef<Id>[]) {
  const tramos: { grupo: string | undefined; inicio: number; items: PestanaDef<Id>[] }[] = [];
  pestanas.forEach((p, i) => {
    const ultimo = tramos[tramos.length - 1];
    if (ultimo && ultimo.grupo === p.grupo) ultimo.items.push(p);
    else tramos.push({ grupo: p.grupo, inicio: i, items: [p] });
  });
  return tramos;
}

/**
 * Una sola lista de pestañas (las flechas recorren todas, de un grupo al siguiente). Si las pestañas traen `grupo`, cada tramo lleva
 * su nombre visible encima y una línea que lo separa del anterior; cada pestaña lo declara con `aria-describedby`.
 * En pantallas angostas la barra se desplaza; se difumina el borde que aún tiene contenido y la pestaña activa queda a la vista.
 */
export function Pestanas<Id extends string>({
  pestanas, activa, onCambio, etiqueta, prefijo, compacta = false,
}: {
  pestanas: readonly PestanaDef<Id>[];
  activa: Id;
  onCambio: (id: Id) => void;
  etiqueta: string;
  prefijo: string;
  compacta?: boolean;
}) {
  const barra = useRef<HTMLDivElement>(null);
  const [fadeIzq, setFadeIzq] = useState(false);
  const [fadeDer, setFadeDer] = useState(false);
  const tramos = agruparPestanas(pestanas);

  useEffect(() => {
    const el = barra.current;
    if (!el) return;
    const medir = () => {
      setFadeIzq(el.scrollLeft > 0);
      setFadeDer(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
    };
    medir();
    el.addEventListener("scroll", medir, { passive: true });
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(medir) : null;
    ro?.observe(el);
    return () => {
      el.removeEventListener("scroll", medir);
      ro?.disconnect();
    };
  }, [pestanas.length]);

  // La pestaña activa queda a la vista dentro de la barra. No se hace al montar, para no mover la página sin que la persona haya elegido.
  const montada = useRef(false);
  useEffect(() => {
    if (!montada.current) { montada.current = true; return; }
    document.getElementById(`${prefijo}-tab-${activa}`)?.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "auto" });
  }, [activa, prefijo]);

  const mover = (e: KeyboardEvent, i: number) => {
    let sig = i;
    if (e.key === "ArrowRight") sig = (i + 1) % pestanas.length;
    else if (e.key === "ArrowLeft") sig = (i - 1 + pestanas.length) % pestanas.length;
    else if (e.key === "Home") sig = 0;
    else if (e.key === "End") sig = pestanas.length - 1;
    else return;
    e.preventDefault();
    onCambio(pestanas[sig].id);
    document.getElementById(`${prefijo}-tab-${pestanas[sig].id}`)?.focus();
  };
  return (
    <div
      ref={barra}
      role="tablist"
      aria-label={etiqueta}
      className={`pestanas-scroll flex min-w-0 overflow-x-auto border-b border-[var(--boveda-linea)] ${fadeIzq ? "pestanas-fade-izq" : ""} ${fadeDer ? "pestanas-fade-der" : ""}`}
    >
      {tramos.map((t, ti) => {
        const idGrupo = `${prefijo}-grupo-${ti}`;
        return (
          <div
            key={t.inicio}
            role="presentation"
            className={`flex shrink-0 flex-col ${ti > 0 ? "ml-2 border-l border-[var(--boveda-linea-fuerte)] pl-2" : ""}`}
          >
            {t.grupo ? (
              <span id={idGrupo} aria-hidden="true" className="whitespace-nowrap px-3 pt-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--portal-subtle)] sm:px-4">
                {t.grupo}
              </span>
            ) : null}
            <div role="presentation" className="flex">
              {t.items.map((p, j) => {
                const sel = p.id === activa;
                const i = t.inicio + j;
                return (
                  <button
                    key={p.id}
                    id={`${prefijo}-tab-${p.id}`}
                    type="button"
                    role="tab"
                    aria-selected={sel}
                    aria-controls={`${prefijo}-panel-${p.id}`}
                    aria-describedby={t.grupo ? idGrupo : undefined}
                    tabIndex={sel ? 0 : -1}
                    onClick={() => onCambio(p.id)}
                    onKeyDown={(e) => mover(e, i)}
                    className={`relative shrink-0 whitespace-nowrap px-3 ${compacta ? "py-2" : "py-3"} text-sm transition sm:px-4 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--ucn-azul-claro)] ${
                      sel
                        ? "font-semibold text-[var(--portal-fg)] after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-[var(--ucn-azul)]"
                        : "text-slate-400 hover:text-[var(--portal-fg)]"
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Formato
// ---------------------------------------------------------------------------
export function num(v: number | null | undefined, dec = 1): string {
  return v == null ? "—" : v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export function entero(v: number | null | undefined): string {
  return v == null ? "—" : v.toLocaleString("es-CL");
}

/** Fracción 0..1 -> "37,5 %". */
export function pct(v: number | null | undefined, dec = 1): string {
  return v == null ? "—" : `${(v * 100).toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec })} %`;
}

/** «38 % de 13»: todo porcentaje se muestra con el tamaño del grupo del que sale. */
export function pctDe(v: number | null | undefined, n: number | null | undefined, dec = 0): string {
  return v == null ? "—" : n == null ? pct(v, dec) : `${pct(v, dec)} de ${entero(n)}`;
}

/** «0,22–0,63» (o `null` si falta algún extremo). */
export function rango(lo: number | null | undefined, hi: number | null | undefined, dec = 2): string | null {
  return lo == null || hi == null ? null : `${num(lo, dec)}–${num(hi, dec)}`;
}

/** Métrica de un grupo con su intervalo de 95 %: «0,41 (0,22–0,63)»; «no calculable» cuando no hay valor. */
export function metricaConIc(v: number | null | undefined, lo: number | null | undefined, hi: number | null | undefined, dec = 2): string {
  if (v == null) return POCOS_CASOS_TEXTOS.noCalculable;
  const r = rango(lo, hi, dec);
  return r ? `${num(v, dec)} (${r})` : num(v, dec);
}

/** Lo mismo para una proporción (0 a 1) mostrada en porcentaje: «12 % (8 %–18 %)». */
export function pctConIc(v: number | null | undefined, lo: number | null | undefined, hi: number | null | undefined, dec = 0): string {
  if (v == null) return POCOS_CASOS_TEXTOS.noCalculable;
  return lo == null || hi == null ? pct(v, dec) : `${pct(v, dec)} (${pct(lo, dec)}–${pct(hi, dec)})`;
}

export function fechaCorta(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}

// ---------------------------------------------------------------------------
// Piezas visuales
// ---------------------------------------------------------------------------
export function Insignia({ children, tono = "neutro", titulo }: { children: ReactNode; tono?: "neutro" | "aviso" | "azul"; titulo?: string }) {
  const clase =
    tono === "aviso"
      ? "border-[color-mix(in_srgb,var(--portal-copper)_40%,transparent)] bg-[var(--ucn-tierra-suave)] text-ucn-tierra-clara"
      : tono === "azul"
        ? "border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)] text-[var(--ucn-azul-claro)]"
        : "border-white/10 bg-white/[0.04] text-slate-300";
  return (
    <span title={titulo} className={`inline-block whitespace-nowrap rounded border px-1.5 py-0.5 text-xs font-medium ${clase}`}>
      {children}
    </span>
  );
}

/** Un grupo de menos de este número de personas lleva la marca «pocos casos» (el servidor la calcula con el mismo valor). */
export const POCOS_CASOS = 10;

/** Marca de un grupo pequeño: la cifra se muestra completa, pero es poco estable. Sin `n` explícito siempre se dibuja. */
export function PocosCasos({ n }: { n?: number | null }) {
  if (n != null && n >= POCOS_CASOS) return null;
  return <Insignia tono="aviso" titulo={POCOS_CASOS_TEXTOS.ayuda}>{POCOS_CASOS_TEXTOS.etiqueta}</Insignia>;
}

/** Texto de apoyo para el pie de una tabla o gráfico que muestra la marca. */
export function LeyendaPocosCasos({ grafico = false, unidad = "personas" }: { grafico?: boolean; unidad?: string }) {
  return (
    <p className="text-xs leading-5 text-[var(--portal-muted)]">
      {(grafico ? POCOS_CASOS_TEXTOS.leyendaGrafico : POCOS_CASOS_TEXTOS.leyendaTabla).replace("{unidad}", unidad)}
    </p>
  );
}

export function Notas({ notas, titulo = "Notas técnicas" }: { notas: readonly string[]; titulo?: string }) {
  if (!notas.length) return null;
  return (
    <details className="mt-4 rounded-md border border-[var(--boveda-linea)] px-3 py-2 text-xs text-[var(--portal-muted)]">
      <summary className="cursor-pointer font-semibold text-[var(--portal-fg)]">{titulo}</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5 leading-5">
        {notas.map((n, i) => <li key={i}>{limpiarCodigos(n)}</li>)}
      </ul>
    </details>
  );
}

export function Titulo({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-3">
      <h3 className="text-base font-semibold text-[var(--portal-fg)]">{children}</h3>
      {sub ? <p className="mt-0.5 text-xs text-[var(--portal-muted)]">{sub}</p> : null}
    </div>
  );
}

export function Metrica({ etiqueta, valor, detalle }: { etiqueta: string; valor: ReactNode; detalle?: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 rounded-md border border-white/10 bg-white/[0.02] px-3 py-2">
      <span className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-muted)]">{etiqueta}</span>
      <span className="text-lg font-semibold text-[var(--portal-fg)]">{valor}</span>
      {detalle ? <span className="text-xs text-[var(--portal-muted)]">{detalle}</span> : null}
    </div>
  );
}

/** Contenedor de tabla con scroll horizontal en pantallas angostas. */
export function TablaScroll({ children, etiqueta }: { children: ReactNode; etiqueta: string }) {
  return (
    <div className="relative overflow-x-auto rounded-md border border-[var(--boveda-linea)]" role="region" aria-label={etiqueta} tabIndex={0}>
      {children}
    </div>
  );
}

export const TH = "whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-400";
export const TD = "px-3 py-2 align-top text-sm text-[var(--portal-fg)]";
export const FILA = "border-t border-[var(--boveda-linea)]";

/** Franja de aviso (p. ej. «las predicciones individuales no están habilitadas»). */
export function Aviso({ children, titulo, tono = "azul" }: { children: ReactNode; titulo?: string; tono?: "azul" | "tierra" }) {
  const clase =
    tono === "tierra"
      ? "border-[color-mix(in_srgb,var(--portal-copper)_45%,transparent)] bg-[var(--ucn-tierra-suave)]"
      : "border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)]";
  return (
    <div role="note" className={`rounded-md border px-4 py-3 text-sm ${clase}`}>
      {titulo ? <p className="font-semibold text-[var(--portal-fg)]">{titulo}</p> : null}
      <div className={`leading-6 text-[var(--portal-muted)] ${titulo ? "mt-0.5" : ""}`}>{children}</div>
    </div>
  );
}

/** Control segmentado accesible (radiogrupo) para elegir una opción entre pocas. */
export function Segmentado<Id extends string>({
  opciones, valor, onCambio, etiqueta,
}: {
  opciones: readonly { id: Id; label: string }[];
  valor: Id;
  onCambio: (id: Id) => void;
  etiqueta: string;
}) {
  return (
    <div role="radiogroup" aria-label={etiqueta} className="inline-flex max-w-full flex-wrap overflow-hidden rounded border border-[var(--boveda-linea-fuerte)]">
      {opciones.map((o) => {
        const sel = o.id === valor;
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={sel}
            onClick={() => onCambio(o.id)}
            className={`h-9 px-3 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--ucn-azul-claro)] ${
              sel ? "bg-[var(--ucn-azul-suave)] font-semibold text-[var(--portal-fg)]" : "text-slate-400 hover:bg-white/[0.04] hover:text-[var(--portal-fg)]"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Etiqueta pequeña de un control de formulario (misma tipografía en todas las vistas). */
export const ETIQUETA_CAMPO = "mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-400";

/**
 * Los mismos datos del gráfico en tabla. Los números se escriben con los formatos del módulo (enteros con separador de miles,
 * decimales con coma); lo que ya es un porcentaje o un rango llega como texto. `columnaN` es la columna con el tamaño del grupo de
 * cada fila: si es menor que POCOS_CASOS, la fila lleva la marca «pocos casos».
 */
export interface DatosGrafico {
  columnas: string[];
  filas: (string | number | null)[][];
  columnaN?: number;
  /** Lo que cuenta la columna de tamaño («personas» si no se indica): decide el texto de la leyenda «pocos casos». */
  unidad?: string;
}

const celdaDato = (v: string | number | null | undefined): string =>
  v == null ? "—" : typeof v === "number" ? (Number.isInteger(v) ? entero(v) : num(v, 2)) : v;

function TablaDatos({ datos }: { datos: DatosGrafico }) {
  const { columnas, filas, columnaN } = datos;
  const esPocos = (f: (string | number | null)[]) => {
    const n = columnaN == null ? null : f[columnaN];
    return typeof n === "number" && n < POCOS_CASOS;
  };
  return (
    <details className="mt-1 text-xs leading-5 text-[var(--portal-muted)]">
      <summary className="cursor-pointer list-item py-3 font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
        Ver los datos
      </summary>
      <TablaScroll etiqueta="Datos del gráfico">
        <table className="w-full min-w-[20rem] text-left">
          <thead>
            <tr>{columnas.map((c, i) => <th key={i} className={i === 0 ? TH : `${TH} text-right`}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={i} className={FILA}>
                {f.map((v, j) => (
                  <td key={j} className={j === 0 ? TD : `${TD} text-right tabular-nums`}>
                    {celdaDato(v)}{j === 0 && esPocos(f) ? <> <PocosCasos /></> : null}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TablaScroll>
      {filas.some(esPocos) ? <div className="mt-2"><LeyendaPocosCasos unidad={datos.unidad} /></div> : null}
    </details>
  );
}

/** Marco común de un gráfico: borde, relleno y descripción visible para lectores de pantalla. Con `datos`, ofrece «Ver los datos» (tabla plegada). */
export function MarcoGrafico({ children, descripcion, datos, tablaExterna }: {
  children: ReactNode; descripcion?: string; datos?: DatosGrafico;
  /** Título de la tabla plegada que ofrece OTRO elemento (el «Ver los M» de un gráfico recortado): el aviso de fallo remite a ella. */
  tablaExterna?: string;
}) {
  const hayDatos = datos != null && datos.filas.length > 0;
  return (
    <HayTablaContext.Provider value={hayDatos ? "Ver los datos" : tablaExterna ?? null}>
      <figure className="m-0 rounded-md border border-[var(--boveda-linea)] bg-black/10 p-2">
        {children}
        {descripcion ? <figcaption className="sr-only">{descripcion}</figcaption> : null}
        {hayDatos ? <TablaDatos datos={datos} /> : null}
      </figure>
    </HayTablaContext.Provider>
  );
}
