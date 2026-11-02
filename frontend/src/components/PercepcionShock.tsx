"use client";

/**
 * Bloque «Qué pasa cuando hay un paro» (pregunta C del plan de simulación).
 *
 * LO QUE ESTE BLOQUE NO MUESTRA, Y ES LO IMPORTANTE
 * -------------------------------------------------
 * No muestra un promedio. La respuesta que un directivo querría —«un paro cuesta X
 * puntos y se recupera en Y semanas»— no se puede dar: hay diez episodios en el
 * calendario, pero la ingesta tiene volumen recién desde fines de 2024 y la mayoría
 * quedó sin comentarios alrededor. Promediar un caso medible con nueve vacíos produce
 * un número con aspecto de resultado.
 *
 * Entonces muestra CASOS, cada uno con su evidencia declarada, y dice cuántos no se
 * pudieron medir. Que la lista de «sin datos» sea larga no es un defecto de la vista:
 * es el estado real del conocimiento, y esconderlo sería el defecto.
 *
 * DOS DISTINCIONES QUE LA UI NO PUEDE APLASTAR
 * --------------------------------------------
 * * **«No recuperó» ≠ «no medible».** La primera es un hallazgo: el episodio dejó
 *   huella. La segunda es falta de datos. Pintarlas igual convertiría una ausencia
 *   de información en una conclusión.
 * * **Fechas confirmadas ≠ estimadas.** Sobre una fecha aproximada se puede leer la
 *   caída con cuidado, pero no la duración ni la velocidad de recuperación.
 */

import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import { esCancelacion, percepcionApi, type EpisodioShock, type ShockResponse } from "../lib/percepcion";
import { CARD, COLOR_NEG, COLOR_POS, TituloBloque, fmt, nro } from "./PercepcionUI";

const ETIQUETA_EVIDENCIA: Record<string, string> = {
  suficiente: "medible",
  parcial: "parcial",
  insuficiente: "sin datos alrededor",
};

function Caso({ e }: { e: EpisodioShock }) {
  const medible = e.evidencia === "suficiente";
  const estimado = e.confianza !== "confirmado";

  return (
    <div className="border-b border-white/5 py-2.5 last:border-0">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-sm text-slate-500">
          {e.desde}
          {e.hasta && e.hasta !== e.desde ? ` → ${e.hasta}` : ""}
        </span>
        <span className="text-sm text-slate-100">{e.nombre}</span>
        {e.ambito && e.ambito !== "global" ? (
          <span className="text-sm text-slate-500">· {e.ambito}</span>
        ) : null}
        <span
          className={`text-sm ${medible ? "text-dato-favorable" : "text-slate-500"}`}
          title={
            medible
              ? "Tiene volumen suficiente antes y durante para medir el efecto."
              : "No hay comentarios suficientes alrededor: no se puede medir el efecto."
          }
        >
          {ETIQUETA_EVIDENCIA[e.evidencia] ?? e.evidencia}
        </span>
        {estimado ? (
          <span
            className="text-sm text-ucn-tierra-clara"
            title="Fechas aproximadas: la caída se puede leer con cuidado, la duración y la recuperación no."
          >
            fechas estimadas
          </span>
        ) : null}
      </div>

      {e.componentes.length > 1 ? (
        <p className="mt-0.5 text-sm text-slate-500">
          Un solo shock, cargado en {e.componentes.length} partes: {e.componentes.join(" + ")}
        </p>
      ) : null}

      {medible ? (
        <>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span className="text-sm text-slate-400">
              antes <strong className="text-slate-100">{fmt(e.indice_previo)}</strong>
              {" → "}
              durante <strong className="text-slate-100">{fmt(e.indice_durante)}</strong>
            </span>
            <span
              className="text-lg font-semibold"
              style={{ color: (e.caida ?? 0) < 0 ? COLOR_NEG : COLOR_POS }}
            >
              {(e.caida ?? 0) > 0 ? "+" : ""}
              {fmt(e.caida)}
            </span>
            {e.dias ? <span className="text-sm text-slate-500">{nro(e.dias)} días</span> : null}
          </div>
          <p className="mt-0.5 text-sm leading-5 text-slate-400">
            {e.recuperado_en_semanas ? (
              <>
                Volvió al nivel previo y se sostuvo a partir de la semana{" "}
                <strong className="text-slate-100">{e.recuperado_en_semanas}</strong>.
              </>
            ) : (
              <span className="text-slate-500">{e.motivo_recuperacion}</span>
            )}
          </p>
        </>
      ) : null}
    </div>
  );
}

/**
 * Vista de BARRIDO de los episodios medibles. Las tarjetas de abajo siguen teniendo el
 * detalle (ventanas, recuperación); acá se ven los seis casos de un vistazo.
 *
 * La columna que más informa es la de ADVERSOS, y no el índice. «Toma pabellón +19,0»
 * parece un resultado hasta que se ve que tuvo 2 comentarios adversos de 47: esa
 * variación no midió el conflicto, midió el posteo normal de esas semanas. Por eso las
 * filas con menos de 3 adversos van atenuadas.
 */
function TablaEpisodios({ episodios }: { episodios: EpisodioShock[] }) {
  if (!episodios.length) return null;
  return (
    <div className="mb-3 overflow-x-auto rounded-md border border-white/10 bg-white/[0.02]">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500">
            <th className="px-3 py-2 text-left font-medium uppercase tracking-wide">Episodio</th>
            <th className="px-2 py-2 text-right font-medium uppercase tracking-wide">n</th>
            <th
              className="bg-white/[0.06] px-2 py-2 text-right font-semibold uppercase tracking-wide text-slate-400"
              title="Índice de la ventana con el peso por tema. Es el principal. El crédito de un tema que no es mérito de la UCN (mascotas, vida estudiantil, organización estudiantil) cuenta la mitad; el daño de un negativo cuenta entero."
            >
              Índice
            </th>
            <th
              className="px-2 py-2 text-right font-medium uppercase tracking-wide"
              title="El mismo cálculo sin pesos por tema: el número con el que se leyó la serie histórica."
            >
              Sin pesos
            </th>
            <th
              className="px-2 py-2 text-right font-medium uppercase tracking-wide"
              title="Solo los canales donde la crítica existe. 19 cuentas nunca recibieron un negativo en cuatro años."
            >
              Crítico
            </th>
            <th
              className="px-2 py-2 text-right font-medium uppercase tracking-wide"
              title="Volumen crudo de comentarios adversos. Es lo que un promedio esconde."
            >
              Adversos
            </th>
            <th className="px-2 py-2 text-right font-medium uppercase tracking-wide">Δ</th>
            <th
              className="px-3 py-2 text-right font-medium uppercase tracking-wide"
              title="La misma variación con la mezcla de cuentas fija: descuenta el cambio de quién comenta."
            >
              Δ sin mezcla
            </th>
          </tr>
        </thead>
        <tbody>
          {episodios.map((e) => {
            // Menos de 3 adversos: la variación no mide el conflicto.
            const flaco = (e.n_adversos ?? 0) < 3;
            return (
              <tr key={e.nombre} className="border-t border-white/5" style={{ opacity: flaco ? 0.5 : 1 }}>
                <td className="px-3 py-2 text-left text-slate-400">{e.nombre}</td>
                <td className="px-2 py-2 text-right tabular-nums text-slate-500">
                  {e.n_adversos !== null && e.pct_adversos !== null && e.pct_adversos > 0
                    ? nro(Math.round((e.n_adversos * 100) / e.pct_adversos))
                    : "—"}
                </td>
                <td className="bg-white/[0.06] px-2 py-2 text-right font-semibold tabular-nums text-slate-100">
                  {fmt(e.indice_ponderado)}
                </td>
                <td className="px-2 py-2 text-right tabular-nums text-slate-500">
                  {fmt(e.indice_durante)}
                </td>
                <td className="px-2 py-2 text-right tabular-nums text-slate-400">
                  {fmt(e.indice_critico)}
                </td>
                <td
                  className="px-2 py-2 text-right tabular-nums"
                  style={{ color: flaco ? undefined : COLOR_NEG }}
                >
                  {e.n_adversos ?? "—"}
                  {e.pct_adversos !== null ? (
                    <span className="ml-1 text-slate-500">{fmt(e.pct_adversos)}%</span>
                  ) : null}
                </td>
                <td
                  className="px-2 py-2 text-right tabular-nums"
                  style={{ color: (e.caida ?? 0) < 0 ? COLOR_NEG : COLOR_POS }}
                >
                  {(e.caida ?? 0) > 0 ? "+" : ""}
                  {fmt(e.caida)}
                </td>
                <td
                  className="px-3 py-2 text-right tabular-nums"
                  style={{ color: (e.caida_estandarizada ?? 0) < 0 ? COLOR_NEG : COLOR_POS }}
                >
                  {e.caida_estandarizada === null ? "—" : (
                    <>
                      {(e.caida_estandarizada ?? 0) > 0 ? "+" : ""}
                      {fmt(e.caida_estandarizada)}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="px-3 pb-2 pt-1 text-sm leading-4 text-slate-500">
        Las filas atenuadas tienen menos de 3 comentarios adversos: su variación no mide
        el conflicto, mide el posteo normal de esas semanas.
      </p>
    </div>
  );
}

export function PercepcionShock() {
  const [data, setData] = useState<ShockResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verTodos, setVerTodos] = useState(false);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.shock(false, opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar la respuesta a shock.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const medibles = (data?.episodios ?? []).filter((e) => e.evidencia !== "insuficiente");
  const resto = (data?.episodios ?? []).filter((e) => e.evidencia === "insuficiente");

  return (
    <div className={`${CARD} transition-opacity duration-200`} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="Qué pasa cuando hay un paro">
        Cuánto cae el índice durante una interrupción y cuánto tarda en volver, medido
        en la sede donde ocurrió. Son <strong>casos</strong>, no un promedio: la mayoría
        de los episodios del calendario no tiene comentarios alrededor con los cuales
        medir nada.
      </TituloBloque>

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      {data ? (
        <>
          <div className="mb-2 flex flex-wrap gap-2">
            <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Episodios del calendario
              </p>
              <p className="text-lg font-semibold text-slate-100">{nro(data.total)}</p>
            </div>
            <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Medibles</p>
              <p className="text-lg font-semibold" style={{ color: COLOR_POS }}>
                {nro(data.medibles)}
              </p>
              <p className="max-w-[16rem] text-sm leading-4 text-slate-500">
                con {data.n_min_por_semana}+ comentarios por semana antes y durante
              </p>
            </div>
            {data.caida_rango ? (
              <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Rango de caída
                </p>
                <p className="text-lg font-semibold" style={{ color: COLOR_NEG }}>
                  {fmt(data.caida_rango[0])} a {fmt(data.caida_rango[1])}
                </p>
              </div>
            ) : null}
          </div>

          <TablaEpisodios episodios={medibles} />

          {medibles.map((e) => (
            <Caso key={`${e.nombre}-${e.desde}`} e={e} />
          ))}

          {resto.length ? (
            <div className="mt-2 border-t border-white/5 pt-2">
              <button
                type="button"
                onClick={() => setVerTodos((v) => !v)}
                className="rounded border border-white/10 px-2.5 py-1 text-sm text-slate-400 transition hover:border-white/25 hover:text-slate-100"
              >
                {verTodos ? "Ocultar" : `Ver los ${resto.length} episodios sin datos alrededor`}
              </button>
              {verTodos ? (
                <div className="mt-1">
                  {resto.map((e) => (
                    <Caso key={`${e.nombre}-${e.desde}`} e={e} />
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {data.avisos.length ? (
            <ul className="mt-3 space-y-1 border-t border-white/5 pt-2">
              {data.avisos.map((a) => (
                <li key={a} className="text-sm leading-5 text-slate-500">
                  · {a}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default PercepcionShock;
