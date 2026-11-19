"use client";

// «Histórico»: piezas comunes de un bloque y los bloques de los temas Permanencia (perfil y primer semestre), Rendimiento en asignaturas,
// Egreso y eliminación (causales por programa y tiempo de egreso) y Fundamentos del modelo. Cada bloque recibe lo que dice el servidor, completo y con la
// marca «pocos casos» en los grupos de menos de 10; si viene vacío (null, porque el bloque no se abre por facultad) se avisa.
import { useState, type ReactNode } from "react";

import {
  type ConModelo, type HistCausalesPrograma, type HistCuellos, type HistEsperado, type HistEsperar, type HistPerfil, type HistPrimerSemestre, type HistRamos,
  type HistSemestreMalla, type HistSenales, type HistTiempo, type TareaId,
} from "../lib/neural";
import {
  COLOR_DEJAN, etiquetaReprobaciones, opcionCausalesPrograma, opcionCuellos, opcionEsperado, opcionPerfil, opcionPrimerSemestre, opcionRamos, opcionSemestreMalla,
  opcionSenales, opcionTiempo, type FilaEsperado,
} from "../lib/neuralGraficosHistorico";
import { FICHA_SIMPLE, HISTORICO_TEXTOS as TX, llenar, momentoSimple, periodoLegible } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import { ChipPoblacion, NeuralModeloEtiqueta } from "./NeuralModeloEtiqueta";
import { Aviso, CARD, type DatosGrafico, LeyendaPocosCasos, MarcoGrafico, POCOS_CASOS, PocosCasos, Segmentado, TD, TH, TablaScroll, FILA, entero, num, pct, pctDe, useAncho } from "./NeuralUI";

// ---------------------------------------------------------------------------
// Piezas comunes de un bloque
// ---------------------------------------------------------------------------
export function Bloque({ n, titulo, definicion, poblacion, modelo, children, idPrefijo = "neural-hist", siempreUcn = false }: {
  n: number; titulo: string; definicion: string; poblacion: string;
  /** El bloque solo existe para toda la UCN (aunque el servidor no lo marque): su chip dice «Toda la UCN». */
  siempreUcn?: boolean;
  /** El bloque tal como llega del servidor: de él sale la etiqueta del modelo. Sin bloque (sin datos) no hay etiqueta. */
  modelo?: (ConModelo & { aplica_a_poblacion?: boolean }) | null;
  children: ReactNode; idPrefijo?: string;
}) {
  return (
    <section className={CARD} aria-labelledby={`${idPrefijo}-${n}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 id={`${idPrefijo}-${n}`} tabIndex={-1} className="min-w-0 scroll-mt-24 text-lg font-semibold leading-7 text-[var(--portal-fg)] focus:outline-none">
          <span className="mr-2 text-[var(--portal-muted)]">{n}.</span>{titulo}
        </h2>
        <ChipPoblacion soloUcn={siempreUcn || modelo?.aplica_a_poblacion === false} />
      </div>
      <p className="mt-0.5 text-xs text-[var(--portal-muted)]">{poblacion}</p>
      {modelo ? <NeuralModeloEtiqueta bloque={modelo} /> : null}
      <details className="mt-1 max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">
        <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
          Qué se está mirando
        </summary>
        <p className="mt-1">{definicion}</p>
      </details>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** En una cuadrícula con gráfico, `PRIMERO_EN_CELULAR` sube la cifra clave sobre el gráfico en pantallas angostas y la deja a su lado en las grandes. */
export const PRIMERO_EN_CELULAR = "order-first lg:order-none";

export function Clave({ valor, texto, children, className = "" }: { valor: ReactNode; texto: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <div className={`min-w-0 ${className}`.trim()}>
      <div className="text-3xl font-bold leading-9 text-[var(--portal-fg)]">{valor}</div>
      <p className="mt-0.5 text-sm leading-6 text-[var(--portal-fg)]">{texto}</p>
      {children}
    </div>
  );
}

export function ComoUsarlo({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--portal-muted)]">
      <strong className="font-semibold text-[var(--portal-fg)]">{TX.comoUsarEtiqueta}.</strong> {children}
    </p>
  );
}

export const DISPOSICION = "grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]";

export function Cuadro({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="mr-3 inline-flex items-center gap-1.5">
      <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />{children}
    </span>
  );
}

export function Puntos({ llenos, color, etiqueta }: { llenos: number; color: string; etiqueta: string }) {
  return (
    <div role="img" aria-label={etiqueta} className="flex flex-wrap gap-1.5">
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} aria-hidden className="inline-block h-5 w-5 rounded-full" style={{ background: i < llenos ? color : "rgba(237,237,239,0.14)" }} />
      ))}
    </div>
  );
}

/** Aviso de un bloque sin cifras: el servidor no trae datos para este grupo, o el bloque solo existe para toda la UCN. */
export function BloqueSinDatos({ soloUcn = false }: { soloUcn?: boolean }) {
  return <Aviso>{TX.sinDatos}{soloUcn ? <> {TX.soloUcn}</> : null}</Aviso>;
}

/** Gráfico que se redibuja según el ancho disponible (para que en el celular no haya desborde horizontal). */
function Grafico({ construir, aria, descripcion, datos, tablaExterna }: {
  construir: (ancho: number) => { option: Record<string, unknown>; alto: number }; aria: string; descripcion: string;
  /** Los mismos datos del gráfico en una tabla plegada «Ver los datos». */
  datos?: DatosGrafico;
  /** Si el gráfico está recortado, el título de la tabla «Ver los M …» que trae todos (la que dibuja `Recorte`). */
  tablaExterna?: string;
}) {
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const g = construir(ancho);
  return (
    <div ref={ref} className="min-w-0">
      <MarcoGrafico datos={datos} tablaExterna={tablaExterna} descripcion={descripcion}><EChartsChart option={g.option} height={g.alto} ariaLabel={aria} /></MarcoGrafico>
    </div>
  );
}

/** Título de la tabla plegada de `Recorte` (nulo si no hay recorte): el aviso de fallo de un gráfico recortado remite a ella. */
const verRecorte = (mostrados: number, total: number, que: string): string | undefined =>
  total > mostrados ? llenar(TX.recorte.ver, { n: entero(mostrados), m: entero(total), que }) : undefined;

/** Si el gráfico muestra solo los `mostrados` mayores de `total`, lo dice y deja todos en una tabla plegada (misma marca «pocos casos»). Sin recorte, no pinta nada. */
function Recorte({ mostrados, total, que, encabezados, filas, unidad }: {
  mostrados: number; total: number; que: string; encabezados: readonly string[]; unidad?: string;
  filas: readonly { nombre: string; pocos: boolean; celdas: readonly string[] }[];
}) {
  if (total <= mostrados) return null;
  const r = TX.recorte;
  const valores = { n: entero(mostrados), m: entero(total), que };
  return (
    <div className="max-w-3xl">
      <p className="text-xs leading-5 text-[var(--portal-muted)]">{llenar(r.aviso, valores)}</p>
      <details className="mt-1 text-xs leading-5 text-[var(--portal-muted)]">
        <summary className="cursor-pointer list-item py-3 font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
          {llenar(r.ver, valores)}
        </summary>
        <TablaScroll etiqueta={llenar(r.etiqueta, valores)}>
          <table className="w-full min-w-[28rem] text-left">
            <thead>
              <tr>{encabezados.map((h, i) => <th key={h} className={i === 0 ? TH : `${TH} text-right`}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {filas.map((f, i) => (
                <tr key={i} className={FILA}>
                  <td className={TD}>{f.nombre}{f.pocos ? <> <PocosCasos /></> : null}</td>
                  {f.celdas.map((c, j) => <td key={j} className={`${TD} text-right tabular-nums`}>{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </TablaScroll>
        {filas.some((f) => f.pocos) ? <div className="mt-2"><LeyendaPocosCasos unidad={unidad} /></div> : null}
      </details>
    </div>
  );
}

/** Celdas de una fila de ramo (inscripciones, reprobados y % con su intervalo): las usan la tabla «Ver los datos» y la de los recortados. */
const celdasRamo = (f: { intentos: number; reprobados: number; tasa: number; lo: number | null; hi: number | null }): (string | number)[] =>
  [f.intentos, f.reprobados, f.lo != null && f.hi != null ? `${pct(f.tasa, 0)} (${pct(f.lo, 0)}–${pct(f.hi, 0)})` : pct(f.tasa, 0)];
const celdasEsperado = (f: { intentos: number; observados: number; esperados: number; diferencia: number; lo: number; hi: number }): (string | number)[] =>
  [f.intentos, f.observados, Math.round(f.esperados), `${f.diferencia > 0 ? "+" : ""}${entero(Math.round(f.diferencia))} (${entero(Math.round(f.lo))} a ${entero(Math.round(f.hi))})`];

const ventana = (desde: string, hasta: string) => llenar(TX.ventana, { desde: periodoLegible(desde), hasta: periodoLegible(hasta) });
const NOTA_ASOCIACION = "Muestra asociación, no causa.";

// ---------------------------------------------------------------------------
// Permanencia: perfil de ingreso
// ---------------------------------------------------------------------------
export function BloquePerfil({ n, b, cohortes }: { n: number; b: HistPerfil | null | undefined; cohortes: string }) {
  const t = TX.perfil;
  const dims = (b?.dimensiones ?? []).filter((d) => d.filas.length > 0);
  const filas = dims.flatMap((d) => d.filas.filter((f) => f.pct_siguieron != null).map((f) => ({ ...f, dimension: d.dimension })));
  const menor = filas.reduce<(typeof filas)[number] | null>((m, f) => (m == null || (f.pct_siguieron ?? 1) < (m.pct_siguieron ?? 1) ? f : m), null);
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={llenar(t.definicion, { cohortes })} poblacion={llenar(TX.poblacion.modelo, { cohortes })}>
      {b == null || dims.length === 0 ? <BloqueSinDatos /> : (
        <>
          {menor ? (
            <Clave
              valor={pctDe(menor.pct_siguieron, menor.n, 0)}
              texto={<>siguió al año siguiente en el grupo de menor continuidad: <b>{menor.etiqueta}</b> ({t.dimensiones[menor.dimension as keyof typeof t.dimensiones] ?? menor.dimension}){menor.pocos_casos ? <> <PocosCasos /></> : null}</>}
            />
          ) : null}
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            {dims.map((d) => (
              <div key={d.dimension} className="min-w-0">
                <p className="mb-1 text-sm font-semibold text-[var(--portal-fg)]">{t.dimensiones[d.dimension as keyof typeof t.dimensiones] ?? d.dimension}</p>
                <Grafico
                  construir={(ancho) => opcionPerfil(d, ancho)}
                  datos={{
                    columnas: [t.dimensiones[d.dimension as keyof typeof t.dimensiones] ?? d.dimension, "Estudiantes", "Siguieron", "El modelo esperaba"],
                    filas: d.filas.map((f) => [f.etiqueta, f.n, pct(f.pct_siguieron, 1), pct(f.pct_esperado, 1)]),
                    columnaN: 1,
                  }}
                  descripcion={`Porcentaje que siguió y que el modelo esperaba, según ${t.dimensiones[d.dimension as keyof typeof t.dimensiones] ?? d.dimension}.`}
                  aria={`Barras: continuidad según ${t.dimensiones[d.dimension as keyof typeof t.dimensiones] ?? d.dimension}.`}
                />
              </div>
            ))}
          </div>
          {b.nota_asociacion ? <p className="mt-2 text-xs font-medium text-[var(--portal-muted)]">{NOTA_ASOCIACION}</p> : null}
          {dims.some((d) => d.filas.some((f) => f.pocos_casos)) ? <div className="mt-2"><LeyendaPocosCasos grafico /></div> : null}
        </>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Permanencia: primer semestre
// ---------------------------------------------------------------------------
export function BloquePrimerSemestre({ n, b, cohortes }: { n: number; b: HistPrimerSemestre | null | undefined; cohortes: string }) {
  const t = TX.primerSemestre;
  const filas = b?.filas ?? [];
  const sinReprobar = filas.find((f) => f.reprobaciones === "0");
  const conNumero = filas.filter((f) => f.reprobaciones !== "0" && Number.isFinite(parseInt(f.reprobaciones, 10)));
  const mayor = conNumero.reduce<(typeof filas)[number] | undefined>((m, f) => (m == null || parseInt(f.reprobaciones, 10) > parseInt(m.reprobaciones, 10) ? f : m), undefined);
  const primera = sinReprobar;
  const ultima = sinReprobar ? mayor : undefined;
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={llenar(t.definicion, { cohortes })} poblacion={llenar(TX.poblacion.primerSemestre, { cohortes })}>
      {b == null || filas.length === 0 ? <BloqueSinDatos /> : (
        <div className={DISPOSICION}>
          <Grafico
            construir={() => opcionPrimerSemestre(filas)}
            datos={{
              columnas: ["Ramos reprobados en el primer semestre", "Estudiantes", "Siguieron"],
              filas: filas.map((f) => [etiquetaReprobaciones(f.reprobaciones), f.n, pct(f.pct_siguieron, 1)]),
              columnaN: 1,
            }}
            descripcion="Porcentaje que siguió al año siguiente según los ramos reprobados en el primer semestre."
            aria="Barras: continuidad según ramos reprobados en el primer semestre."
          />
          <Clave
            className={PRIMERO_EN_CELULAR}
            valor={primera ? <>{pctDe(primera.pct_siguieron, primera.n, 0)}{primera.pocos_casos ? <> <PocosCasos /></> : null}</> : "—"}
            texto={primera && ultima
              ? <>siguió entre quienes no reprobaron ramos en el primer semestre, frente a <b>{pctDe(ultima.pct_siguieron, ultima.n, 0)}</b> entre quienes reprobaron {etiquetaReprobaciones(ultima.reprobaciones).toLowerCase()}{ultima.pocos_casos ? <> <PocosCasos /></> : null}</>
              : <>siguió entre quienes no reprobaron ramos en el primer semestre</>}
          >
            {filas.some((f) => f.pocos_casos) ? <div className="mt-2"><LeyendaPocosCasos grafico /></div> : null}
            {b.nota_asociacion ? <p className="mt-2 text-xs font-medium text-[var(--portal-muted)]">{NOTA_ASOCIACION}</p> : null}
          </Clave>
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Ramos: los más reprobados
// ---------------------------------------------------------------------------
type MedidaRamos = "tasa" | "reprobados";
const OPCIONES_MEDIDA: readonly { id: MedidaRamos; label: string }[] = [
  { id: "tasa", label: "Por porcentaje de reprobados" },
  { id: "reprobados", label: "Por cantidad de reprobados" },
];

export function BloqueRamos({ n, b }: { n: number; b: HistRamos | null | undefined }) {
  const t = TX.ramosReprobados;
  const [medida, setMedida] = useState<MedidaRamos>("tasa");
  const periodo = b ? { desde: periodoLegible(b.desde), hasta: periodoLegible(b.hasta) } : { desde: "—", hasta: "—" };
  // El servidor ya entrega cada lista ordenada: por_tasa por el límite inferior del intervalo de 95 % (así pesa cuántos intentos hay) y por_volumen por cantidad.
  // Estas filas no traen bandera: «pocos casos» = menos de 10 inscripciones en el ramo (POCOS_CASOS).
  const todas = (b ? (medida === "tasa" ? b.por_tasa : b.por_volumen) : []).map((f) => ({ ...f, pocos: f.intentos < POCOS_CASOS }));
  const filas = todas.slice(0, 10);
  const mayor = b?.por_tasa[0];
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={llenar(t.definicion, periodo)} poblacion={`Período: ${periodo.desde} a ${periodo.hasta}, todas las cohortes de pregrado.`}>
      {b == null || !mayor ? <BloqueSinDatos /> : (
        <div className="space-y-3">
          <Clave valor={pctDe(mayor.tasa, mayor.intentos, 0)} texto={<>de las inscripciones en <b>{mayor.nombre}</b> terminó en reprobación ({entero(mayor.reprobados)} de {entero(mayor.intentos)}{mayor.lo != null && mayor.hi != null ? `; intervalo de 95 %: ${pct(mayor.lo, 0)}–${pct(mayor.hi, 0)}` : ""}){mayor.intentos < POCOS_CASOS ? <> <PocosCasos /></> : null}</>} />
          <Segmentado etiqueta="Ordenar los ramos" opciones={OPCIONES_MEDIDA} valor={medida} onCambio={setMedida} />
          {filas.some((f) => f.pocos) ? <LeyendaPocosCasos grafico unidad="inscripciones" /> : null}
          {filas.length ? (
            <Grafico
              construir={(ancho) => opcionRamos(filas, ancho, medida)}
              tablaExterna={verRecorte(filas.length, todas.length, TX.recorte.ramos)}
              datos={todas.length > filas.length ? undefined : {
                columnas: [TX.recorte.col.ramo, TX.recorte.col.inscripciones, TX.recorte.col.reprobados, TX.recorte.col.pctReprobado],
                filas: filas.map((f) => [f.nombre, ...celdasRamo(f)]),
                columnaN: 1,
                unidad: "inscripciones",
              }}
              descripcion="Los ramos más reprobados, por porcentaje o por cantidad de reprobados."
              aria="Barras: ramos más reprobados."
            />
          ) : <BloqueSinDatos />}
          <Recorte
            mostrados={filas.length} total={todas.length} que={TX.recorte.ramos} unidad="inscripciones"
            encabezados={[TX.recorte.col.ramo, TX.recorte.col.inscripciones, TX.recorte.col.reprobados, TX.recorte.col.pctReprobado]}
            filas={todas.map((f) => ({
              nombre: f.nombre, pocos: f.pocos,
              celdas: celdasRamo(f).map((c) => (typeof c === "number" ? entero(c) : c)),
            }))}
          />
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Ramos: reprobación frente a lo esperado
// ---------------------------------------------------------------------------
type NivelEsperado = "ramos" | "deptos";
const OPCIONES_NIVEL_ESPERADO: readonly { id: NivelEsperado; label: string }[] = [
  { id: "ramos", label: "Por ramo" },
  { id: "deptos", label: "Por departamento" },
];

export function BloqueEsperado({ n, b }: { n: number; b: HistEsperado | null | undefined }) {
  const t = TX.ramosEsperado;
  const [pedida, setPedida] = useState<string>("prueba");
  const [nivel, setNivel] = useState<NivelEsperado>("ramos");
  const claves = b ? Object.keys(b.ventanas) : [];
  const clave = claves.includes(pedida) ? pedida : claves[0];
  const v = b && clave ? b.ventanas[clave] : undefined;
  const todas: FilaEsperado[] = v
    ? (nivel === "ramos" ? v.ramos.map((r) => ({ ...r, nombre: r.nombre, pocos: r.intentos < POCOS_CASOS })) : v.deptos.map((d) => ({ ...d, nombre: d.depto_desc || d.depto, pocos: d.intentos < POCOS_CASOS })))
        .sort((x, y) => y.diferencia - x.diferencia)
    : [];
  const filas = todas.slice(0, 12);
  const conMas = filas.filter((f) => f.lo > 0).length;
  const textoVentana = v ? ventana(v.desde, v.hasta) : "";
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={v ? `${textoVentana} Todas las cohortes de pregrado.` : "Todas las cohortes de pregrado."}>
      {b == null || !v ? <BloqueSinDatos /> : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-3">
            {claves.length > 1 ? (
              <Segmentado
                etiqueta="Período" valor={clave} onCambio={setPedida}
                opciones={claves.map((c) => ({ id: c, label: (t.ventanas as Record<string, string>)[c] ?? c }))}
              />
            ) : null}
            <Segmentado etiqueta="Agrupar" opciones={OPCIONES_NIVEL_ESPERADO} valor={nivel} onCambio={setNivel} />
          </div>
          {filas.length ? (
            <>
              <Clave
                valor={entero(conMas)}
                texto={<>{nivel === "ramos" ? "ramos" : "departamentos"} de los {entero(filas.length)} mostrados reprueban <b>más de lo esperado</b> (todo su rango queda sobre cero)</>}
              />
              {filas.some((f) => f.pocos) ? <LeyendaPocosCasos grafico unidad="inscripciones" /> : null}
              <Grafico
                construir={(ancho) => opcionEsperado(filas, ancho)}
                tablaExterna={verRecorte(filas.length, todas.length, nivel === "ramos" ? TX.recorte.ramos : TX.recorte.departamentos)}
                datos={todas.length > filas.length ? undefined : {
                  columnas: [nivel === "ramos" ? TX.recorte.col.ramo : TX.recorte.col.departamento, TX.recorte.col.inscripciones, TX.recorte.col.reprobaron, TX.recorte.col.esperados, TX.recorte.col.diferencia],
                  filas: filas.map((f) => [f.nombre, ...celdasEsperado(f)]),
                  columnaN: 1,
                  unidad: "inscripciones",
                }}
                descripcion="Diferencia entre reprobados y reprobados esperados por el modelo, con su rango."
                aria="Puntos y líneas: reprobados de más o de menos que lo esperado."
              />
              <Recorte
                mostrados={filas.length} total={todas.length} que={nivel === "ramos" ? TX.recorte.ramos : TX.recorte.departamentos} unidad="inscripciones"
                encabezados={[nivel === "ramos" ? TX.recorte.col.ramo : TX.recorte.col.departamento, TX.recorte.col.inscripciones, TX.recorte.col.reprobaron, TX.recorte.col.esperados, TX.recorte.col.diferencia]}
                filas={todas.map((f) => ({
                  nombre: f.nombre, pocos: f.pocos,
                  celdas: celdasEsperado(f).map((c) => (typeof c === "number" ? entero(c) : c)),
                }))}
              />
            </>
          ) : <BloqueSinDatos />}
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Ramos: cuellos de botella
// ---------------------------------------------------------------------------
export function BloqueCuellos({ n, b, ventanaRamos }: { n: number; b: HistCuellos | null | undefined; ventanaRamos: string }) {
  const t = TX.cuellos;
  // Sin intentos en la fila: el tamaño del grupo es el número de reprobaciones (pocos casos = menos de 10, POCOS_CASOS).
  const todas = (b?.filas ?? []).slice().sort((x, y) => y.impacto - x.impacto).map((f) => ({ ...f, pocos: f.reprobados < POCOS_CASOS }));
  const filas = todas.slice(0, 10);
  const top = filas[0];
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={ventanaRamos ? `${ventanaRamos} Todas las cohortes de pregrado.` : "Todas las cohortes de pregrado."}>
      {b == null || !top ? <BloqueSinDatos /> : (
        <div className="space-y-3">
          <div className={DISPOSICION}>
            <div className="min-w-0 space-y-1">
              {filas.some((f) => f.pocos) ? <LeyendaPocosCasos grafico unidad="reprobaciones" /> : null}
              <Grafico
                construir={(ancho) => opcionCuellos(filas, ancho)}
                tablaExterna={verRecorte(filas.length, todas.length, TX.recorte.ramos)}
                datos={todas.length > filas.length ? undefined : {
                  columnas: [TX.recorte.col.ramo, TX.recorte.col.reprobaciones, TX.recorte.col.dependientes, TX.recorte.col.impacto],
                  filas: filas.map((f) => [f.nombre, f.reprobados, f.dependientes, f.impacto]),
                  columnaN: 1,
                  unidad: "reprobaciones",
                }}
                descripcion="Los ramos que más frenan el avance: reprobados por ramos que dependen de ellos."
                aria="Barras: impacto de cada ramo sobre el avance."
              />
            </div>
            <Clave
              className={PRIMERO_EN_CELULAR}
              valor={entero(top.dependientes)}
              texto={<>ramos dependen de <b>{top.nombre}</b>, que acumula {entero(top.reprobados)} reprobaciones</>}
            />
          </div>
          <Recorte
            mostrados={filas.length} total={todas.length} que={TX.recorte.ramos} unidad="reprobaciones"
            encabezados={[TX.recorte.col.ramo, TX.recorte.col.reprobaciones, TX.recorte.col.dependientes, TX.recorte.col.impacto]}
            filas={todas.map((f) => ({ nombre: f.nombre, pocos: f.pocos, celdas: [entero(f.reprobados), entero(f.dependientes), entero(f.impacto)] }))}
          />
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Ramos: semestre de la malla
// ---------------------------------------------------------------------------
export function BloqueSemestreMalla({ n, b, ventanaRamos }: { n: number; b: HistSemestreMalla | null | undefined; ventanaRamos: string }) {
  const t = TX.semestreMalla;
  const filas = b?.filas ?? [];
  const mayor = filas.reduce<(typeof filas)[number] | null>((m, f) => (f.tasa != null && (m == null || f.tasa > (m.tasa ?? -1)) ? f : m), null);
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={ventanaRamos ? `${ventanaRamos} Todas las cohortes de pregrado.` : "Todas las cohortes de pregrado."}>
      {b == null || filas.length === 0 || !mayor ? <BloqueSinDatos /> : (
        <div className={DISPOSICION}>
          <Grafico
            construir={() => opcionSemestreMalla(filas)}
            datos={{
              columnas: ["Semestre de la malla", "Ramos cursados", "Reprobados", "% reprobado"],
              filas: filas.map((f) => [`${f.semestre}.º`, f.intentos, f.reprobados, pct(f.tasa, 1)]),
              columnaN: 1,
            }}
            descripcion="Porcentaje de ramos reprobados según el semestre de la malla."
            aria="Barras: reprobación por semestre de la malla."
          />
          <Clave
            className={PRIMERO_EN_CELULAR}
            valor={`${mayor.semestre}.º`}
            texto={<>semestre de la malla, donde más se reprueba: <b>{pctDe(mayor.tasa, mayor.intentos, 0)}</b> ramos cursados{mayor.intentos < POCOS_CASOS ? <> <PocosCasos /></> : null}</>}
          />
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Egreso y causas: causales por programa
// ---------------------------------------------------------------------------
const PLURAL_NIVEL: Record<string, string> = { programa: "programas", facultad: "facultades" };

export function BloqueCausalesPrograma({ n, b }: { n: number; b: HistCausalesPrograma | null | undefined }) {
  const t = TX.causalesPrograma;
  const nivel = b?.nivel ?? "programa";
  const periodo = b ? { desde: periodoLegible(b.desde), hasta: periodoLegible(b.hasta) } : { desde: "—", hasta: "—" };
  const todas = b?.filas ?? [];
  const conDetalleTodas = todas.filter((f) => f.causales && f.causales.length > 0).sort((x, y) => y.total - x.total);
  const conDetalle = conDetalleTodas.slice(0, 15);
  const masProgramas = conDetalleTodas.slice(15);
  const sinDetalle = todas.filter((f) => !f.causales || f.causales.length === 0);
  const causaPrincipal = (f: (typeof todas)[number]) => {
    const c = (f.causales ?? []).slice().sort((x, y) => y.n - x.n)[0];
    return c ? `${c.etiqueta} (${entero(c.n)})` : "—";
  };
  const total = todas.reduce((s, f) => s + f.total, 0);
  const porCausa = new Map<string, number>();
  for (const f of conDetalleTodas) for (const c of f.causales ?? []) if (c.grupo !== "otros") porCausa.set(c.etiqueta, (porCausa.get(c.etiqueta) ?? 0) + c.n);
  const base = conDetalleTodas.reduce((s, f) => s + f.total, 0);
  const principal = [...porCausa.entries()].sort((x, y) => y[1] - x[1])[0];
  return (
    <Bloque
      modelo={b} n={n} titulo={t.titulo}
      definicion={llenar(t.definicion, { nivel, nivelPlural: PLURAL_NIVEL[nivel] ?? nivel, ...periodo })}
      poblacion={`Período: ${periodo.desde} a ${periodo.hasta}, todas las cohortes de pregrado.`}
    >
      {b == null || todas.length === 0 ? <BloqueSinDatos /> : (
        <div className="space-y-3">
          <Clave valor={entero(total)} texto={<>eliminaciones de pregrado entre {periodo.desde} y {periodo.hasta}</>}>
            {principal && base > 0 ? (
              <p className="mt-2 text-xs leading-5 text-[var(--portal-muted)]">
                Entre {nivel === "facultad" ? "las" : "los"} {PLURAL_NIVEL[nivel] ?? nivel} con detalle, la causa más frecuente es «{principal[0]}» ({pct(principal[1] / base, 0)} de sus eliminaciones).
              </p>
            ) : null}
          </Clave>
          {conDetalle.length ? (
            <Grafico
              construir={(ancho) => opcionCausalesPrograma(conDetalle, ancho)}
              datos={{
                columnas: [nivel === "facultad" ? "Facultad" : "Programa", "Eliminaciones", "Causa principal"],
                filas: conDetalle.map((f) => [f.programa, f.total, causaPrincipal(f)]),
                columnaN: 1,
                unidad: "eliminaciones",
              }}
              descripcion="Reparto de las eliminaciones según la causa del reglamento, por programa."
              aria="Barras apiladas: causas de eliminación por programa."
            />
          ) : <BloqueSinDatos />}
          {todas.some((f) => f.pocos_casos) ? <LeyendaPocosCasos grafico unidad="eliminaciones" /> : null}
          {masProgramas.length ? (
            <div>
              <p className="mb-1 text-xs text-[var(--portal-muted)]">{t.noGrafican}</p>
              <TablaScroll etiqueta="Filas que no se grafican por espacio">
                <table className="w-full min-w-[22rem] text-left">
                  <thead><tr><th className={TH}>{nivel === "facultad" ? "Facultad" : "Programa"}</th><th className={`${TH} text-right`}>Eliminaciones</th><th className={TH}>Causa principal</th></tr></thead>
                  <tbody>
                    {masProgramas.map((f) => (
                      <tr key={f.cod_programa ?? f.programa} className={FILA}>
                        <td className={TD}>{f.programa}{f.pocos_casos ? <> <PocosCasos /></> : null}</td><td className={`${TD} text-right tabular-nums`}>{entero(f.total)}</td><td className={TD}>{causaPrincipal(f)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TablaScroll>
            </div>
          ) : null}
          {sinDetalle.length ? (
            <div>
              <p className="mb-1 text-xs text-[var(--portal-muted)]">{t.sinDetalle}</p>
              <TablaScroll etiqueta="Filas sin detalle por causa">
                <table className="w-full min-w-[18rem] text-left">
                  <thead><tr><th className={TH}>{nivel === "facultad" ? "Facultad" : "Programa"}</th><th className={`${TH} text-right`}>Eliminaciones</th></tr></thead>
                  <tbody>
                    {sinDetalle.map((f) => (
                      <tr key={f.cod_programa ?? f.programa} className={FILA}>
                        <td className={TD}>{f.programa}{f.pocos_casos ? <> <PocosCasos /></> : null}</td><td className={`${TD} text-right tabular-nums`}>{entero(f.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TablaScroll>
            </div>
          ) : null}
          <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{t.nota}</p>
          <p className="max-w-3xl text-xs font-medium leading-5 text-[var(--portal-muted)]">El motivo personal no existe en los datos.</p>
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Egreso y causas: cuánto tardan en egresar
// ---------------------------------------------------------------------------
export function BloqueTiempo({ n, b, cohortes }: { n: number; b: HistTiempo | null | undefined; cohortes: string }) {
  const t = TX.tiempo;
  const todas = b?.filas ?? [];
  const ordenadas = todas.slice().sort((x, y) => y.n - x.n);
  const filas = ordenadas.slice(0, 12);
  const conCifra = todas.filter((f) => f.pct_a_tiempo != null);
  const base = conCifra.reduce((s, f) => s + f.n, 0);
  const promedio = base > 0 ? conCifra.reduce((s, f) => s + (f.pct_a_tiempo ?? 0) * f.n, 0) / base : null;
  return (
    <Bloque modelo={b} n={n} titulo={t.titulo} definicion={t.definicion} poblacion={cohortes === "—" ? "Cohortes con seguimiento suficiente." : `Datos: cohortes ${cohortes}, con seguimiento suficiente.`}>
      {b == null || filas.length === 0 ? <BloqueSinDatos /> : (
        <div className="space-y-3">
          {promedio != null ? (
            <Clave valor={pctDe(promedio, base, 0)} texto={<>egresa dentro de la duración nominal, en promedio entre los {entero(conCifra.length)} programas con cifra{base < POCOS_CASOS ? <> <PocosCasos /></> : null}</>} />
          ) : null}
          <Grafico
            construir={(ancho) => opcionTiempo(filas, ancho)}
            tablaExterna={verRecorte(filas.length, ordenadas.length, TX.recorte.programas)}
            datos={ordenadas.length > filas.length ? undefined : {
              columnas: [TX.recorte.col.programa, TX.recorte.col.estudiantes, TX.recorte.col.aTiempo, TX.recorte.col.mas1, TX.recorte.col.mas2],
              filas: filas.map((f) => [f.programa, f.n, pct(f.pct_a_tiempo, 0), pct(f.pct_mas_1, 0), pct(f.pct_mas_2, 0)]),
              columnaN: 1,
            }}
            descripcion="Porcentaje acumulado de egreso por programa: a tiempo, con un año y con dos años de atraso."
            aria="Barras: egreso a tiempo y con atraso por programa."
          />
          <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{b.regla_duracion}</p>
          {todas.some((f) => f.pocos_casos) ? <LeyendaPocosCasos grafico /> : null}
          <Recorte
            mostrados={filas.length} total={ordenadas.length} que={TX.recorte.programas}
            encabezados={[TX.recorte.col.programa, TX.recorte.col.estudiantes, TX.recorte.col.aTiempo, TX.recorte.col.mas1, TX.recorte.col.mas2]}
            filas={ordenadas.map((f) => ({
              nombre: f.programa, pocos: f.pocos_casos,
              celdas: [entero(f.n), pct(f.pct_a_tiempo, 0), pct(f.pct_mas_1, 0), pct(f.pct_mas_2, 0)],
            }))}
          />
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// Cómo decide el modelo: señales y espera de un semestre
// ---------------------------------------------------------------------------
const esTarea = (t: string): t is TareaId => t in FICHA_SIMPLE;
const nombreTarea = (t: string) => (esTarea(t) ? FICHA_SIMPLE[t].tema : t);
const momento = (t: string, k: number) => (esTarea(t) ? momentoSimple(t, "", k) : `tras ${k} semestres`);

export function BloqueSenales({ n, b, filtro }: { n: number; b: HistSenales | null | undefined; filtro: string }) {
  const t = TX.senales;
  const tareas = (b?.tareas ?? []).filter((x) => x.senales.length > 0);
  const primera = tareas[0]?.senales[0];
  return (
    <Bloque modelo={b} siempreUcn n={n} titulo={t.titulo} definicion={t.definicion} poblacion="Datos: estudiantes de prueba de cada modelo, toda la UCN.">
      {b == null || tareas.length === 0 ? <BloqueSinDatos soloUcn={filtro !== "Toda la UCN"} /> : (
        <div className="space-y-4">
          {primera ? (
            <Clave valor={`${num(primera.peso_pct, 0)} %`} texto={<>del peso del modelo de {nombreTarea(tareas[0].tarea).toLowerCase()} lo tiene la señal <b>{primera.etiqueta}</b></>} />
          ) : null}
          <div className="grid gap-4 lg:grid-cols-2">
            {tareas.map((x) => (
              <div key={`${x.tarea}-${x.k}`} className="min-w-0 rounded-md border border-[var(--boveda-linea)] p-3">
                <p className="text-sm font-semibold text-[var(--portal-fg)]">{nombreTarea(x.tarea)}</p>
                <p className="mb-2 text-xs text-[var(--portal-muted)]">
                  Con la información disponible {momento(x.tarea, x.k)}. {llenar(x.tarea === "t2" ? t.muestraInscripciones : t.muestra, { n: entero(x.n_muestra) })}
                </p>
                <Grafico
                  construir={(ancho) => opcionSenales(x.senales.slice(0, 5), ancho)}
                  datos={{ columnas: ["Señal", "Peso en el modelo"], filas: x.senales.slice(0, 5).map((s) => [s.etiqueta, `${num(s.peso_pct, 1)} %`]) }}
                  descripcion={`${t.peso} Modelo de ${nombreTarea(x.tarea).toLowerCase()}.`}
                  aria={`Barras: señales que más pesan en el modelo de ${nombreTarea(x.tarea).toLowerCase()}.`}
                />
              </div>
            ))}
          </div>
          <p className="text-xs text-[var(--portal-muted)]">{t.peso}</p>
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

export function BloqueEsperar({ n, b, filtro }: { n: number; b: HistEsperar | null | undefined; filtro: string }) {
  const t = TX.esperar;
  const comps = b?.comparaciones ?? [];
  const completas = comps.filter((c) => c.de_cada_10_antes != null && c.de_cada_10_despues != null);
  const difs = completas.map((c) => (c.de_cada_10_despues ?? 0) - (c.de_cada_10_antes ?? 0));
  const mejora = difs.length > 0 && difs.every((d) => d > 0.5) ? "mejora" : difs.length > 0 && difs.every((d) => d <= 0.5) ? "no mejora" : "mixta";
  const pares = completas.map((c) => `${nombreTarea(c.tarea).toLowerCase()}: ${num(c.de_cada_10_antes, 1)} → ${num(c.de_cada_10_despues, 1)} de cada 10`).join("; ");
  const puntos = (v: number | null) => (v == null ? null : Math.max(0, Math.min(10, Math.round(v))));
  return (
    <Bloque modelo={b} siempreUcn n={n} titulo={t.titulo} definicion={t.definicion} poblacion="Datos: estudiantes de prueba de cada modelo, toda la UCN.">
      {b == null || comps.length === 0 ? <BloqueSinDatos soloUcn={filtro !== "Toda la UCN"} /> : (
        <div className="space-y-4">
          {completas.length ? (
            <Clave
              valor={mejora === "mejora" ? "Sí mejora" : mejora === "no mejora" ? "No mejora" : "Depende"}
              texto={<>
                {mejora === "mejora" ? "Esperar un semestre más mejora la anticipación del modelo" : mejora === "no mejora" ? "Esperar un semestre más no mejora la anticipación del modelo" : "Esperar un semestre más mejora la anticipación en unos casos y en otros no"}
                {" "}(de cada 10 estudiantes que no continúan, los que el modelo alcanza, antes → después): {pares}.
              </>}
            />
          ) : null}
          <div className="grid gap-4 lg:grid-cols-2">
            {comps.map((c) => (
              <div key={`${c.tarea}-${c.k_antes}-${c.k_despues}`} className="min-w-0 rounded-md border border-[var(--boveda-linea)] p-3">
                <p className="mb-2 text-sm font-semibold text-[var(--portal-fg)]">{nombreTarea(c.tarea)}</p>
                {([[t.antes, c.k_antes, c.de_cada_10_antes, COLOR_DEJAN], [t.despues, c.k_despues, c.de_cada_10_despues, "#9DBAD6"]] as const).map(([rotulo, k, valor, color]) => {
                  const llenos = puntos(valor);
                  return (
                    <div key={rotulo} className="mb-2">
                      {llenos == null ? (
                        <Aviso>{TX.sinDatos}</Aviso>
                      ) : (
                        <Puntos llenos={llenos} color={color} etiqueta={`${num(valor, 1)} de cada 10 ${rotulo.toLowerCase()}`} />
                      )}
                      <p className="mt-1 text-xs text-[var(--portal-muted)]">
                        <b className="text-[var(--portal-fg)]">{rotulo}:</b> {momento(c.tarea, k)}{valor == null ? "" : ` · ${num(valor, 1)} de cada 10`}
                      </p>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          {b.nota_poblaciones ? <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{t.poblaciones}</p> : null}
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}
