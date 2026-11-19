"use client";

// Panel «¿Qué tan bien funcionó?»: escalera de ablación con intervalos, comparaciones pareadas y conclusiones.
// Todo agregado (conjunto de prueba). No hay predicciones por persona en ninguna parte de esta vista.
import { useMemo, useState } from "react";

import type { ComparacionModelos, ResumenModelos, TareaModelo, Veredicto } from "../lib/neural";
import {
  COLOR_FAMILIA, ETIQUETA_FAMILIA, METRICAS_TAREA, TITULO_TAREA, cortesDe, modelosDe, opcionEscalera, textoDelta,
} from "../lib/neuralGraficosModelos";
import { limpiarCodigos } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import { FILA, Insignia, MarcoGrafico, Segmentado, TD, TH, TablaScroll, Titulo, Vacio, entero } from "./NeuralUI";

export const TONO: Record<Veredicto, "azul" | "neutro" | "aviso"> = { mejora: "azul", sin_diferencia: "neutro", empeora: "aviso" };
export const TEXTO_VEREDICTO: Record<Veredicto, string> = { mejora: "Mejora", sin_diferencia: "Sin diferencia clara", empeora: "Empeora" };

export function EtiquetaCorte({ tarea, k }: { tarea: TareaModelo; k: number }) {
  if (tarea === "t2") return <>Todos los cursos</>;
  if (tarea === "t3" && k === 0) return <>Al ingreso (k = 0)</>;
  return <>Después de {k} semestre{k === 1 ? "" : "s"} (k = {k})</>;
}

export function Titulares({ datos, tarea, claves }: { datos: ResumenModelos; tarea: TareaModelo; claves?: readonly string[] }) {
  const lista = datos.titulares.filter((t) => t.tarea === tarea && (!claves || claves.some((c) => t.clave.startsWith(c))));
  if (lista.length === 0) return null;
  return (
    <ul className="space-y-2">
      {lista.map((t) => (
        <li key={t.clave} className="flex gap-2 text-sm leading-6 text-[var(--portal-fg)]">
          <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--portal-copper)]" />
          <span>{limpiarCodigos(t.texto)}</span>
        </li>
      ))}
    </ul>
  );
}

export function PanelResultados({
  datos, tarea, resaltar = [], corteInicial,
}: {
  datos: ResumenModelos; tarea: TareaModelo; resaltar?: readonly string[]; corteInicial?: number;
}) {
  const cortes = useMemo(() => cortesDe(datos.modelos, tarea), [datos.modelos, tarea]);
  const [corteElegido, setCorte] = useState<number | null>(corteInicial ?? null);
  const corte = corteElegido != null && cortes.includes(corteElegido) ? corteElegido : (cortes[cortes.length - 1] ?? 0);
  const metricas = METRICAS_TAREA[tarea];
  const [metricaId, setMetrica] = useState(metricas[0].id);
  const def = metricas.find((m) => m.id === metricaId) ?? metricas[0];
  const modelos = useMemo(() => modelosDe(datos.modelos, tarea, corte), [datos.modelos, tarea, corte]);
  const grafico = useMemo(() => (modelos.length ? opcionEscalera(modelos, def, resaltar) : null), [modelos, def, resaltar]);
  const comparaciones = useMemo(() => {
    const nombres = new Map(modelos.map((m) => [m.modelo, m.nombre]));
    return datos.comparaciones
      .filter((c) => c.tarea === tarea && c.corte_k === corte && c.metrica === def.id && nombres.has(c.modelo_a) && nombres.has(c.modelo_b))
      .map((c) => ({ c, a: nombres.get(c.modelo_a) ?? c.modelo_a, b: nombres.get(c.modelo_b) ?? c.modelo_b }));
  }, [datos.comparaciones, modelos, tarea, corte, def.id]);
  const familias = [...new Set(modelos.map((m) => m.familia))];
  const n = modelos[0]?.n_evaluacion ?? null;

  if (modelos.length === 0) return <Vacio titulo="Sin resultados exportados">Aún no hay métricas de esta tarea. Ejecuta el exportador del resumen de modelos.</Vacio>;

  return (
    <div className="space-y-4">
      <Titulo sub={TITULO_TAREA[tarea].pregunta}>¿Qué tan bien funcionó? · {TITULO_TAREA[tarea].corto}</Titulo>
      <div className="flex flex-wrap items-center gap-3">
        {cortes.length > 1 ? (
          <Segmentado
            etiqueta="Momento de la estimación (k)"
            valor={String(corte)}
            onCambio={(v) => setCorte(Number(v))}
            opciones={cortes.map((k) => ({ id: String(k), label: tarea === "t3" && k === 0 ? "Al ingreso" : `k = ${k}` }))}
          />
        ) : null}
        <Segmentado etiqueta="Métrica" valor={def.id} onCambio={setMetrica} opciones={metricas.map((m) => ({ id: m.id, label: m.etiqueta }))} />
      </div>
      <p className="text-xs leading-5 text-[var(--portal-muted)]">
        <strong className="text-[var(--portal-fg)]">{def.etiqueta}</strong>: {def.descripcion} Conjunto de prueba{n ? ` (n = ${entero(n)})` : ""}, <EtiquetaCorte tarea={tarea} k={corte} />.
        Cada punto trae su intervalo del 95 %.
      </p>
      {grafico ? (
        <MarcoGrafico descripcion={`Escalera de ablación: ${def.etiqueta} de cada modelo con su intervalo de confianza.`}>
          <EChartsChart option={grafico.option} height={grafico.alto} ariaLabel={`${def.etiqueta} de cada modelo con su intervalo del 95 %, por escalón de información.`} />
        </MarcoGrafico>
      ) : null}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--portal-muted)]" aria-label="Leyenda de familias">
        {familias.map((f) => (
          <span key={f}><span aria-hidden="true" className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full align-baseline" style={{ background: COLOR_FAMILIA[f] }} />{ETIQUETA_FAMILIA[f] ?? f}</span>
        ))}
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--portal-muted)]">Conclusiones de las pruebas</p>
        <Titulares datos={datos} tarea={tarea} />
      </div>

      {comparaciones.length > 0 ? (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--portal-muted)]">Diferencias pareadas ({def.etiqueta}, A − B)</p>
          <TablaScroll etiqueta="Diferencias pareadas entre modelos">
            <table className="w-full">
              <caption className="sr-only">Diferencia de {def.etiqueta} entre pares de modelos, con su intervalo del 95 %</caption>
              <thead><tr><th className={TH}>A</th><th className={TH}>B</th><th className={TH}>Diferencia [IC 95 %]</th><th className={TH}>Lectura</th></tr></thead>
              <tbody>
                {comparaciones.slice(0, 40).map(({ c, a, b }) => <FilaComparacion key={`${c.modelo_a}-${c.modelo_b}`} c={c} a={a} b={b} dec={def.decimales} />)}
              </tbody>
            </table>
          </TablaScroll>
          <p className="mt-2 text-xs text-[var(--portal-muted)]">Una diferencia es real solo si su intervalo no incluye el cero. Para el error integrado (IBS), menor es mejor.</p>
        </div>
      ) : null}
    </div>
  );
}

export function FilaComparacion({ c, a, b, dec }: { c: Pick<ComparacionModelos, "delta" | "ic_inf" | "ic_sup" | "veredicto">; a: string; b: string; dec: number }) {
  return (
    <tr className={FILA}>
      <td className={TD}>{a}</td><td className={TD}>{b}</td>
      <td className={`${TD} whitespace-nowrap tabular-nums`}>{textoDelta(c, dec)}</td>
      <td className={TD}><Insignia tono={TONO[c.veredicto]}>{TEXTO_VEREDICTO[c.veredicto]}</Insignia></td>
    </tr>
  );
}
