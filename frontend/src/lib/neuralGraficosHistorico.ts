// Opciones de ECharts de la vista «Lo que pasó» (funciones puras: datos -> opción). Sin dependencias del DOM.
// Los datos ya vienen agregados y completos (los grupos de menos de 10 personas traen la marca pocos casos); aquí no se recalcula nada.
import type {
  HistAlcance, HistAnio, HistCausal, HistCuelloFila, HistEsperadoCifras, HistPerfilDimension, HistPrimerSemestreFila, HistProgramaCausales,
  HistPuntoFacultad, HistRamoFila, HistSemestre, HistSemestreMallaFila, HistSenal, HistTiempoFila,
} from "./neural";
import { OPACIDAD_POCOS, datoPocos, esc, marcaPocos } from "./neuralGraficos";
import { PALETA } from "./paleta";

const coma = (v: number, dec = 1) => v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const pc = (v: number | null | undefined, dec = 1) => (v == null ? "—" : `${coma(v * 100, dec)} %`);
const ent = (v: number) => Math.round(v).toLocaleString("es-CL");
const EJE_PCT = (dec = 0) => ({ formatter: (v: number) => `${coma(v * 100, dec)} %` });

export const COLOR_DEJAN = PALETA.azul;
export const COLOR_ELIMINADOS = PALETA.adverso;
export const COLOR_SIGUIERON = PALETA.favorable;
const SIN_DATO = "sin dato";

// ---------------------------------------------------------------------------
// 1. Barras apiladas por semestre de permanencia
// ---------------------------------------------------------------------------
/** `pocos`: la cohorte (el denominador de todas las filas) tiene menos de 10 estudiantes, así que todas las barras se ven más claras. */
export function opcionSemestres(filas: readonly HistSemestre[], pocos = false, nCohorte?: number | null): { option: Record<string, unknown>; alto: number } {
  const cats = filas.map((f) => String(f.semestre));
  const option = {
    animation: false,
    grid: { left: 8, right: 12, top: 30, bottom: 36, containLabel: true },
    legend: { top: 0, data: ["Deja la UCN", "Eliminado"] },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? -1;
        const f = filas[i];
        if (!f) return "";
        const celda = (n: number | null, p: number | null) => (n == null ? SIN_DATO : `${ent(n)} estudiantes (${pc(p)} de la cohorte)`);
        return [`<strong>Semestre ${f.semestre}${marcaPocos(pocos, nCohorte)}</strong>`, `Deja la UCN: ${celda(f.dejan, f.pct_dejan)}`,
          `Eliminado: ${celda(f.eliminados, f.pct_eliminados)}`].join("<br/>");
      },
    },
    xAxis: { type: "category", data: cats, name: "Semestre desde el ingreso", nameLocation: "middle", nameGap: 26 },
    yAxis: { type: "value", axisLabel: EJE_PCT(0), name: "% de la cohorte", nameLocation: "end", nameGap: 8 },
    series: [
      { name: "Deja la UCN", type: "bar", stack: "bajas", data: filas.map((f) => datoPocos(f.pct_dejan ?? 0, pocos)), itemStyle: { color: COLOR_DEJAN }, barMaxWidth: 26 },
      { name: "Eliminado", type: "bar", stack: "bajas", data: filas.map((f) => datoPocos(f.pct_eliminados ?? 0, pocos)), itemStyle: { color: COLOR_ELIMINADOS }, barMaxWidth: 26 },
    ],
  };
  return { option, alto: 270 };
}

// ---------------------------------------------------------------------------
// 2. Anillo «siguieron» y puntos «ocurrió frente a esperado» por facultad
// ---------------------------------------------------------------------------
export function opcionAnillo(pctSiguieron: number): Record<string, unknown> {
  return {
    animation: false,
    title: { text: pc(pctSiguieron, 0), subtext: "siguieron", left: "center", top: "center", itemGap: 2,
      textStyle: { color: PALETA.fg, fontSize: 24, fontWeight: 700 }, subtextStyle: { color: PALETA.muted, fontSize: 12 } },
    tooltip: { show: false },
    series: [{
      type: "pie", radius: ["64%", "86%"], startAngle: 90, silent: true, label: { show: false }, labelLine: { show: false },
      itemStyle: { borderColor: PALETA.panel, borderWidth: 2 },
      data: [{ value: pctSiguieron, name: "Siguieron", itemStyle: { color: COLOR_SIGUIERON } },
        { value: 1 - pctSiguieron, name: "No siguieron", itemStyle: { color: "rgba(237,237,239,0.14)" } }],
    }],
  };
}

export function opcionPuntosFacultad(
  puntos: readonly HistPuntoFacultad[], seleccionada: string | null, ancho: number,
): { option: Record<string, unknown>; alto: number } {
  const angosto = ancho > 0 && ancho < 520;
  const etiqueta = Math.round(Math.min(210, Math.max(110, ancho * 0.46)));
  const valores = puntos.flatMap((p) => [p.pct_siguieron, p.pct_esperado]);
  const minimo = Math.max(0, Math.floor((Math.min(0.9, ...valores) - 0.02) * 50) / 50);
  const data = puntos.map((p, i) => ({ value: [i, p.pct_siguieron, p.pct_esperado, p.pocos_casos ? 1 : 0] }));
  const option = {
    animation: false,
    grid: { left: 8, right: 22, top: 8, bottom: 34, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = puntos[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        const dif = (f.pct_siguieron - f.pct_esperado) * 100;
        return [`<strong>${esc(f.facultad)}</strong>`, `Estudiantes: ${ent(f.n)}${marcaPocos(f.pocos_casos)}`, `Siguieron: ${pc(f.pct_siguieron)} de ${ent(f.n)}`,
          `El modelo esperaba: ${pc(f.pct_esperado)}`, `Diferencia: ${dif > 0 ? "+" : ""}${coma(dif, 1)} puntos`].join("<br/>");
      },
    },
    xAxis: { type: "value", min: minimo, max: 1, axisLabel: EJE_PCT(0), name: "% que siguió", nameLocation: "middle", nameGap: 24,
      splitLine: { lineStyle: { color: PALETA.linea } } },
    yAxis: {
      type: "category", data: puntos.map((p) => p.facultad), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: etiqueta, overflow: "break", lineHeight: 13,
        color: (v: string) => (seleccionada && v === seleccionada ? PALETA.fg : PALETA.muted) },
    },
    series: [{
      type: "custom", data, encode: { x: [1, 2], y: 0 },
      renderItem: (_p: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[] }) => {
        const y = api.value(0);
        const ocurrio = api.coord([api.value(1), y]);
        const esperado = api.coord([api.value(2), y]);
        const resaltada = seleccionada != null && puntos[y]?.facultad === seleccionada;
        const color = resaltada ? PALETA.azulClaro : COLOR_SIGUIERON;
        const op = api.value(3) === 1 ? OPACIDAD_POCOS : 1;
        return {
          type: "group", children: [
            { type: "line", shape: { x1: ocurrio[0], y1: ocurrio[1], x2: esperado[0], y2: esperado[1] }, style: { stroke: PALETA.subtle, lineWidth: 2, opacity: 0.8 * op } },
            { type: "circle", shape: { cx: esperado[0], cy: esperado[1], r: 5.5 }, style: { fill: "#121314", stroke: color, lineWidth: 2, opacity: op } },
            { type: "circle", shape: { cx: ocurrio[0], cy: ocurrio[1], r: 5.5 }, style: { fill: color, stroke: "#121314", lineWidth: 1, opacity: op } },
          ],
        };
      },
    }],
  };
  return { option, alto: Math.max(190, puntos.length * 40 + 56) };
}

// ---------------------------------------------------------------------------
// 3. Eliminados por año (ocurrido y esperado) y por causal
// ---------------------------------------------------------------------------
/** Línea de totales de eliminados por año calendario, con la marca del reglamento (desde el 2.º semestre de ese año). */
export function opcionTotales(totales: readonly { anio: number; eliminados: number }[], anioReglamento: number): { option: Record<string, unknown>; alto: number } {
  const idx = totales.findIndex((a) => a.anio >= anioReglamento);
  const serie: Record<string, unknown> = {
    name: "Eliminados", type: "line", data: totales.map((a) => a.eliminados), symbol: "circle", symbolSize: 7, smooth: false,
    lineStyle: { width: 3, color: COLOR_ELIMINADOS }, itemStyle: { color: COLOR_ELIMINADOS },
    label: { show: true, position: "top", color: PALETA.muted, fontSize: 10, formatter: (p: { value: number }) => ent(p.value) },
  };
  if (idx >= 0) {
    serie.markLine = {
      silent: true, symbol: "none", lineStyle: { color: PALETA.tierra, type: "dotted", width: 1.5 },
      label: { formatter: `reglamento ${anioReglamento} (desde 202520)`, color: PALETA.tierraClara, position: "insideStartTop", fontSize: 11 },
      data: [{ xAxis: idx }],
    };
  }
  const option = {
    animation: false,
    grid: { left: 8, right: 22, top: 30, bottom: 28, containLabel: true },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const a = totales[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        return a ? `<strong>${a.anio}</strong><br/>${ent(a.eliminados)} estudiantes eliminados` : "";
      },
    },
    xAxis: { type: "category", data: totales.map((a) => String(a.anio)), boundaryGap: false },
    yAxis: { type: "value", min: 0, name: "estudiantes eliminados", nameLocation: "end", nameGap: 8, axisLabel: { formatter: (v: number) => ent(v) } },
    series: [serie],
  };
  return { option, alto: 270 };
}

export function opcionAnios(anios: readonly HistAnio[], anioReglamento: number): { option: Record<string, unknown>; alto: number } {
  const cats = anios.map((a) => String(a.anio));
  const idxReglamento = anios.findIndex((a) => a.anio >= anioReglamento);
  const tope = Math.max(0.02, Math.max(...anios.flatMap((a) => [a.tasa, a.tasa_esperada ?? 0])) * 1.2);
  const hayEsperado = anios.some((a) => a.tasa_esperada != null);
  const observada: Record<string, unknown> = {
    name: "Ocurrió", type: "line", data: anios.map((a) => datoPocos(a.tasa, a.pocos_casos)), symbol: "circle", symbolSize: 7, smooth: false,
    lineStyle: { width: 3, color: COLOR_ELIMINADOS }, itemStyle: { color: COLOR_ELIMINADOS },
  };
  if (idxReglamento >= 0) {
    observada.markLine = {
      silent: true, symbol: "none", lineStyle: { color: PALETA.tierra, type: "dotted", width: 1.5 },
      label: { formatter: `reglamento ${anioReglamento}`, color: PALETA.tierraClara, position: "insideEndTop", fontSize: 11 },
      data: [{ xAxis: idxReglamento }],
    };
  }
  const series: Record<string, unknown>[] = [observada];
  if (hayEsperado) {
    series.push({
      name: "El modelo esperaba", type: "line", data: anios.map((a) => a.tasa_esperada), symbol: "diamond", symbolSize: 8, smooth: false,
      connectNulls: false, lineStyle: { width: 2, type: "dashed", color: PALETA.azulClaro }, itemStyle: { color: PALETA.azulClaro },
    });
  }
  const option = {
    animation: false,
    grid: { left: 8, right: 16, top: 34, bottom: 34, containLabel: true },
    legend: { top: 0, data: series.map((s) => s.name) },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const a = anios[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        if (!a) return "";
        const filas = [`<strong>${a.anio}${a.parcial ? " (año parcial)" : ""}</strong>`,
          `Ocurrió: ${ent(a.eliminados)} de ${ent(a.n)} estudiantes (${pc(a.tasa)})${marcaPocos(a.pocos_casos)}`];
        if (a.esperados != null && a.tasa_esperada != null) filas.push(`El modelo esperaba: ${ent(a.esperados)} (${pc(a.tasa_esperada)})`);
        return filas.join("<br/>");
      },
    },
    xAxis: { type: "category", data: cats, boundaryGap: false },
    yAxis: { type: "value", min: 0, max: tope, axisLabel: EJE_PCT(0), name: "% eliminado", nameLocation: "end", nameGap: 8 },
    series,
  };
  return { option, alto: 260 };
}

/** Orden de las causas en el gráfico (mayor porcentaje primero, «otras» al final); la tabla «Ver los datos» usa el mismo. */
export function ordenarCausales(filas: readonly HistCausal[]): HistCausal[] {
  return [...filas].sort((a, b) => (a.grupo === "otras" || a.grupo === "otros" ? 1 : b.grupo === "otras" || b.grupo === "otros" ? -1 : (b.pct ?? -1) - (a.pct ?? -1)));
}

export function opcionCausales(filas: readonly HistCausal[], ancho: number): { option: Record<string, unknown>; alto: number } {
  const orden = ordenarCausales(filas);
  const angosto = ancho > 0 && ancho < 420;
  const option = {
    animation: false,
    grid: { left: 8, right: angosto ? 44 : 56, top: 6, bottom: 6, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = orden[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        return [`<strong>${esc(f.etiqueta)}</strong>`, f.n == null ? SIN_DATO : `${ent(f.n)} eliminaciones (${pc(f.pct)})`].join("<br/>");
      },
    },
    xAxis: { type: "value", show: false, max: Math.max(0.1, ...orden.map((f) => f.pct ?? 0)) * 1.15 },
    yAxis: { type: "category", data: orden.map((f) => f.etiqueta), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: Math.round(Math.min(150, Math.max(84, ancho * 0.36))), overflow: "break" } },
    series: [{
      type: "bar", barMaxWidth: 16, itemStyle: { color: COLOR_ELIMINADOS, borderRadius: [0, 2, 2, 0] },
      data: orden.map((f, i) => ({ value: f.pct ?? 0, itemStyle: { opacity: f.grupo === "otras" || f.grupo === "otros" ? 0.45 : 1 - Math.min(0.5, i * 0.12) } })),
      label: { show: true, position: "right", color: PALETA.muted, fontSize: 11,
        formatter: (p: { dataIndex: number }) => (orden[p.dataIndex]?.pct == null ? "—" : pc(orden[p.dataIndex].pct, 0)) },
    }],
  };
  return { option, alto: Math.max(170, orden.length * 34 + 16) };
}

// ---------------------------------------------------------------------------
// 4. Curva de alcance
// ---------------------------------------------------------------------------
export function opcionCurva(a: HistAlcance): { option: Record<string, unknown>; alto: number } {
  const x = a.fraccion_apoyo;
  const option = {
    animation: false,
    grid: { left: 8, right: 18, top: 16, bottom: 40, containLabel: true },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const p = (params as { dataIndex: number }[])[0];
        const pt = a.curva[p?.dataIndex ?? -1];
        if (!pt) return "";
        return [`Apoyando al ${pc(pt.apoyados, 0)} de mayor riesgo`, `se alcanza al ${pc(pt.alcanzados, 0)} de quienes no continuaron`,
          `Al azar: ${pc(pt.apoyados, 0)}`].join("<br/>");
      },
    },
    xAxis: { type: "value", min: 0, max: 1, axisLabel: EJE_PCT(0), name: "% de estudiantes apoyados", nameLocation: "middle", nameGap: 26,
      splitLine: { show: false } },
    yAxis: { type: "value", min: 0, max: 1, axisLabel: EJE_PCT(0), name: "% de bajas alcanzadas", nameLocation: "end", nameGap: 8 },
    series: [
      { name: "Con el modelo", type: "line", data: a.curva.map((p) => [p.apoyados, p.alcanzados]), symbol: "none", smooth: false,
        lineStyle: { width: 3, color: COLOR_DEJAN }, areaStyle: { color: COLOR_DEJAN, opacity: 0.12 }, z: 3,
        markPoint: {
          symbol: "circle", symbolSize: 11, itemStyle: { color: COLOR_DEJAN, borderColor: "#121314", borderWidth: 1 },
          label: { show: true, position: "right", distance: 8, color: PALETA.fg, fontSize: 11,
            formatter: `${pc(x, 0)} apoyado → ${pc(a.pct_alcanzado, 0)} alcanzado` },
          data: [{ coord: [x, a.pct_alcanzado] }],
        } },
      { name: "Al azar", type: "line", data: [[0, 0], [1, 1]], symbol: "none", silent: true, tooltip: { show: false },
        lineStyle: { type: "dashed", color: PALETA.subtle, width: 1.5 }, z: 1 },
    ],
  };
  return { option, alto: 270 };
}

// ---------------------------------------------------------------------------
// Temas «Permanencia», «Ramos», «Egreso y causas» y «Cómo decide el modelo»
// ---------------------------------------------------------------------------
type Opcion = { option: Record<string, unknown>; alto: number };

const anchoEtiqueta = (ancho: number, tope = 170) => Math.round(Math.min(tope, Math.max(90, ancho * 0.38)));
const recortar = (s: string, max: number) => (s.length > max ? `${s.slice(0, max - 1)}…` : s);
const REJILLA = { lineStyle: { color: PALETA.linea } };

/** Una dimensión del perfil de ingreso: continuidad ocurrida y esperada por grupo (barras horizontales pareadas). */
export function opcionPerfil(dim: HistPerfilDimension, ancho: number): Opcion {
  const filas = dim.filas;
  const angosto = ancho > 0 && ancho < 460;
  const option = {
    animation: false,
    grid: { left: 8, right: 16, top: 30, bottom: 30, containLabel: true },
    legend: { top: 0, data: ["Siguió", "El modelo esperaba"] },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const f = filas[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        if (!f) return "";
        return [`<strong>${esc(f.etiqueta)}</strong>`, `Estudiantes: ${ent(f.n)}${marcaPocos(f.pocos_casos)}`, `Siguió: ${pc(f.pct_siguieron)} de ${ent(f.n)}`,
          `El modelo esperaba: ${pc(f.pct_esperado)}`].join("<br/>");
      },
    },
    xAxis: { type: "value", min: (v: { min: number }) => Math.max(0, Math.floor((v.min - 0.05) * 20) / 20), max: 1, axisLabel: EJE_PCT(0),
      name: "% que siguió al año siguiente", nameLocation: "middle", nameGap: 24, splitLine: REJILLA },
    yAxis: { type: "category", data: filas.map((f) => f.etiqueta), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho), overflow: "break" } },
    series: [
      { name: "Siguió", type: "bar", data: filas.map((f) => datoPocos(f.pct_siguieron, f.pocos_casos)), itemStyle: { color: COLOR_SIGUIERON }, barMaxWidth: 14 },
      { name: "El modelo esperaba", type: "bar", data: filas.map((f) => ({ value: f.pct_esperado, itemStyle: { opacity: f.pocos_casos ? 0.45 * OPACIDAD_POCOS : 0.45 } })), itemStyle: { color: PALETA.azulClaro, opacity: 0.45 }, barMaxWidth: 14 },
    ],
  };
  return { option, alto: Math.max(170, filas.length * 46 + 70) };
}

/** «3+» -> «3 o más»; «0» -> «Ninguna»; «otros» -> «Otros». */
export function etiquetaReprobaciones(r: string): string {
  if (r === "otros") return "Otros";
  if (r === "0") return "Ninguna";
  return r.endsWith("+") ? `${r.slice(0, -1)} o más` : r;
}

/** Continuidad según las reprobaciones del primer semestre. */
export function opcionPrimerSemestre(filas: readonly HistPrimerSemestreFila[]): Opcion {
  const nombre = etiquetaReprobaciones;
  const option = {
    animation: false,
    grid: { left: 8, right: 12, top: 18, bottom: 40, containLabel: true },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const f = filas[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        return f ? [`<strong>Reprobaciones: ${esc(nombre(f.reprobaciones))}</strong>`, `Estudiantes: ${ent(f.n)}${marcaPocos(f.pocos_casos)}`, `Siguió: ${pc(f.pct_siguieron)} de ${ent(f.n)}`].join("<br/>") : "";
      },
    },
    xAxis: { type: "category", data: filas.map((f) => nombre(f.reprobaciones)), name: "Ramos reprobados en el primer semestre", nameLocation: "middle", nameGap: 26 },
    yAxis: { type: "value", min: 0, max: 1, axisLabel: EJE_PCT(0), name: "% que siguió", nameLocation: "end", nameGap: 8, splitLine: REJILLA },
    series: [{
      type: "bar", data: filas.map((f) => datoPocos(f.pct_siguieron, f.pocos_casos)), itemStyle: { color: COLOR_SIGUIERON }, barMaxWidth: 40,
      label: { show: true, position: "top", color: PALETA.muted, fontSize: 11, formatter: (p: { value: number | null }) => pc(p.value, 0) },
    }],
  };
  return { option, alto: 250 };
}

/** Ramos con mayor reprobación: barras horizontales por porcentaje de reprobados o por cantidad de reprobados. */
/** Fila con la marca «pocos casos» (menos de 10 inscripciones); la calcula el llamador con POCOS_CASOS porque estas filas no traen bandera. */
export type ConPocos<T> = T & { pocos: boolean };

export function opcionRamos(filas: readonly ConPocos<HistRamoFila>[], ancho: number, medida: "tasa" | "reprobados"): Opcion {
  const angosto = ancho > 0 && ancho < 460;
  const valor = (f: HistRamoFila) => (medida === "tasa" ? f.tasa : f.reprobados);
  const conIntervalo = medida === "tasa";
  const textoTasa = (f: ConPocos<HistRamoFila>, dec: number) => (f.lo != null && f.hi != null ? `${pc(f.tasa, dec)} (${pc(f.lo, dec)}–${pc(f.hi, dec)})` : pc(f.tasa, dec));
  const option = {
    animation: false,
    grid: { left: 8, right: conIntervalo ? (angosto ? 112 : 132) : (angosto ? 46 : 58), top: 6, bottom: 6, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = filas[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        return [`<strong>${esc(f.nombre)}</strong>`, f.depto ? `Departamento: ${esc(f.depto)}` : "", `Inscripciones: ${ent(f.intentos)}${marcaPocos(f.pocos)}`,
          `Reprobaciones: ${ent(f.reprobados)} de ${ent(f.intentos)} (${textoTasa(f, 1)}; intervalo de 95 %)`].filter(Boolean).join("<br/>");
      },
    },
    xAxis: { type: "value", show: false, max: Math.max(...filas.map(valor), medida === "tasa" ? 0.1 : 10) * 1.15 },
    yAxis: { type: "category", data: filas.map((f) => recortar(f.nombre, angosto ? 28 : 40)), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho, 220), overflow: "break" } },
    series: [{
      type: "bar", barMaxWidth: 16, data: filas.map((f) => datoPocos(valor(f), f.pocos)), itemStyle: { color: COLOR_ELIMINADOS, borderRadius: [0, 2, 2, 0] },
      label: { show: true, position: "right", color: PALETA.muted, fontSize: 11,
        formatter: (p: { value: number; dataIndex: number }) => {
          const f = filas[p.dataIndex];
          return medida === "tasa" && f ? textoTasa(f, 0) : ent(p.value);
        } },
    }],
  };
  return { option, alto: Math.max(170, filas.length * 34 + 16) };
}

export interface FilaEsperado extends HistEsperadoCifras { nombre: string; pocos: boolean }

/** Reprobados observados menos esperados, con su intervalo: un punto y una línea por ramo o departamento. */
export function opcionEsperado(filas: readonly FilaEsperado[], ancho: number): Opcion {
  const angosto = ancho > 0 && ancho < 460;
  const data = filas.map((f, i) => ({ value: [i, f.diferencia, f.lo, f.hi, f.pocos ? 1 : 0] }));
  const extremo = Math.max(1, ...filas.flatMap((f) => [Math.abs(f.lo), Math.abs(f.hi), Math.abs(f.diferencia)]));
  const option = {
    animation: false,
    grid: { left: 8, right: 22, top: 8, bottom: 34, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = filas[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        return [`<strong>${esc(f.nombre)}</strong>`, `Inscripciones: ${ent(f.intentos)}${marcaPocos(f.pocos)}`, `Reprobaciones: ${ent(f.observados)}`,
          `El modelo esperaba: ${ent(f.esperados)}`, `Diferencia: ${f.diferencia > 0 ? "+" : ""}${ent(f.diferencia)} (rango ${ent(f.lo)} a ${ent(f.hi)})`].join("<br/>");
      },
    },
    xAxis: { type: "value", min: -extremo * 1.1, max: extremo * 1.1, name: "reprobaciones de más (+) o de menos (−) que lo esperado", nameLocation: "middle", nameGap: 24,
      splitLine: REJILLA, axisLabel: { formatter: (v: number) => ent(v) } },
    yAxis: { type: "category", data: filas.map((f) => recortar(f.nombre, angosto ? 26 : 38)), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho, 220), overflow: "break" } },
    series: [{
      type: "custom", data, encode: { x: [1, 2, 3], y: 0 },
      markLine: { silent: true, symbol: "none", lineStyle: { color: PALETA.subtle, type: "dashed", width: 1 }, label: { show: false }, data: [{ xAxis: 0 }] },
      renderItem: (_p: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[] }) => {
        const y = api.value(0);
        const centro = api.coord([api.value(1), y]);
        const lo = api.coord([api.value(2), y]);
        const hi = api.coord([api.value(3), y]);
        const mas = api.value(2) > 0;
        const color = mas ? COLOR_ELIMINADOS : PALETA.azul;
        const op = api.value(4) === 1 ? OPACIDAD_POCOS : 1;
        return {
          type: "group", children: [
            { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: color, lineWidth: 2, opacity: 0.7 * op } },
            { type: "circle", shape: { cx: centro[0], cy: centro[1], r: 5 }, style: { fill: color, stroke: "#121314", lineWidth: 1, opacity: op } },
          ],
        };
      },
    }],
  };
  return { option, alto: Math.max(190, filas.length * 34 + 56) };
}

/** Ramos que frenan el avance: impacto = reprobados × ramos que dependen de él. */
export function opcionCuellos(filas: readonly ConPocos<HistCuelloFila>[], ancho: number): Opcion {
  const angosto = ancho > 0 && ancho < 460;
  const option = {
    animation: false,
    grid: { left: 8, right: angosto ? 50 : 62, top: 6, bottom: 6, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = filas[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        return [`<strong>${esc(f.nombre)}</strong>`, `Reprobaciones: ${ent(f.reprobados)}${marcaPocos(f.pocos)}`, `Ramos que dependen de él: ${ent(f.dependientes)}`,
          `Impacto: ${ent(f.impacto)}`].join("<br/>");
      },
    },
    xAxis: { type: "value", show: false, max: Math.max(1, ...filas.map((f) => f.impacto)) * 1.15 },
    yAxis: { type: "category", data: filas.map((f) => recortar(f.nombre, angosto ? 28 : 40)), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho, 220), overflow: "break" } },
    series: [{
      type: "bar", barMaxWidth: 16, data: filas.map((f) => datoPocos(f.impacto, f.pocos)), itemStyle: { color: PALETA.serie3, borderRadius: [0, 2, 2, 0] },
      label: { show: true, position: "right", color: PALETA.muted, fontSize: 11, formatter: (p: { value: number }) => ent(p.value) },
    }],
  };
  return { option, alto: Math.max(170, filas.length * 34 + 16) };
}

/** Porcentaje de reprobación por semestre de la malla; una cifra sin dato queda como barra vacía. */
export function opcionSemestreMalla(filas: readonly HistSemestreMallaFila[]): Opcion {
  const option = {
    animation: false,
    grid: { left: 8, right: 12, top: 22, bottom: 40, containLabel: true },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const f = filas[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        if (!f) return "";
        return [`<strong>Semestre ${f.semestre} de la malla</strong>`, `Ramos cursados: ${ent(f.intentos)}`,
          f.reprobados == null || f.tasa == null ? `Reprobados: ${SIN_DATO}` : `Reprobados: ${ent(f.reprobados)} de ${ent(f.intentos)} (${pc(f.tasa)})`].join("<br/>");
      },
    },
    xAxis: { type: "category", data: filas.map((f) => String(f.semestre)), name: "Semestre de la malla", nameLocation: "middle", nameGap: 26 },
    yAxis: { type: "value", min: 0, axisLabel: EJE_PCT(0), name: "% de ramos reprobados", nameLocation: "end", nameGap: 8, splitLine: REJILLA },
    series: [{
      type: "bar", data: filas.map((f) => f.tasa), itemStyle: { color: COLOR_ELIMINADOS }, barMaxWidth: 30,
      label: { show: true, position: "top", color: PALETA.muted, fontSize: 10, formatter: (p: { value: number | null }) => (p.value == null ? "—" : pc(p.value, 0)) },
    }],
  };
  return { option, alto: 260 };
}

/** Causas de eliminación por programa: barras horizontales apiladas al 100 % (solo filas con detalle por causa). */
export function opcionCausalesPrograma(filas: readonly HistProgramaCausales[], ancho: number): Opcion {
  const angosto = ancho > 0 && ancho < 460;
  const grupos: { grupo: string; etiqueta: string }[] = [];
  for (const f of filas) for (const c of f.causales ?? []) if (!grupos.some((g) => g.grupo === c.grupo)) grupos.push({ grupo: c.grupo, etiqueta: c.etiqueta });
  grupos.sort((a, b) => (a.grupo === "otros" ? 1 : b.grupo === "otros" ? -1 : 0));
  const colores = [PALETA.adverso, PALETA.azul, PALETA.serie3, PALETA.azulClaro, PALETA.tierraClara, PALETA.neutro];
  const parte = (f: HistProgramaCausales, g: string) => {
    const c = (f.causales ?? []).find((x) => x.grupo === g);
    return c ? c.n / f.total : 0;
  };
  const option = {
    animation: false,
    grid: { left: 8, right: 16, top: 56, bottom: 8, containLabel: true },
    legend: { top: 0, type: "scroll", data: grupos.map((g) => g.etiqueta) },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const f = filas[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        if (!f) return "";
        const lineas = (f.causales ?? []).map((c) => `${esc(c.etiqueta)}: ${ent(c.n)} (${pc(c.n / f.total, 0)})`);
        return [`<strong>${esc(f.programa)}</strong>`, `Eliminaciones: ${ent(f.total)}${marcaPocos(f.pocos_casos)}`, ...lineas].join("<br/>");
      },
    },
    xAxis: { type: "value", min: 0, max: 1, axisLabel: EJE_PCT(0), splitLine: REJILLA },
    yAxis: { type: "category", data: filas.map((f) => recortar(f.programa, angosto ? 26 : 38)), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho, 220), overflow: "break" } },
    series: grupos.map((g, i) => ({
      name: g.etiqueta, type: "bar", stack: "causas", barMaxWidth: 18, data: filas.map((f) => datoPocos(parte(f, g.grupo), f.pocos_casos)),
      itemStyle: { color: colores[i % colores.length] },
    })),
  };
  return { option, alto: Math.max(190, filas.length * 30 + 80) };
}

/** Egreso por programa: porcentaje acumulado dentro de la duración nominal, con 1 y con 2 años de atraso. */
export function opcionTiempo(filas: readonly HistTiempoFila[], ancho: number): Opcion {
  const angosto = ancho > 0 && ancho < 460;
  const nombres = ["A tiempo", "Con 1 año de atraso", "Con 2 años de atraso"];
  const campos = ["pct_a_tiempo", "pct_mas_1", "pct_mas_2"] as const;
  const colores = [COLOR_SIGUIERON, PALETA.serie3, COLOR_ELIMINADOS];
  const option = {
    animation: false,
    grid: { left: 8, right: 16, top: 34, bottom: 30, containLabel: true },
    legend: { top: 0, data: nombres },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const f = filas[(params as { dataIndex: number }[])[0]?.dataIndex ?? -1];
        if (!f) return "";
        return [`<strong>${esc(f.programa)}</strong>`, `Estudiantes: ${ent(f.n)}${marcaPocos(f.pocos_casos)}`, `Duración nominal: ${f.duracion_nominal_sem} semestres`,
          ...campos.map((c, i) => `${nombres[i]}: ${f[c] == null ? SIN_DATO : `${pc(f[c], 0)} de ${ent(f.n)}`}`)].join("<br/>");
      },
    },
    xAxis: { type: "value", min: 0, max: 1, axisLabel: EJE_PCT(0), name: "% que egresa (acumulado)", nameLocation: "middle", nameGap: 24, splitLine: REJILLA },
    yAxis: { type: "category", data: filas.map((f) => recortar(f.programa, angosto ? 26 : 38)), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho, 220), overflow: "break" } },
    series: campos.map((c, i) => ({ name: nombres[i], type: "bar", barMaxWidth: 10, data: filas.map((f) => datoPocos(f[c], f.pocos_casos)), itemStyle: { color: colores[i] } })),
  };
  return { option, alto: Math.max(200, filas.length * 48 + 70) };
}

/** Señales que más pesan en un modelo: porcentaje del peso total (sin signos ni causas). */
export function opcionSenales(senales: readonly HistSenal[], ancho: number): Opcion {
  const angosto = ancho > 0 && ancho < 460;
  const option = {
    animation: false,
    grid: { left: 8, right: angosto ? 46 : 58, top: 6, bottom: 6, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = senales[(p as { dataIndex: number }).dataIndex];
        return f ? [`<strong>${esc(f.etiqueta)}</strong>`, `Pesa ${coma(f.peso_pct, 1)} % de lo que mira el modelo`].join("<br/>") : "";
      },
    },
    xAxis: { type: "value", show: false, max: Math.max(1, ...senales.map((s) => s.peso_pct)) * 1.15 },
    yAxis: { type: "category", data: senales.map((s) => recortar(s.etiqueta, angosto ? 28 : 40)), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: anchoEtiqueta(ancho, 220), overflow: "break" } },
    series: [{
      type: "bar", barMaxWidth: 16, data: senales.map((s) => s.peso_pct), itemStyle: { color: COLOR_DEJAN, borderRadius: [0, 2, 2, 0] },
      label: { show: true, position: "right", color: PALETA.muted, fontSize: 11, formatter: (p: { value: number }) => `${coma(p.value, 0)} %` },
    }],
  };
  return { option, alto: Math.max(150, senales.length * 34 + 16) };
}
