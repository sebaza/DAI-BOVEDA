"use client";

// Pestaña Cohortes: resultados por generación de ingreso de un programa y la curva de créditos o promedio por semestre.
import { useMemo, useState } from "react";

import { neuralApi, type CohorteResultado, type CohortesPrograma, type EstadisticaComparacion, type FacultadFiltro, type ProgramaResumen } from "../lib/neural";
import { opcionBanda, type PuntoBanda } from "../lib/neuralGraficos";
import { COHORTES_TEXTOS as TX, llenar } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import { NeuralSelectorPoblacion, UCN, resolverFiltro, type SeleccionPoblacion } from "./NeuralSelectorPoblacion";
import { TrasladosDelPrograma } from "./NeuralTraslados";
import {
  CARD, Carga, ErrorCarga, Esqueleto, FILA, Insignia, LeyendaPocosCasos, MarcoGrafico, Notas, POCOS_CASOS, PocosCasos, SELECT, TD, TH, TablaScroll, Titulo, Vacio,
  entero, num, pct, useCarga, type DatosGrafico,
} from "./NeuralUI";

/**
 * Los programas de la pestaña agrupados por facultad. `/neural/programas` no trae la facultad: se toma de la lista de facultades que
 * ya conoce «Histórico» (mismo código de programa). Los programas que ahí no figuran quedan en un grupo aparte.
 */
function jerarquiaDeCohortes(lista: readonly ProgramaResumen[], base: readonly FacultadFiltro[]): FacultadFiltro[] {
  const facultadDe = new Map<string, string>();
  for (const f of base) for (const p of f.programas) facultadDe.set(p.codigo, f.facultad);
  const grupos = new Map<string, { codigo: string; nombre: string }[]>();
  for (const p of lista) {
    const fac = facultadDe.get(p.cod_programa) ?? TX.otrosProgramas;
    grupos.set(fac, [...(grupos.get(fac) ?? []), { codigo: p.cod_programa, nombre: p.nombre_programa ?? p.cod_programa }]);
  }
  const orden = [...base.map((f) => f.facultad), TX.otrosProgramas].filter((f) => f !== UCN && grupos.has(f));
  return [
    { facultad: UCN, programas: [] },
    ...orden.map((f) => ({ facultad: f, programas: (grupos.get(f) ?? []).sort((x, y) => x.nombre.localeCompare(y.nombre, "es")) })),
  ];
}

/** `seleccion` es la del panel: elegir aquí también la cambia en «Histórico» y «Proyecciones» (si ahí figura el programa). */
export function NeuralCohortes({ seleccion, onSeleccion, onVerTraslados }: {
  seleccion: SeleccionPoblacion;
  onSeleccion: (s: SeleccionPoblacion) => void;
  onVerTraslados?: () => void;
}) {
  const programas = useCarga((s) => neuralApi.programas(s), []);
  const facultades = useCarga((s) => neuralApi.historico({ facultad: null, programa: null }, s), []);
  // Sin la lista de facultades (si falla) igual se puede elegir: los programas quedan en un solo grupo.
  const jerarquia = useMemo(
    () => (programas.fase === "ok" && facultades.fase !== "cargando"
      ? jerarquiaDeCohortes(programas.datos, facultades.fase === "ok" ? facultades.datos.jerarquia ?? [] : [])
      : null),
    [programas, facultades],
  );
  // «Otros programas» es solo un grupo de esta pestaña: nunca sale de aquí como facultad. Al escribir se guarda como Toda la UCN con
  // el programa; al leer, un programa de ese grupo con Toda la UCN se muestra de nuevo dentro del grupo.
  // Elegir el grupo en sí (sin programa) solo lo abre aquí, en `otrosAbierto`, para que su lista de programas se pueda recorrer.
  const [otrosAbierto, setOtrosAbierto] = useState(false);
  const sel = useMemo<SeleccionPoblacion>(() => {
    const otros = jerarquia?.find((f) => f.facultad === TX.otrosProgramas);
    if (seleccion.facultad !== UCN) return seleccion;
    if (seleccion.programa === null) return otrosAbierto && otros ? { ...seleccion, facultad: TX.otrosProgramas } : seleccion;
    return otros?.programas.some((p) => p.codigo === seleccion.programa) ? { ...seleccion, facultad: TX.otrosProgramas } : seleccion;
  }, [seleccion, jerarquia, otrosAbierto]);
  const escribir = (s: SeleccionPoblacion) => {
    if (s.facultad !== TX.otrosProgramas) { setOtrosAbierto(false); onSeleccion(s); return; }
    if (s.programa === null) { setOtrosAbierto(true); return; }
    onSeleccion({ ...s, facultad: UCN });
  };
  const r = resolverFiltro(sel, jerarquia);
  const cod = r.filtro.programa ?? "";
  return (
    <div className="space-y-5">
      {programas.fase === "error" ? (
        <ErrorCarga mensaje={programas.mensaje} status={programas.status} onReintentar={programas.reintentar} />
      ) : jerarquia === null ? (
        <section className={CARD} aria-label="Elegir población"><Esqueleto filas={2} /></section>
      ) : (
        <NeuralSelectorPoblacion
          idPrefijo="neural-coh" jerarquia={jerarquia} seleccion={r.seleccion} onSeleccion={escribir}
          programaSinDatos={false} facultadSinDatos={false}
        >
          {r.facultadSinDatos ? (
            <p role="status" className="min-w-0 basis-full text-xs leading-5 text-[var(--portal-muted)]">{llenar(TX.sinDatosFacultad, { facultad: sel.facultad })}</p>
          ) : null}
          {r.programaSinDatos ? (
            <p role="status" className="min-w-0 basis-full text-xs leading-5 text-[var(--portal-muted)]">
              {llenar(TX.sinDatosPrograma, { programa: seleccion.nombrePrograma ?? seleccion.programa ?? "El programa elegido" })}
            </p>
          ) : null}
        </NeuralSelectorPoblacion>
      )}
      {cod ? (
        <Programa key={cod} cod={cod} onVerTraslados={onVerTraslados} />
      ) : (
        <Vacio titulo={TX.elige}>
          {sel.facultad !== UCN && !r.facultadSinDatos ? llenar(TX.eligeDeFacultad, { facultad: sel.facultad }) : TX.eligeAyuda}
        </Vacio>
      )}
    </div>
  );
}

function Programa({ cod, onVerTraslados }: { cod: string; onVerTraslados?: () => void }) {
  const estado = useCarga((s) => neuralApi.cohortes(cod, s), [cod]);
  return (
    <Carga estado={estado} filas={6} alto="h-8">
      {(d) => (
        <div className="space-y-5">
          <section className={CARD} aria-label="Resultados por cohorte">
            <Titulo sub="Cada fila es una generación: las personas que ingresaron al programa en el mismo período. Se cuenta a quienes siguen tras el primer año y a quienes se titulan dentro de la duración del plan o con uno o dos años más.">
              Resultados por generación · {d.nombre_programa ?? d.cod_programa}
            </Titulo>
            <TablaResultados filas={d.resultados} />
          </section>
          <section className={CARD} aria-label="Curva por semestre">
            <Curva d={d} />
          </section>
          <TrasladosDelPrograma cod={cod} onVerTodo={onVerTraslados} />
          <Notas notas={d.notas} />
        </div>
      )}
    </Carga>
  );
}

function celdaTitulados(r: CohorteResultado, censurado: boolean, v: number | null) {
  if (censurado) return <Insignia tono="aviso" titulo="La ventana de observación aún no termina: no hay valor, no es cero.">en curso</Insignia>;
  if (v == null) return "—";
  return <>{entero(v)} <span className="text-xs text-[var(--portal-subtle)]">de {entero(r.n_ingreso)} ({pct(v / r.n_ingreso)})</span></>;
}

function TablaResultados({ filas }: { filas: CohorteResultado[] }) {
  if (filas.length === 0) return <Vacio>El programa no tiene cohortes con resultados.</Vacio>;
  const dur = filas.find((f) => f.duracion_anios != null)?.duracion_anios ?? null;
  return (
    <TablaScroll etiqueta="Resultados por cohorte">
      <table className="w-full">
        <caption className="sr-only">Ingreso, continuidad tras el primer año y titulación por generación</caption>
        <thead>
          <tr>
            <th className={TH}>Generación</th><th className={TH}>Ingresaron</th><th className={TH}>Siguen tras el 1.er año</th>
            <th className={TH}>Titulados en la duración del plan{dur ? ` (${dur} años)` : ""}</th>
            <th className={TH}>Titulados con 1 año más</th><th className={TH}>Titulados con 2 años más</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((r) => (
            <tr key={r.cohorte} className={FILA}>
              <td className={TD}>{r.cohorte}</td>
              <td className={`${TD} ${r.pocos_casos ? "opacity-60" : ""}`}>
                {entero(r.n_ingreso)}{r.pocos_casos ? <> <PocosCasos /></> : null}
              </td>
              <td className={TD}>
                {r.censurado_retencion ? <Insignia tono="aviso" titulo="Aún no se observa el semestre 3.">en curso</Insignia>
                  : r.n_retencion_obs ? <>{entero(r.n_retenidos)} <span className="text-xs text-[var(--portal-subtle)]">de {entero(r.n_retencion_obs)} ({pct((r.n_retenidos ?? 0) / r.n_retencion_obs)})</span></>
                  : "—"}
              </td>
              <td className={TD}>{celdaTitulados(r, r.censurado_d, r.titulados_d)}</td>
              <td className={TD}>{celdaTitulados(r, r.censurado_d1, r.titulados_d1)}</td>
              <td className={TD}>{celdaTitulados(r, r.censurado_d2, r.titulados_d2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="space-y-1 border-t border-[var(--boveda-linea)] px-3 py-2">
        <LeyendaPocosCasos />
        <p className="text-xs leading-5 text-[var(--portal-muted)]">«En curso»: aún no pasa el tiempo para saberlo.</p>
      </div>
    </TablaScroll>
  );
}

function Curva({ d }: { d: CohortesPrograma }) {
  const [cohorte, setCohorte] = useState("");
  const [metrica, setMetrica] = useState<"creditos" | "promedio">("creditos");
  const cohortes = useMemo(() => [...new Set(d.semestres_por_cohorte.map((s) => s.cohorte))].sort(), [d.semestres_por_cohorte]);
  const dec = metrica === "creditos" ? 0 : 2;

  const base: (EstadisticaComparacion & { semestre_k: number })[] = useMemo(
    () => (cohorte ? d.semestres_por_cohorte.filter((s) => s.cohorte === cohorte) : d.semestres_programa)
      .slice().sort((a, b) => a.semestre_k - b.semestre_k),
    [d, cohorte],
  );
  const puntos = useMemo<PuntoBanda[]>(
    () => base.map((s) => metrica === "creditos"
      ? { k: s.semestre_k, p25: s.creditos_p25, p50: s.creditos_p50, p75: s.creditos_p75, n: s.n_activos, pocosCasos: s.n_activos < POCOS_CASOS }
      : { k: s.semestre_k, p25: s.promedio_p25, p50: s.promedio_p50, p75: s.promedio_p75, n: s.n_promedio, pocosCasos: s.n_promedio < POCOS_CASOS }),
    [base, metrica],
  );
  const nombreRef = cohorte ? `Generación ${cohorte}` : "Todo el programa";
  const option = useMemo(
    () => opcionBanda({ puntos, decimales: dec, etiquetaY: metrica === "creditos" ? "Créditos acumulados" : "Promedio acumulado", nombreReferencia: nombreRef }),
    [puntos, dec, metrica, nombreRef],
  );
  const hayVisibles = puntos.some((p) => p.p50 != null);
  const datos: DatosGrafico = {
    columnas: ["Semestre desde el ingreso", "Personas", "25 %", "Valor central (mediana)", "75 %"],
    filas: puntos.map((p) => [String(p.k), p.n, p.p25 == null ? null : num(p.p25, dec), p.p50 == null ? null : num(p.p50, dec), p.p75 == null ? null : num(p.p75, dec)]),
    columnaN: 1,
  };

  return (
    <>
      <Titulo sub="Valor central (mediana) y rango central (del 25 % al 75 % de las personas) entre quienes siguen activos en cada semestre desde el ingreso.">Evolución por semestre</Titulo>
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="w-56">
          <label htmlFor="neural-coh-sel" className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-400">Generación</label>
          <select id="neural-coh-sel" className={SELECT} value={cohorte} onChange={(e) => setCohorte(e.target.value)}>
            <option value="">Todo el programa</option>
            {cohortes.map((c) => <option key={c} value={c}>Generación {c}</option>)}
          </select>
        </div>
        <div className="w-56">
          <label htmlFor="neural-coh-met" className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-400">Indicador</label>
          <select id="neural-coh-met" className={SELECT} value={metrica} onChange={(e) => setMetrica(e.target.value as "creditos" | "promedio")}>
            <option value="creditos">Créditos acumulados</option>
            <option value="promedio">Promedio acumulado</option>
          </select>
        </div>
      </div>
      {puntos.length === 0 || !hayVisibles ? (
        <Vacio>Sin datos por semestre para este grupo.</Vacio>
      ) : (
        <MarcoGrafico
          datos={datos}
          descripcion={`${metrica === "creditos" ? "Créditos acumulados" : "Promedio acumulado"} por semestre desde el ingreso (${nombreRef}): valor central y rango del 25 % al 75 %.`}
        >
          <EChartsChart option={option} height={320} ariaLabel="Valor central y rango central por semestre desde el ingreso; el detalle de cada punto muestra cuántas personas hay." />
        </MarcoGrafico>
      )}
      {puntos.some((p) => p.pocosCasos && p.p50 != null) ? <div className="mt-2"><LeyendaPocosCasos grafico /></div> : null}
    </>
  );
}
