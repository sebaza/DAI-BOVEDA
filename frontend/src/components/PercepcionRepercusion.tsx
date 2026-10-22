"use client";

/**
 * REPERCUSIÓN — qué parte de los comentarios etiqueta a otras personas.
 *
 * Etiquetar es llamar a otros a la conversación: un post con muchas etiquetas movió a la
 * gente a compartirlo, aunque los comentarios no digan nada. Por eso no es opinión y el
 * subtema «Etiquetan a otras personas» no entra en el sentimiento, pero sí es una señal.
 *
 * Solo conteos (la API no envía texto ni handles). Es una COTA INFERIOR: los handles de
 * solo letras escritos sin «@» no se pueden detectar.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import type { Filtro, RepercusionResponse } from "../lib/percepcion";
import { esCancelacion, percepcionApi } from "../lib/percepcion";
import { PALETA } from "../lib/paleta";
import { EChartsChart } from "./EChartsChart";
import { CARD, TituloBloque, nro } from "./PercepcionUI";

const TOP = 5;

function opcionSemanas(data: RepercusionResponse): Record<string, unknown> {
  return {
    tooltip: { trigger: "axis", valueFormatter: (v: number) => `${v}%` },
    grid: { left: 8, right: 12, top: 10, bottom: 4, containLabel: true },
    xAxis: { type: "category", data: data.semanas.map((s) => s.semana.slice(5)), axisLabel: { fontSize: 12 } },
    yAxis: { type: "value", min: 0, axisLabel: { fontSize: 12, formatter: "{value}%" } },
    series: [
      {
        type: "line",
        data: data.semanas.map((s) => s.porcentaje),
        showSymbol: false,
        lineStyle: { color: PALETA.azul, width: 2 },
        itemStyle: { color: PALETA.azul },
      },
    ],
  };
}

export function PercepcionRepercusion({ filtro }: { filtro: Filtro }) {
  const [data, setData] = useState<RepercusionResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async (f: Filtro) => {
    const ctrl = nueva();
    setCargando(true);
    try {
      setData(await percepcionApi.repercusion(f, TOP, { signal: ctrl.signal }));
      setError(null);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => { void cargar(filtro); }, [cargar, filtro]);

  const opcion = useMemo(
    () => (data && data.semanas.length > 1 ? opcionSemanas(data) : null),
    [data],
  );
  const hay = !!data && data.disponible && data.comentarios > 0;

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="Repercusión">
        Parte de los comentarios que etiquetan a otras personas: llaman a otros a la
        conversación.
      </TituloBloque>

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      {hay && data ? (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div>
            <div className="text-[32px] font-semibold leading-none tabular-nums text-slate-100">
              {data.porcentaje.toLocaleString("es-CL")}%
            </div>
            <p className="mt-2 text-sm leading-5 text-slate-400">
              {nro(data.con_etiqueta)} de {nro(data.comentarios)} comentarios.{" "}
              {nro(data.solo_etiquetas)} solo etiquetan.
            </p>
            <p className="mt-1 text-xs text-slate-500">Es un mínimo: no se detectan todas las etiquetas.</p>
          </div>
          <div className="min-w-0">
            {opcion ? (
              <EChartsChart option={opcion} height={140} ariaLabel="Comentarios con etiquetas por semana" />
            ) : null}
          </div>
          {data.publicaciones.length > 0 ? (
            <ul className="space-y-1 md:col-span-2">
              {data.publicaciones.map((p) => (
                <li
                  key={p.publicacion_id}
                  className="flex flex-wrap items-baseline justify-between gap-x-4 rounded border border-white/5 bg-white/[0.02] px-3 py-1.5 text-sm text-slate-400"
                >
                  <span className="min-w-0 flex-1 truncate">
                    {p.fecha ?? "—"} · {p.cuenta ?? "(cuenta sin nombre)"}
                  </span>
                  <span className="shrink-0 tabular-nums">
                    <strong className="text-slate-100">{p.porcentaje.toLocaleString("es-CL")}%</strong>
                    {" · "}{nro(p.con_etiqueta)} de {nro(p.n_comentarios)}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : !cargando && !error ? (
        <p className="py-6 text-center text-sm text-slate-500">
          {data && !data.disponible
            ? "Aún no hay datos de repercusión: falta precalcular los derivados."
            : "Sin comentarios en este período."}
        </p>
      ) : null}
    </div>
  );
}

export default PercepcionRepercusion;
