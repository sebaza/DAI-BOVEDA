"use client";

/**
 * Bloque «Qué comunicación genera conversación» (pregunta B del plan de simulación).
 *
 * LAS DOS BARRAS SON EL PUNTO
 * ---------------------------
 * Cada rasgo se muestra con su efecto CRUDO y con el CONTROLADO por cuenta, y no por
 * prolijidad estadística: la diferencia entre los dos es lo que separa «este formato
 * funciona» de «las cuentas que usan este formato ya generaban más conversación».
 *
 * Sobre el corpus, dos rasgos tienen efecto crudo apreciable que NO sobrevive al
 * control. Mostrar solo el crudo habría llevado a recomendar algo que no hace nada.
 *
 * Por eso el número grande es el intra-cuenta, y el crudo va detrás, en gris, como
 * referencia. Si un lector se queda con uno solo, tiene que ser el bueno.
 *
 * Y por eso el aviso de correlación no es una nota al pie: este bloque se lee como
 * una recomendación de qué hacer, y la evidencia no alcanza para tanto.
 */

import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import { esCancelacion } from "../lib/percepcion";
import { PALETA } from "@/lib/paleta";

import {
  percepcionApi,
  type CaracteristicaComunicacion,
  type ComunicacionResponse,
} from "../lib/percepcion";
import { CARD, COLOR_NEG, COLOR_POS, TituloBloque, fmt, nro } from "./PercepcionUI";

function Rasgo({ f, escala }: { f: CaracteristicaComunicacion; escala: number }) {
  const intra = f.efecto_intra;
  const positivo = (intra ?? 0) > 0;
  const color = f.solido ? (positivo ? COLOR_POS : COLOR_NEG) : PALETA.subtle;
  const ancho = intra !== null && escala > 0 ? Math.min(100, (Math.abs(intra) / escala) * 100) : 0;

  return (
    <div className="border-b border-white/5 py-2 last:border-0">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className={`text-sm ${f.solido ? "text-slate-100" : "text-slate-400"}`}>
          {f.etiqueta}
        </span>
        {f.solido ? (
          <span
            className="rounded border border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)] px-1.5 py-0.5 text-xs uppercase tracking-wide text-dato-favorable"
            title="Supera las dos pruebas: el efecto crudo supera su margen de error Y se sostiene comparando cada cuenta consigo misma."
          >
            sólido
          </span>
        ) : null}
        <span className="ml-auto text-base font-semibold" style={{ color }}>
          {intra !== null ? `${intra > 0 ? "+" : ""}${fmt(intra)}` : "n/d"}
        </span>
      </div>

      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full" style={{ width: `${ancho}%`, background: color }} />
      </div>

      <div className="mt-1 text-sm leading-4 text-slate-500">
        Comparando cada cuenta consigo misma: gana en{" "}
        <strong className="text-slate-400">
          {nro(f.cuentas_a_favor)} de {nro(f.cuentas_comparables)}
        </strong>{" "}
        cuentas que publican de las dos formas.
        {f.cuentas_comparables === 0 ? (
          <span className="text-ucn-tierra-clara">
            {" "}Ninguna cuenta usa ambas formas: no hay con qué controlar.
          </span>
        ) : null}
        <br />
        En crudo: {fmt(f.tasa_sin)}% → {fmt(f.tasa_con)}% ({f.efecto_crudo > 0 ? "+" : ""}
        {fmt(f.efecto_crudo)} ± {fmt(f.margen)})
      </div>
    </div>
  );
}

export function PercepcionComunicacion() {
  const [data, setData] = useState<ComunicacionResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.comunicacion(opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar el análisis.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const escala = Math.max(
    1,
    ...(data?.caracteristicas ?? []).map((f) => Math.abs(f.efecto_intra ?? 0)),
  );

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="Qué comunicación genera conversación">
        Qué rasgos de una publicación se asocian con que la comunidad responda. El
        número grande compara <strong>cada cuenta consigo misma</strong>; el de abajo,
        en gris, es la comparación cruda — que mide <em>quién</em> publica tanto como{" "}
        <em>cómo</em>.
      </TituloBloque>

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      {data ? (
        <>
          <p className="mb-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm leading-5 text-slate-400">
            De {nro(data.publicaciones)} publicaciones,{" "}
            <strong className="text-slate-100">{nro(data.con_conversacion)}</strong>{" "}
            generaron conversación ({fmt(data.tasa_base)}%). Los puntos de abajo son
            cuánto sube o baja esa probabilidad.
          </p>

          {data.caracteristicas.map((f) => (
            <Rasgo key={f.rasgo} f={f} escala={escala} />
          ))}

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

export default PercepcionComunicacion;
