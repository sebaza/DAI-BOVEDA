"use client";

/**
 * Bloque «Resumen semanal» — el párrafo narrativo escrito por el LLM.
 *
 * Vive en la pestaña Resumen, arriba del detalle, porque contesta la pregunta que
 * un directivo hace primero y que ningún gráfico contesta solo: *qué pasó*.
 *
 * ES A NIVEL UNIVERSIDAD, SIEMPRE
 * -------------------------------
 * No depende del filtro global — ni de la sede ni de los días. Dos razones:
 *
 * 1. **Volumen.** Hay 40–165 comentarios por semana en TODA la UCN. Partirlos por
 *    unidad deja ~5 por facultad, contra los 30 que el módulo exige para afirmar
 *    algo. Un resumen por unidad diría "evidencia insuficiente" casi siempre.
 * 2. **Período cerrado.** El texto está cacheado contra la SEMANA. Si respetara el
 *    slider de días, el párrafo dejaría de corresponder al período que dice cubrir.
 *
 * Lo que un promedio institucional taparía —una sede que se desploma mientras otra
 * sube— entra igual: el backend calcula las unidades que se salieron de lo suyo y
 * el redactor tiene orden de nombrarlas.
 *
 * TRES COSAS QUE LA UI TIENE QUE DECIR SIEMPRE
 * --------------------------------------------
 * 1. **Que lo escribió un modelo.** Un párrafo en prosa al lado de números medidos
 *    se lee como si tuviera la misma autoridad, y no la tiene.
 * 2. **De cuándo es.** El texto está cacheado por huella de datos: si la ingesta no
 *    corrió, es de hace una semana, y eso hay que verlo sin preguntar.
 * 3. **Cuánto costó.** Es el único bloque del tablero que gasta plata. Esconderlo
 *    sería exactamente la clase de cosa que después nadie puede auditar.
 */

import { useCallback, useEffect, useState } from "react";

import {
  percepcionApi,
  type ResumenSemanalResponse,
  type SemanaDisponible,
} from "../lib/percepcion";
import { CARD, TituloBloque, fechaCorta, nro } from "./PercepcionUI";

/** Umbral de evidencia del módulo. Debajo de esto la lectura es indicativa. */
const N_MIN_EVIDENCIA = 30;

function costoLegible(usd: number | null): string {
  if (usd === null || usd === undefined) return "";
  // Son milésimas de dólar: con 2 decimales se ve "0,00" y parece gratis por error
  // de redondeo, no por ser barato. Cuatro decimales dicen la verdad.
  return `US$ ${usd.toFixed(4)}`;
}

function cuandoLegible(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("es-CL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/** Una flecha de navegación semanal, con el aviso de costo cuando corresponde. */
function BotonSemana({
  hacia, destino, ocupado, onClick,
}: {
  hacia: "atras" | "adelante";
  destino?: SemanaDisponible;
  ocupado: boolean;
  onClick: () => void;
}) {
  const atras = hacia === "atras";
  // Ir a una semana sin resumen escrito dispara una llamada al modelo. Son
  // milésimas de dólar, pero el usuario tiene que poder saberlo ANTES del clic:
  // un botón que gasta plata sin decirlo es una trampa, por barato que sea.
  const generara = Boolean(destino && !destino.tiene_resumen);
  const titulo = !destino
    ? (atras ? "No hay semanas anteriores con datos" : "Ya está en la más reciente")
    : `${atras ? "Semana anterior" : "Semana siguiente"}: ${destino.semana}` +
      ` · ${destino.n_comentarios} comentarios` +
      (generara ? " · se va a redactar (tiene costo)" : " · ya está redactada");

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!destino || ocupado}
      title={titulo}
      aria-label={titulo}
      className="relative rounded-full border border-white/10 px-2 py-0.5 text-[11px] leading-4 text-slate-300 transition hover:border-white/25 hover:text-white disabled:opacity-30"
    >
      {atras ? "‹" : "›"}
      {generara ? (
        <span
          className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-[var(--portal-copper,#e0aa4e)]"
          aria-hidden
        />
      ) : null}
    </button>
  );
}

export function PercepcionResumenSemanal() {
  const [data, setData] = useState<ResumenSemanalResponse | null>(null);
  const [semanas, setSemanas] = useState<SemanaDisponible[]>([]);
  // `null` = la última con datos. Se guarda el lunes en ISO, igual que el backend.
  const [semana, setSemana] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [regenerando, setRegenerando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // El catálogo se pide UNA vez: es lectura pura, no gasta tokens, y sin él la
  // navegación tendría que adivinar a qué semanas puede saltar.
  useEffect(() => {
    void (async () => {
      try {
        const r = await percepcionApi.semanasResumen("global", null, 260);
        setSemanas(r.semanas);
      } catch {
        // Sin catálogo el bloque sigue mostrando la última semana; solo se pierden
        // las flechas. No es motivo para vaciar la pantalla.
      }
    })();
  }, []);

  const cargar = useCallback(
    async (forzar = false) => {
      if (forzar) setRegenerando(true);
      else setCargando(true);
      setError(null);
      try {
        setData(await percepcionApi.resumenSemanal(
          "global", null, semana ?? undefined, forzar));
      } catch (e) {
        setError(e instanceof Error ? e.message : "No se pudo cargar el resumen semanal.");
      } finally {
        setCargando(false);
        setRegenerando(false);
      }
    },
    [semana],
  );

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // Índice de la semana mostrada dentro del catálogo (0 = la más reciente).
  // Con `semana === null` el backend eligió la última, que es el índice 0.
  const idx = semana === null ? 0 : semanas.findIndex((s) => s.semana === semana);
  const enCatalogo = idx >= 0;
  // ← va hacia ATRÁS en el tiempo, y el catálogo está ordenado de nuevo a viejo,
  // así que "anterior" es idx+1. Es al revés de lo que sugiere la flecha; por eso
  // se nombra por el TIEMPO y no por la posición.
  const masVieja = enCatalogo ? semanas[idx + 1] : undefined;
  const masNueva = enCatalogo && idx > 0 ? semanas[idx - 1] : undefined;

  const irA = (destino?: SemanaDisponible) => {
    if (!destino || cargando || regenerando) return;
    setSemana(destino.semana);
  };

  if (cargando && !data) {
    return (
      <div className={CARD}>
        <p className="py-4 text-center text-sm text-slate-500">Cargando resumen semanal…</p>
      </div>
    );
  }
  if (error && !data) {
    return (
      <div className={CARD}>
        <p className="text-sm text-[#f2777a]">{error}</p>
      </div>
    );
  }
  if (!data) return null;

  const periodo = data.periodo
    ? `${fechaCorta(data.periodo.desde)} – ${fechaCorta(data.periodo.hasta)}`
    : "";
  const pocaEvidencia = data.hay_datos && data.n_comentarios < N_MIN_EVIDENCIA;

  return (
    <div className={CARD} style={{ opacity: regenerando ? 0.55 : 1 }} aria-busy={regenerando}>
      <TituloBloque
        titulo="Resumen semanal"
        extra={
          <>
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
              redactado por IA
            </span>
            {semanas.length > 1 ? (
              <span className="ml-auto flex items-center gap-1">
                <BotonSemana
                  hacia="atras"
                  destino={masVieja}
                  ocupado={cargando || regenerando}
                  onClick={() => irA(masVieja)}
                />
                {/* Volver a la última es el gesto más frecuente después de curiosear
                    hacia atrás, y encontrarlo a fuerza de flechas es tedioso. */}
                <button
                  type="button"
                  onClick={() => setSemana(null)}
                  disabled={idx === 0 || cargando || regenerando}
                  className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-400 transition hover:border-white/25 hover:text-white disabled:opacity-30"
                  title="Volver a la última semana con datos"
                >
                  hoy
                </button>
                <BotonSemana
                  hacia="adelante"
                  destino={masNueva}
                  ocupado={cargando || regenerando}
                  onClick={() => irA(masNueva)}
                />
              </span>
            ) : null}
          </>
        }
      >
        Semana {periodo} · toda la universidad
        {idx > 0 ? (
          <>
            {" "}
            <strong className="text-slate-400">
              (semana histórica, {idx} {idx === 1 ? "semana" : "semanas"} atrás)
            </strong>
          </>
        ) : null}
        . Lo escribe un modelo a partir de los datos ya agregados de este tablero —
        interpreta, no calcula: todas las cifras salen de los mismos conteos que ves
        más abajo. Se regenera cuando entran datos nuevos, no en cada visita.
      </TituloBloque>

      {data.texto ? (
        <p className="whitespace-pre-line text-[13px] leading-6 text-slate-200">{data.texto}</p>
      ) : (
        <p className="py-2 text-sm text-slate-500">
          {data.aviso ?? "Todavía no hay resumen para esta semana."}
        </p>
      )}

      {/* Avisos que cambian cómo hay que leer el texto. */}
      {data.cifras_dudosas?.length ? (
        <p className="mt-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-[11px] leading-5 text-rose-200">
          <strong>Revisa antes de citar.</strong> El texto menciona cifras que no están
          en los datos de la semana ({data.cifras_dudosas.slice(0, 5).join(", ")}). El
          resto del tablero no está afectado: es este párrafo el que hay que verificar.
        </p>
      ) : null}
      {data.desactualizado ? (
        <p className="mt-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-5 text-amber-200">
          Llegaron datos nuevos pero no se pudo regenerar el texto, así que esto es el
          resumen anterior: no refleja lo último. {data.aviso}
        </p>
      ) : null}
      {pocaEvidencia ? (
        <p className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-[11px] leading-5 text-slate-400">
          Solo {nro(data.n_comentarios)} comentarios en la semana (el módulo pide{" "}
          {N_MIN_EVIDENCIA} para afirmar algo de una unidad). Léelo como indicio, no
          como medición.
        </p>
      ) : null}

      {/* Trazabilidad: de cuándo es, con qué modelo y cuánto costó. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-white/5 pt-3 text-[10px] text-slate-500">
        {data.hay_datos ? <span>{nro(data.n_comentarios)} comentarios</span> : null}
        {data.generado_en ? <span>· generado {cuandoLegible(data.generado_en)}</span> : null}
        {data.modelo ? <span>· {data.modelo}</span> : null}
        {data.costo_usd !== null ? <span>· {costoLegible(data.costo_usd)}</span> : null}
        {data.desde_cache && !data.desactualizado ? (
          <span
            className="text-slate-400"
            title="Los datos no cambiaron desde la última generación: se sirvió el texto guardado sin llamar al modelo."
          >
            · sin datos nuevos, no se volvió a generar
          </span>
        ) : null}
        {data.hay_datos ? (
          <button
            type="button"
            onClick={() => void cargar(true)}
            disabled={regenerando}
            className="ml-auto rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-300 transition hover:border-white/25 hover:text-white disabled:opacity-40"
            title="Vuelve a llamar al modelo aunque los datos no hayan cambiado. Tiene costo."
          >
            {regenerando ? "Regenerando…" : "Regenerar"}
          </button>
        ) : null}
      </div>

      {error ? <p className="mt-2 text-[11px] text-[#f2777a]">{error}</p> : null}
    </div>
  );
}

export default PercepcionResumenSemanal;
