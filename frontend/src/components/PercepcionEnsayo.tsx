"use client";

/**
 * ENSAYO DE COMUNICACIÓN — «¿una publicación así va a generar conversación?».
 *
 * Es lo ÚNICO que quedó vivo del proyecto de simulación, y conviene saber por qué:
 * la pregunta original —anticipar el índice de la semana que viene— se cerró con dos
 * evidencias (el modelo poblacional no supera la vara ni con la postura vieja ni con
 * la mejorada) y sin camino de datos (esperar las semanas que faltan son 5,7 años).
 *
 * Esta pregunta cambia la variable a predecir y con eso se vuelve contestable.
 *
 * LO QUE ESTE BLOQUE NO PROMETE, Y SE DICE EN PANTALLA
 * ---------------------------------------------------
 * * No predice el ÍNDICE. Dice si va a haber conversación, no de qué color.
 * * No es causal. Que los reels correlacionen con más conversación no prueba que
 *   convertir un post en reel la produzca.
 *
 * EL NÚMERO PUEDE VENIR DE DOS LUGARES Y NO VALEN LO MISMO
 * --------------------------------------------------------
 * Con 6.153 publicaciones, casi toda combinación frecuente ya existe en el corpus:
 * entonces se CUENTA su tasa real en vez de sumar efectos. Solo cuando la
 * combinación es rara se cae a la suma, que supone que los rasgos no interactúan.
 *
 * Y esa suposición sería mala: medido, un reel con emojis da 56,4 % contra los
 * 39,3 % que predice la suma, y un reel con hashtags rinde MENOS que un reel solo.
 * Por eso el origen del número se muestra siempre, no escondido en un tooltip.
 */

import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import type { EnsayoResponse } from "../lib/percepcion";
import { esCancelacion, percepcionApi } from "../lib/percepcion";
import { CARD, COLOR_COPPER, COLOR_POS, TituloBloque, fmt, nro } from "./PercepcionUI";

export function PercepcionEnsayo() {
  const [rasgos, setRasgos] = useState<string[]>([]);
  const [data, setData] = useState<EnsayoResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async (rs: string[]) => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.ensayo(rs, opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo correr el ensayo.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => { void cargar(rasgos); }, [cargar, rasgos]);

  const alternar = (r: string) =>
    setRasgos((prev) => (prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r]));

  const p = data?.probabilidad ?? null;
  const observado = data?.fuente === "observado";
  // La barra usa la tasa base como referencia: lo que importa no es el valor
  // absoluto sino si esta publicación supera a la publicación promedio.
  const base = data?.tasa_base ?? 0;

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="¿Esta publicación va a generar conversación?">
        {/* Español latinoamericano NEUTRO, sin voseo (regla de Alberto, 2026-08-07:
            «hablame en español latino, no con acento argentino»). El voseo entró
            una vez con este módulo y ya se corrigió en main; no re-introducirlo. */}
        Arma una publicación con las características de abajo y mira qué tan probable
        es que reciba comentarios. Se compara contra la publicación promedio de la UCN,
        que conversa el <strong>{fmt(base)}%</strong> de las veces.
      </TituloBloque>

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      {data ? (
        <>
          {/* ---- los rasgos elegibles ---- */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {data.rasgos.map((r) => {
              const on = rasgos.includes(r.rasgo);
              return (
                <button
                  key={r.rasgo}
                  type="button"
                  onClick={() => alternar(r.rasgo)}
                  aria-pressed={on}
                  title={
                    r.solido
                      ? `Efecto medido dentro de cada cuenta: ${r.efecto_intra! > 0 ? "+" : ""}${r.efecto_intra} puntos`
                      : "Su efecto no se distingue del azar: se puede elegir, pero no mueve el número"
                  }
                  className={`rounded border px-3 py-1.5 text-sm transition ${
                    on
                      ? "border-[color-mix(in_srgb,var(--portal-cyan)_50%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_15%,transparent)] font-semibold text-ucn-azul-claro"
                      : "border-white/10 bg-white/[0.03] text-slate-400 hover:bg-white/[0.07]"
                  }`}
                >
                  {r.etiqueta}
                  {/* Marcar los NO sólidos en el propio botón evita que alguien arme
                      una publicación entera con rasgos que no hacen nada. */}
                  {r.solido ? (
                    <span className="ml-1.5 opacity-70">
                      {r.efecto_intra! > 0 ? "+" : ""}{r.efecto_intra}
                    </span>
                  ) : (
                    <span className="ml-1.5 text-sm text-slate-500">sin evidencia</span>
                  )}
                </button>
              );
            })}
            {rasgos.length ? (
              <button
                type="button"
                onClick={() => setRasgos([])}
                className="rounded border border-white/10 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-400"
              >
                Limpiar
              </button>
            ) : null}
          </div>

          {/* ---- el resultado ---- */}
          <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500">
                  Probabilidad de generar conversación
                </p>
                <p className="mt-1 flex items-baseline gap-2">
                  <span
                    className="text-3xl font-bold tabular-nums"
                    style={{ color: p !== null && p >= base ? COLOR_POS : COLOR_COPPER }}
                  >
                    {p === null ? "—" : `${fmt(p)}%`}
                  </span>
                  {data.margen > 0 ? (
                    <span className="text-sm text-slate-500">± {fmt(data.margen)}</span>
                  ) : null}
                </p>
              </div>
              {/* EL ORIGEN DEL NÚMERO, visible y no en un tooltip: un dato contado y
                  una suma de efectos no se leen igual. */}
              <span
                className={`rounded border px-2.5 py-1 text-sm ${
                  observado
                    ? "border-[color-mix(in_srgb,var(--portal-cyan)_40%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_10%,transparent)] text-ucn-azul-claro"
                    : "border-[color-mix(in_srgb,var(--portal-copper)_40%,transparent)] bg-[color-mix(in_srgb,var(--portal-copper)_10%,transparent)] text-ucn-tierra-clara"
                }`}
              >
                {observado
                  ? `contado sobre ${nro(data.n_observado)} publicaciones reales`
                  : data.fuente === "estimado"
                    ? "estimado sumando efectos"
                    : "la publicación promedio"}
              </span>
            </div>

            {/* Barra con la tasa base marcada: sin esa referencia, un 41 % no dice
                si es bueno o malo. */}
            {p !== null ? (
              <div className="relative mt-3 h-2.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max(0, Math.min(100, p))}%`,
                    background: p >= base ? COLOR_POS : COLOR_COPPER,
                  }}
                />
                <span
                  className="absolute top-0 h-full border-l border-dashed border-white/50"
                  style={{ left: `${Math.max(0, Math.min(100, base))}%` }}
                  title={`Publicación promedio: ${fmt(base)}%`}
                />
              </div>
            ) : null}
            <p className="mt-1.5 text-sm text-slate-500">
              La línea punteada es la publicación promedio ({fmt(base)}%).
            </p>

            {data.aplicados.length ? (
              <p className="mt-2 text-sm text-slate-400">
                Suman:{" "}
                {data.aplicados.map((a, i) => (
                  <span key={a.rasgo}>
                    {i > 0 ? " · " : ""}
                    {a.etiqueta}{" "}
                    <span className="text-slate-500">
                      ({a.efecto! > 0 ? "+" : ""}{a.efecto})
                    </span>
                  </span>
                ))}
              </p>
            ) : null}
            {data.ignorados.length ? (
              <p className="mt-1 text-sm text-[color-mix(in_srgb,var(--portal-copper)_80%,transparent)]">
                No mueven el número: {data.ignorados.map((a) => a.etiqueta).join(" · ")} —
                su efecto no se distingue del azar.
              </p>
            ) : null}
          </div>

          {data.avisos.length ? (
            <ul className="mt-3 space-y-1 border-t border-white/5 pt-2.5">
              {data.avisos.map((a) => (
                <li key={a} className="text-sm leading-5 text-slate-500">· {a}</li>
              ))}
            </ul>
          ) : null}

          <p className="mt-2 text-sm text-slate-500">
            Sobre {nro(data.publicaciones)} publicaciones ingestadas.
          </p>
        </>
      ) : null}
    </div>
  );
}

export default PercepcionEnsayo;
