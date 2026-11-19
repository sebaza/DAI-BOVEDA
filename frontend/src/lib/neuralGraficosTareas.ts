// Opciones de ECharts y utilidades de las páginas por tarea (T1 a T6) de la vista «Modelos». Funciones puras.
// Solo agregados: métricas, deciles de calibración y tasas por programa o facultad; jamás una persona.
import type { CalibracionTarea, GrupoTarea, ModeloResultado, ModeloTarea, TareaId } from "./neural";
import { OPACIDAD_POCOS, datoPocos, esc, marcaPocos } from "./neuralGraficos";
import type { DefinicionMetrica } from "./neuralGraficosModelos";
import { PALETA } from "./paleta";

const coma = (v: number, dec = 1) => v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const pc = (v: number | null | undefined, dec = 1) => (v == null ? "—" : `${coma(v * 100, dec)} %`);

export const TAREAS: readonly TareaId[] = ["t1", "t2", "t3", "t4", "t5", "t6"];

/** Nombre corto para el selector de tareas y para las tarjetas. */
export const NOMBRE_CORTO: Record<TareaId, string> = {
  t1: "T1 · Continuidad", t2: "T2 · Aprobación por ramo", t3: "T3 · Tiempo hasta egreso",
  t4: "T4 · Cambio de programa", t5: "T5 · Eliminación", t6: "T6 · Postgrado UCN",
};
export const SELECTOR_TAREA: Record<TareaId, string> = {
  t1: "T1 Continuidad", t2: "T2 Aprobación", t3: "T3 Egreso", t4: "T4 Cambio", t5: "T5 Eliminación", t6: "T6 Postgrado",
};

const AP = { id: "ap", etiqueta: "AP", descripcion: "Precisión promedio: qué tan arriba quedan las personas o casos que sí ocurren.", menorEsMejor: false, decimales: 3 };
const AUC = { id: "roc_auc", etiqueta: "ROC-AUC", descripcion: "Probabilidad de ordenar un caso que ocurre por encima de uno que no.", menorEsMejor: false, decimales: 3 };
const BRIER = { id: "brier", etiqueta: "Brier", descripcion: "Error cuadrático de las probabilidades (menor es mejor).", menorEsMejor: true, decimales: 4 };
const ECE = { id: "ece", etiqueta: "ECE", descripcion: "Error de calibración: cuánto se alejan las probabilidades de las frecuencias observadas (menor es mejor).", menorEsMejor: true, decimales: 4 };
const C12 = { id: "c_12", etiqueta: "C(12)", descripcion: "Índice de concordancia a 12 semestres: orden correcto de quién egresa antes.", menorEsMejor: false, decimales: 3 };
const IBS = { id: "ibs", etiqueta: "IBS", descripcion: "Error de Brier integrado a lo largo del tiempo (menor es mejor).", menorEsMejor: true, decimales: 4 };

export const METRICAS_PAGINA: Record<TareaId, DefinicionMetrica[]> = {
  t1: [AP, AUC, BRIER, ECE], t2: [AP, AUC, BRIER, ECE], t3: [C12, IBS],
  t4: [AP, AUC, BRIER, ECE], t5: [AP, AUC, BRIER, ECE], t6: [AP, AUC, BRIER, ECE],
};

export const ETIQUETA_PARTICION: Record<string, string> = {
  train: "Entrenamiento", valid: "Validación", test: "Prueba", posterior: "Control posterior", todas: "Todas las unidades",
};

export const ETIQUETA_BANDA: Record<string, string> = {
  reprobado: "Reprobado", unanimidad: "Aprobado por Unanimidad", distincion: "Aprobado con Distinción",
  maxima_distincion: "Aprobado con Máxima Distinción",
};
export const BANDAS = ["reprobado", "unanimidad", "distincion", "maxima_distincion"] as const;

/** Adapta los modelos de una vista (variante + corte) a la forma que espera la escalera de ablación. */
export function modelosDeVista(modelos: readonly ModeloTarea[], tarea: TareaId, variante: string, corte: number): ModeloResultado[] {
  return modelos
    .filter((m) => m.variante === variante && m.corte_k === corte && Object.keys(m.metricas).length > 0)
    .map((m) => ({
      tarea, corte_k: m.corte_k, modelo: m.modelo, nombre: m.nombre, familia: m.familia, escalon: m.escalon,
      escalon_nombre: m.escalon_nombre, n_evaluacion: m.n_evaluacion, metricas: m.metricas,
    }))
    .sort((a, b) => a.escalon - b.escalon || a.nombre.localeCompare(b.nombre, "es"));
}

// ---------------------------------------------------------------------------
// Calibración: riesgo medio predicho (x) frente a la tasa observada (y) por grupo de riesgo. La diagonal es la calibración perfecta.
// ---------------------------------------------------------------------------
export function opcionCalibracion(
  series: readonly { nombre: string; color: string; puntos: readonly CalibracionTarea[] }[],
  etiquetaGrupo: string,
): { option: Record<string, unknown>; alto: number } {
  const valores = series.flatMap((s) => s.puntos.flatMap((p) => [p.riesgo_medio, p.tasa_observada])).filter((v): v is number => v != null);
  const tope = Math.max(0.02, Math.max(0, ...valores) * 1.08);
  const option = {
    animation: false,
    grid: { left: 8, right: 20, top: 34, bottom: 34, containLabel: true },
    legend: { top: 0, type: "scroll", data: series.map((s) => s.nombre) },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const x = p as { seriesName: string; data: { value: [number, number]; n?: number; decil?: number; pocos?: boolean } };
        if (!x.data?.n) return "";
        return [`<strong>${esc(x.seriesName)}</strong>`, `${etiquetaGrupo} ${x.data.decil}${x.data.pocos ? marcaPocos(true, x.data.n) : ` (n = ${x.data.n.toLocaleString("es-CL")})`}`,
          `Predicho: ${pc(x.data.value[0])}`, `Lo que ocurrió: ${pc(x.data.value[1])}`].join("<br/>");
      },
    },
    xAxis: {
      type: "value", min: 0, max: tope, name: "Riesgo medio predicho", nameLocation: "middle", nameGap: 24,
      axisLabel: { formatter: (v: number) => `${coma(v * 100, v * 100 < 10 ? 1 : 0)} %` }, splitLine: { lineStyle: { color: PALETA.linea } },
    },
    yAxis: {
      type: "value", min: 0, max: tope, name: "Tasa observada", nameLocation: "end",
      axisLabel: { formatter: (v: number) => `${coma(v * 100, v * 100 < 10 ? 1 : 0)} %` }, splitLine: { lineStyle: { color: PALETA.linea } },
    },
    series: [
      ...series.map((s, i) => ({
        name: s.nombre, type: "line", symbol: "circle", symbolSize: 9, lineStyle: { width: 1.5, color: s.color, opacity: 0.7 },
        itemStyle: { color: s.color }, z: 3 + i,
        data: s.puntos.filter((p) => p.riesgo_medio != null && p.tasa_observada != null)
          .map((p) => ({ ...datoPocos([p.riesgo_medio as number, p.tasa_observada as number], p.pocos_casos), n: p.n, decil: p.decil, pocos: p.pocos_casos })),
      })),
      {
        name: "Calibración perfecta", type: "line", symbol: "none", silent: true, tooltip: { show: false },
        lineStyle: { type: "dashed", color: PALETA.subtle, width: 1 }, data: [[0, 0], [tope, tope]], z: 1,
      },
    ],
  };
  return { option, alto: 300 };
}

// ---------------------------------------------------------------------------
// Esperado frente a observado por grupo: un punto observado con su intervalo, un punto esperado y el tramo que los une.
// ---------------------------------------------------------------------------
export const MAX_GRUPOS_GRAFICO = 25;

export interface OpcionesDumbbell {
  mostrarEsperada: boolean; ancho: number; etiquetaEvento: string;
  /** En T2 cada grupo cuenta inscripciones (no personas): el tooltip lo dice así. */
  tarea?: TareaId;
}

/** Intervalo de 95 % de lo observado: el propio del grupo o, si falta, el de la tasa (nulo si no se pudo calcular). */
export function intervaloObservada(g: GrupoTarea): [number, number] | null {
  const lo = g.obs_inf ?? g.tasa_lo, hi = g.obs_sup ?? g.tasa_hi;
  return lo != null && hi != null ? [lo, hi] : null;
}

/** Intervalo de 95 % de lo anticipado por el modelo. */
export function intervaloEsperada(g: GrupoTarea): [number, number] | null {
  const lo = g.esp_inf ?? g.esperado_lo, hi = g.esp_sup ?? g.esperado_hi;
  return lo != null && hi != null ? [lo, hi] : null;
}

export function nombreGrupo(g: GrupoTarea, nivel: string): string {
  return nivel === "programa" ? `${g.nombre} (${g.grupo})` : g.nombre;
}

export function opcionDumbbell(
  grupos: readonly GrupoTarea[], nivel: string, o: OpcionesDumbbell,
): { option: Record<string, unknown>; alto: number; n: number; recortado: boolean } {
  const ordenados = [...grupos].sort((a, b) => b.n - a.n).slice(0, MAX_GRUPOS_GRAFICO)
    .sort((a, b) => (b.observada ?? 0) - (a.observada ?? 0));
  const recortado = grupos.length > ordenados.length;
  const etiquetas = ordenados.map((g) => nombreGrupo(g, nivel));
  const valores = ordenados.flatMap((g) => [g.observada, intervaloObservada(g)?.[0], intervaloObservada(g)?.[1], o.mostrarEsperada ? g.esperada : null])
    .filter((v): v is number => v != null);
  const tope = Math.max(0.02, Math.max(0, ...valores) * 1.1);
  const ancho = Math.round(Math.min(230, Math.max(96, o.ancho * 0.42)));
  const angosto = o.ancho > 0 && o.ancho < 520;
  const data = ordenados.map((g, i) => {
    const io = intervaloObservada(g);
    return {
      value: [i, g.observada ?? 0, io?.[0] ?? g.observada ?? 0, io?.[1] ?? g.observada ?? 0, o.mostrarEsperada ? (g.esperada ?? -1) : -1, g.pocos_casos ? 1 : 0],
    };
  });
  const option = {
    animation: false,
    grid: { left: 8, right: 22, top: 8, bottom: 34, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const g = ordenados[(p as { dataIndex: number }).dataIndex];
        if (!g) return "";
        const ic = (a: number | null, b: number | null) => (a != null && b != null ? ` [${pc(a)}; ${pc(b)}]` : "");
        const filas = [`<strong>${esc(nombreGrupo(g, nivel))}</strong>`];
        if (g.facultad) filas.push(esc(g.facultad));
        filas.push(`${o.tarea === "t2" ? "Inscripciones" : "Personas"}: ${g.n.toLocaleString("es-CL")}${g.eventos != null ? ` · ${g.eventos.toLocaleString("es-CL")} casos` : ""}${marcaPocos(g.pocos_casos)}`);
        const io = intervaloObservada(g), ie = intervaloEsperada(g);
        filas.push(`Lo que ocurrió: ${pc(g.observada)} de ${g.n.toLocaleString("es-CL")}${ic(io?.[0] ?? null, io?.[1] ?? null)}`);
        if (o.mostrarEsperada && g.esperada != null) {
          filas.push(`Lo que anticipó el modelo: ${pc(g.esperada)}${ic(ie?.[0] ?? null, ie?.[1] ?? null)}`);
          if (g.observada != null) filas.push(`Diferencia (anticipado − ocurrido): ${coma((g.esperada - g.observada) * 100, 1)} puntos`);
        }
        return filas.join("<br/>");
      },
    },
    xAxis: {
      type: "value", min: 0, max: tope, name: `Tasa de ${o.etiquetaEvento}`, nameLocation: "middle", nameGap: 24,
      axisLabel: { formatter: (v: number) => `${coma(v * 100, v * 100 < 10 ? 1 : 0)} %` }, splitLine: { lineStyle: { color: PALETA.linea } },
    },
    yAxis: {
      type: "category", data: etiquetas, inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: ancho, overflow: "truncate", ellipsis: "…" },
    },
    series: [{
      type: "custom", data, encode: { x: [1, 2, 3, 4], y: 0 },
      renderItem: (_p: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[] }) => {
        const y = api.value(0);
        const obs = api.coord([api.value(1), y]);
        const lo = api.coord([api.value(2), y]);
        const hi = api.coord([api.value(3), y]);
        const espValor = api.value(4);
        const op = api.value(5) === 1 ? OPACIDAD_POCOS : 1;
        const hijos: Record<string, unknown>[] = [];
        if (espValor >= 0) {
          const esp = api.coord([espValor, y]);
          hijos.push({ type: "line", shape: { x1: obs[0], y1: obs[1], x2: esp[0], y2: esp[1] }, style: { stroke: PALETA.subtle, lineWidth: 2, opacity: 0.8 * op } });
          hijos.push({ type: "rect", shape: { x: esp[0] - 5, y: esp[1] - 5, width: 10, height: 10 }, style: { fill: PALETA.adverso, stroke: "#121314", lineWidth: 1, opacity: op } });
        }
        hijos.push({ type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: PALETA.azulClaro, lineWidth: 1.5, opacity: 0.7 * op } });
        hijos.push({ type: "circle", shape: { cx: obs[0], cy: obs[1], r: 5 }, style: { fill: PALETA.azul, stroke: "#121314", lineWidth: 1, opacity: op } });
        return { type: "group", children: hijos };
      },
    }],
  };
  return { option, alto: Math.max(180, ordenados.length * (angosto ? 28 : 26) + 70), n: ordenados.length, recortado };
}

/** Diferencia esperado − observado en puntos porcentuales ("+1,2"). */
export function textoPuntos(esperada: number | null, observada: number | null): string {
  if (esperada == null || observada == null) return "—";
  const d = (esperada - observada) * 100;
  return `${d > 0 ? "+" : ""}${coma(d, 1)}`;
}
