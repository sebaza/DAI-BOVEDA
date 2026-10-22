"use client";

/**
 * Bloque «Calendario cargado» — qué eventos conoce el módulo.
 *
 * Vive en CONVERSACIÓN, junto al ABM de marcas y solo con la administración
 * abierta. Estuvo en Simulación, o sea que el formulario para dar de alta un
 * evento vivía en una pestaña y la lista de lo cargado en otra.
 *
 * ⚠️ Los números que muestra salen de la BASE, no del JSON versionado
 * (`percepcion_calendario_ucn.json`). Los dos pueden diferir: el JSON es la
 * fuente, pero alguien tiene que correr `_cargar_calendario_percepcion.py` para
 * que entre. Si acá aparecen menos eventos de los que el archivo declara, es que
 * falta esa carga — no que se hayan perdido.
 *
 * Existe porque los 125 eventos del calendario académico estaban en la base y en el
 * gráfico, pero en ningún lugar donde se los pudiera LEER. Un dato que alimenta un
 * modelo y que nadie puede inspeccionar es un dato en el que hay que confiar a ciegas.
 *
 * Lo que este bloque tiene que dejar claro, además de la lista:
 *
 * * **Cuántos eventos son de fecha CONFIRMADA y cuántos no.** El calendario declara
 *   varios casos sin verificar («la duración efectiva del paro no está documentada»,
 *   «fechas exactas no verificadas»). Medir duración o velocidad de recuperación con
 *   esos mediría la suposición, no el hecho.
 * * **Cuántos episodios disruptivos hay.** Es el cuello de botella real del proyecto:
 *   el efecto del paro está medido (−9,5 puntos), pero con seis semanas disruptivas
 *   la media es un estimador pésimo. No faltan datos: faltan CASOS.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import { esCancelacion, percepcionApi, type EventoItem } from "../lib/percepcion";
import { CARD, TituloBloque, nro } from "./PercepcionUI";

const DISRUPTIVOS = new Set(["paro", "toma", "emergencia"]);

const COLOR_CONFIANZA: Record<string, string> = {
  confirmado: "text-dato-favorable",
  estimado: "text-ucn-tierra-clara",
  planificado: "text-slate-500",
};

const AYUDA_CONFIANZA: Record<string, string> = {
  confirmado: "Fecha documentada.",
  estimado: "El hecho ocurrió, pero las fechas son aproximadas. No usar para medir duración.",
  planificado: "Fecha de calendario futura: todavía puede moverse.",
};

function anio(iso: string): string {
  return iso.slice(0, 4);
}

export function PercepcionCalendarioDatos() {
  const [eventos, setEventos] = useState<EventoItem[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [soloDisruptivos, setSoloDisruptivos] = useState(false);
  const [abierto, setAbierto] = useState(false);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      const r = await percepcionApi.eventosTodos(opts);
      setEventos(r.items);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar el calendario.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const resumen = useMemo(() => {
    const porConfianza: Record<string, number> = {};
    const porAnio: Record<string, number> = {};
    let disruptivos = 0;
    for (const e of eventos) {
      const c = e.confianza ?? "estimado";
      porConfianza[c] = (porConfianza[c] ?? 0) + 1;
      porAnio[anio(e.fecha_inicio)] = (porAnio[anio(e.fecha_inicio)] ?? 0) + 1;
      if (DISRUPTIVOS.has(e.tipo)) disruptivos += 1;
    }
    return { porConfianza, porAnio, disruptivos };
  }, [eventos]);

  const lista = useMemo(() => {
    const base = soloDisruptivos ? eventos.filter((e) => DISRUPTIVOS.has(e.tipo)) : eventos;
    return [...base].sort((a, b) => b.fecha_inicio.localeCompare(a.fecha_inicio));
  }, [eventos, soloDisruptivos]);

  return (
    <div className={CARD} style={{ opacity: cargando ? 0.55 : 1 }} aria-busy={cargando}>
      <TituloBloque titulo="Calendario cargado">
        Las causas registradas con las que se explica la percepción: matrículas,
        recesos, evaluaciones, titulaciones y movilizaciones, 2022–2026. Es el insumo
        del baseline de calendario y de cualquier medición de respuesta a shock.
      </TituloBloque>

      {error ? <p className="text-sm text-ucn-tierra-clara">{error}</p> : null}

      <div className="mb-3 flex flex-wrap gap-2">
        <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
          <p className="text-xs uppercase tracking-wide text-slate-500">Eventos</p>
          <p className="text-lg font-semibold text-slate-100">{nro(eventos.length)}</p>
        </div>
        <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
          <p className="text-xs uppercase tracking-wide text-slate-500">Disruptivos</p>
          <p className="text-lg font-semibold text-ucn-tierra-clara">{nro(resumen.disruptivos)}</p>
          <p className="text-sm text-slate-500">paros, tomas y emergencias</p>
        </div>
        {(["confirmado", "estimado", "planificado"] as const).map((c) =>
          resumen.porConfianza[c] ? (
            <div key={c} className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">{c}</p>
              <p className={`text-lg font-semibold ${COLOR_CONFIANZA[c]}`}>
                {nro(resumen.porConfianza[c])}
              </p>
              <p className="max-w-[15rem] text-sm leading-4 text-slate-500">
                {AYUDA_CONFIANZA[c]}
              </p>
            </div>
          ) : null,
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <span>Por año:</span>
        {Object.entries(resumen.porAnio)
          .sort()
          .map(([a, n]) => (
            <span key={a} className="rounded border border-white/10 px-2 py-0.5">
              {a}: {n}
            </span>
          ))}
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-white/5 pt-2">
        <button
          type="button"
          onClick={() => setAbierto((v) => !v)}
          className="rounded border border-white/10 px-2.5 py-1 text-sm text-slate-400 transition hover:border-white/25 hover:text-slate-100"
        >
          {abierto ? "Ocultar la lista" : "Ver la lista completa"}
        </button>
        {abierto ? (
          <button
            type="button"
            onClick={() => setSoloDisruptivos((v) => !v)}
            className={
              soloDisruptivos
                ? "rounded border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-2.5 py-1 text-sm text-ucn-tierra-clara"
                : "rounded border border-white/10 px-2.5 py-1 text-sm text-slate-400 transition hover:border-white/25 hover:text-slate-100"
            }
          >
            solo paros y tomas
          </button>
        ) : null}
      </div>

      {abierto ? (
        <div className="mt-2 max-h-96 overflow-y-auto rounded-md border border-white/5">
          {lista.map((e) => {
            const c = e.confianza ?? "estimado";
            return (
              <div
                key={`${e.nombre}-${e.fecha_inicio}`}
                className="border-b border-white/5 px-3 py-1.5 last:border-0"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="font-mono text-sm text-slate-500">
                    {e.fecha_inicio}
                    {e.fecha_fin && e.fecha_fin !== e.fecha_inicio ? ` → ${e.fecha_fin}` : ""}
                  </span>
                  <span className="text-sm text-slate-100">{e.nombre}</span>
                  <span className={`text-sm ${COLOR_CONFIANZA[c]}`} title={AYUDA_CONFIANZA[c]}>
                    {c}
                  </span>
                  {e.ambito && e.ambito !== "global" ? (
                    <span className="text-sm text-slate-500">· {e.ambito}</span>
                  ) : null}
                </div>
                {e.descripcion ? (
                  <p className="text-sm leading-5 text-slate-500">{e.descripcion}</p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export default PercepcionCalendarioDatos;
