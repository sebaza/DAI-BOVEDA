"use client";

/**
 * Bloque «Conflicto» — va PEGADO al índice en el Resumen, y por un motivo.
 *
 * El índice es un promedio de tono. Dos cosas que un promedio no puede decir, y que
 * son justamente las que un directivo necesita durante un conflicto:
 *
 *   1. CUÁNTOS comentarios adversos hubo. «104 comentarios adversos» es información
 *      distinta de «el índice bajó 4 puntos». Un promedio sobre cientos de mensajes
 *      amables absorbe una decena de mensajes duros sin moverse.
 *   2. CUÁNTO depende ese número de con qué se lo compare.
 *
 * LO SEGUNDO NO ES UN ESCRÚPULO ESTADÍSTICO
 * -----------------------------------------
 * Sobre el episodio "Toma Campus Angamos", comparar contra 21 días decía que el
 * conflicto BAJABA y comparar contra 28 decía que se TRIPLICABA — porque adentro de
 * la segunda ventana caía Fiestas Patrias, una semana de mucho comentario amable.
 *
 * El mismo episodio, dos titulares opuestos, según dónde se ponga un corte que nadie
 * ve. Por eso este bloque barre seis ventanas y **solo afirma algo si el signo aguanta
 * en todas**. Cuando no aguanta, dice "no concluyente" — que es un resultado, no una
 * falla.
 */

import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import { PALETA } from "@/lib/paleta";

import { esCancelacion, percepcionApi, type ConflictoResponse, type Filtro } from "../lib/percepcion";
import { CARD, COLOR_NEG, COLOR_POS, TituloBloque, fmt, nro } from "./PercepcionUI";

const COLOR_TENDENCIA: Record<string, string> = {
  sube: COLOR_NEG,
  baja: COLOR_POS,
  igual: PALETA.neutro,
};

const TITULO_TENDENCIA: Record<string, string> = {
  sube: "El conflicto SUBIÓ",
  baja: "El conflicto bajó",
  igual: "El conflicto se mantiene",
};

export function PercepcionConflicto({ filtro }: { filtro: Filtro }) {
  const [data, setData] = useState<ConflictoResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verBarrido, setVerBarrido] = useState(false);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.conflicto(filtro, opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar la señal de conflicto.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [filtro, nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  if (error && !data) {
    return (
      <div className={CARD}>
        <p className="text-sm text-ucn-tierra-clara">{error}</p>
      </div>
    );
  }
  if (!data?.hay_datos || !data.actual) return null;

  const a = data.actual;
  const tend = data.tendencia;
  const color = data.consistente && tend ? COLOR_TENDENCIA[tend] : PALETA.neutro;

  return (
    <div className={`${CARD} transition-opacity duration-200`} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="Conflicto: cuántos, no cuánto">
        El índice de arriba es un <strong>promedio de tono</strong>: sobre cientos de
        mensajes amables, una decena de mensajes duros no lo mueve. Acá va el volumen
        adverso en crudo, y si su variación se sostiene mirando distintos períodos de
        comparación.
      </TituloBloque>

      <div className="flex flex-wrap items-end gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Comentarios adversos
          </p>
          <p className="text-3xl font-bold" style={{ color }}>
            {nro(a.n_adversos)}
          </p>
          <p className="text-sm text-slate-500">
            {a.pct_adversos !== null ? `${fmt(a.pct_adversos)}% de ${nro(a.n)}` : `de ${nro(a.n)}`}
          </p>
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium" style={{ color }}>
            {data.consistente && tend ? TITULO_TENDENCIA[tend] : "Variación no concluyente"}
          </p>
          {data.explicacion ? (
            <p className="mt-0.5 text-sm leading-5 text-slate-400">{data.explicacion}</p>
          ) : null}
        </div>
      </div>

      {data.comparaciones.length ? (
        <div className="mt-3 border-t border-white/5 pt-2">
          <button
            type="button"
            onClick={() => setVerBarrido((v) => !v)}
            className="toque rounded border border-white/10 px-2.5 py-1 text-sm text-slate-400 transition hover:border-white/25 hover:text-slate-100"
          >
            {verBarrido ? "Ocultar" : `Ver el barrido de ${data.comparaciones.length} períodos`}
          </button>

          {verBarrido ? (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 text-left font-medium">Comparado contra</th>
                    <th className="px-2 py-1 text-right font-medium">n</th>
                    <th className="px-2 py-1 text-right font-medium">% adversos</th>
                    <th className="px-2 py-1 text-right font-medium">Δ adversos</th>
                    <th className="px-2 py-1 text-right font-medium">Δ índice</th>
                  </tr>
                </thead>
                <tbody>
                  {data.comparaciones.map((c) => (
                    <tr key={c.dias_previos} className="border-t border-white/5">
                      <td className="py-1 text-left text-slate-400">
                        los {c.dias_previos} días previos
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-slate-500">
                        {nro(c.n_previo)}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-slate-400">
                        {fmt(c.pct_adversos_previo)}%
                      </td>
                      <td
                        className="px-2 py-1 text-right font-semibold tabular-nums"
                        style={{
                          color:
                            c.signo === "sube" ? COLOR_NEG : c.signo === "baja" ? COLOR_POS : PALETA.neutro,
                        }}
                      >
                        {(c.delta_adversos ?? 0) > 0 ? "+" : ""}
                        {fmt(c.delta_adversos)}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-slate-500">
                        {(c.delta_indice ?? 0) > 0 ? "+" : ""}
                        {fmt(c.delta_indice)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-sm leading-4 text-slate-500">
                Cada fila compara el período actual contra un tramo previo distinto. Si
                la columna «Δ adversos» no mantiene el signo, el resultado depende de
                dónde se ponga el corte y por eso no se afirma.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      {data.avisos.length ? (
        <ul className="mt-2 space-y-1 border-t border-white/5 pt-2">
          {data.avisos.map((av) => (
            <li key={av} className="text-sm leading-5 text-slate-500">
              · {av}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default PercepcionConflicto;
