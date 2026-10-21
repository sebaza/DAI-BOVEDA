"use client";

/**
 * Bloque «Qué unidad se mueve de verdad» — volatilidad con el ruido descontado.
 *
 * Vive en la pestaña Comparar, que es donde se comparan unidades entre sí.
 *
 * LO QUE ESTA UI TIENE QUE COMUNICAR, O NO SIRVE
 * ----------------------------------------------
 * 1. **Que la barra NO es la variación observada.** Es lo que queda después de
 *    descontar el ruido de muestreo. Sin eso, el lector piensa que puede reproducir
 *    el número con una desviación estándar, no le da, y desconfía del tablero.
 * 2. **Que "sin señal" no es "estable".** Una unidad cuya variación no supera al
 *    ruido no es tranquila: es indeterminada. Pintarla como la más estable del
 *    ranking sería inventar un hallazgo donde hay falta de evidencia.
 * 3. **Que el ranking no cubre a toda la universidad.** Las unidades sin semanas
 *    suficientes quedan afuera y hay que decir cuántas son.
 *
 * NO usa el filtro global de días: la volatilidad es una propiedad de la serie
 * completa de cada unidad. Medirla sobre 30 días daría 4 puntos por unidad, que no
 * alcanzan para separar señal de ruido.
 */

import { useCallback, useEffect, useState } from "react";

import {
  percepcionApi,
  type UnidadVolatilidad,
  type VolatilidadResponse,
} from "../lib/percepcion";
import { CARD, COLOR_COPPER, SELECT, TituloBloque, fmt, nro } from "./PercepcionUI";

type Nivel = "campus" | "facultad" | "departamento";

const ETIQUETA_NIVEL: Record<Nivel, string> = {
  campus: "Sede",
  facultad: "Facultad",
  departamento: "Departamento",
};

function Fila({ u, maximo }: { u: UnidadVolatilidad; maximo: number }) {
  const real = u.volatilidad_real;
  const ancho = real !== null && maximo > 0 ? Math.max(3, (real / maximo) * 100) : 0;

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-b border-white/5 py-2 last:border-0">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="truncate text-sm text-slate-100" title={u.nombre}>
            {u.nombre}
          </span>
          {!u.evidencia_suficiente ? (
            <span
              className="shrink-0 text-sm text-slate-500"
              title={`Mediana de ${u.n_mediana} comentarios por semana. El ruido ya está descontado, pero la cifra tiene más incertidumbre.`}
            >
              volumen bajo
            </span>
          ) : null}
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
          {real !== null ? (
            <div
              className="h-full rounded-full"
              style={{ width: `${ancho}%`, background: COLOR_COPPER }}
            />
          ) : null}
        </div>
        <div className="mt-1 text-sm text-slate-500">
          {nro(u.semanas)} semanas · mediana {nro(u.n_mediana)} comentarios · índice{" "}
          {fmt(u.indice_medio)} · variación observada {fmt(u.sd_observada)}, de la cual{" "}
          {fmt(u.sd_ruido)} es ruido de muestreo
        </div>
      </div>
      <div className="text-right">
        {real !== null ? (
          <span className="text-lg font-semibold" style={{ color: COLOR_COPPER }}>
            {fmt(real)}
          </span>
        ) : (
          <span
            className="text-sm text-slate-500"
            title="Su variación no supera al ruido de muestreo. No significa que sea estable: significa que con este volumen no se puede afirmar ni una cosa ni la otra."
          >
            sin señal
          </span>
        )}
      </div>
    </div>
  );
}

export function PercepcionVolatilidad() {
  const [nivel, setNivel] = useState<Nivel>("facultad");
  const [data, setData] = useState<VolatilidadResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.volatilidad(nivel));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar la volatilidad.");
    } finally {
      setCargando(false);
    }
  }, [nivel]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const conSenal = (data?.unidades ?? []).filter((u) => u.volatilidad_real !== null);
  const maximo = conSenal.length ? Math.max(...conSenal.map((u) => u.volatilidad_real!)) : 0;

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque
        titulo="Qué unidad se mueve de verdad"
        extra={
          <select
            className={`${SELECT} ml-auto`}
            value={nivel}
            onChange={(e) => setNivel(e.target.value as Nivel)}
          >
            {(Object.keys(ETIQUETA_NIVEL) as Nivel[]).map((n) => (
              <option key={n} value={n}>
                {ETIQUETA_NIVEL[n]}
              </option>
            ))}
          </select>
        }
      >
        Mide cuánto varía el índice de cada unidad semana a semana, <strong>descontando
        lo que se explica solo por tener pocos comentarios</strong>. Una unidad chica
        oscila sola: sin ese descuento, el ranking mediría tamaño de muestra y no
        volatilidad. La barra es lo que queda después de restar ese ruido.
      </TituloBloque>

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      {data && !data.unidades.length && !cargando ? (
        <p className="py-4 text-center text-sm text-slate-500">
          Ninguna {ETIQUETA_NIVEL[nivel].toLowerCase()} tiene semanas suficientes para
          medir volatilidad sin inventar.
        </p>
      ) : null}

      {data?.unidades.map((u) => (
        <Fila key={u.nombre} u={u} maximo={maximo} />
      ))}

      {data?.avisos.length ? (
        <ul className="mt-3 space-y-1 border-t border-white/5 pt-3">
          {data.avisos.map((a) => (
            <li key={a} className="text-sm leading-5 text-slate-500">
              · {a}
            </li>
          ))}
        </ul>
      ) : null}

      {data?.sin_evidencia.length ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm text-slate-500 hover:text-slate-400">
            Ver las {data.sin_evidencia.length} unidades que quedaron fuera
          </summary>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            {data.sin_evidencia.join(" · ")}
          </p>
        </details>
      ) : null}
    </div>
  );
}

export default PercepcionVolatilidad;
