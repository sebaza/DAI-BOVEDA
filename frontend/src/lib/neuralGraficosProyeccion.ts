// Opciones de ECharts de la vista «Lo que viene» (funciones puras: datos -> opción). Sin dependencias del DOM.
// Los datos ya vienen agregados y completos (los grupos de menos de 10 personas traen la marca pocos casos); aquí no se recalcula nada.
// Toda proyección se dibuja como rango: una barra clara de «lo» a «hi» y un punto en el valor central.
import { OPACIDAD_POCOS, esc, marcaPocos } from "./neuralGraficos";
import { PALETA } from "./paleta";

const coma = (v: number, dec = 1) => v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const ent = (v: number) => Math.round(v).toLocaleString("es-CL");
const pc = (v: number, dec = 0) => `${coma(v * 100, dec)} %`;

export const COLOR_UMBRAL = PALETA.adverso;
export const COLOR_CONTINUIDAD = PALETA.favorable;
export const COLOR_ELIMINACION = PALETA.adverso;
export const COLOR_EGRESO = PALETA.serie3;

type Opcion = { option: Record<string, unknown>; alto: number };

// ---------------------------------------------------------------------------
// Umbral: barras de las categorías cercanas al umbral (conteo exacto)
// ---------------------------------------------------------------------------
/** `n`: tamaño del grupo que decide «pocos casos» (el de todo el bloque). */
export interface FilaUmbral { id: string; etiqueta: string; valor: number; pocos: boolean; n?: number }

export function opcionUmbral(filas: readonly FilaUmbral[], ancho: number): Opcion {
  const angosto = ancho > 0 && ancho < 420;
  const max = Math.max(10, ...filas.map((f) => f.valor));
  const option = {
    animation: false,
    grid: { left: 8, right: angosto ? 44 : 56, top: 6, bottom: 6, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = filas[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        return [`<strong>${esc(f.etiqueta)}</strong>`, `${ent(f.valor)} estudiantes${marcaPocos(f.pocos, f.n)}`].join("<br/>");
      },
    },
    xAxis: { type: "value", show: false, max: max * 1.18 },
    yAxis: { type: "category", data: filas.map((f) => f.etiqueta), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: Math.round(Math.min(150, Math.max(84, ancho * 0.36))), overflow: "break" } },
    series: [{
      type: "bar", barMaxWidth: 18, itemStyle: { color: COLOR_UMBRAL, borderRadius: [0, 2, 2, 0] },
      data: filas.map((f) => ({ value: f.valor, itemStyle: { opacity: f.pocos ? OPACIDAD_POCOS : 1 } })),
      label: { show: true, position: "right", color: PALETA.muted, fontSize: 11,
        formatter: (p: { dataIndex: number }) => { const v = filas[p.dataIndex]?.valor; return v == null ? "—" : ent(v); } },
    }],
  };
  return { option, alto: Math.max(120, filas.length * 40 + 16) };
}

// ---------------------------------------------------------------------------
// Rangos por cohorte (continuidad, eliminación y egreso): % del grupo, con barra de lo a hi y punto central
// ---------------------------------------------------------------------------
export interface FilaRango {
  etiqueta: string; n: number; esperados: number; lo: number; hi: number; nota?: string; pocos?: boolean;
}

export function opcionRangos(filas: readonly FilaRango[], ancho: number, color: string, ejeX: string): Opcion {
  const angosto = ancho > 0 && ancho < 420;
  const div = (f: FilaRango, v: number) => (f.n > 0 ? v / f.n : 0);
  const maxX = Math.max(0.05, ...filas.map((f) => div(f, f.hi))) * 1.12;
  const option = {
    animation: false,
    grid: { left: 8, right: 16, top: 8, bottom: 34, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const f = filas[(p as { dataIndex: number }).dataIndex];
        if (!f) return "";
        const l = [
          `<strong>${esc(f.etiqueta)}</strong>`,
          `Estudiantes del grupo: ${ent(f.n)}${marcaPocos(!!f.pocos)}`,
          `Esperado: ${ent(f.esperados)} (${pc(div(f, f.esperados), 1)})`,
          `Entre ${ent(f.lo)} y ${ent(f.hi)} (${pc(div(f, f.lo), 1)} a ${pc(div(f, f.hi), 1)})`,
        ];
        if (f.nota) l.push(esc(f.nota));
        return l.join("<br/>");
      },
    },
    xAxis: { type: "value", min: 0, max: maxX, splitNumber: angosto ? 3 : 5, axisLabel: { formatter: (v: number) => pc(v, 0), hideOverlap: true, fontSize: angosto ? 10 : 11 }, name: ejeX, nameLocation: "middle", nameGap: 24 },
    yAxis: { type: "category", data: filas.map((f) => f.etiqueta), inverse: true, axisTick: { show: false },
      axisLabel: { fontSize: angosto ? 10 : 11, width: Math.round(Math.min(170, Math.max(90, ancho * 0.38))), overflow: "break" } },
    series: [
      { name: "base", type: "bar", stack: "rango", silent: true, tooltip: { show: false }, itemStyle: { color: "transparent" },
        data: filas.map((f) => div(f, f.lo)) },
      { name: "rango", type: "bar", stack: "rango", barMaxWidth: 16, itemStyle: { color, opacity: 0.4, borderRadius: 2 },
        data: filas.map((f) => ({ value: Math.max(0, div(f, f.hi) - div(f, f.lo)), itemStyle: { opacity: f.pocos ? 0.4 * OPACIDAD_POCOS : 0.4 } })) },
      { name: "central", type: "scatter", symbolSize: 9, itemStyle: { color }, z: 5,
        data: filas.map((f) => ({ value: [div(f, f.esperados), f.etiqueta], itemStyle: { opacity: f.pocos ? OPACIDAD_POCOS : 1 } })),
        label: { show: true, position: "top", color: PALETA.muted, fontSize: 11,
          formatter: (p: { dataIndex: number }) => { const f = filas[p.dataIndex]; return f ? pc(div(f, f.esperados), 0) : ""; } } },
    ],
  };
  return { option, alto: Math.max(130, filas.length * 54 + 52) };
}
