"use client";

// Esperado frente a observado por programa, facultad, sexo, vía de ingreso y tipo de colegio (solo agregados). El servidor
// entrega todos los grupos, con su intervalo de 95 % y la marca «pocos casos» (n < 10); esta sección no recalcula nada.
import { useMemo, useState } from "react";

import { neuralApi, type FichaTarea, type GrupoTarea, type NivelGrupo, type ResumenGrupoTarea, type TareaId, type VistaTarea } from "../lib/neural";
import {
  BANDAS, ETIQUETA_BANDA, MAX_GRUPOS_GRAFICO, intervaloEsperada, intervaloObservada, nombreGrupo, opcionDumbbell, textoPuntos,
} from "../lib/neuralGraficosTareas";
import { GRUPOS_TEXTOS, llenar } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import {
  Aviso, Carga, FILA, LeyendaPocosCasos, MarcoGrafico, Notas, PocosCasos, Segmentado, TD, TH, TablaScroll, Titulo, Vacio, entero,
  metricaConIc, num, pct, pctConIc, useAncho, useCarga,
} from "./NeuralUI";

type Columna = "nombre" | "facultad" | "n" | "eventos" | "observada" | "esperada" | "brecha" | "ap" | "auc";
interface Orden { col: Columna; asc: boolean }

const NIVELES_BASE: { id: NivelGrupo; label: string }[] = (["programa", "facultad", "sexo", "via", "tipo_colegio"] as const)
  .map((id) => ({ id, label: GRUPOS_TEXTOS.niveles[id] }));

function valorOrden(g: GrupoTarea, col: Columna, nivel: NivelGrupo): number | string {
  switch (col) {
    case "nombre": return nombreGrupo(g, nivel).toLocaleLowerCase("es");
    case "facultad": return (g.facultad ?? "").toLocaleLowerCase("es");
    case "n": return g.n;
    case "eventos": return g.eventos ?? -1;
    case "observada": return g.observada ?? -1;
    case "esperada": return g.esperada ?? -1;
    case "brecha": return g.esperada != null && g.observada != null ? g.esperada - g.observada : -Infinity;
    case "ap": return g.ap ?? -1;
    case "auc": return g.roc_auc ?? -1;
  }
}

function ordenar(grupos: readonly GrupoTarea[], o: Orden, nivel: NivelGrupo): GrupoTarea[] {
  const signo = o.asc ? 1 : -1;
  return [...grupos].sort((a, b) => {
    const x = valorOrden(a, o.col, nivel), y = valorOrden(b, o.col, nivel);
    const r = typeof x === "string" && typeof y === "string" ? x.localeCompare(y, "es") : (x as number) - (y as number);
    return r === 0 ? a.nombre.localeCompare(b.nombre, "es") : r * signo;
  });
}

function explicacionEsperado(tarea: TareaId, evento: string): string {
  if (tarea === "t2") return "Para cada grupo se compara lo que el modelo anticipaba con lo que realmente ocurrió: «Lo que anticipó el modelo» es el porcentaje que pronosticó en cada banda de nota y «Lo que ocurrió», el porcentaje real en el conjunto de prueba.";
  if (tarea === "t6") return `Para cada grupo se muestra la tasa de «${evento}» que ocurrió y el riesgo esperado del modelo conservado. ${GRUPOS_TEXTOS.t6}`;
  return `Para cada grupo se compara lo que el modelo anticipaba con lo que realmente ocurrió: «Lo que anticipó el modelo» es la tasa de «${evento}» que pronostica en promedio para el grupo y «Lo que ocurrió», la tasa real en el conjunto de prueba.`;
}

export function SeccionGrupos({ tarea, ficha, vista }: { tarea: TareaId; ficha: FichaTarea; vista: VistaTarea }) {
  const niveles = useMemo(
    () => (tarea === "t6" ? [...NIVELES_BASE, { id: "nivel_postgrado" as NivelGrupo, label: GRUPOS_TEXTOS.niveles.nivel_postgrado }] : NIVELES_BASE),
    [tarea],
  );
  const [nivel, setNivel] = useState<NivelGrupo>("programa");
  const [banda, setBanda] = useState<string>(BANDAS[0]);
  const [verEsperado, setVerEsperado] = useState(false);
  const estado = useCarga((s) => neuralApi.modelosGrupos(tarea, nivel, vista.variante, vista.corte_k, s), [tarea, nivel, vista.variante, vista.corte_k]);
  const pron = vista.pronostico_agregado;
  // Las bandas de nota de T2 existen solo por programa y por facultad; los demás niveles traen una sola categoría.
  const usaBandas = tarea === "t2" && (nivel === "programa" || nivel === "facultad");
  const mostrarEsperada = pron === "no_disponible" ? false : pron === "no_confiable" ? verEsperado : true;

  return (
    <section className="space-y-4" aria-label="Por programa y facultad">
      <Titulo sub={GRUPOS_TEXTOS.sub}>Por programa, facultad y otros grupos</Titulo>
      <div className="flex flex-wrap items-center gap-3">
        <Segmentado etiqueta="Agrupar por" valor={nivel} onCambio={setNivel} opciones={niveles} />
        {usaBandas ? (
          <Segmentado etiqueta="Banda de nota" valor={banda} onCambio={setBanda}
            opciones={BANDAS.map((b) => ({ id: b, label: ETIQUETA_BANDA[b] }))} />
        ) : null}
      </div>
      {pron === "no_confiable" ? (
        <Aviso tono="tierra" titulo="El modelo no es confiable para pronosticar por grupo en esta tarea">
          Por eso se muestra lo que ocurrió; lo que anticipó el modelo queda oculto salvo que lo pidas.{" "}
          <label className="mt-2 flex items-center gap-2 text-[var(--portal-fg)]">
            <input type="checkbox" checked={verEsperado} onChange={(e) => setVerEsperado(e.target.checked)} className="h-4 w-4 accent-[var(--ucn-azul)]" />
            Mostrar de todos modos lo que anticipó el modelo
          </label>
        </Aviso>
      ) : null}
      <Carga estado={estado} filas={4} alto="h-8">
        {(d) => {
          const grupos = d.grupos.filter((g) => (usaBandas ? g.categoria === banda : true));
          const resumen = d.resumen.find((r) => (usaBandas ? r.categoria === banda : true));
          return (
            <Cuerpo tarea={tarea} evento={d.evento} nivel={nivel} grupos={grupos} resumen={resumen} mostrarEsperada={mostrarEsperada}
              pron={pron} notas={d.notas} />
          );
        }}
      </Carga>
    </section>
  );
}

function Cuerpo({
  tarea, evento, nivel, grupos, resumen, mostrarEsperada, pron, notas,
}: {
  tarea: TareaId; evento: string; nivel: NivelGrupo; grupos: GrupoTarea[]; resumen: ResumenGrupoTarea | undefined;
  mostrarEsperada: boolean; pron: string; notas: string[];
}) {
  const [orden, setOrden] = useState<Orden>({ col: "n", asc: false });
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const filas = useMemo(() => ordenar(grupos, orden, nivel), [grupos, orden, nivel]);
  const grafico = useMemo(
    () => (grupos.length ? opcionDumbbell(grupos, nivel, { mostrarEsperada, ancho, etiquetaEvento: evento, tarea }) : null),
    [grupos, nivel, mostrarEsperada, ancho, evento, tarea],
  );
  if (grupos.length === 0) {
    return (
      <Vacio titulo="Sin grupos">{GRUPOS_TEXTOS.vacio}</Vacio>
    );
  }
  const hayEsperada = grupos.some((g) => g.esperada != null) && mostrarEsperada;
  const hayFacultad = nivel === "programa" && grupos.some((g) => g.facultad);
  const columnas: { col: Columna; label: string; visible: boolean; derecha?: boolean }[] = [
    { col: "nombre", label: GRUPOS_TEXTOS.columnaNivel[nivel], visible: true },
    { col: "facultad", label: "Facultad", visible: hayFacultad },
    { col: "n", label: nivel === "nivel_postgrado" ? "Egresados" : "Personas evaluadas", visible: true, derecha: true },
    { col: "eventos", label: "Casos del evento", visible: grupos.some((g) => g.eventos != null), derecha: true },
    { col: "observada", label: "Lo que ocurrió", visible: true, derecha: true },
    { col: "esperada", label: "Lo que anticipó el modelo", visible: hayEsperada, derecha: true },
    { col: "brecha", label: "Diferencia: anticipado − ocurrido (puntos)", visible: hayEsperada, derecha: true },
    { col: "ap", label: "Qué tan bien ordena el modelo: AP (intervalo de 95 %)", visible: mostrarEsperada && grupos.some((g) => g.ap != null), derecha: true },
    { col: "auc", label: "ROC-AUC (intervalo de 95 %)", visible: mostrarEsperada && grupos.some((g) => g.roc_auc != null), derecha: true },
  ];
  const visibles = columnas.filter((c) => c.visible);
  const alternar = (col: Columna) => setOrden((o) => (o.col === col ? { col, asc: !o.asc } : { col, asc: col === "nombre" || col === "facultad" }));

  return (
    <div className="space-y-3">
      <p className="text-xs leading-5 text-[var(--portal-muted)]">{explicacionEsperado(tarea, evento)}</p>
      {resumen ? <LineaResumen r={resumen} hayEsperada={hayEsperada} /> : null}
      {grafico ? (
        <div ref={ref}>
          <MarcoGrafico descripcion={`Lo que ocurrió${hayEsperada ? " y lo que anticipó el modelo" : ""} en cada grupo, ordenado de mayor a menor.`}>
            <EChartsChart option={grafico.option} height={grafico.alto} ariaLabel={`Lo que ocurrió${hayEsperada ? " y lo que anticipó el modelo" : ""} en cada grupo.`} />
          </MarcoGrafico>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--portal-muted)]" aria-label="Leyenda">
        <span><span aria-hidden="true" className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-[var(--ucn-azul)] align-baseline" />Lo que ocurrió, con su margen de incertidumbre (95 %)</span>
        {hayEsperada ? <span><span aria-hidden="true" className="mr-1.5 inline-block h-2.5 w-2.5 bg-[var(--portal-copper)] align-baseline" />Lo que anticipó el modelo</span> : null}
      </div>
      {grafico?.recortado ? (
        <p className="text-xs text-[var(--portal-muted)]">{llenar(GRUPOS_TEXTOS.recortado, { max: String(MAX_GRUPOS_GRAFICO), n: entero(grupos.length) })}</p>
      ) : null}
      {grupos.some((g) => g.pocos_casos) ? <LeyendaPocosCasos grafico unidad={tarea === "t2" ? "inscripciones" : "personas"} /> : null}
      <TablaScroll etiqueta="Tabla de grupos, ordenable por columna">
        <table className="w-full">
          <caption className="sr-only">Lo que ocurrió y lo que anticipó el modelo en cada grupo. Cada encabezado ordena la tabla.</caption>
          <thead>
            <tr>
              {visibles.map((c) => (
                <th key={c.col} scope="col" className={`${TH} ${c.derecha ? "text-right" : ""}`}
                  aria-sort={orden.col === c.col ? (orden.asc ? "ascending" : "descending") : "none"}>
                  <button type="button" onClick={() => alternar(c.col)}
                    className="inline-flex items-center gap-1 uppercase tracking-wider hover:text-[var(--portal-fg)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
                    {c.label}<span aria-hidden="true">{orden.col === c.col ? (orden.asc ? "▲" : "▼") : ""}</span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((g) => (
              <tr key={`${g.categoria}-${g.grupo}`} className={`${FILA} ${g.pocos_casos ? "opacity-60" : ""}`}>
                <td className={`${TD} min-w-[14rem]`}>{nombreGrupo(g, nivel)}{g.pocos_casos ? <> <PocosCasos /></> : null}</td>
                {hayFacultad ? <td className={`${TD} min-w-[12rem]`}>{g.facultad ?? "—"}</td> : null}
                <td className={`${TD} text-right tabular-nums`}>{entero(g.n)}</td>
                {visibles.some((c) => c.col === "eventos") ? <td className={`${TD} text-right tabular-nums`}>{entero(g.eventos)}</td> : null}
                <td className={`${TD} whitespace-nowrap text-right tabular-nums`}>
                  {pctConIc(g.observada, intervaloObservada(g)?.[0], intervaloObservada(g)?.[1], 1)}
                  <span className="block text-xs text-[var(--portal-subtle)]">de {entero(g.n)}</span>
                </td>
                {hayEsperada ? (
                  <>
                    <td className={`${TD} whitespace-nowrap text-right tabular-nums`}>
                      {pctConIc(g.esperada, intervaloEsperada(g)?.[0], intervaloEsperada(g)?.[1], 1)}
                      <span className="block text-xs text-[var(--portal-subtle)]">de {entero(g.n)}</span>
                    </td>
                    <td className={`${TD} text-right tabular-nums`}>{textoPuntos(g.esperada, g.observada)}</td>
                  </>
                ) : null}
                {visibles.some((c) => c.col === "ap") ? <td className={`${TD} whitespace-nowrap text-right tabular-nums`}>{metricaConIc(g.ap, g.ap_lo, g.ap_hi)}</td> : null}
                {visibles.some((c) => c.col === "auc") ? <td className={`${TD} whitespace-nowrap text-right tabular-nums`}>{metricaConIc(g.roc_auc, g.auc_lo, g.auc_hi)}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      </TablaScroll>
      {pron === "confiable" ? <p className="text-xs text-[var(--portal-muted)]">Una diferencia pequeña entre lo anticipado y lo ocurrido es normal; compárala con el margen de incertidumbre de lo ocurrido.</p> : null}
      <Notas notas={notas} titulo={GRUPOS_TEXTOS.notas} />
    </div>
  );
}

function LineaResumen({ r, hayEsperada }: { r: ResumenGrupoTarea; hayEsperada: boolean }) {
  const partes: string[] = [];
  if (r.grupos_total != null) partes.push(llenar(GRUPOS_TEXTOS.grupos, { n: entero(r.grupos_total) }));
  if (hayEsperada && r.mae_modelo != null && r.mae_base != null) {
    partes.push(`Error promedio del modelo al anticipar la tasa del grupo: ${pct(r.mae_modelo)}; con la tasa histórica del programa: ${pct(r.mae_base)} (menor es mejor).`);
  }
  if (hayEsperada && r.spearman != null) partes.push(`Qué tan parecido es el orden de los grupos que anticipó el modelo al orden real (0 = nada, 1 = idéntico): ${num(r.spearman, 2)}.`);
  if (partes.length === 0) return null;
  return <p className="text-sm leading-6 text-[var(--portal-fg)]">{partes.join(" ")}</p>;
}
