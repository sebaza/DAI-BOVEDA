"use client";

// Etiqueta del modelo que respalda una conclusión: «T1 · Continuidad · CatBoost … · corte al 1.er semestre», con el desplegable
// «Cómo se calculó» (población, partición y si es esperado o proyección). Un bloque solo descriptivo dice «Dato observado, sin modelo».
// Los códigos T1–T6 pueden mostrarse al lector, siempre junto al nombre en español de la tarea. Todo sale de lo que dice el servidor.
// Un modelo que el servidor no pudo identificar (`modelo_no_identificado`) no muestra etiqueta alguna.
import { createContext, useContext } from "react";

import type { ConModelo, ModeloVisible } from "../lib/neural";
import { MODELO_TEXTOS as TX, llenar } from "../lib/neuralLenguaSimple";

/** Texto de la población que se está mirando (toda la UCN, una facultad o un programa), tal como la muestra el bloque; lo pone cada pestaña. */
export const PoblacionContext = createContext<string>("Toda la UCN");

/**
 * Único formato de la población de un bloque: «Toda la UCN», «Facultad» o «Facultad · NOMBRE DEL PROGRAMA (código)».
 * Recibe lo que la pestaña mostró de verdad (la respuesta del servidor), no la selección cruda.
 */
export function textoPoblacion(filtro: string, programa?: { nombre: string; codigo: string; facultad: string } | null): string {
  return programa ? `${programa.facultad} · ${programa.nombre} (${programa.codigo})` : filtro;
}

/** Chip discreto con la población del bloque; con `soloUcn` (el bloque no cambia con la población) dice «Toda la UCN». */
export function ChipPoblacion({ soloUcn = false }: { soloUcn?: boolean }) {
  const contexto = useContext(PoblacionContext);
  return (
    <span className="inline-flex max-w-full items-baseline gap-1 rounded-md border border-[var(--boveda-linea)] px-2 py-0.5 text-xs leading-5 text-[var(--portal-muted)] [overflow-wrap:anywhere]">
      <span className="shrink-0 font-medium">{TX.poblacion}:</span>
      <span>{soloUcn ? "Toda la UCN" : contexto}</span>
    </span>
  );
}

/** «T1 · Continuidad · CatBoost (…) · corte al 1.er semestre». El corte ya viene en español desde el servidor. */
export function textoModelo(m: ModeloVisible): string {
  return [`${m.tarea} · ${m.tarea_nombre}`, m.modelo_nombre, m.corte ? llenar(TX.corte, { corte: m.corte }) : ""].filter(Boolean).join(" · ");
}

/** Un modelo: su etiqueta y el desplegable «Cómo se calculó». */
export function EtiquetaModelo({ modelo }: { modelo: ModeloVisible }) {
  const poblacion = useContext(PoblacionContext);
  const tipo = (TX.tipos as Record<string, string>)[modelo.tipo] ?? modelo.tipo;
  return (
    <div className="min-w-0 max-w-3xl">
      <p className="inline-block max-w-full rounded-md border border-[var(--boveda-linea)] px-2 py-1 text-xs leading-5 text-[var(--portal-fg)] [overflow-wrap:anywhere]">
        {textoModelo(modelo)}
      </p>
      <details className="mt-1 text-xs leading-5 text-[var(--portal-muted)]">
        <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
          {TX.comoSeCalculo}
        </summary>
        <dl className="mt-1 space-y-0.5 [overflow-wrap:anywhere]">
          <div><dt className="inline font-semibold text-[var(--portal-fg)]">{TX.poblacion}: </dt><dd className="inline">{poblacion}</dd></div>
          <div><dt className="inline font-semibold text-[var(--portal-fg)]">{TX.particion}: </dt><dd className="inline">{modelo.particion}</dd></div>
          <div><dt className="inline font-semibold text-[var(--portal-fg)]">{TX.calculo}: </dt><dd className="inline">{tipo}</dd></div>
        </dl>
      </details>
    </div>
  );
}

/**
 * La etiqueta de un bloque: un modelo, varios (cada uno con su etiqueta) o «Dato observado, sin modelo». Con
 * `aplica_a_poblacion: false` agrega la nota de que el bloque describe el modelo y no cambia con la población elegida.
 */
export function NeuralModeloEtiqueta({ bloque }: { bloque: ConModelo & { aplica_a_poblacion?: boolean } }) {
  const varios = bloque.modelo ? [] : (bloque.modelos ?? []);
  // Un bloque que describe el modelo se calcula siempre sobre toda la UCN, sea cual sea la población elegida.
  const poblacion = bloque.aplica_a_poblacion === false ? "Toda la UCN" : null;
  const cuerpo = (
    <div className="mt-2 space-y-1.5">
      {bloque.modelo ? (
        <EtiquetaModelo modelo={bloque.modelo} />
      ) : varios.length > 0 ? (
        <>
          <p className="text-xs leading-5 text-[var(--portal-muted)]">{TX.varios}</p>
          {varios.map((m) => <EtiquetaModelo key={`${m.tarea}-${m.modelo}-${m.k}-${m.particion}-${m.tipo}`} modelo={m} />)}
        </>
      ) : bloque.modelo_no_identificado ? null : (
        <p className="text-xs leading-5 text-[var(--portal-muted)]">{TX.observado}</p>
      )}
      {bloque.aplica_a_poblacion === false ? <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{TX.noCambia}</p> : null}
    </div>
  );
  return poblacion ? <PoblacionContext.Provider value={poblacion}>{cuerpo}</PoblacionContext.Provider> : cuerpo;
}
