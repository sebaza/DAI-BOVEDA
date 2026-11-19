// Opciones de ECharts y utilidades de la vista «Modelos» (funciones puras). Solo métricas agregadas de benchmarks.
import type { ComparacionModelos, ModeloResultado, ParametroModelo, TareaModelo } from "./neural";
import { esc } from "./neuralGraficos";
import { PALETA } from "./paleta";

const coma = (v: number, dec = 3) => v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });

export const COLOR_FAMILIA: Record<string, string> = {
  referencia: PALETA.neutro,
  regresion: PALETA.serie3,
  arboles: PALETA.azul,
  red: PALETA.adverso,
  red_grafo: PALETA.tierraClara,
};
export const ETIQUETA_FAMILIA: Record<string, string> = {
  referencia: "Referencia (sin modelo)",
  regresion: "Regresión (logística / Cox)",
  arboles: "Árboles (CatBoost)",
  red: "Red neuronal",
  red_grafo: "Red o árboles con grafo curricular",
};

export interface DefinicionMetrica { id: string; etiqueta: string; descripcion: string; menorEsMejor: boolean; decimales: number }

export const METRICAS_TAREA: Record<TareaModelo, DefinicionMetrica[]> = {
  t1: [
    { id: "ap", etiqueta: "AP", descripcion: "Precisión promedio: qué tan arriba quedan las personas que dejan de continuar.", menorEsMejor: false, decimales: 3 },
    { id: "roc_auc", etiqueta: "ROC-AUC", descripcion: "Probabilidad de ordenar a una persona que no continúa por encima de una que sí.", menorEsMejor: false, decimales: 3 },
  ],
  t2: [
    { id: "ap", etiqueta: "AP", descripcion: "Precisión promedio para detectar la reprobación del curso.", menorEsMejor: false, decimales: 3 },
    { id: "roc_auc", etiqueta: "ROC-AUC", descripcion: "Probabilidad de ordenar un intento reprobado por encima de uno aprobado.", menorEsMejor: false, decimales: 3 },
  ],
  t3: [
    { id: "c_12", etiqueta: "C(12)", descripcion: "Índice de concordancia a 12 semestres: orden correcto de quién egresa antes.", menorEsMejor: false, decimales: 3 },
    { id: "ibs", etiqueta: "IBS", descripcion: "Error de Brier integrado: error de las probabilidades a lo largo del tiempo (menor es mejor).", menorEsMejor: true, decimales: 4 },
  ],
};

export const TITULO_TAREA: Record<TareaModelo, { corto: string; pregunta: string }> = {
  t1: { corto: "T1 · Continuidad a un año", pregunta: "¿La persona seguirá matriculada dos períodos regulares después del corte?" },
  t2: { corto: "T2 · Aprobación por intento", pregunta: "¿Aprobará el curso en el período que viene?" },
  t3: { corto: "T3 · Tiempo hasta egreso", pregunta: "¿Cuánto falta para egresar y con qué probabilidad ocurre antes de salir del programa?" },
};

export function valorParametro(arq: readonly ParametroModelo[], tarea: TareaModelo, corte: number, modelo: string, clave: string): number | null {
  return arq.find((a) => a.tarea === tarea && a.corte_k === corte && a.modelo === modelo && a.clave === clave)?.valor_num ?? null;
}

/** Constante tomada del código del modelo (corte_k = -1 en la tabla de arquitectura). */
export function valorCodigo(arq: readonly ParametroModelo[], modelo: string, clave: string): number | null {
  return arq.find((a) => a.corte_k === -1 && a.modelo === modelo && a.clave === clave)?.valor_num ?? null;
}

export function textoCodigo(arq: readonly ParametroModelo[], modelo: string, clave: string): string | null {
  return arq.find((a) => a.corte_k === -1 && a.modelo === modelo && a.clave === clave)?.valor_texto ?? null;
}

export function modelosDe(modelos: readonly ModeloResultado[], tarea: TareaModelo, corte: number): ModeloResultado[] {
  return modelos
    .filter((m) => m.tarea === tarea && m.corte_k === corte && m.metricas && Object.keys(m.metricas).length > 0)
    .slice()
    .sort((a, b) => a.escalon - b.escalon || a.nombre.localeCompare(b.nombre, "es"));
}

export function cortesDe(modelos: readonly ModeloResultado[], tarea: TareaModelo): number[] {
  return [...new Set(modelos.filter((m) => m.tarea === tarea).map((m) => m.corte_k))].sort((a, b) => a - b);
}

export function comparar(comp: readonly ComparacionModelos[], tarea: TareaModelo, corte: number, a: string, b: string, metrica: string): ComparacionModelos | undefined {
  return comp.find((c) => c.tarea === tarea && c.corte_k === corte && c.modelo_a === a && c.modelo_b === b && c.metrica === metrica);
}

// ---------------------------------------------------------------------------
// Escalera de ablación: un punto con su intervalo del 95 % por modelo, agrupado por escalón.
// ---------------------------------------------------------------------------
export function opcionEscalera(
  modelos: readonly ModeloResultado[], def: DefinicionMetrica, resaltar: readonly string[] = [], ancho = 0,
): { option: Record<string, unknown>; alto: number; n: number } {
  const filas = modelos.filter((m) => m.metricas[def.id]?.valor != null);
  const nombres = filas.map((m) => `${m.escalon}· ${m.nombre}`);
  const valores = filas.flatMap((m) => {
    const x = m.metricas[def.id];
    return [x.valor, x.ic_inf, x.ic_sup].filter((v): v is number => v != null);
  });
  const min = Math.min(...valores), max = Math.max(...valores);
  // En pantallas angostas las etiquetas se parten en líneas (no se cortan) y cada fila gana altura.
  const angosto = ancho > 0 && ancho < 520;
  const anchoEtiqueta = angosto ? Math.max(96, Math.round(ancho * 0.4)) : 200;
  const margen = Math.max((max - min) * 0.08, 0.005);
  const data = filas.map((m, i) => {
    const x = m.metricas[def.id];
    return {
      value: [i, x.valor, x.ic_inf ?? x.valor, x.ic_sup ?? x.valor],
      itemStyle: { color: COLOR_FAMILIA[m.familia] ?? PALETA.neutro, opacity: resaltar.length === 0 || resaltar.includes(m.modelo) ? 1 : 0.4 },
    };
  });
  const option = {
    animation: false,
    grid: { left: 8, right: 28, top: 12, bottom: 30, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const i = (p as { dataIndex: number }).dataIndex;
        const m = filas[i];
        const x = m?.metricas[def.id];
        if (!m || !x || x.valor == null) return "";
        const ic = x.ic_inf != null && x.ic_sup != null ? ` [${coma(x.ic_inf, def.decimales)}; ${coma(x.ic_sup, def.decimales)}]` : "";
        return [
          `<strong>${esc(m.nombre)}</strong>`,
          `${esc(m.escalon_nombre)}`,
          `${def.etiqueta}: ${coma(x.valor, def.decimales)}${ic}`,
          m.n_evaluacion ? `n de evaluación: ${m.n_evaluacion.toLocaleString("es-CL")}` : "",
        ].filter(Boolean).join("<br/>");
      },
    },
    xAxis: {
      type: "value", min: Math.max(0, min - margen), max: max + margen, name: def.etiqueta, nameLocation: "middle", nameGap: 24,
      axisLabel: { formatter: (v: number) => coma(v, def.decimales > 3 ? 3 : 2) }, splitLine: { lineStyle: { color: PALETA.linea } },
    },
    yAxis: {
      type: "category", data: nombres, inverse: true, axisTick: { show: false },
      axisLabel: angosto ? { fontSize: 10, width: anchoEtiqueta, overflow: "break", lineHeight: 12 } : { fontSize: 11, width: anchoEtiqueta, overflow: "truncate" },
    },
    series: [{
      type: "custom", data, encode: { x: [1, 2, 3], y: 0 },
      renderItem: (_p: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[]; visual: (k: string) => string }) => {
        const y = api.value(0);
        const lo = api.coord([api.value(2), y]);
        const hi = api.coord([api.value(3), y]);
        const pt = api.coord([api.value(1), y]);
        const color = api.visual("color");
        return {
          type: "group",
          children: [
            { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: color, lineWidth: 2 } },
            { type: "line", shape: { x1: lo[0], y1: lo[1] - 5, x2: lo[0], y2: lo[1] + 5 }, style: { stroke: color, lineWidth: 2 } },
            { type: "line", shape: { x1: hi[0], y1: hi[1] - 5, x2: hi[0], y2: hi[1] + 5 }, style: { stroke: color, lineWidth: 2 } },
            { type: "circle", shape: { cx: pt[0], cy: pt[1], r: 5 }, style: { fill: color, stroke: "#121314", lineWidth: 1 } },
          ],
        };
      },
    }],
  };
  return { option, alto: Math.max(200, filas.length * (angosto ? 46 : 30) + 70), n: filas.length };
}

export function textoIntervalo(v: number | null, lo: number | null, hi: number | null, dec = 3): string {
  if (v == null) return "—";
  return lo != null && hi != null ? `${coma(v, dec)} [${coma(lo, dec)}; ${coma(hi, dec)}]` : coma(v, dec);
}

export function textoDelta(c: Pick<ComparacionModelos, "delta" | "ic_inf" | "ic_sup"> | undefined, dec = 3): string {
  if (!c || c.delta == null) return "—";
  return textoIntervalo(c.delta, c.ic_inf, c.ic_sup, dec);
}
