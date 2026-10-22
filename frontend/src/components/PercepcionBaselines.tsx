"use client";

/**
 * Bloque «La vara» — los baselines que cualquier simulación debe superar (pregunta A).
 *
 * LO QUE ESTE BLOQUE NO ES
 * ------------------------
 * No es un pronóstico. Nadie debería mirar acá para saber cómo va a estar la semana
 * que viene. Es un instrumento de decisión de proyecto: dice cuánto acierta lo más
 * tonto que se puede hacer, para poder responder si vale la pena construir algo más.
 *
 * LAS DOS LÍNEAS QUE HAY QUE LEER PRIMERO
 * ---------------------------------------
 * * **Error irreducible** — el ruido de muestreo del propio índice. Ningún modelo
 *   puede bajar de ahí, pero ⚠️ TAMPOCO ES EL TECHO ALCANZABLE: mide el error de
 *   medición, no lo impredecible, y confundirlos infla el margen aparente unas cuatro
 *   veces. La cota real se midió en la fase 2 (MAE 6,22, ver abajo).
 * * **Decir siempre el promedio** — el desvío de la serie. Un modelo que erra más
 *   que esto es peor que no pensar.
 *
 * LO QUE LA FASE 2 DEJÓ ACÁ (08-09-2026)
 * --------------------------------------
 * El modelo poblacional que pedía el plan se midió y NO supera la vara (7,50-7,71
 * contra 6,82), así que por la regla del proyecto no se integró. Lo que sí mejoró fue
 * el camino contrario: un `suavizado` exponencial de UN parámetro, que ahora es el
 * mejor baseline y subió la vara de 7,31 a 6,82.
 *
 * Con la cota in-sample en 6,22 quedan ~0,6 puntos de margen efectivo, y lo mínimo
 * demostrable con 74 semanas es 0,58. Un modelo que alcanzara la cota sería
 * indistinguible del ruido: por eso el plan se cierra acá y no sigue a agentes
 * generativos. Detalle en `INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md` §0.
 */

import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import { esCancelacion, percepcionApi, type BaselinesResponse } from "../lib/percepcion";
import { CARD, COLOR_COPPER, COLOR_NEG, COLOR_POS, TituloBloque, fmt, nro } from "./PercepcionUI";

export function PercepcionBaselines() {
  const [data, setData] = useState<BaselinesResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.baselines(opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudieron cargar los baselines.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const piso = data?.error_irreducible ?? null;
  const promedio = data?.desvio_serie ?? null;
  const mejor = data?.modelos[0] ?? null;
  // El margen es lo único que una simulación puede llegar a ganar.
  const margen = mejor && piso !== null ? mejor.mae - piso : null;
  // Escala de las barras: el peor caso es errar como el promedio histórico.
  const tope = Math.max(promedio ?? 0, ...(data?.modelos.map((m) => m.mae) ?? [0]));

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      {/* TONO: esto lo lee un vicerrector, no un data scientist. La versión anterior
          decía "lo más tonto posible" y "lo que erraría no pensar" — desdeñoso con
          métodos que son perfectamente razonables, y opaco para quien tiene que
          decidir si financiar el proyecto. Lo que necesita saber es qué margen hay,
          no cómo se llama la técnica. */}
      <TituloBloque titulo="Cuánto se puede anticipar el índice">
        Antes de construir un modelo hay que saber cuánto acierta lo simple. Cuatro
        métodos elementales —repetir la última semana, usar el promedio, etc.—
        pronostican el índice usando <strong>solo el pasado</strong>. Lo que erran
        marca el piso: un modelo que no lo supere no agrega nada. El error se mide en
        puntos de índice.
      </TituloBloque>

      {/* CONTRA QUÉ SERIE se midió. No es un detalle: hasta 09-2026 la vara corría
          sobre el índice sin pesos por tema mientras el tablero mostraba el ponderado,
          y con eso «el modelo le ganó a la vara» y «el índice subió» hablaban de dos
          series distintas. Declararlo es lo que impide que vuelva a pasar sin que
          nadie se entere. Mismo criterio que el rótulo de método del resto del panel. */}
      {data ? (
        <p className="mb-3 text-sm text-slate-500">
          Medido sobre{" "}
          <strong className="text-slate-400">
            {data.serie === "ponderada"
              ? "el mismo índice que muestra el tablero"
              : "el índice sin pesos por tema"}
          </strong>
          {data.serie === "ponderada"
            ? ", con el peso por tema aplicado. Es la serie que se usa para decidir, así que es contra la que hay que pronosticar."
            : ", de conteos crudos. Sirve de contraste histórico, pero no es lo que muestra el tablero."}
        </p>
      ) : null}

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      {data && piso !== null ? (
        <>
          <div className="mb-3 grid gap-2 sm:grid-cols-2">
            {/* ANTES ESTE BLOQUE DECÍA "lo mejor alcanzable", Y ERA FALSO.
                El error irreducible mide el ruido de MUESTREO, no lo impredecible. Al
                medir la fase 2 se vio la diferencia: el piso de ruido da 2,86, pero el
                mejor modelo lineal con seis parámetros y ventaja injusta (ajustado
                in-sample) apenas llega a 6,22. Presentar 2,86 como meta alcanzable
                hacía parecer que quedaba cuatro veces más margen del que hay, que es
                justo la clase de número que sostiene un proyecto que no va a ningún
                lado. Ver INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md §0. */}
            <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Ruido del propio dato
              </p>
              <p className="text-xl font-semibold" style={{ color: COLOR_POS }}>
                {fmt(piso)}
              </p>
              <p className="text-sm leading-5 text-slate-500">
                Lo que el índice oscila <strong>solo por muestreo</strong>: con 40 a 165
                comentarios por semana, el dato ya trae este margen. No es una meta
                alcanzable —lo impredecible pesa mucho más que el ruido—, es el punto por
                debajo del cual un número dejaría de significar nada.
              </p>
            </div>
            <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Sin modelo, usando el promedio
              </p>
              <p className="text-xl font-semibold" style={{ color: COLOR_NEG }}>
                {fmt(promedio)}
              </p>
              <p className="text-sm leading-5 text-slate-500">
                Lo que se erra respondiendo siempre «como el promedio». Un modelo que
                no baje de acá <strong>no justifica construirse</strong>.
              </p>
            </div>
          </div>

          {data.modelos.map((m) => (
            <div key={m.nombre} className="border-b border-white/5 py-2 last:border-0">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm text-slate-100">{m.descripcion}</span>
                <span className="shrink-0 text-base font-semibold" style={{ color: COLOR_COPPER }}>
                  {fmt(m.mae)}
                </span>
              </div>
              <div className="relative mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${tope ? (m.mae / tope) * 100 : 0}%`, background: COLOR_COPPER }}
                />
                {/* Marca del piso: hace ver de un vistazo cuánto margen queda. */}
                {tope ? (
                  <div
                    className="absolute top-0 h-full w-px"
                    style={{ left: `${(piso / tope) * 100}%`, background: COLOR_POS }}
                    title={`Error irreducible: ${fmt(piso)}`}
                  />
                ) : null}
              </div>
              <div className="mt-1 text-sm text-slate-500">
                {m.nombre} · RMSE {fmt(m.rmse)} · {nro(m.n_predicciones)} predicciones
                {m.indistinguible_del_techo ? " · ya tocó el piso de ruido" : ""}
                {m.peor_que_no_hacer_nada ? " · peor que el promedio" : ""}
              </div>
            </div>
          ))}

          {/* ESTE BLOQUE PROMETÍA DE MÁS. Presentaba `mejor − piso` como «todo lo que
              una simulación puede aportar», y eso confunde el ruido de medición con lo
              impredecible: daba ~4 puntos de margen donde lo medido es 0,6. La fase 2
              se construyó y se cerró contra el número correcto, no contra este. */}
          {margen !== null ? (
            <p className="mt-3 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm leading-5 text-slate-400">
              <strong>Distancia al ruido: {fmt(margen)} puntos</strong> — entre el mejor
              método ({fmt(mejor?.mae)}) y el ruido del dato ({fmt(piso)}). Es un límite
              teórico, <strong>no el margen real</strong>: casi todo lo que varía el
              índice es señal auténtica e impredecible desde el pasado. Medido en
              septiembre de 2026, lo mejor que alcanzó un modelo lineal con seis
              parámetros —y con los datos a la vista, o sea con ventaja— fue 6,22. Contra
              eso el margen efectivo es de unos <strong>0,6 puntos</strong>, y hacen falta
              74 semanas para distinguir 0,58. Por eso el proyecto de simulación se cerró
              acá en vez de escalar a agentes.
            </p>
          ) : null}

          <p className="mt-2 text-sm text-slate-500">
            {nro(data.evaluadas)} semanas evaluadas de {nro(data.semanas_con_datos)} con{" "}
            {data.n_min_semana}+ comentarios.
          </p>

          {data.avisos.length ? (
            <ul className="mt-2 space-y-1 border-t border-white/5 pt-2">
              {data.avisos.map((a) => (
                <li key={a} className="text-sm leading-5 text-slate-500">
                  · {a}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}

      {data && piso === null && !cargando ? (
        <p className="py-4 text-center text-sm text-slate-500">
          {data.avisos[0] ?? "No hay semanas suficientes para evaluar un pronóstico."}
        </p>
      ) : null}
    </div>
  );
}

export default PercepcionBaselines;
