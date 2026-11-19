"use client";

// Pestaña «Histórico»: preguntas sobre lo que ya ocurrió, contadas en estudiantes y ordenadas en cuatro temas (Permanencia, Rendimiento en
// asignaturas, Egreso y eliminación, Fundamentos del modelo). Cada bloque tiene su gráfico, un número clave, una frase de qué se está mirando y «Cómo
// usarlo». Los números vienen del servidor (todos los grupos, con la marca «pocos casos» bajo 10); aquí solo se ordenan y se dibujan. Nunca hay una cifra ni
// una lista por estudiante. La facultad y el programa elegidos se mantienen al cambiar de tema y de pestaña.
import { useEffect, useState } from "react";

import { neuralApi, type FacultadFiltro, type HistAlcance, type HistEliminados, type HistoricoVista, type HistSemestres, type HistSiguieron } from "../lib/neural";
import {
  COLOR_DEJAN, COLOR_ELIMINADOS, opcionAnillo, opcionAnios, opcionCausales, opcionCurva, opcionPuntosFacultad,
  opcionSemestres, opcionTotales, ordenarCausales,
} from "../lib/neuralGraficosHistorico";
import { HISTORICO_TEXTOS as TX, llenar, periodoLegible } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import {
  BloqueCausalesPrograma, BloqueCuellos, BloqueEsperado, BloqueEsperar, BloquePerfil, BloquePrimerSemestre, BloqueRamos, BloqueSemestreMalla,
  BloqueSenales, BloqueTiempo, Bloque, Clave, ComoUsarlo, Cuadro, DISPOSICION, BloqueSinDatos, Puntos, PRIMERO_EN_CELULAR,
} from "./NeuralLoQuePasoTemas";
import { ChipPoblacion, PoblacionContext, textoPoblacion } from "./NeuralModeloEtiqueta";
import { NeuralSelectorPoblacion, UCN, resolverFiltro, type SeleccionPoblacion } from "./NeuralSelectorPoblacion";
import {
  Aviso, CARD, Carga, type DatosGrafico, LeyendaPocosCasos, MarcoGrafico, Notas, POCOS_CASOS, PocosCasos, Segmentado, Vacio, entero, num, pct, pctDe, useAncho,
  useCarga,
} from "./NeuralUI";

export type TemaHistorico = "permanencia" | "ramos" | "egreso" | "modelo";
const TEMAS: readonly TemaHistorico[] = ["permanencia", "ramos", "egreso", "modelo"];

/** [2022, 2023] -> «2022 y 2023»; [2015, 2020] -> «2015 a 2020». */
function rango(r: readonly number[] | null | undefined): string {
  if (!r) return "—";
  const [a, b] = r;
  return a === b ? String(a) : b - a === 1 ? `${a} y ${b}` : `${a} a ${b}`;
}

export function NeuralLoQuePaso({ seleccion, onSeleccion }: { seleccion: SeleccionPoblacion; onSeleccion: (s: SeleccionPoblacion) => void }) {
  const [jerarquia, setJerarquia] = useState<FacultadFiltro[] | null>(null);
  const [tema, setTema] = useState<TemaHistorico>("permanencia");
  const [destino, setDestino] = useState<{ id: string } | null>(null);
  const r = resolverFiltro(seleccion, jerarquia);
  const estado = useCarga((s) => neuralApi.historico(r.filtro, s), [r.filtro.facultad, r.filtro.programa]);
  useEffect(() => {
    if (estado.fase === "ok") setJerarquia(estado.datos.jerarquia ?? []);
  }, [estado]);
  // Una cifra de «Lo esencial» cambia de tema y, ya pintado el bloque, baja hasta él y le da el foco.
  useEffect(() => {
    if (!destino) return;
    const el = document.getElementById(destino.id);
    if (el) {
      const quieto = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({ behavior: quieto ? "auto" : "smooth", block: "start" });
      el.focus({ preventScroll: true });
    }
    setDestino(null);
  }, [destino, tema]);
  const ir = (nuevo: TemaHistorico, bloque: number) => {
    setTema(nuevo);
    setDestino({ id: `neural-hist-${bloque}` });
  };
  return (
    <div className="space-y-5">
      <NeuralSelectorPoblacion idPrefijo="neural-hist" jerarquia={jerarquia} seleccion={r.seleccion} onSeleccion={onSeleccion} programaSinDatos={r.programaSinDatos} facultadSinDatos={r.facultadSinDatos}>
        {estado.fase === "ok" && estado.datos.disponible ? (
          <p className="min-w-0 basis-full text-xs leading-5 text-[var(--portal-muted)]">{TX.leyenda}</p>
        ) : null}
      </NeuralSelectorPoblacion>
      {!r.esperandoLista && estado.fase === "ok" && estado.datos.disponible ? <LoEsencial d={estado.datos} onIr={ir} /> : null}
      <Segmentado etiqueta={TX.tema} valor={tema} onCambio={setTema} opciones={TEMAS.map((id) => ({ id, label: TX.temas[id] }))} />
      <Carga estado={r.esperandoLista ? { fase: "cargando" } : estado} filas={6} alto="h-10">
        {(d) => (d.disponible ? <Bloques d={d} tema={tema} /> : <Vacio titulo="Aún no hay datos">{TX.noDisponible}</Vacio>)}
      </Carga>
    </div>
  );
}

// ---------------------------------------------------------------------------
// «Lo esencial»: tres cifras de la misma respuesta, cada una enlazada a su bloque
// ---------------------------------------------------------------------------
interface CifraEsencial {
  id: string; titulo: string; tema: TemaHistorico; bloque: number;
  /** Sin cifra para esta población: la tarjeta dice «sin datos». */
  cifra: { valor: string; detalle: string; pocos: boolean } | null;
}

function cifrasEsenciales(d: HistoricoVista): CifraEsencial[] {
  const t = TX.esencial;
  const s = d.siguieron;
  const m = d.semestres;
  const e = d.eliminados?.clave ?? null;
  return [
    {
      id: "continuidad", titulo: t.continuidad.titulo, tema: "permanencia", bloque: 1,
      cifra: s ? { valor: pct(s.pct_siguieron, 0), detalle: llenar(t.continuidad.detalle, { siguieron: entero(s.siguieron), n: entero(s.n) }), pocos: s.pocos_casos || s.n < POCOS_CASOS } : null,
    },
    {
      id: "bajas", titulo: t.bajas.titulo, tema: "permanencia", bloque: 2,
      cifra: m && m.pct_bajas_primer_anio != null && m.bajas != null
        ? { valor: pct(m.pct_bajas_primer_anio, 0), detalle: llenar(t.bajas.detalle, { n: entero(m.bajas) }), pocos: m.pocos_casos || m.bajas < POCOS_CASOS }
        : null,
    },
    {
      id: "eliminados", titulo: e ? llenar(t.eliminados.titulo, { anio: String(e.anio) }) : t.eliminados.tituloSinDatos, tema: "egreso", bloque: 1,
      cifra: e ? { valor: entero(e.eliminados), detalle: t.eliminados.detalle, pocos: e.eliminados < POCOS_CASOS } : null,
    },
  ];
}

function LoEsencial({ d, onIr }: { d: HistoricoVista; onIr: (tema: TemaHistorico, bloque: number) => void }) {
  const t = TX.esencial;
  return (
    <PoblacionContext.Provider value={textoPoblacion(d.filtro, d.programa)}>
      <section className={CARD} aria-labelledby="neural-hist-esencial">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 id="neural-hist-esencial" className="min-w-0 text-lg font-semibold leading-7 text-[var(--portal-fg)]">{t.titulo}</h2>
          <ChipPoblacion />
        </div>
        <ul className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {cifrasEsenciales(d).map((c) => (
            <li key={c.id} className="min-w-0">
              <button
                type="button"
                onClick={() => onIr(c.tema, c.bloque)}
                className="flex min-h-11 w-full min-w-0 flex-col items-start rounded-md border border-[var(--boveda-linea)] p-3 text-left transition hover:bg-white/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]"
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{c.titulo}</span>
                {c.cifra ? (
                  <>
                    <span className="mt-1 text-2xl font-bold leading-8 text-[var(--portal-fg)]">{c.cifra.valor}</span>
                    <span className="text-sm leading-5 text-[var(--portal-fg)]">{c.cifra.detalle}</span>
                    {c.cifra.pocos ? <span className="mt-1"><PocosCasos /></span> : null}
                  </>
                ) : (
                  <span className="mt-1 text-sm leading-6 text-[var(--portal-muted)]">{t.sinDatos}</span>
                )}
                <span className="mt-2 text-xs font-medium text-[var(--ucn-azul-claro)]">{t.ver} →</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </PoblacionContext.Provider>
  );
}

function Bloques({ d, tema }: { d: HistoricoVista; tema: TemaHistorico }) {
  return (
    <PoblacionContext.Provider value={textoPoblacion(d.filtro, d.programa)}>
      <BloquesDelTema d={d} tema={tema} />
    </PoblacionContext.Provider>
  );
}

function BloquesDelTema({ d, tema }: { d: HistoricoVista; tema: TemaHistorico }) {
  const sigue = rango(d.cohortes.siguieron);
  const ramos = d.ramos_reprobados;
  const ventanaRamos = ramos ? `Período: ${periodoLegible(ramos.desde)} a ${periodoLegible(ramos.hasta)}.` : "";
  return (
    <div className="space-y-5">
      {tema === "permanencia" ? (
        <>
          <BloqueSiguieron b={d.siguieron} puntos={d.por_facultad} filtro={d.programa?.facultad ?? d.filtro} cohortes={sigue} />
          <BloqueSemestres b={d.semestres} cohortes={rango(d.cohortes.semestres)} />
          <BloqueAlcance b={d.alcance} cohortes={rango(d.cohortes.alcance)} />
          <BloquePerfil n={4} b={d.perfil_ingreso} cohortes={rango(d.cohortes.perfil_ingreso ?? d.cohortes.siguieron)} />
          <BloquePrimerSemestre n={5} b={d.primer_semestre} cohortes={rango(d.cohortes.primer_semestre ?? d.cohortes.siguieron)} />
        </>
      ) : null}
      {tema === "ramos" ? (
        <>
          <BloqueRamos n={1} b={d.ramos_reprobados} />
          <BloqueEsperado n={2} b={d.ramos_esperado} />
          <BloqueCuellos n={3} b={d.cuellos_botella} ventanaRamos={ventanaRamos} />
          <BloqueSemestreMalla n={4} b={d.semestre_malla} ventanaRamos={ventanaRamos} />
        </>
      ) : null}
      {tema === "egreso" ? (
        <>
          <BloqueEliminados b={d.eliminados} prueba={rango(d.cohortes.test_t5)} anios={d.cohortes.eliminados ? `${d.cohortes.eliminados[0]} a ${d.cohortes.eliminados[1]}` : "—"} causalesDesde={d.periodo_causales_desde} />
          <BloqueCausalesPrograma n={2} b={d.causales_programa} />
          <BloqueTiempo n={3} b={d.tiempo_egreso} cohortes={rango(d.cohortes.tiempo_egreso)} />
        </>
      ) : null}
      {tema === "modelo" ? (
        <>
          <BloqueSenales n={1} b={d.senales} filtro={d.filtro} />
          <BloqueEsperar n={2} b={d.esperar_semestre} filtro={d.filtro} />
        </>
      ) : null}
      <Notas notas={d.notas} titulo="Cómo se calcularon estas cifras" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. ¿En qué semestre se pierden más estudiantes?
// ---------------------------------------------------------------------------
function BloqueSemestres({ b, cohortes }: { b: HistSemestres | null; cohortes: string }) {
  const t = TX.semestres;
  return (
    <Bloque modelo={b} n={2} titulo={t.titulo} definicion={llenar(t.definicion, { cohortes })} poblacion={llenar(TX.poblacion.semestres, { cohortes })}>
      {b === null ? <BloqueSinDatos /> : <ContenidoSemestres b={b} />}
    </Bloque>
  );
}

function ContenidoSemestres({ b }: { b: HistSemestres }) {
  const g = opcionSemestres(b.filas, b.pocos_casos, b.n);
  const datos: DatosGrafico = {
    columnas: ["Semestre desde el ingreso", "Deja la UCN", "Eliminado", "% que deja la UCN", "% eliminado", "Estudiantes de la cohorte"],
    filas: b.filas.map((f) => [`${f.semestre}.º`, f.dejan, f.eliminados, pct(f.pct_dejan, 1), pct(f.pct_eliminados, 1), b.n]),
    columnaN: 5,
  };
  const total = (f: { dejan: number | null; eliminados: number | null }) => (f.dejan ?? 0) + (f.eliminados ?? 0);
  const pico = b.filas.reduce((m, f) => (total(f) > total(m) ? f : m), b.filas[0]);
  return (
    <>
      <div className={DISPOSICION}>
        <div className="min-w-0">
          {b.pocos_casos ? <div className="mb-1"><LeyendaPocosCasos grafico /></div> : null}
          <MarcoGrafico datos={datos} descripcion="Porcentaje de la cohorte que deja la UCN o es eliminado, por semestre desde el ingreso.">
            <EChartsChart option={g.option} height={g.alto} ariaLabel="Barras apiladas: bajas por semestre desde el ingreso." />
          </MarcoGrafico>
        </div>
        <Clave
          className={PRIMERO_EN_CELULAR}
          valor={b.pct_bajas_primer_anio == null ? "—" : pctDe(b.pct_bajas_primer_anio, b.bajas, 0)}
          texto={<>de las bajas ocurre en el <b>primer año</b> (semestres 1 y 2)</>}
        >
          {b.pocos_casos || (b.bajas != null && b.bajas < POCOS_CASOS) ? <div className="mt-1"><PocosCasos /></div> : null}
          <p className="mt-2 text-xs text-[var(--portal-muted)]">
            <Cuadro color={COLOR_DEJAN}>deja la UCN</Cuadro><Cuadro color={COLOR_ELIMINADOS}>eliminado</Cuadro>
          </p>
          {b.bajas != null ? (
            <p className="mt-2 text-xs leading-5 text-[var(--portal-muted)]">
              {entero(b.bajas)} bajas en los primeros 12 semestres, de {entero(b.n)} estudiantes ({pct(b.pct_bajas, 0)}).
            </p>
          ) : null}
        </Clave>
      </div>
      <ComoUsarlo>
        El semestre con más bajas es el {pico.semestre}.º ({total(pico) > 0 ? `${entero(total(pico))} estudiantes` : "sin dato"}):
        el apoyo preventivo conviene antes de ese semestre, no después.
      </ComoUsarlo>
    </>
  );
}

// ---------------------------------------------------------------------------
// 1. ¿Cuántos pasaron al año siguiente?
// ---------------------------------------------------------------------------
function BloqueSiguieron({ b, puntos, filtro, cohortes }: {
  b: HistSiguieron | null; puntos: HistoricoVista["por_facultad"]; filtro: string; cohortes: string;
}) {
  const t = TX.siguieron;
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const g = puntos.length ? opcionPuntosFacultad(puntos, filtro === UCN ? null : filtro, ancho) : null;
  const dif = b ? Math.abs(b.diferencia) : 0;
  const datosFacultades: DatosGrafico = {
    columnas: ["Facultad", "Estudiantes", "Siguieron", "El modelo esperaba"],
    filas: puntos.map((p) => [p.facultad, p.n, pct(p.pct_siguieron, 1), pct(p.pct_esperado, 1)]),
    columnaN: 1,
  };
  return (
    <Bloque modelo={b} n={1} titulo={t.titulo} definicion={llenar(t.definicion, { cohortes })} poblacion={llenar(TX.poblacion.modelo, { cohortes })}>
      {b === null ? <BloqueSinDatos /> : (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
          <div className="flex items-center gap-4">
            <div className="h-[120px] w-[120px] shrink-0">
              <EChartsChart option={opcionAnillo(b.pct_siguieron)} height={120} ariaLabel={`${pct(b.pct_siguieron, 0)} siguió al año siguiente.`} />
            </div>
            <div className="min-w-0 text-sm leading-6 text-[var(--portal-fg)]">
              <div><b>Ocurrió:</b> {entero(b.siguieron)} de {entero(b.n)}{b.pocos_casos ? <> <PocosCasos /></> : null}</div>
              <div><b>El modelo esperaba:</b> {entero(Math.round(b.esperados))} de {entero(b.n)}{b.pocos_casos ? <> <PocosCasos /></> : null}</div>
              <div className="text-[var(--ucn-azul-claro)]">
                Diferencia: {entero(Math.round(dif))} ({pct(b.esperados ? dif / b.esperados : null, 1)}) {b.diferencia < 0 ? "menos" : "más"} de lo esperado
              </div>
            </div>
          </div>
          <div ref={ref} className="min-w-0 flex-1 basis-72">
            {g ? (
              <>
                <p className="mb-1 text-xs text-[var(--portal-muted)]">{filtro === UCN ? t.leyendaUcn : t.leyendaFiltro}</p>
                {puntos.some((p) => p.pocos_casos) ? <div className="mb-1"><LeyendaPocosCasos grafico /></div> : null}
                <MarcoGrafico datos={datosFacultades} descripcion={filtro === UCN ? t.descripcionUcn : t.descripcionFiltro}>
                  <EChartsChart option={g.option} height={g.alto} ariaLabel="Puntos por facultad: lo que ocurrió frente a lo que el modelo esperaba." />
                </MarcoGrafico>
              </>
            ) : null}
          </div>
        </div>
      )}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

// ---------------------------------------------------------------------------
// 3. ¿Cuántos fueron eliminados cada año?
// ---------------------------------------------------------------------------
function BloqueEliminados({ b, prueba, anios, causalesDesde }: { b: HistEliminados | null; prueba: string; anios: string; causalesDesde: string | null }) {
  const t = TX.eliminados;
  return (
    <Bloque modelo={b} n={1} titulo={t.titulo} definicion={llenar(t.definicion, { prueba })} poblacion={llenar(TX.poblacion.eliminados, { anios })}>
      {b === null ? <BloqueSinDatos /> : <ContenidoEliminados b={b} causalesDesde={causalesDesde} />}
    </Bloque>
  );
}

function ContenidoEliminados({ b, causalesDesde }: { b: HistEliminados; causalesDesde: string | null }) {
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const totales = b.totales.length ? opcionTotales(b.totales, b.anio_reglamento) : null;
  const modelo = b.anios.length ? opcionAnios(b.anios, b.anio_reglamento) : null;
  const barras = b.causales ? opcionCausales(b.causales.filas, ancho) : null;
  const conEsperado = b.anios.filter((a) => a.esperados != null);
  const esperados = conEsperado.reduce((s, a) => s + (a.esperados ?? 0), 0);
  const ocurridos = conEsperado.reduce((s, a) => s + a.eliminados, 0);
  const hayPrueba = conEsperado.length > 0 && esperados > 0;
  const desde = causalesDesde ? causalesDesde.slice(0, 4) : "2016";
  const datosTotales: DatosGrafico = { columnas: ["Año", "Estudiantes eliminados"], filas: b.totales.map((a) => [String(a.anio), a.eliminados]) };
  const datosCausales: DatosGrafico | undefined = b.causales
    ? { columnas: ["Causa", "Eliminaciones", "Porcentaje"], filas: ordenarCausales(b.causales.filas).map((c) => [c.etiqueta, c.n, pct(c.pct, 1)]) }
    : undefined;
  const datosModelo: DatosGrafico = {
    columnas: ["Año", "Estudiantes", "Eliminados", "Ocurrió", "El modelo esperaba"],
    filas: b.anios.map((a) => [`${a.anio}${a.parcial ? " (parcial)" : ""}`, a.n, a.eliminados, pct(a.tasa, 1), pct(a.tasa_esperada, 1)]),
    columnaN: 1,
  };
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-3">
          {b.clave ? (
            <Clave valor={entero(b.clave.eliminados)} texto={<>estudiantes de pregrado eliminados en <b>{b.clave.anio}</b>, el último año completo</>} />
          ) : null}
          {totales ? (
            <MarcoGrafico datos={datosTotales} descripcion="Estudiantes de pregrado eliminados por año calendario.">
              <EChartsChart option={totales.option} height={totales.alto} ariaLabel="Línea por año: total de estudiantes de pregrado eliminados." />
            </MarcoGrafico>
          ) : <Vacio>{TX.sinDatos}</Vacio>}
        </div>
        <div ref={ref} className="min-w-0">
          <p className="mb-1 text-sm font-semibold text-[var(--portal-fg)]">Por causa (reglamento)</p>
          <p className="mb-2 text-xs text-[var(--portal-muted)]">Todas las eliminaciones de pregrado desde {desde}.</p>
          {barras ? (
            <MarcoGrafico datos={datosCausales} descripcion="Porcentaje de eliminaciones según la causa del reglamento.">
              <EChartsChart option={barras.option} height={barras.alto} ariaLabel="Barras: eliminados por causa del reglamento." />
            </MarcoGrafico>
          ) : <Vacio>{TX.sinDatos}</Vacio>}
        </div>
      </div>
      {modelo ? (
        <div className="mt-4 max-w-3xl rounded-md border border-[var(--boveda-linea)] p-3">
          <p className="text-sm font-semibold text-[var(--portal-fg)]">Lo que el modelo anticipa: eliminación en el 2.º año de la carrera</p>
          <p className="mb-2 text-xs text-[var(--portal-muted)]">
            De quienes terminaron su 2.º semestre, el porcentaje eliminado en los dos semestres siguientes.{" "}
            <Cuadro color={COLOR_ELIMINADOS}>ocurrió</Cuadro>- - el modelo esperaba (solo años de prueba)
          </p>
          {b.anios.some((a) => a.pocos_casos) ? <div className="mb-1"><LeyendaPocosCasos grafico /></div> : null}
          <MarcoGrafico datos={datosModelo} descripcion="Porcentaje eliminado en el 2.º año de la carrera, ocurrido y esperado por el modelo.">
            <EChartsChart option={modelo.option} height={modelo.alto} ariaLabel="Líneas por año: eliminación en el 2.º año, ocurrida y esperada por el modelo." />
          </MarcoGrafico>
        </div>
      ) : null}
      <ComoUsarlo>
        {hayPrueba ? (
          <>
            En los años de prueba ({conEsperado[0].anio}{conEsperado.length > 1 ? ` a ${conEsperado[conEsperado.length - 1].anio}` : ""}) el modelo esperaba{" "}
            {entero(Math.round(esperados))} eliminados en el 2.º año y ocurrieron {entero(ocurridos)} ({ocurridos >= esperados ? "más" : "menos"} de lo esperado, {num(Math.abs(ocurridos - esperados) / esperados * 100, 0)} %).{" "}
            El reglamento {b.anio_reglamento} es posterior: antes de proyectar hacia adelante hay que comprobar que el modelo sigue calzando.
          </>
        ) : (
          <>Sin años de prueba para este grupo, solo se muestra lo ocurrido. El reglamento {b.anio_reglamento} cambió las causales de eliminación, así que los años desde entonces no se comparan directo con los anteriores.</>
        )}
      </ComoUsarlo>
      <div className="mt-3 max-w-3xl"><Aviso>{TX.eliminados.avisoRegistro}</Aviso></div>
    </>
  );
}

// ---------------------------------------------------------------------------
// 4. Si se hubiera usado el modelo para elegir a quién apoyar
// ---------------------------------------------------------------------------
function BloqueAlcance({ b, cohortes }: { b: HistAlcance | null; cohortes: string }) {
  const t = TX.alcance;
  return (
    <Bloque modelo={b} n={3} titulo={t.titulo} definicion={llenar(t.definicion, { cohortes })} poblacion={llenar(TX.poblacion.modelo, { cohortes })}>
      {b === null ? <BloqueSinDatos /> : <ContenidoAlcance b={b} />}
      <ComoUsarlo>{t.comoUsar}</ComoUsarlo>
    </Bloque>
  );
}

function ContenidoAlcance({ b }: { b: HistAlcance }) {
  const g = opcionCurva(b);
  const exacto = b.pct_alcanzado * 10;
  const con = Math.max(0, Math.min(10, Math.round(exacto)));
  const casi = con > exacto;
  const azar = Math.max(0, Math.min(10, Math.round(b.al_azar_de_cada_10)));
  const datos: DatosGrafico = {
    columnas: ["% de estudiantes apoyados (mayor riesgo primero)", "% de las bajas alcanzadas"],
    filas: b.curva.map((p) => [pct(p.apoyados, 0), pct(p.alcanzados, 0)]),
  };
  return (
    <div className={DISPOSICION}>
      <div className="min-w-0">
        <MarcoGrafico datos={datos} descripcion="Curva de alcance: porcentaje de las bajas que se alcanza según el porcentaje de estudiantes apoyados, frente a elegir al azar.">
          <EChartsChart option={g.option} height={g.alto} ariaLabel="Curva de alcance del modelo frente a elegir al azar." />
        </MarcoGrafico>
      </div>
      <div className={`min-w-0 space-y-3 ${PRIMERO_EN_CELULAR}`}>
        <Clave valor={<>{casi ? "Casi " : ""}{con} de cada 10 <span className="text-lg font-semibold text-[var(--portal-muted)]">({pctDe(b.pct_alcanzado, b.eventos, 0)})</span></>} texto={<>de quienes no continuaron habría alcanzado el apoyo, con el {pct(b.fraccion_apoyo, 0)} de mayor riesgo</>} />
        {b.pocos_casos || b.eventos < POCOS_CASOS ? <PocosCasos /> : null}
        <div>
          <Puntos llenos={con} color={COLOR_DEJAN} etiqueta={`${con} de cada 10 con el modelo`} />
          <p className="mt-1 text-xs text-[var(--portal-muted)]">
            con el modelo, apoyando a {entero(b.apoyados)} estudiantes ({entero(b.alcanzados)} de {entero(b.eventos)} que no continuaron)
          </p>
        </div>
        <div>
          <Puntos llenos={azar} color="#8C9097" etiqueta={`${azar} de cada 10 al azar`} />
          <p className="mt-1 text-xs text-[var(--portal-muted)]">eligiendo al azar la misma cantidad</p>
        </div>
      </div>
    </div>
  );
}
