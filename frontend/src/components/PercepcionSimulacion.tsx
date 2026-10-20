"use client";

/**
 * Hoja SIMULACIÓN — el proyecto de modelar la percepción, no el tablero de leerla.
 *
 * Vive aparte de las otras cuatro pestañas a propósito. Resumen, Alertas, Comparar y
 * Conversación contestan **qué pasó**, con datos observados. Acá se contesta **qué
 * pasaría**, con modelos que hay que validar antes de creerles. Mezclarlas haría que
 * un pronóstico se leyera con la misma autoridad que un conteo, y no la tiene.
 *
 * ⚠️ ESTA PESTAÑA NO ES EL DEPÓSITO DE LO QUE NO ENCUENTRA LUGAR. Llegó a tener
 * cinco bloques y dos no eran simulación: la VOLATILIDAD por unidad (que es un
 * ranking entre unidades → Comparar, como decía su propio docstring) y el
 * CALENDARIO CARGADO (que es la lista de lectura del mismo calendario cuyo
 * formulario de alta vive en Conversación). Es el mismo cajón de sastre que ya fue
 * el Tablero y después "Explorar", con otro nombre. Antes de sumar un bloque acá:
 * ¿contesta "qué pasaría"? Si contesta "qué pasó", su lugar es otro.
 *
 * El plan completo está en `INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md`. Cuatro
 * preguntas, que se abordan de a una:
 *
 *   D · ¿qué unidad es más volátil?          ← LISTO · se muestra en COMPARAR
 *   A · ¿cómo va a estar la percepción?      ← la VARA está puesta (MAE 6,82)
 *   C · ¿cuánto cae y tarda tras un shock?   ← LISTO · 11 episodios, 7 medibles
 *   B · ¿qué pasa si comunicamos distinto?   ← LISTO: reel +14,6 pts, controlado por cuenta
 *
 * Cada bloque que entre acá tiene que traer su propia medida de cuánto le podés
 * creer. Un número sin su barra de error, en una hoja que se llama "Simulación", es
 * peor que no mostrarlo.
 *
 * LA FASE 2 SE MIDIÓ Y ESTÁ CERRADA (08-09-2026). El modelo POBLACIONAL de
 * compartimentos que pedía el plan no supera la vara —da 7,50-7,71 contra 6,82— porque
 * las tres cosas que suponía no están en los datos: no hay contagio (hay reversión a la
 * media, φ≈0,52), los eventos no aportan sobre el estado previo (−2,22 ± 2,03), y la
 * composición mejora in-sample pero no sobrevive al walk-forward. Lo que sí mejoró fue
 * MENOS modelo: un suavizado exponencial de un parámetro.
 *
 * ⚠️ El piso de ruido (2,86) NO es el techo de un pronóstico: mide el error de muestreo,
 * no lo impredecible. La cota medida —mejor modelo lineal con 6 parámetros ajustado
 * in-sample, con ventaja injusta— es 6,22. Contra una vara de 6,82 quedan 0,60 puntos,
 * y lo mínimo demostrable con 74 semanas es 0,58. Por eso el plan se cierra acá y no
 * sigue a la fase 3. Todo el detalle en `INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md`.
 *
 * ⚠️ Los números de arriba se re-miden cuando cambia el corpus o el esquema del índice,
 * y se han movido tres veces. Última actualización 08-09-2026, sobre 8.174 comentarios
 * y la serie PONDERADA (hasta esa fecha la vara corría sobre el índice canónico
 * mientras el tablero mostraba el ponderado: eran dos series distintas).
 */

import { useState } from "react";

import { PercepcionBaselines } from "./PercepcionBaselines";
import { PercepcionComunicacion } from "./PercepcionComunicacion";
import { PercepcionEnsayo } from "./PercepcionEnsayo";
import { PercepcionShock } from "./PercepcionShock";
import { CARD, SubPestanas } from "./PercepcionUI";

/** Las tres preguntas de Simulación, nombradas por lo que contestan.
 *
 * «La vara», «respuesta a shock» y «qué comunicación genera conversación» son
 * nombres del plan del proyecto, no de un director. Y hay una razón extra para
 * separarlas acá: los tres bloques son largos y ninguno se lee en función del
 * otro — se consultan de a uno, cuando surge esa pregunta puntual. */
const SUB_SIMULACION = [
  {
    // VA PRIMERA porque es la única que se USA, no que se lee: las otras tres
    // informan un resultado ya medido y esta se opera para decidir algo. Es
    // también lo único que quedó vivo del proyecto de simulación.
    id: "ensayo",
    label: "¿Va a generar conversación?",
    hint:
      // Español latinoamericano NEUTRO, sin voseo (regla de Alberto, 2026-08-07).
      "Arma una publicación y mira qué tan probable es que reciba comentarios. Cuando esa " +
      "combinación de características ya existe en el corpus, el número está CONTADO sobre " +
      "publicaciones reales en vez de estimado — y se dice cuál de las dos cosas es.",
  },
  {
    id: "vara",
    label: "¿Se puede predecir?",
    hint:
      "Cuánto acierta lo más simple que se puede hacer. Es la vara que cualquier modelo " +
      "tiene que superar para valer la pena — y también el techo de lo alcanzable, porque " +
      "buena parte de lo que varía el índice es ruido del propio dato.",
  },
  {
    id: "shock",
    label: "¿Qué pasa tras un paro?",
    hint:
      "Cuánto cae la percepción y cuánto tarda en recuperarse, caso por caso. La lista de " +
      "episodios sin datos suficientes es parte del resultado, no un defecto de la vista.",
  },
  {
    id: "comunicacion",
    label: "¿Qué comunicación funciona?",
    hint:
      "Qué formatos generan más conversación, con el efecto controlado por cuenta: separa " +
      "«este formato funciona» de «las cuentas que lo usan ya generaban más».",
  },
] as const;

export function PercepcionSimulacion() {
  // Abre en el ENSAYO y no en la vara: es lo único de esta hoja que se usa para
  // decidir algo en vez de para leer un resultado ya cerrado.
  const [sub, setSub] = useState<"ensayo" | "vara" | "shock" | "comunicacion">("ensayo");
  return (
    <div className="space-y-4">
      {/* TONO: quien lee esto decide si el proyecto sigue, no cómo se implementa.
          La versión anterior abría con "EN CONSTRUCCIÓN" y hablaba de "modelos que
          hay que validar antes de creerles" — honesto, pero se lee como una excusa
          antes de que nadie haya preguntado. Lo que corresponde decir primero es qué
          se puede afirmar hoy y con cuánto respaldo. */}
      <div className={CARD}>
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-200">
            Qué se puede anticipar, y con cuánto respaldo
          </span>
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-amber-200">
            evidencia preliminar
          </span>
        </div>
        <p className="text-[11px] leading-5 text-slate-500">
          Las demás secciones informan <strong>lo que ocurrió</strong>. Esta responde
          tres preguntas de proyección — si el índice se puede anticipar, qué efecto
          tiene un paro, y qué formatos de comunicación generan más conversación — y{" "}
          <strong>cada respuesta viene con el margen de error de su propia
          evidencia</strong>. Va separada del resto para que una proyección no se lea
          con la misma autoridad que un conteo.
        </p>
      </div>

      <SubPestanas opciones={SUB_SIMULACION} activa={sub} onCambio={setSub} />

      {/* B — EL ENSAYO. Lo único de esta hoja que se OPERA en vez de leerse, y lo
          único que quedó vivo del proyecto: la pregunta de anticipar el índice se
          cerró con dos evidencias y sin camino de datos. */}
      {sub !== "ensayo" ? null : <PercepcionEnsayo />}

      {/* A — la vara. Define si el resto valía la pena construirse; el veredicto
          quedó en que no, y por eso ya no abre la hoja. */}
      {sub !== "vara" ? null : <PercepcionBaselines />}

      {/* C — un caso medible de diez. La lista larga de "sin datos" es el resultado,
          no un defecto de la vista. */}
      {sub !== "shock" ? null : <PercepcionShock />}

      {/* B — la última de las cuatro. */}
      {sub !== "comunicacion" ? null : <PercepcionComunicacion />}

      {/* Los límites van SIEMPRE visibles, fuera de las sub-pestañas: acotan a las
          tres por igual, y esconderlos detrás de un clic sería justo lo contrario
          de lo que esta pestaña declara hacer. */}
      <div className={CARD}>
        <p className="mb-2 text-sm font-medium text-slate-200">
          Qué haría falta para afirmar más
        </p>
        <p className="text-[11px] leading-5 text-slate-500">
          Las tres preguntas están respondidas hasta donde los datos permiten, y las
          tres se topan con el mismo techo: <strong>la cantidad y la cobertura de los
          comentarios, no la técnica de análisis</strong>. Los tres puntos siguientes
          son lo que acota hoy cualquier conclusión de esta sección.
        </p>
        <ul className="mt-2 space-y-1 text-[11px] leading-5 text-slate-500">
          <li>
            · <strong>Falta el 47 % de los comentarios</strong> que Instagram declara
            en las publicaciones ya recolectadas. La ingesta se hizo sin los comentarios
            ocultos, que son los que la plataforma marca como ofensivos o spam. La
            consecuencia importa para leer todo el módulo:{" "}
            <strong>el índice está sesgado hacia lo positivo</strong>, y la percepción
            real es probablemente algo peor que la que se muestra.
          </li>
          <li>
            · <strong>76,9 % de quienes comentan lo hace una sola vez</strong>. No hay
            personas a las que seguir en el tiempo, así que no se puede modelar cómo
            cambia de opinión un mismo miembro de la comunidad.
          </li>
          <li>
            · De los ~7 puntos que varía el índice de una semana a otra,{" "}
            <strong>unos 4 se explican solo por cuántos comentarios hubo</strong>. Un
            movimiento menor a eso no es una señal: es el tamaño de la muestra.
          </li>
        </ul>
      </div>
    </div>
  );
}

export default PercepcionSimulacion;
