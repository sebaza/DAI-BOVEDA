"use client";

// Pestaña «Proyecciones»: proyección para los estudiantes actuales, siempre como rango y con su fecha de corte. Cuatro bloques en este
// orden: umbral (dónde poner tutorías, lo principal), continuidad, eliminación y egreso. Cada bloque trae su gráfico, un número clave,
// una frase de qué se está mirando y «Cómo usarlo». Los números vienen del servidor (todos los grupos, con la marca «pocos casos» bajo 10;
// un bloque puede venir vacío): aquí solo se ordenan y se dibujan. Nunca hay una cifra ni una lista por estudiante.
import { useEffect, useState, type ReactNode } from "react";

import {
  neuralApi, type ConModelo, type FacultadFiltro, type ModeloVisible, type ProyCohorte, type ProyCohorteEgreso, type ProyContinuidad, type ProyEgreso, type ProyEliminacion, type ProyHito,
  type ProyUmbral, type ProyeccionVista,
} from "../lib/neural";
import {
  COLOR_CONTINUIDAD, COLOR_EGRESO, COLOR_ELIMINACION, opcionRangos, opcionUmbral, type FilaRango, type FilaUmbral,
} from "../lib/neuralGraficosProyeccion";
import { MODELO_TEXTOS, PROYECCION_TEXTOS as TX, llenar, periodoLegible } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import { Bloque, BloqueSinDatos, Clave, ComoUsarlo, PRIMERO_EN_CELULAR } from "./NeuralLoQuePasoTemas";
import { EtiquetaModelo, PoblacionContext, textoPoblacion } from "./NeuralModeloEtiqueta";
import { NeuralSelectorPoblacion, UCN, resolverFiltro, type SeleccionPoblacion } from "./NeuralSelectorPoblacion";
import {
  Aviso, Carga, type DatosGrafico, FILA, LeyendaPocosCasos, MarcoGrafico, Notas, PocosCasos, TD, TH, TablaScroll, Vacio,
  entero, pct, useAncho, useCarga,
} from "./NeuralUI";

const PREFIJO = "neural-proy";

// ---------------------------------------------------------------------------
// Textos de cifras (rango, corte, cohorte)
// ---------------------------------------------------------------------------
const rangoTexto = (lo: number, hi: number) => llenar(TX.rangoEtiqueta, { lo: entero(Math.round(lo)), hi: entero(Math.round(hi)) });
const periodoCorto = (p: string) => periodoLegible(p).replace("semestre", "sem.");
const textoCorte = (corte: string | null) => (corte ? llenar(TX.corte, { corte: `${periodoLegible(corte)} (${corte})` }) : "");
const etiquetaCohorte = (c: number | string) => (typeof c === "number" ? `Ingreso ${c}` : TX.cohorteOtra);
const etiquetaFila = (c: number | string, corte: string | null) => `${etiquetaCohorte(c)}${corte ? ` · corte ${periodoCorto(corte)}` : ""}`;

/** Fila de un gráfico de rangos y de su tabla: lo que dibuja el gráfico más los rótulos que lee la tabla. */
interface FilaCohorte extends FilaRango { cohorte: string; corte: string; hasta: string; modelo: ModeloVisible | null }

/** Un bloque con varios modelos lleva la etiqueta en cada cohorte del detalle; con un solo modelo basta la del bloque. */
const modeloPorCohorte = (b: ConModelo) => !b.modelo && (b.modelos?.length ?? 0) > 0;

export function NeuralLoQueViene({ seleccion, onSeleccion }: { seleccion: SeleccionPoblacion; onSeleccion: (s: SeleccionPoblacion) => void }) {
  const [jerarquia, setJerarquia] = useState<FacultadFiltro[] | null>(null);
  const r = resolverFiltro(seleccion, jerarquia);
  const estado = useCarga((s) => neuralApi.proyeccion(r.filtro, s), [r.filtro.facultad, r.filtro.programa]);
  useEffect(() => {
    if (estado.fase === "ok") setJerarquia(estado.datos.jerarquia ?? []);
  }, [estado]);
  return (
    <div className="space-y-5">
      <NeuralSelectorPoblacion idPrefijo="neural-proy" jerarquia={jerarquia} seleccion={r.seleccion} onSeleccion={onSeleccion} programaSinDatos={r.programaSinDatos} facultadSinDatos={r.facultadSinDatos}>
        {estado.fase === "ok" && estado.datos.disponible ? (
          <p className="min-w-0 basis-full text-xs leading-5 text-[var(--portal-muted)]">
            {TX.soloGrupos}{estado.datos.corte ? ` ${textoCorte(estado.datos.corte)}.` : ""}
          </p>
        ) : null}
      </NeuralSelectorPoblacion>
      <Carga estado={r.esperandoLista ? { fase: "cargando" } : estado} filas={6} alto="h-10">
        {(d) => (d.disponible ? <Bloques d={d} /> : <Vacio titulo="Aún no hay datos">{TX.noDisponible}</Vacio>)}
      </Carga>
    </div>
  );
}

function Bloques({ d }: { d: ProyeccionVista }) {
  const corte = textoCorte(d.corte);
  return (
    <PoblacionContext.Provider value={textoPoblacion(d.filtro, d.programa)}>
      <BloquesProyeccion d={d} corte={corte} />
    </PoblacionContext.Provider>
  );
}

function BloquesProyeccion({ d, corte }: { d: ProyeccionVista; corte: string }) {
  return (
    <div className="space-y-5">
      <BloqueUmbral n={1} b={d.umbral} corte={corte} />
      <BloqueContinuidad n={2} b={d.continuidad} corte={corte} sinProyeccion={d.filtro === UCN ? d.sin_proyeccion?.n ?? null : null} />
      <BloqueEliminacion n={3} b={d.eliminacion} corte={corte} />
      <BloqueEgreso n={4} b={d.egreso} corte={corte} />
      <Notas notas={TX.notas} titulo="Cómo se calcularon estas cifras" />
    </div>
  );
}

/** Rango de una cifra («entre lo y hi») con la central al lado, para mostrarla bajo el número clave. */
function Rango({ lo, hi, esperados }: { lo: number; hi: number; esperados: number }) {
  return (
    <p className="mt-1 text-sm leading-6 text-[var(--portal-fg)]">
      <b>{rangoTexto(lo, hi)}</b>
      <span className="text-[var(--portal-muted)]"> ({llenar(TX.esperadoEtiqueta, { esperado: entero(Math.round(esperados)) })})</span>
    </p>
  );
}

// ---------------------------------------------------------------------------
// 1. Umbral: dónde poner tutorías este semestre
// ---------------------------------------------------------------------------
function BloqueUmbral({ n, b, corte }: { n: number; b: ProyUmbral | null; corte: string }) {
  const t = TX.umbral;
  return (
    <Bloque modelo={b} idPrefijo={PREFIJO} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={`${corte}. ${t.nota}`}>
      {b === null ? <BloqueSinDatos /> : <ContenidoUmbral b={b} />}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

function ContenidoUmbral({ b }: { b: ProyUmbral }) {
  const t = TX.umbral;
  const [ref, ancho] = useAncho<HTMLDivElement>();
  // Las cuatro categorías vienen siempre en un documento vigente; una nula (documento antiguo) simplemente no se dibuja.
  const filas: FilaUmbral[] = (["en_umbral", "a_1", "a_2"] as const).flatMap((id) => {
    const valor = b[id];
    // «Pocos casos» sigue la misma regla que en el resto del módulo: el tamaño del grupo, que aquí es el de todo el bloque
    // (`b.n`, bandera del servidor); una categoría con pocos estudiantes dentro de un grupo grande no se marca.
    return valor == null ? [] : [{ id, etiqueta: t.categorias[id], valor, pocos: b.pocos_casos, n: b.n }];
  });
  const g = filas.length ? opcionUmbral(filas, ancho) : null;
  const datos: DatosGrafico = { columnas: ["Cercanía al umbral", "Estudiantes actuales"], filas: filas.map((f) => [f.etiqueta, f.valor]) };
  return (
    <div className="space-y-3">
      <div className="grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div ref={ref} className="min-w-0">
          {g ? (
            <MarcoGrafico datos={datos} descripcion="Cantidad de estudiantes actuales según su cercanía al umbral de eliminación por reprobaciones.">
              <EChartsChart option={g.option} height={g.alto} ariaLabel="Barras: estudiantes en el umbral, a 1 y a 2 reprobaciones de llegar a él." />
            </MarcoGrafico>
          ) : <Vacio>{TX.sinDatos}</Vacio>}
        </div>
        {b.en_umbral != null ? (
          <Clave className={PRIMERO_EN_CELULAR} valor={entero(b.en_umbral)} texto={t.clave}>
            <p className="mt-2 text-xs leading-5 text-[var(--portal-muted)]">
              de {entero(b.n)} estudiantes actuales.{b.pocos_casos ? <> <PocosCasos /></> : null}
            </p>
          </Clave>
        ) : null}
      </div>
      {b.lejos != null ? <p className="max-w-3xl text-sm leading-6 text-[var(--portal-fg)]">{llenar(t.lejos, { n: entero(b.lejos) })}</p> : null}
      {filas.some((f) => f.pocos) ? <LeyendaPocosCasos grafico /> : null}
      {b.nota_p58 ? <div className="max-w-3xl"><Aviso>{t.p58}</Aviso></div> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piezas comunes de los bloques con proyección
// ---------------------------------------------------------------------------
function GraficoRangos({ filas, color, ejeX, aria, descripcion }: {
  filas: readonly FilaRango[]; color: string; ejeX: string; aria: string; descripcion: string;
}) {
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const g = opcionRangos(filas, ancho, color, ejeX);
  return (
    <div ref={ref} className="min-w-0">
      <MarcoGrafico descripcion={descripcion}><EChartsChart option={g.option} height={g.alto} ariaLabel={aria} /></MarcoGrafico>
    </div>
  );
}

/** Los mismos números del gráfico, en tabla (con scroll horizontal propio en el celular). */
function TablaCohortes({ filas, etiqueta, conModelo = false }: { filas: readonly FilaCohorte[]; etiqueta: string; conModelo?: boolean }) {
  const c = TX.columnas;
  return (
    <details className="mt-3 max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">
      <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
        {TX.detalleCohortes}
      </summary>
      <div className="mt-2">
        <TablaScroll etiqueta={etiqueta}>
          <table className="w-full min-w-[34rem] border-collapse">
            <thead>
              <tr>
                <th className={TH}>{c.cohorte}</th><th className={TH}>{c.corte}</th><th className={TH}>{c.hasta}</th>
                <th className={TH}>{c.estudiantes}</th><th className={TH}>{c.esperado}</th><th className={TH}>{c.rango}</th>
                {conModelo ? <th className={TH}>{MODELO_TEXTOS.columna}</th> : null}
              </tr>
            </thead>
            <tbody>
              {filas.map((f, i) => (
                <tr key={i} className={FILA}>
                  <td className={TD}>{f.cohorte}</td><td className={TD}>{f.corte}</td><td className={TD}>{f.hasta}</td>
                  <td className={`${TD} ${f.pocos ? "opacity-60" : ""}`}>{entero(f.n)}{f.pocos ? <> <PocosCasos /></> : null}</td><td className={TD}>{entero(Math.round(f.esperados))}</td>
                  <td className={TD}>{rangoTexto(f.lo, f.hi)}</td>
                  {conModelo ? <td className={`${TD} min-w-[16rem]`}>{f.modelo ? <EtiquetaModelo modelo={f.modelo} /> : null}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </TablaScroll>
        {filas.some((f) => f.pocos) ? <div className="mt-2"><LeyendaPocosCasos /></div> : null}
      </div>
    </details>
  );
}

function filasDeCohortes(por: readonly ProyCohorte[]): FilaCohorte[] {
  return por.map((c) => ({
    etiqueta: etiquetaFila(c.cohorte, c.corte), cohorte: etiquetaCohorte(c.cohorte), corte: c.corte ? periodoLegible(c.corte) : "—",
    hasta: c.horizonte ? periodoLegible(c.horizonte) : "—", n: c.n, pocos: c.pocos_casos, esperados: c.esperados, lo: c.lo, hi: c.hi,
    modelo: c.modelo ?? null,
    nota: c.horizonte ? `Proyección hasta ${periodoLegible(c.horizonte)}` : undefined,
  }));
}

// ---------------------------------------------------------------------------
// 2. Continuidad
// ---------------------------------------------------------------------------
function BloqueContinuidad({ n, b, corte, sinProyeccion }: { n: number; b: ProyContinuidad | null; corte: string; sinProyeccion: number | null }) {
  const t = TX.continuidad;
  return (
    <Bloque modelo={b} idPrefijo={PREFIJO} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={`${corte}. Rango, no un número exacto.`}>
      {b === null ? <BloqueSinDatos /> : <ContenidoContinuidad b={b} />}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
      {sinProyeccion != null ? (
        <p className="mt-2 max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{llenar(TX.sinProyeccion, { n: entero(sinProyeccion) })}</p>
      ) : null}
    </Bloque>
  );
}

function ContenidoContinuidad({ b }: { b: ProyContinuidad }) {
  const t = TX.continuidad;
  const filas = filasDeCohortes(b.por_cohorte);
  const sinHistorial = b.por_cohorte.reduce((s, c) => s + (c.sin_historial_beneficios ?? 0), 0);
  return (
    <>
      <div className="grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0">
          {filas.length ? (
            <GraficoRangos filas={filas} color={COLOR_CONTINUIDAD} ejeX={TX.continuidad.ejeX} aria="Rangos por cohorte: porcentaje que se espera que continúe."
              descripcion="Porcentaje esperado de continuidad por cohorte, con su rango, en estudiantes actuales." />
          ) : <Vacio>{TX.sinDatos}</Vacio>}
        </div>
        <Clave className={PRIMERO_EN_CELULAR} valor={pct(b.n > 0 ? b.esperados / b.n : null, 0)} texto={<>{t.clave} (de {entero(b.n)})</>}>
          <Rango lo={b.lo} hi={b.hi} esperados={b.esperados} />
          {b.pocos_casos ? <div className="mt-1"><PocosCasos /></div> : null}
        </Clave>
      </div>
      {filas.length ? <TablaCohortes filas={filas} etiqueta="Continuidad esperada por cohorte" conModelo={modeloPorCohorte(b)} /> : null}
      {filas.some((f) => f.pocos) ? <div className="mt-2"><LeyendaPocosCasos grafico /></div> : null}
      {sinHistorial > 0 ? (
        <p className="mt-2 max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{llenar(t.historial, { n: entero(sinHistorial) })}</p>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// 3. Eliminación (orientativa)
// ---------------------------------------------------------------------------
function BloqueEliminacion({ n, b, corte }: { n: number; b: ProyEliminacion | null; corte: string }) {
  const t = TX.eliminacion;
  return (
    <Bloque modelo={b} idPrefijo={PREFIJO} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={`${corte}. Rango, no un número exacto.`}>
      {b === null ? <BloqueSinDatos /> : <ContenidoEliminacion b={b} />}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

function ContenidoEliminacion({ b }: { b: ProyEliminacion }) {
  const t = TX.eliminacion;
  const filas = filasDeCohortes(b.por_cohorte).map((f, i) => {
    const c = b.por_cohorte[i];
    return c.horizonte_desde && c.horizonte
      ? { ...f, nota: `Proyección de ${periodoLegible(c.horizonte_desde)} hasta ${periodoLegible(c.horizonte)}` }
      : f;
  });
  return (
    <>
      <div className="mb-3 max-w-3xl"><Aviso tono="tierra" titulo={t.avisoTitulo}>{t.aviso}</Aviso></div>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0">
          {filas.length ? (
            <GraficoRangos filas={filas} color={COLOR_ELIMINACION} ejeX={t.ejeX} aria="Rangos por cohorte: porcentaje que podría ser eliminado."
              descripcion="Porcentaje esperado de eliminación por cohorte, con su rango, en los dos semestres siguientes al corte." />
          ) : <Vacio>{TX.sinDatos}</Vacio>}
        </div>
        <div className={`min-w-0 space-y-4 ${PRIMERO_EN_CELULAR}`}>
          <Clave valor={entero(Math.round(b.esperados))} texto={<>{t.clave} (de {entero(b.n)} estudiantes)</>}>
            <Rango lo={b.lo} hi={b.hi} esperados={b.esperados} />
            {b.pocos_casos ? <div className="mt-1"><PocosCasos /></div> : null}
          </Clave>
          <div className="rounded-md border border-[var(--boveda-linea)] p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{t.observado}</p>
            <p className="mt-1 text-2xl font-bold leading-8 text-[var(--portal-fg)]">{b.observados_hasta_hoy == null ? "—" : entero(b.observados_hasta_hoy)}</p>
            <p className="text-sm leading-6 text-[var(--portal-muted)]">
              {b.observados_hasta_hoy == null ? TX.sinCifra : llenar(t.observadoTexto, { periodo: periodoLegible(b.periodo_observado) })}
            </p>
            <p className="mt-1 text-xs leading-5 text-[var(--portal-muted)]">{t.observadoSeparado}</p>
          </div>
        </div>
      </div>
      {filas.length ? <TablaCohortes filas={filas} etiqueta="Eliminación esperada por cohorte" conModelo={modeloPorCohorte(b)} /> : null}
      {filas.some((f) => f.pocos) ? <div className="mt-2"><LeyendaPocosCasos grafico /></div> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// 4. Egreso: a tiempo y con 2 semestres de atraso
// ---------------------------------------------------------------------------
type Hito = "nominal" | "nominal_mas_2";

function BloqueEgreso({ n, b, corte }: { n: number; b: ProyEgreso | null; corte: string }) {
  const t = TX.egreso;
  return (
    <Bloque modelo={b} idPrefijo={PREFIJO} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={`${corte}. Rango, no un número exacto.`}>
      {b === null ? <BloqueSinDatos /> : <ContenidoEgreso b={b} />}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

function ContenidoEgreso({ b }: { b: ProyEgreso }) {
  const t = TX.egreso;
  return (
    <div className="space-y-5">
      {b.pocos_casos ? <PocosCasos /> : null}
      <div className="grid gap-5 lg:grid-cols-2">
        <VentanaEgreso titulo={t.nominal} hito="nominal" total={b.nominal} por={b.por_cohorte} yaPasado={b.ya_pasado_nominal} n={b.n} conModelo={modeloPorCohorte(b)} />
        <VentanaEgreso titulo={t.nominalMas2} hito="nominal_mas_2" total={b.nominal_mas_2} por={b.por_cohorte} yaPasado={b.ya_pasado_nominal_mas_2} n={b.n} conModelo={modeloPorCohorte(b)} />
      </div>
      {b.horizonte_truncado ? (
        <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{llenar(t.truncado, { n: entero(b.horizonte_truncado) })}</p>
      ) : null}
      {b.por_cohorte.some((c) => c.pocos_casos) ? <LeyendaPocosCasos grafico /> : null}
      <details className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">
        <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">{t.reglaTitulo}</summary>
        <p className="mt-1">{t.regla}</p>
      </details>
    </div>
  );
}

function VentanaEgreso({ titulo, hito, total, por, yaPasado, n, conModelo }: {
  titulo: string; hito: Hito; total: ProyHito | null; por: readonly ProyCohorteEgreso[]; yaPasado: number | null; n: number; conModelo: boolean;
}) {
  const t = TX.egreso;
  const filas: FilaCohorte[] = por.flatMap((c) => {
    const h = c[hito];
    return h ? [{
      etiqueta: etiquetaFila(c.cohorte, c.corte), cohorte: etiquetaCohorte(c.cohorte), corte: c.corte ? periodoLegible(c.corte) : "—",
      hasta: periodoLegible(h.hasta), n: c.n, pocos: c.pocos_casos, esperados: h.esperados, lo: h.lo, hi: h.hi, modelo: c.modelo ?? null,
      nota: `Egresos entre ${periodoLegible(h.desde)} y ${periodoLegible(h.hasta)}`,
    }] : [];
  });
  const clave: ReactNode = total ? (
    <Clave valor={entero(Math.round(total.esperados))} texto={<>{t.clave} (de {entero(n)} estudiantes)</>}>
      <Rango lo={total.lo} hi={total.hi} esperados={total.esperados} />
      <p className="mt-1 text-xs leading-5 text-[var(--portal-muted)]">{llenar(t.periodo, { desde: periodoLegible(total.desde), hasta: periodoLegible(total.hasta) })}</p>
    </Clave>
  ) : <p className="text-sm leading-6 text-[var(--portal-muted)]">{t.noDisponible}</p>;
  return (
    <div className="min-w-0 space-y-3 rounded-md border border-[var(--boveda-linea)] p-3">
      <h3 className="text-base font-semibold leading-6 text-[var(--portal-fg)]">{titulo}</h3>
      {clave}
      {yaPasado ? <p className="text-xs leading-5 text-[var(--portal-muted)]">{llenar(t.yaPasado, { n: entero(yaPasado) })}</p> : null}
      {filas.length ? (
        <>
          <GraficoRangos filas={filas} color={COLOR_EGRESO} ejeX={t.ejeX} aria={`Rangos por cohorte: porcentaje que podría egresar (${titulo.toLowerCase()}).`}
            descripcion={`Porcentaje esperado de egreso por cohorte, con su rango (${titulo.toLowerCase()}).`} />
          <TablaCohortes filas={filas} etiqueta={`Egreso esperado por cohorte (${titulo.toLowerCase()})`} conModelo={conModelo} />
        </>
      ) : null}
    </div>
  );
}
