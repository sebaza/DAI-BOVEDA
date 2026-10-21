"use client";

/**
 * LO MÁS HABLADO DEL PERÍODO — qué publicaciones concentran la conversación.
 *
 * POR QUÉ EXISTE, Y NO ES UNA VISTA MÁS
 * -------------------------------------
 * La auditoría de septiembre 2026 revisó seis caídas del índice y en las seis la
 * explicación salió del mismo lugar: mirar QUÉ PUBLICACIÓN concentraba los
 * comentarios. Sin ese dato, la etiqueta del calendario lleva a la conclusión
 * equivocada — y llevó, dos veces:
 *
 *   · El −8,1 de Fiestas Patrias no era ánimo: DOS publicaciones del mismo sorteo
 *     juntaban 128 de 161 comentarios (79,5 %), con índice 50,5 y 50,6. Gente
 *     etiquetando amigos, no opinión.
 *   · La caída del 17-08-2026 no era descontento: era un post de condolencias por
 *     un profesor fallecido.
 *
 * Un promedio sobre una muestra que concentra el 80 % en un solo post no describe
 * a una comunidad: describe a ese post.
 *
 * LAS DOS DECISIONES DE LECTURA
 * -----------------------------
 * 1. **Ordena por VOLUMEN, no por índice.** Lo primero que hay que saber es cuánto
 *    pesa cada publicación en la muestra, porque eso decide si el promedio del
 *    período significa algo. El índice va al lado para ver hacia dónde empuja.
 * 2. **La CONCENTRACIÓN va arriba y con veredicto.** No es un número decorativo:
 *    por encima del 40 % el período no se puede leer como promedio y hay que ir
 *    publicación por publicación. Decirlo en palabras evita que alguien lea 44 %
 *    y no sepa qué hacer con eso.
 */

import { useCallback, useEffect, useState } from "react";

import type { Filtro, PublicacionesDominantesResponse } from "../lib/percepcion";
import { percepcionApi } from "../lib/percepcion";
import { CARD, TituloBloque, colorIndice, fmt, nro } from "./PercepcionUI";

/** Por encima de acá, el promedio del período describe a UNA publicación. */
const CONCENTRACION_ALTA = 40;

export function PercepcionDominantes({ filtro }: { filtro: Filtro }) {
  const [data, setData] = useState<PublicacionesDominantesResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (f: Filtro) => {
    setCargando(true);
    try {
      setData(await percepcionApi.publicacionesDominantes(f, 12));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { void cargar(filtro); }, [cargar, filtro]);

  const conc = data?.concentracion ?? null;
  const concentrado = conc !== null && conc >= CONCENTRACION_ALTA;

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="Lo más hablado del período" vidaMedia={filtro.vidaMedia} ignoraRecencia>
        Las publicaciones que concentran la conversación, ordenadas por cuántos
        comentarios juntaron. Es lo que explica un movimiento del índice cuando el
        calendario no alcanza: una caída puede ser descontento, un sorteo donde la
        gente etiqueta amigos, o un post de condolencias.
      </TituloBloque>

      {error ? <p className="text-sm text-[#f2777a]">{error}</p> : null}

      {data && data.items.length > 0 ? (
        <>
          {/* La concentración PRIMERO y con veredicto: es lo que dice si el resto
              del tablero se puede leer como promedio en este período. */}
          <div
            className={`mb-3 rounded-xl border px-3 py-2 text-[11px] leading-5 ${
              concentrado
                ? "border-amber-400/30 bg-amber-400/[0.07] text-amber-100/90"
                : "border-white/10 bg-white/[0.03] text-slate-400"
            }`}
          >
            {nro(data.n_comentarios)} comentarios en{" "}
            <strong className="text-slate-200">{nro(data.n_publicaciones)}</strong>{" "}
            publicaciones. La más grande junta{" "}
            <strong className={concentrado ? "text-amber-200" : "text-slate-200"}>
              {conc}%
            </strong>{" "}
            del período.
            {concentrado ? (
              <>
                {" "}<strong>Con esta concentración el promedio describe a esa
                publicación, no a la comunidad</strong>: conviene leer caso por caso.
              </>
            ) : (
              <> La conversación está repartida: el promedio del período es representativo.</>
            )}
          </div>

          <ul className="space-y-1.5">
            {data.items.map((p) => (
              <li
                key={p.publicacion_id}
                className="rounded-2xl border border-white/5 bg-white/[0.02] px-3 py-2"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <span className="min-w-0 flex-1 text-[12.5px] leading-5 text-slate-300">
                    {p.cuenta ?? "(cuenta sin nombre)"}
                    {p.cuenta_tipo ? <span className="ml-2 rounded-full bg-white/[0.04] px-2 py-0.5 text-[10.5px] text-slate-400">{p.cuenta_tipo}</span> : null}
                    {p.desde ? <span className="ml-2 text-slate-500">{p.desde === p.hasta || !p.hasta ? p.desde : `${p.desde} → ${p.hasta}`}</span> : null}
                  </span>
                  <span className="flex shrink-0 items-baseline gap-3">
                    <span className="text-[11px] tabular-nums text-slate-500">
                      {nro(p.n_comentarios)} com.
                    </span>
                    <span
                      className="text-sm font-bold tabular-nums"
                      style={{ color: colorIndice(p.indice) }}
                    >
                      {fmt(p.indice)}
                    </span>
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-slate-500">
                  {p.pct_neg !== null ? <span>{p.pct_neg}% negativos</span> : null}
                  {/* Barra de PESO en la muestra, no de índice: es la variable que
                      decide si el promedio del período se puede leer. */}
                  <span className="flex flex-1 items-center gap-2">
                    <span className="h-1 min-w-[40px] flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                      <span
                        className="block h-full rounded-full bg-[var(--portal-cyan)]"
                        style={{ width: `${Math.min(100, p.pct_del_periodo)}%` }}
                      />
                    </span>
                    <span className="tabular-nums">{p.pct_del_periodo}% del período</span>
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : !cargando && !error ? (
        <p className="py-6 text-center text-sm text-slate-500">
          Sin comentarios en este período.
        </p>
      ) : null}
    </div>
  );
}

export default PercepcionDominantes;
