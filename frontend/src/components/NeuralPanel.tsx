"use client";

// DAI Neural — panel del módulo: pestañas principales. Las ya visitadas siguen montadas (ocultas) para que
// las selecciones no se pierdan al cambiar de pestaña.
// Orden pensado como un relato para quien decide, en tres grupos: «Lo que pasó» (Histórico, Cohortes, Traslados), «Lo que viene»
// (Proyecciones) y «Cuánto confiar» (Modelos, Modelo por facultad, Calidad de los datos).
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { esCancelacion, neuralApi } from "../lib/neural";
import { PROPOSITO_PESTANA, TERMINOS_MODULO } from "../lib/neuralLenguaSimple";
import { NeuralAceptacion } from "./NeuralAceptacion";
import { NeuralCalidad } from "./NeuralCalidad";
import { NeuralCohortes } from "./NeuralCohortes";
import { NeuralFacultades } from "./NeuralFacultades";
import { NeuralLoQuePaso } from "./NeuralLoQuePaso";
import { NeuralLoQueViene } from "./NeuralLoQueViene";
import { NeuralModelos } from "./NeuralModelos";
import { AvisoSeccionSinPoblacion, SELECCION_UCN, type SeleccionPoblacion } from "./NeuralSelectorPoblacion";
import { NeuralTraslados } from "./NeuralTraslados";
import { AceptacionRevocadaContext, Insignia, Pestanas, type PestanaDef } from "./NeuralUI";

type Vista = "historico" | "proyeccion" | "modelos" | "facultad" | "cohortes" | "traslados" | "calidad";
const PASO = "Lo que pasó";
const VIENE = "Lo que viene";
const CONFIAR = "Cuánto confiar";
const PESTANAS: readonly PestanaDef<Vista>[] = [
  { id: "historico", label: "Histórico", grupo: PASO },
  { id: "cohortes", label: "Cohortes", grupo: PASO },
  { id: "traslados", label: "Traslados", grupo: PASO },
  { id: "proyeccion", label: "Proyecciones", grupo: VIENE },
  { id: "modelos", label: "Modelos", grupo: CONFIAR },
  { id: "facultad", label: "Modelo por facultad", grupo: CONFIAR },
  { id: "calidad", label: "Calidad de los datos", grupo: CONFIAR },
];
const PREFIJO = "neural";
// Build-time switch (see docs/github-pages.md); literal on purpose so the bundler folds it.
const MODO_PAGES = process.env.NEXT_PUBLIC_MODO === "pages";

/** "2026-11-19T10:00:00Z" -> "19-11-2026"; null if it does not have the expected shape. */
function fechaPublicacion(publicadoEn: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(publicadoEn);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : null;
}

/** Pages: publication date. If the request fails the line is omitted and nothing else is blocked. */
function usePublicadoEl(): string | null {
  const [fecha, setFecha] = useState<string | null>(null);
  useEffect(() => {
    if (!MODO_PAGES) return;
    const ctl = new AbortController();
    neuralApi.publicacion(ctl.signal)
      .then((p) => setFecha(fechaPublicacion(p.publicado_en)))
      .catch((e: unknown) => { if (!esCancelacion(e)) setFecha(null); });
    return () => ctl.abort();
  }, []);
  return fecha;
}
/** Pestañas que no usan la población elegida: lo dicen una vez arriba cuando hay una población distinta de Toda la UCN. */
const SIN_POBLACION: ReadonlySet<Vista> = new Set<Vista>(["modelos", "calidad"]);

export function NeuralPanel() {
  const publicadoEl = usePublicadoEl();
  const [vista, setVista] = useState<Vista>("historico");
  const [visitadas, setVisitadas] = useState<ReadonlySet<Vista>>(new Set<Vista>(["historico"]));
  // La población elegida (facultad y programa) se comparte entre «Histórico», «Proyecciones», «Cohortes» y «Traslados» (que abre el detalle del programa); «Modelo por facultad» la toma como valor inicial.
  const [seleccion, setSeleccion] = useState<SeleccionPoblacion>(SELECCION_UCN);
  const [aceptada, setAceptada] = useState(false);
  const [rechazada, setRechazada] = useState(false);
  const alAceptar = useCallback(() => { setRechazada(false); setAceptada(true); }, []);
  const volverALaPuerta = useCallback(() => { setRechazada(true); setAceptada(false); }, []);
  const cambiar = (v: Vista) => {
    setVista(v);
    setVisitadas((s) => (s.has(v) ? s : new Set(s).add(v)));
  };
  const contenido: Record<Vista, () => ReactNode> = {
    historico: () => <NeuralLoQuePaso seleccion={seleccion} onSeleccion={setSeleccion} />,
    proyeccion: () => <NeuralLoQueViene seleccion={seleccion} onSeleccion={setSeleccion} />,
    modelos: () => <NeuralModelos onVerFacultades={() => cambiar("facultad")} />,
    facultad: () => <NeuralFacultades seleccion={seleccion} onSeleccion={setSeleccion} />,
    cohortes: () => <NeuralCohortes seleccion={seleccion} onSeleccion={setSeleccion} onVerTraslados={() => cambiar("traslados")} />,
    traslados: () => <NeuralTraslados seleccion={seleccion} onSeleccion={setSeleccion} />,
    calidad: () => <NeuralCalidad />,
  };
  return (
    <div className="space-y-4">
      <div>
        <p className="boveda-kicker">DAI Neural</p>
        <h1 className="portal-title mt-1 text-2xl font-bold text-[var(--portal-fg)]">Trayectorias estudiantiles</h1>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--portal-muted)]">
          Qué tan bien pueden los modelos anticipar la trayectoria de los estudiantes de pregrado de la UCN (continuar, aprobar, egresar,
          cambiar de programa), y qué muestran los datos históricos de cohortes y traslados. Son cifras de conjuntos: no se muestran
          nombres, RUT ni listas de estudiantes.
        </p>
        {publicadoEl ? <p className="mt-1 text-xs text-[var(--portal-muted)]">Datos publicados el {publicadoEl}.</p> : null}
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Condiciones de uso del módulo">
          <Insignia tono="azul">Solo lectura</Insignia>
          <Insignia>Sin nombres ni listas de estudiantes</Insignia>
        </div>
        <details className="mt-3 max-w-3xl rounded-md border border-[var(--boveda-linea)] px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold text-[var(--portal-fg)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
            Palabras que se usan en este módulo
          </summary>
          <dl className="mt-2 grid gap-x-6 gap-y-2 md:grid-cols-2">
            {TERMINOS_MODULO.map((t) => (
              <div key={t.termino}>
                <dt className="text-sm font-semibold text-[var(--portal-fg)]">{t.termino}</dt>
                <dd className="text-sm leading-6 text-[var(--portal-muted)]">{t.definicion}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
      {!aceptada ? (
        <NeuralAceptacion onAceptada={alAceptar} trasRechazo={rechazada} onReintentar={alAceptar} />
      ) : (
        <AceptacionRevocadaContext.Provider value={volverALaPuerta}>
          <Pestanas pestanas={PESTANAS} activa={vista} onCambio={cambiar} etiqueta="Secciones de DAI Neural" prefijo={PREFIJO} />
          {PESTANAS.map((p) =>
            visitadas.has(p.id) ? (
              <div
                key={p.id}
                role="tabpanel"
                id={`${PREFIJO}-panel-${p.id}`}
                aria-labelledby={`${PREFIJO}-tab-${p.id}`}
                hidden={vista !== p.id}
                className="space-y-4 pt-1"
              >
                <Proposito id={p.id} />
                {SIN_POBLACION.has(p.id) ? <AvisoSeccionSinPoblacion seleccion={seleccion} /> : null}
                {contenido[p.id]()}
              </div>
            ) : null,
          )}
        </AceptacionRevocadaContext.Provider>
      )}
    </div>
  );
}

/** Una frase que dice para qué sirve la pestaña y cómo leerla (siempre arriba, antes de cualquier tabla o gráfico). */
function Proposito({ id }: { id: Vista }) {
  const t = PROPOSITO_PESTANA[id];
  return (
    <div className="max-w-3xl">
      <p className="text-base leading-7 text-[var(--portal-fg)]">{t.proposito}</p>
      <p className="mt-1 text-sm leading-6 text-[var(--portal-muted)]"><strong className="font-semibold text-[var(--portal-fg)]">Cómo leerla.</strong> {t.leer}</p>
    </div>
  );
}
