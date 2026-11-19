"use client";

// Pestaña «Modelo por facultad»: elige una facultad o un programa y ve, para cada tarea (T1 a T6), qué porcentaje de
// estudiantes vivió la situación («Lo que ocurrió») y cuánto lo anticipó el modelo conservado. Debajo, una tabla para comparar
// todas las facultades (o todos los programas) de un vistazo.
// Solo agregados: nunca una persona. Se muestran todos los grupos; los de menos de 10 llevan la marca «pocos casos».
import { useMemo, useState } from "react";

import type { FacultadFiltro, GrupoTarea, ProgramaFiltro } from "../lib/neural";
import {
  cargarFacultades, cargarProgramas, etiquetaPrograma, facultadInicial, programaInicial,
  type DatosFacultades, type DatosProgramas, type DatosTareaFacultad, type NivelVista, type ProgramaInfo,
} from "../lib/neuralFacultades";
import { NOMBRE_CORTO, intervaloEsperada, intervaloObservada } from "../lib/neuralGraficosTareas";
import {
  EVENTO_FACULTAD, FACULTAD_TEXTOS, FICHA_SIMPLE, etiquetaEvaluacion, lecturaBrecha, llenar, momentoSimple,
} from "../lib/neuralLenguaSimple";
import { Semaforo } from "./NeuralModelosSemaforo";
import { BuscadorPoblacion, UCN, type SeleccionPoblacion } from "./NeuralSelectorPoblacion";
import {
  CARD, Carga, ETIQUETA_CAMPO, FILA, INPUT, LeyendaPocosCasos, PocosCasos, SELECT, Segmentado, TD, TH, TablaScroll, Titulo, Vacio, entero,
  pct, useCarga,
} from "./NeuralUI";

const OPCIONES_NIVEL: readonly { id: NivelVista; label: string }[] = [
  { id: "facultad", label: "Facultad" },
  { id: "programa", label: "Programa" },
];

/** Palabras del nivel elegido, para no repetir textos casi idénticos. */
const PALABRAS = {
  facultad: { art: "la facultad", Este: "Esta facultad", plural: "facultades", todos: "todas las facultades" },
  programa: { art: "el programa", Este: "Este programa", plural: "programas", todos: "todos los programas" },
} as const;

/**
 * `seleccion` es la población que la persona eligió en otras pestañas: con un programa abre a nivel programa en ese programa; con
 * solo una facultad, a nivel facultad en esa facultad. Después los controles de esta pestaña son propios y no la modifican; si la
 * selección compartida cambia mientras tanto, la pestaña la vuelve a tomar. El buscador sí la modifica (igual que el de las otras
 * pestañas): elegir un resultado fija el nivel y el grupo de aquí y escribe la selección compartida.
 */
export function NeuralFacultades({ seleccion, onSeleccion }: { seleccion: SeleccionPoblacion; onSeleccion: (s: SeleccionPoblacion) => void }) {
  const [nivel, setNivel] = useState<NivelVista>(seleccion.programa !== null ? "programa" : "facultad");
  const [programaVisitado, setProgramaVisitado] = useState(seleccion.programa !== null);
  // Cada nivel se carga una sola vez (el de programas solo cuando se pide) y su selección se conserva al alternar.
  const estadoF = useCarga((s) => cargarFacultades(s), []);
  const estadoP = useCarga((s) => cargarProgramas(s), [], programaVisitado);
  const [facultad, setFacultad] = useState<string | null>(seleccion.facultad);
  const [programa, setPrograma] = useState<string | null>(seleccion.programa);
  const [tomada, setTomada] = useState(seleccion);
  // Aviso de que el programa compartido no está aquí y se abrió su facultad; se borra al elegir algo en esta pestaña.
  const [aviso, setAviso] = useState<string | null>(null);
  const [revisada, setRevisada] = useState<string | null>(null);
  if (tomada.facultad !== seleccion.facultad || tomada.programa !== seleccion.programa) {
    setTomada(seleccion);
    setAviso(null);
    setFacultad(seleccion.facultad);
    setPrograma(seleccion.programa);
    // Sin programa (una facultad o Toda la UCN) se pasa siempre a nivel facultad: con Toda la UCN muestra el aviso de que esta pestaña
    // no tiene esa población, nunca un programa ni una facultad que la persona no eligió.
    if (seleccion.programa !== null) { setProgramaVisitado(true); setNivel("programa"); }
    else setNivel("facultad");
  }

  // Un programa compartido que esta pestaña no trae: si se conoce su facultad y esta pestaña la trae, se abre a nivel facultad en ella.
  // Si no, se queda a nivel programa con el aviso de siempre (nunca se muestra otro programa sin decirlo).
  const clave = `${seleccion.facultad}|${seleccion.programa}`;
  if (revisada !== clave && nivel === "programa" && programa !== null && programa === seleccion.programa && estadoP.fase === "ok"
    && !estadoP.datos.programas.some((p) => p.codigo === programa)) {
    if (seleccion.facultad === UCN) setRevisada(clave);
    else if (estadoF.fase === "ok") {
      setRevisada(clave);
      if (estadoF.datos.facultades.includes(seleccion.facultad)) {
        setNivel("facultad");
        setFacultad(seleccion.facultad);
        setAviso(llenar(FACULTAD_TEXTOS.programaAFacultad, {
          programa: `${seleccion.nombrePrograma ?? programa} (${programa})`, facultad: seleccion.facultad,
        }));
      }
    }
  }

  const cambiarNivel = (n: NivelVista) => {
    if (n === "programa") setProgramaVisitado(true);
    setAviso(null);
    setNivel(n);
  };
  const elegirFacultad = (f: string) => { setAviso(null); setFacultad(f); };
  const elegirPrograma = (c: string) => { setAviso(null); setPrograma(c); };

  // Lista del buscador: las facultades y los programas con cifras de ESTA pestaña. Es nula (el buscador avisa «Cargando…») hasta que se
  // conocen ambas; los programas se cargan recién al enfocar el buscador (`onActivar`).
  const jerarquiaBuscador = useMemo<FacultadFiltro[] | null>(() => {
    if (estadoF.fase === "cargando" || estadoP.fase === "cargando") return null;
    const grupos = new Map<string, ProgramaFiltro[]>();
    if (estadoF.fase === "ok") for (const f of estadoF.datos.facultades) grupos.set(f, []);
    if (estadoP.fase === "ok") {
      for (const p of estadoP.datos.programas) grupos.set(p.facultad, [...(grupos.get(p.facultad) ?? []), { codigo: p.codigo, nombre: p.nombre }]);
    }
    return [...grupos.entries()].map(([facultad, programas]) => ({ facultad, programas }));
  }, [estadoF, estadoP]);
  const buscar = (s: SeleccionPoblacion) => {
    setAviso(null);
    setFacultad(s.facultad);
    setPrograma(s.programa);
    if (s.programa !== null) { setProgramaVisitado(true); setNivel("programa"); } else setNivel("facultad");
    onSeleccion(s);
  };

  return (
    <div className="space-y-5">
      <section className={CARD} aria-label="Buscar facultad o programa">
        <BuscadorPoblacion idPrefijo="neural-fac" jerarquia={jerarquiaBuscador} onSeleccion={buscar} onActivar={() => setProgramaVisitado(true)} />
      </section>
      <section className={CARD} aria-label="Elegir nivel">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Ver por</span>
          <Segmentado opciones={OPCIONES_NIVEL} valor={nivel} onCambio={cambiarNivel} etiqueta="Ver por facultad o por programa" />
        </div>
      </section>
      {aviso ? <p role="status" className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{aviso}</p> : null}
      {nivel === "facultad" ? (
        <Carga estado={estadoF} filas={5} alto="h-10">
          {(d) => (d.facultades.length === 0
            ? <Vacio titulo="Sin cifras por facultad">Las tareas exportadas no traen cifras por facultad.</Vacio>
            : <VistaFacultad datos={d} facultad={facultadVigente(d, facultad)} onElegir={elegirFacultad} nota={notaFacultad(d, facultad, seleccion)} />)}
        </Carga>
      ) : (
        <Carga estado={estadoP} filas={5} alto="h-10">
          {(d) => (d.programas.length === 0
            ? <Vacio titulo="Sin cifras por programa">Las tareas exportadas no traen cifras por programa.</Vacio>
            : <VistaPrograma datos={d} programa={programaVigente(d, programa)} onElegir={elegirPrograma} nota={notaPrograma(d, programa, seleccion)} />)}
        </Carga>
      )}
    </div>
  );
}

/** La facultad elegida si esta pestaña trae cifras para ella; si no, la que tiene más tareas (esta pestaña no ofrece lo que no tiene). */
function facultadVigente(d: DatosFacultades, f: string | null): string {
  return f !== null && d.facultades.includes(f) ? f : facultadInicial(d);
}
function programaVigente(d: DatosProgramas, c: string | null): string {
  return c !== null && d.programas.some((p) => p.codigo === c) ? c : programaInicial(d);
}

/** Aviso cuando la selección compartida pide algo que esta pestaña no trae (y la persona aún no eligió otra cosa aquí). */
function notaFacultad(d: DatosFacultades, f: string | null, sel: SeleccionPoblacion): string | null {
  if (f === null || f !== sel.facultad || d.facultades.includes(f)) return null;
  if (f === UCN) return llenar(FACULTAD_TEXTOS.sinDatosUcn, { otra: facultadVigente(d, f) });
  return llenar(FACULTAD_TEXTOS.sinDatosFacultad, { facultad: f, otra: facultadVigente(d, f) });
}
function notaPrograma(d: DatosProgramas, c: string | null, sel: SeleccionPoblacion): string | null {
  if (c === null || c !== sel.programa || d.programas.some((p) => p.codigo === c)) return null;
  const otro = d.programas.find((p) => p.codigo === programaVigente(d, c));
  return llenar(FACULTAD_TEXTOS.sinDatosPrograma, { programa: `${sel.nombrePrograma ?? c} (${c})`, otro: otro ? etiquetaPrograma(otro) : "otro programa" });
}

function textoCobertura(nivel: NivelVista, conDatos: number, total: number): string {
  if (conDatos === total) return `Hay cifras para las ${total} tareas.`;
  return `Hay cifras para ${conDatos} de ${total} tareas; en las demás no hay cifras para ${PALABRAS[nivel].art}.`;
}

// ---------------------------------------------------------------------------
// Nivel facultad
// ---------------------------------------------------------------------------
function VistaFacultad({ datos, facultad, onElegir, nota }: { datos: DatosFacultades; facultad: string; onElegir: (f: string) => void; nota: string | null }) {
  const conDatos = datos.tareas.filter((t) => t.porGrupo.has(facultad)).length;
  const filas = useMemo(() => datos.facultades.map((f) => ({ clave: f, etiqueta: f, facultad: null })), [datos.facultades]);
  return (
    <>
      <section className={CARD} aria-label="Elegir facultad">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,26rem)_1fr] sm:items-end">
          <div>
            <label htmlFor="neural-facultad" className={ETIQUETA_CAMPO}>Facultad</label>
            <select id="neural-facultad" className={SELECT} value={facultad} onChange={(e) => onElegir(e.target.value)}>
              {datos.facultades.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <p className="text-sm leading-6 text-[var(--portal-muted)]" aria-live="polite">{textoCobertura("facultad", conDatos, datos.tareas.length)}</p>
        </div>
        {nota ? <p role="status" className="mt-3 max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{nota}</p> : null}
      </section>
      <Detalle nivel="facultad" tareas={datos.tareas} clave={facultad} filas={filas} onElegir={onElegir} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Nivel programa
// ---------------------------------------------------------------------------
function VistaPrograma({ datos, programa, onElegir, nota }: { datos: DatosProgramas; programa: string; onElegir: (c: string) => void; nota: string | null }) {
  const conDatos = datos.tareas.filter((t) => t.porGrupo.has(programa)).length;
  const porFacultad = useMemo(() => {
    const m = new Map<string, ProgramaInfo[]>();
    for (const p of datos.programas) m.set(p.facultad, [...(m.get(p.facultad) ?? []), p]);
    return [...m.entries()];
  }, [datos.programas]);
  const filas = useMemo(
    () => datos.programas.map((p) => ({ clave: p.codigo, etiqueta: etiquetaPrograma(p), facultad: p.facultad })),
    [datos.programas],
  );
  return (
    <>
      <section className={CARD} aria-label="Elegir programa">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,32rem)_1fr] sm:items-end">
          <div>
            <label htmlFor="neural-programa" className={ETIQUETA_CAMPO}>Programa</label>
            <select id="neural-programa" className={SELECT} value={programa} onChange={(e) => onElegir(e.target.value)}>
              {porFacultad.map(([fac, ps]) => (
                <optgroup key={fac} label={fac}>
                  {ps.map((p) => <option key={p.codigo} value={p.codigo}>{etiquetaPrograma(p)}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
          <p className="text-sm leading-6 text-[var(--portal-muted)]" aria-live="polite">{textoCobertura("programa", conDatos, datos.tareas.length)}</p>
        </div>
        {nota ? <p role="status" className="mt-3 max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{nota}</p> : null}
      </section>
      <Detalle nivel="programa" tareas={datos.tareas} clave={programa} filas={filas} onElegir={onElegir} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Tarjetas + comparación (comunes a los dos niveles)
// ---------------------------------------------------------------------------
interface FilaComparar { clave: string; etiqueta: string; facultad: string | null }

function Detalle({ nivel, tareas, clave, filas, onElegir }: {
  nivel: NivelVista; tareas: DatosTareaFacultad[]; clave: string; filas: FilaComparar[]; onElegir: (c: string) => void;
}) {
  const w = PALABRAS[nivel];
  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {tareas.map((t) => <TarjetaTarea key={t.tarea} t={t} nivel={nivel} clave={clave} />)}
      </div>

      <section className={CARD} aria-label={`Comparar ${w.plural}`}>
        <Titulo sub={`Porcentaje de lo que ocurrió en cada ${nivel}. Cada columna mide algo distinto: compara ${w.plural} hacia abajo, no tareas hacia el lado. Toca un nombre para ver su detalle arriba.`}>
          Comparar {w.todos}
        </Titulo>
        <TablaComparativa nivel={nivel} tareas={tareas} filas={filas} clave={clave} onElegir={onElegir} />
        <ul className="mt-3 space-y-1 text-xs leading-5 text-[var(--portal-muted)]">
          <li>«—» significa que la tarea no trae cifra para {w.art}. Bajo cada porcentaje va el número de personas de que sale; con menos de 10 se agrega la marca «pocos casos».</li>
          {tareas.filter((t) => t.alternativa && t.porGrupo.size > 0).map((t) => (
            <li key={t.tarea}>† {NOMBRE_CORTO[t.tarea]}: la evaluación principal no se calculó por {nivel}; se usa «{etiquetaEvaluacion(t.vista.variante, t.vista.etiqueta)}».</li>
          ))}
          {tareas.filter((t) => t.porGrupo.size === 0).map((t) => (
            <li key={t.tarea}>{NOMBRE_CORTO[t.tarea]}: todavía no se calcula por {nivel}{nivel === "facultad" ? " (solo por programa)" : ""}, por eso la columna está vacía («·»).</li>
          ))}
          <li>El largo de la barra de fondo compara {w.plural} dentro de la misma columna.</li>
        </ul>
      </section>
    </>
  );
}

function TarjetaTarea({ t, nivel, clave }: { t: DatosTareaFacultad; nivel: NivelVista; clave: string }) {
  const ficha = FICHA_SIMPLE[t.tarea];
  const ev = EVENTO_FACULTAD[t.tarea];
  const g = t.porGrupo.get(clave);
  const momento = momentoSimple(t.tarea, t.vista.variante, t.vista.corte_k);
  return (
    <article className="flex min-w-0 flex-col rounded-md border border-[var(--boveda-linea)] p-4" aria-label={NOMBRE_CORTO[t.tarea]}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-[var(--portal-fg)]">{NOMBRE_CORTO[t.tarea]}</h3>
        <Semaforo tarea={t.tarea} estado={t.estado} />
      </div>
      <p className="mt-2 text-sm leading-6 text-[var(--portal-muted)]">{ficha.resumen}</p>
      <div className="mt-3 flex-1">
        {g ? <Cifras g={g} t={t} nivel={nivel} /> : <SinDatos t={t} nivel={nivel} />}
      </div>
      <p className="mt-3 border-t border-[var(--boveda-linea)] pt-2 text-xs leading-5 text-[var(--portal-subtle)]">
        Qué se cuenta: {ev.evento}. Se mide {momento}.
        {t.alternativa ? ` Evaluación usada: ${etiquetaEvaluacion(t.vista.variante, t.vista.etiqueta)}.` : ""}
      </p>
    </article>
  );
}

function SinDatos({ t, nivel }: { t: DatosTareaFacultad; nivel: NivelVista }) {
  const caja = "rounded-md border border-dashed border-[var(--boveda-linea-fuerte)] px-3 py-3 text-sm leading-6 text-[var(--portal-muted)]";
  if (t.porGrupo.size === 0) {
    return (
      <div className={caja}>
        <p className="font-semibold text-[var(--portal-fg)]">Aún no calculado por {nivel}</p>
        <p>{nivel === "facultad"
          ? "Esta tarea por ahora se resume solo por programa. Sus resultados están en Modelos."
          : "Esta tarea por ahora no se calcula por programa. Sus resultados están en Modelos."}</p>
      </div>
    );
  }
  return (
    <div className={caja}>
      <p className="font-semibold text-[var(--portal-fg)]">Sin cifra</p>
      <p>{PALABRAS[nivel].Este} no tiene cifra en esta tarea.</p>
    </div>
  );
}

function Cifras({ g, t, nivel }: { g: GrupoTarea; t: DatosTareaFacultad; nivel: NivelVista }) {
  const ev = EVENTO_FACULTAD[t.tarea];
  const mostrarEsperada = t.pronostico === "confiable" || t.pronostico === "descriptivo";
  const io = intervaloObservada(g), ie = intervaloEsperada(g);
  const de = <span className="text-sm font-normal text-[var(--portal-subtle)]"> de {entero(g.n)} {ev.unidad}</span>;
  return (
    <div className={`space-y-3 ${g.pocos_casos ? "[&_.cifra]:opacity-60" : ""}`}>
      {g.pocos_casos ? <PocosCasos /> : null}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-muted)]">Lo que ocurrió</p>
        <p className="cifra text-2xl font-semibold tabular-nums text-[var(--portal-fg)]">{pct(g.observada)}{de}</p>
        <p className="text-xs leading-5 text-[var(--portal-subtle)]">
          {io ? `Entre ${pct(io[0])} y ${pct(io[1])} (intervalo del 95 %). ` : ""}
          {g.eventos != null ? `${entero(g.eventos)} casos.` : ""}
        </p>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-muted)]">Lo que anticipó el modelo</p>
        {mostrarEsperada && g.esperada != null ? (
          <>
            <p className="cifra text-2xl font-semibold tabular-nums text-[var(--portal-fg)]">{pct(g.esperada)}{de}</p>
            {ie ? <p className="text-xs leading-5 text-[var(--portal-subtle)]">Entre {pct(ie[0])} y {pct(ie[1])} (intervalo del 95 %).</p> : null}
            {g.observada != null ? <p className="text-xs leading-5 text-[var(--portal-subtle)]">Anticipó {lecturaBrecha(g.esperada, g.observada)}.</p> : null}
          </>
        ) : (
          <p className="text-sm leading-6 text-[var(--portal-muted)]">
            {t.pronostico === "no_confiable"
              ? `No se muestra: el modelo no es confiable para anticipar por ${nivel} en esta tarea.`
              : `No disponible: en esta tarea el modelo no entrega pronóstico por ${nivel}.`}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabla comparativa: filas = facultades o programas, columnas = T1 a T6 (lo que ocurrió)
// ---------------------------------------------------------------------------
function TablaComparativa({ nivel, tareas, filas, clave, onElegir }: {
  nivel: NivelVista; tareas: DatosTareaFacultad[]; filas: FilaComparar[]; clave: string; onElegir: (c: string) => void;
}) {
  const esPrograma = nivel === "programa";
  const [filtroFac, setFiltroFac] = useState("");
  const [texto, setTexto] = useState("");
  const maximos = useMemo(
    () => tareas.map((t) => Math.max(0, ...[...t.porGrupo.values()].map((g) => g.observada ?? 0))),
    [tareas],
  );
  const facultades = useMemo(() => [...new Set(filas.map((f) => f.facultad).filter((f): f is string => !!f))], [filas]);
  const visibles = useMemo(() => {
    const q = texto.trim().toLocaleLowerCase("es");
    return filas.filter((f) => (!filtroFac || f.facultad === filtroFac) && (!q || f.etiqueta.toLocaleLowerCase("es").includes(q)));
  }, [filas, filtroFac, texto]);
  return (
    <>
      {esPrograma ? (
        <div className="mb-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="neural-filtro-facultad" className={ETIQUETA_CAMPO}>Filtrar por facultad</label>
            <select id="neural-filtro-facultad" className={SELECT} value={filtroFac} onChange={(e) => setFiltroFac(e.target.value)}>
              <option value="">Todas las facultades</option>
              {facultades.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="neural-filtro-texto" className={ETIQUETA_CAMPO}>Buscar programa</label>
            <input id="neural-filtro-texto" type="search" className={INPUT} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Nombre o código" />
          </div>
          <p className="text-xs text-[var(--portal-muted)] sm:col-span-2" aria-live="polite">Se muestran {visibles.length} de {filas.length} programas.</p>
        </div>
      ) : null}
      <TablaScroll etiqueta={`Porcentaje de lo que ocurrió por ${nivel} y tarea`}>
        <table className="w-full min-w-[40rem]">
          <caption className="sr-only">Porcentaje de lo que ocurrió en cada {nivel}, para cada una de las seis tareas</caption>
          <thead>
            <tr>
              <th scope="col" className={`${TH} sticky left-0 z-10 bg-[var(--portal-panel-strong)]`}>{esPrograma ? "Programa" : "Facultad"}</th>
              {esPrograma ? <th scope="col" className={`${TH} min-w-[10rem]`}>Facultad</th> : null}
              {tareas.map((t) => (
                <th key={t.tarea} scope="col" className="min-w-[8.5rem] px-3 py-2 text-left align-bottom">
                  <span className="block text-xs font-semibold text-[var(--portal-fg)]">{NOMBRE_CORTO[t.tarea]}{t.alternativa && t.porGrupo.size > 0 ? " †" : ""}</span>
                  <span className="block text-xs font-normal normal-case tracking-normal text-[var(--portal-muted)]">{EVENTO_FACULTAD[t.tarea].cabecera}</span>
                  <span className="block text-xs font-normal normal-case tracking-normal text-[var(--portal-subtle)]">
                    {momentoSimple(t.tarea, t.vista.variante, t.vista.corte_k)}
                    {t.tarea !== "t2" && t.tarea !== "t6" ? ` (k = ${t.vista.corte_k})` : ""}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibles.length === 0 ? (
              <tr><td colSpan={tareas.length + 2} className={`${TD} text-[var(--portal-muted)]`}>Ningún {nivel} coincide con el filtro.</td></tr>
            ) : visibles.map((f) => {
              const activa = f.clave === clave;
              return (
                <tr key={f.clave} className={`${FILA} ${activa ? "bg-[var(--ucn-azul-suave)]" : ""}`}>
                  <th scope="row" className={`sticky left-0 z-10 min-w-[9.5rem] px-3 py-2 text-left text-sm font-normal sm:min-w-[13rem] ${activa ? "bg-[var(--ucn-azul-suave)]" : "bg-[var(--portal-panel-strong)]"}`}>
                    <button type="button" onClick={() => onElegir(f.clave)} aria-pressed={activa}
                      className="text-left text-[var(--portal-fg)] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
                      {f.etiqueta}
                    </button>
                  </th>
                  {esPrograma ? <td className={`${TD} min-w-[10rem] text-[var(--portal-muted)]`}>{f.facultad}</td> : null}
                  {tareas.map((t, i) => {
                    const g = t.porGrupo.get(f.clave);
                    const v = g?.observada;
                    const ancho = v != null && maximos[i] > 0 ? Math.round((v / maximos[i]) * 100) : 0;
                    return (
                      <td key={t.tarea} className={`${TD} whitespace-nowrap tabular-nums ${g?.pocos_casos ? "opacity-60" : ""}`}
                        style={v != null ? { background: `linear-gradient(90deg, color-mix(in srgb, var(--ucn-azul) 26%, transparent) ${ancho}%, transparent ${ancho}%)` } : undefined}>
                        {v != null && g ? <>{pct(v)}<span className="block text-xs text-[var(--portal-subtle)]">de {entero(g.n)}{g.pocos_casos ? <> <PocosCasos /></> : null}</span></> : t.porGrupo.size === 0
                          ? <span className="text-[var(--portal-subtle)]" title={`Aún no calculado por ${nivel}`}>·<span className="sr-only"> aún no calculado por {nivel}</span></span>
                          : <span className="text-[var(--portal-subtle)]" title="Sin cifra">—<span className="sr-only"> sin cifra</span></span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </TablaScroll>
      <div className="mt-2"><LeyendaPocosCasos /></div>
    </>
  );
}
