// Opciones de ECharts de la vista «Traslados» (funciones puras: datos -> opción). Sin dependencias del DOM.
// Los datos ya vienen agregados y completos (los grupos de menos de 10 personas traen pocos_casos); aquí no se recalcula nada.
import type { BalancePrograma, BalanceAnio, FlujoTraslado, TipoTraslado } from "./neural";
import { OPACIDAD_POCOS, datoPocos, esc, marcaPocos } from "./neuralGraficos";
import { PALETA } from "./paleta";

const nf = (v: number) => v.toLocaleString("es-CL");

export const COLOR_TIPO: Record<TipoTraslado, string> = {
  eleccion_especialidad: PALETA.azulClaro,
  cambio_ciclo: PALETA.serie4,
  continuacion_estudios: PALETA.neutro,
  cambio_carrera: PALETA.adverso,
  traslado_sede: PALETA.serie3,
  traslado_otro: PALETA.tierraClara,
};

export const ETIQUETA_TIPO: Record<TipoTraslado, string> = {
  eleccion_especialidad: "Elección de especialidad",
  cambio_ciclo: "Cambio de ciclo",
  continuacion_estudios: "Continuación tras egreso",
  cambio_carrera: "Cambio de carrera",
  traslado_sede: "Cambio de sede",
  traslado_otro: "Otro traslado",
};

export const TIPOS_ORDEN: readonly TipoTraslado[] = [
  "cambio_carrera", "traslado_otro", "traslado_sede", "eleccion_especialidad", "continuacion_estudios", "cambio_ciclo",
];

export function recortar(texto: string | null | undefined, max = 30): string {
  const t = (texto ?? "").trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

const nombreDe = (nombre: string | null, cod: string) => nombre?.trim() || `Programa ${cod}`;

// ---------------------------------------------------------------------------
// Sankey de los flujos principales. Origen y destino son nodos distintos (un programa puede ser ambos: un
// diagrama de flujo no admite ciclos). El llamador decide cuántos flujos grafica (los más grandes); los demás
// se listan en la tabla. Un flujo de menos de 10 personas se dibuja más claro.
// ---------------------------------------------------------------------------
export interface DisposicionSankey { option: Record<string, unknown>; alto: number; nodos: number }

export function opcionSankey(flujos: readonly FlujoTraslado[], ancho = 0): DisposicionSankey {
  const nodos = new Map<string, { name: string; label: string; depth: number; total: number }>();
  const nodo = (id: string, label: string, depth: number, n: number) => {
    const actual = nodos.get(id);
    if (actual) actual.total += n;
    else nodos.set(id, { name: id, label, depth, total: n });
  };
  const links: Record<string, unknown>[] = [];
  for (const f of flujos) {
    nodo(`o:${f.cod_origen}`, nombreDe(f.nombre_origen, f.cod_origen), 0, f.n);
    nodo(`d:${f.cod_destino}`, nombreDe(f.nombre_destino, f.cod_destino), 1, f.n);
    const tipo = f.tipo_principal;
    links.push({
      source: `o:${f.cod_origen}`, target: `d:${f.cod_destino}`, value: f.n, tipo, pocos: f.pocos_casos,
      lineStyle: { color: tipo ? COLOR_TIPO[tipo] : PALETA.neutro, opacity: f.pocos_casos ? 0.45 * OPACIDAD_POCOS : 0.45 },
    });
  }
  const data = [...nodos.values()].map((n) => ({
    name: n.name, depth: n.depth, label: { formatter: n.label },
    itemStyle: { color: n.depth === 0 ? PALETA.azul : PALETA.serie3, borderColor: "rgba(0,0,0,0.35)" },
    nombreCompleto: n.label,
  }));
  // Las etiquetas se acortan con puntos suspensivos según el ancho disponible; el nombre completo queda en el tooltip.
  const angosto = ancho > 0 && ancho < 560;
  const anchoEtiqueta = ancho > 0 ? Math.round(Math.min(190, Math.max(64, ancho * (angosto ? 0.24 : 0.22)))) : 160;
  const maxPorLado = Math.max(1, ...[0, 1].map((d) => [...nodos.values()].filter((n) => n.depth === d).length));
  const alto = Math.min(900, Math.max(340, maxPorLado * 30 + 60));
  const option = {
    animation: false,
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as { dataType: string; data: { source?: string; target?: string; value?: number; tipo?: TipoTraslado | null; pocos?: boolean; name?: string; nombreCompleto?: string } };
        if (x.dataType === "edge") {
          const o = nodos.get(x.data.source ?? "")?.label ?? "";
          const d = nodos.get(x.data.target ?? "")?.label ?? "";
          const t = x.data.tipo ? ETIQUETA_TIPO[x.data.tipo] : "varios tipos";
          const marca = marcaPocos(!!x.data.pocos);
          return `<strong>${esc(o)}</strong> → <strong>${esc(d)}</strong><br/>${nf(x.data.value ?? 0)} personas · ${esc(t)}${marca}`;
        }
        const total = nodos.get(x.data.name ?? "")?.total ?? 0;
        return `<strong>${esc(x.data.nombreCompleto)}</strong><br/>${nf(total)} personas en los flujos mostrados`;
      },
    },
    series: [{
      type: "sankey", data, links, left: 8, right: anchoEtiqueta + 14, top: 8, bottom: 8, nodeGap: 10, nodeWidth: angosto ? 10 : 14,
      draggable: false, emphasis: { focus: "adjacency" },
      label: { color: PALETA.fg, fontSize: angosto ? 10 : 11, width: anchoEtiqueta, overflow: "truncate", ellipsis: "…" },
      lineStyle: { curveness: 0.5 },
    }],
  };
  return { option, alto, nodos: nodos.size };
}

// ---------------------------------------------------------------------------
// Balance por programa: ganados a la derecha, perdidos a la izquierda y el neto como marca.
// ---------------------------------------------------------------------------
export interface ParBalance { ganados: number; perdidos: number; neto: number }

export function valoresBalance(b: BalancePrograma, sinEleccion: boolean): ParBalance {
  return sinEleccion
    ? { ganados: b.ganados_sin_eleccion, perdidos: b.perdidos_sin_eleccion, neto: b.neto_sin_eleccion }
    : { ganados: b.ganados_total, perdidos: b.perdidos_total, neto: b.neto_total };
}

export function opcionBalance(filas: readonly BalancePrograma[], sinEleccion: boolean, top = 15): { option: Record<string, unknown>; alto: number; n: number } {
  const conDato = filas
    .map((b) => ({ b, v: valoresBalance(b, sinEleccion) }))
    .filter(({ v }) => v.ganados + v.perdidos > 0)
    .sort((a, c) => (c.v.ganados + c.v.perdidos) - (a.v.ganados + a.v.perdidos))
    .slice(0, top);
  const nombres = conDato.map(({ b }) => recortar(nombreDe(b.nombre_programa, b.cod_programa), 28));
  const option = {
    animation: false,
    grid: { left: 8, right: 24, top: 40, bottom: 24, containLabel: true },
    legend: { top: 0, data: ["Ganados", "Perdidos", "Neto"] },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? -1;
        const fila = conDato[i];
        if (!fila) return "";
        const { b, v } = fila;
        return [
          `<strong>${esc(nombreDe(b.nombre_programa, b.cod_programa))}</strong> (${esc(b.cod_programa)})`,
          `Ganados: ${nf(v.ganados)}`,
          `Perdidos: ${nf(v.perdidos)}`,
          `Neto: ${nf(v.neto)}`,
        ].join("<br/>");
      },
    },
    xAxis: { type: "value", axisLabel: { formatter: (v: number) => nf(Math.abs(v)) }, splitLine: { lineStyle: { color: PALETA.linea } } },
    yAxis: { type: "category", data: nombres, inverse: true, axisLabel: { fontSize: 11, width: 150, overflow: "truncate" } },
    series: [
      { name: "Ganados", type: "bar", stack: "flujo", data: conDato.map(({ v }) => v.ganados), itemStyle: { color: PALETA.azul }, barMaxWidth: 16 },
      { name: "Perdidos", type: "bar", stack: "flujo", data: conDato.map(({ v }) => -v.perdidos), itemStyle: { color: PALETA.adverso }, barMaxWidth: 16 },
      {
        name: "Neto", type: "scatter", symbol: "diamond", symbolSize: 10, z: 5, itemStyle: { color: PALETA.serie3, borderColor: "#121314", borderWidth: 1 },
        data: conDato.map(({ v }, i) => [v.neto, i]),
      },
    ],
  };
  return { option, alto: Math.max(220, conDato.length * 28 + 80), n: conDato.length };
}

// ---------------------------------------------------------------------------
// Serie por año (un programa): ganados, perdidos y neto.
// ---------------------------------------------------------------------------
export function opcionBalanceAnios(filas: readonly BalanceAnio[]): Record<string, unknown> {
  return {
    animation: false,
    grid: { left: 48, right: 16, top: 36, bottom: 28 },
    legend: { top: 0, data: ["Ganados", "Perdidos", "Neto"] },
    tooltip: { trigger: "axis", valueFormatter: (v: unknown) => (v == null ? "—" : nf(Number(v))) },
    xAxis: { type: "category", data: filas.map((f) => String(f.anio)) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => nf(v) } },
    series: [
      { name: "Ganados", type: "bar", data: filas.map((f) => f.ganados), itemStyle: { color: PALETA.azul }, barMaxWidth: 22 },
      { name: "Perdidos", type: "bar", data: filas.map((f) => f.perdidos), itemStyle: { color: PALETA.adverso }, barMaxWidth: 22 },
      { name: "Neto", type: "line", data: filas.map((f) => f.neto), itemStyle: { color: PALETA.serie3 }, lineStyle: { width: 2 }, symbolSize: 7, connectNulls: false },
    ],
  };
}

// ---------------------------------------------------------------------------
// Traslados por año y tipo (barras apiladas).
// ---------------------------------------------------------------------------
export function opcionTipoPorAnio(
  filas: readonly { anio: number; tipo: TipoTraslado; n: number; pocos_casos: boolean }[],
): Record<string, unknown> {
  const anios = [...new Set(filas.map((f) => f.anio))].sort((a, b) => a - b);
  const tipos = TIPOS_ORDEN.filter((t) => filas.some((f) => f.tipo === t));
  return {
    animation: false,
    grid: { left: 48, right: 16, top: 56, bottom: 28 },
    legend: { top: 0, type: "scroll", data: tipos.map((t) => ETIQUETA_TIPO[t]) },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const ps = params as { axisValueLabel?: string; marker?: string; seriesName?: string; value?: unknown; data?: { pocos?: boolean; n?: number } }[];
        if (!Array.isArray(ps) || ps.length === 0) return "";
        const filas = ps.map((x) => `${x.marker ?? ""}${esc(x.seriesName)}: ${nf(Number(x.value ?? 0))}${marcaPocos(!!x.data?.pocos, x.data?.n)}`);
        return [`<strong>${esc(ps[0].axisValueLabel)}</strong>`, ...filas].join("<br/>");
      },
    },
    xAxis: { type: "category", data: anios.map(String) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => nf(v) } },
    series: tipos.map((t) => ({
      name: ETIQUETA_TIPO[t], type: "bar", stack: "tipos", itemStyle: { color: COLOR_TIPO[t] }, barMaxWidth: 28,
      data: anios.map((a) => {
        const f = filas.find((x) => x.anio === a && x.tipo === t);
        return f ? { ...datoPocos(f.n, f.pocos_casos), pocos: f.pocos_casos, n: f.n } : 0;
      }),
    })),
  };
}
