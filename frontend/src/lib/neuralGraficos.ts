// Opciones de ECharts de DAI Neural (funciones puras: datos -> opción). Sin dependencias del DOM.
import { PALETA } from "./paleta";

const nf = (v: number, dec = 1) => v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });

/** Escapa texto que viene de la base antes de meterlo en el HTML del tooltip. */
export function esc(s: string | number | null | undefined): string {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);
}

/** Opacidad de las barras y puntos de un grupo de menos de 10 personas («pocos casos»): se ven, pero más claros. */
export const OPACIDAD_POCOS = 0.4;

/** Dato de una serie con su opacidad según el tamaño del grupo (para series de barras o puntos de ECharts). */
export function datoPocos(value: unknown, pocosCasos: boolean): { value: unknown; itemStyle?: { opacity: number } } {
  return pocosCasos ? { value, itemStyle: { opacity: OPACIDAD_POCOS } } : { value };
}

/** Texto de los tooltips para un grupo pequeño: « · pocos casos (n = 7)» (sin `n`, solo « · pocos casos»); vacío si el grupo no es pequeño. */
export function marcaPocos(pocosCasos: boolean, n?: number | null): string {
  if (!pocosCasos) return "";
  return n == null ? " · pocos casos" : ` · pocos casos (n = ${n.toLocaleString("es-CL")})`;
}

// ---------------------------------------------------------------------------
// Banda p25-p75 + mediana de un grupo
// ---------------------------------------------------------------------------
export interface PuntoBanda {
  k: number;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  n: number;
  pocosCasos: boolean;
}

export function opcionBanda(opts: {
  puntos: PuntoBanda[];
  etiquetaY: string;
  decimales: number;
  nombreReferencia: string;
}): Record<string, unknown> {
  const { puntos, etiquetaY, decimales, nombreReferencia } = opts;
  const visible = (p: PuntoBanda) => p.p25 != null && p.p75 != null;
  const cats = puntos.map((p) => String(p.k));
  const base = puntos.map((p) => (visible(p) ? (p.p25 as number) : null));
  const ancho = puntos.map((p) => (visible(p) ? (p.p75 as number) - (p.p25 as number) : null));
  const mediana = puntos.map((p) => (visible(p) ? datoPocos(p.p50, p.pocosCasos) : null));

  const series: Record<string, unknown>[] = [
    { name: "base", type: "line", stack: "banda", data: base, symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, silent: true, tooltip: { show: false } },
    { name: `${nombreReferencia}: rango central (25 % a 75 %)`, type: "line", stack: "banda", data: ancho, symbol: "none", smooth: false, lineStyle: { opacity: 0 }, areaStyle: { color: PALETA.azul, opacity: 0.22 } },
    { name: `${nombreReferencia}: valor central (mediana)`, type: "line", data: mediana, smooth: false, symbol: "circle", symbolSize: 5, lineStyle: { width: 2, color: PALETA.azulClaro }, itemStyle: { color: PALETA.azulClaro } },
  ];
  return {
    animation: false,
    grid: { left: 52, right: 16, top: 36, bottom: 36 },
    legend: { top: 0, data: series.filter((s) => s.name !== "base").map((s) => s.name) },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const arr = params as { dataIndex: number }[];
        const p = puntos[arr[0]?.dataIndex ?? -1];
        if (!p) return "";
        const filas = [`<strong>Semestre ${p.k} desde el ingreso</strong>`];
        const tam = p.pocosCasos ? `pocos casos (n = ${p.n})` : `n = ${p.n}`;
        if (p.p50 == null) filas.push(`${esc(nombreReferencia)}: sin dato (${tam})`);
        else filas.push(`${esc(nombreReferencia)} (${tam}): 25 %: ${nf(p.p25 ?? 0, decimales)} · valor central: ${nf(p.p50, decimales)} · 75 %: ${nf(p.p75 ?? 0, decimales)}`);
        return filas.join("<br/>");
      },
    },
    xAxis: { type: "category", data: cats, boundaryGap: false, name: "Semestres desde el ingreso", nameLocation: "middle", nameGap: 24 },
    yAxis: { type: "value", name: etiquetaY, scale: true },
    series,
  };
}
