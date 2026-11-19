"use client";

// Selector en cascada «Toda la UCN → facultad → programa», compartido por «Histórico» y «Proyecciones». La selección vive en el
// panel; cada pestaña conoce sus propios programas (la lista cambia entre una y otra) y nunca pide uno que no figura en su lista,
// así que no recibe un 404. Si el programa elegido no está en la pestaña activa, se muestra la facultad con una nota y la
// selección se conserva para la otra pestaña. Lo mismo con una facultad que la pestaña no trae: se muestra toda la UCN con una nota.
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { FacultadFiltro, FiltroVista, ProgramaFiltro } from "../lib/neural";
import { SELECTOR_TEXTOS as TX, llenar } from "../lib/neuralLenguaSimple";
import { CARD, ETIQUETA_CAMPO, SELECT } from "./NeuralUI";

export const UCN = "Toda la UCN";

/** Lo que eligió la persona: la facultad («Toda la UCN» si ninguna) y, opcionalmente, un programa de esa facultad (código y nombre). */
export interface SeleccionPoblacion { facultad: string; programa: string | null; nombrePrograma: string | null }
export const SELECCION_UCN: SeleccionPoblacion = { facultad: UCN, programa: null, nombrePrograma: null };

export interface FiltroResuelto {
  /** Lo que se le pide al servidor (nunca un programa que la pestaña no lista). */
  filtro: FiltroVista;
  /** Nombre del programa elegido si la pestaña lo lista. */
  nombrePrograma: string | null;
  /** Hay un programa elegido pero esta pestaña no lo trae: se muestra la facultad. */
  programaSinDatos: boolean;
  /** Hay una facultad elegida pero esta pestaña no la trae: se muestra toda la UCN. */
  facultadSinDatos: boolean;
  /** Aún no se conoce la lista de la pestaña y hay algo elegido: se espera a conocerla antes de mostrar nada. */
  esperandoLista: boolean;
  /**
   * La selección tal como la pestaña la muestra y la usa para pedir datos: igual a la compartida, salvo que «Toda la UCN» con un
   * programa que la pestaña lista bajo una facultad se normaliza a esa facultad con el programa. Así selector, chip y datos coinciden.
   */
  seleccion: SeleccionPoblacion;
}

/**
 * Convierte la selección compartida en el filtro de ESTA pestaña. Sin la lista de la pestaña (`jerarquia` nula, antes de su primera
 * respuesta) pide toda la UCN, que existe siempre, para conocerla; con la lista, pide el programa solo si figura en ella y la
 * facultad solo si figura en ella.
 */
export function resolverFiltro(sel: SeleccionPoblacion, jerarquia: readonly FacultadFiltro[] | null): FiltroResuelto {
  if (jerarquia === null) {
    return { filtro: { facultad: null, programa: null }, nombrePrograma: null, programaSinDatos: false, esperandoLista: sel.facultad !== UCN || sel.programa !== null, facultadSinDatos: false, seleccion: sel };
  }
  // «Toda la UCN» con un programa (lo deja así «Otros programas» de Cohortes): si esta pestaña lista el programa, es el de su facultad.
  if (sel.facultad === UCN && sel.programa !== null) {
    const dueña = jerarquia.find((f) => f.facultad !== UCN && f.programas.some((p) => p.codigo === sel.programa));
    const p = dueña?.programas.find((x) => x.codigo === sel.programa);
    if (dueña && p) {
      return {
        filtro: { facultad: dueña.facultad, programa: p.codigo }, nombrePrograma: p.nombre, programaSinDatos: false, facultadSinDatos: false,
        esperandoLista: false, seleccion: { facultad: dueña.facultad, programa: p.codigo, nombrePrograma: p.nombre },
      };
    }
  }
  const facultadSinDatos = sel.facultad !== UCN && !jerarquia.some((f) => f.facultad === sel.facultad);
  const facultad = facultadSinDatos ? UCN : sel.facultad;
  // Sin la facultad en esta pestaña no se pide ningún programa: la nota de facultad ya explica que se muestra toda la UCN.
  const programa = sel.programa === null || facultadSinDatos ? null : jerarquia.flatMap((f) => f.programas).find((p) => p.codigo === sel.programa) ?? null;
  return {
    filtro: { facultad: facultad === UCN ? null : facultad, programa: programa ? programa.codigo : null },
    nombrePrograma: programa ? programa.nombre : null,
    programaSinDatos: sel.programa !== null && !facultadSinDatos && programa === null,
    facultadSinDatos,
    esperandoLista: false,
    seleccion: sel,
  };
}

// ---- Búsqueda: «ingenieria», «8616» o «comp» encuentran facultades y programas de toda la jerarquía, con o sin tildes ----
/** Mínimo de letras para empezar a buscar y tope de opciones visibles (el resto se avisa, no se dibuja). */
export const BUSQUEDA_MINIMA = 2;
export const BUSQUEDA_LIMITE = 50;

/** Minúsculas, sin tildes ni espacios sobrantes: «Ingeniería » y «ingenieria» son lo mismo. */
export function normalizarBusqueda(texto: string): string {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

export type OpcionBusqueda =
  | { tipo: "facultad"; facultad: string }
  | { tipo: "programa"; facultad: string; programa: ProgramaFiltro };

/** Palabras de una búsqueda: «civil computacion» son dos, y deben aparecer todas (en cualquier orden). */
const palabrasDe = (q: string) => q.split(/\s+/).filter(Boolean);
const contieneTodas = (texto: string, palabras: readonly string[]) => palabras.every((w) => texto.includes(w));

/**
 * Opciones que coinciden con el texto, en tres grupos: primero las facultades, luego los programas que coinciden por su propio nombre
 * o código, y al final los que coinciden solo por el nombre de su facultad. Con varias palabras basta que todas aparezcan, en
 * cualquier orden («civil computacion» encuentra «Ingeniería Civil en Computación e Informática»).
 * `total` cuenta todas las coincidencias; `opciones` trae como mucho `limite`. Con menos de dos letras no hay búsqueda.
 */
export function buscarEnJerarquia(
  jerarquia: readonly FacultadFiltro[] | null, texto: string, limite: number = BUSQUEDA_LIMITE,
): { opciones: OpcionBusqueda[]; total: number } {
  const q = normalizarBusqueda(texto);
  if (q.length < BUSQUEDA_MINIMA || jerarquia === null) return { opciones: [], total: 0 };
  const palabras = palabrasDe(q);
  const facultades: OpcionBusqueda[] = [];
  const porSuNombre: OpcionBusqueda[] = [];
  const porSuFacultad: OpcionBusqueda[] = [];
  for (const f of jerarquia) {
    if (f.facultad === UCN) continue;
    const nombreFacultad = normalizarBusqueda(f.facultad);
    if (contieneTodas(nombreFacultad, palabras)) facultades.push({ tipo: "facultad", facultad: f.facultad });
    for (const p of f.programas) {
      const propio = `${normalizarBusqueda(p.nombre)} ${normalizarBusqueda(p.codigo)}`;
      const opcion: OpcionBusqueda = { tipo: "programa", facultad: f.facultad, programa: p };
      if (contieneTodas(propio, palabras)) porSuNombre.push(opcion);
      else if (contieneTodas(`${propio} ${nombreFacultad}`, palabras)) porSuFacultad.push(opcion);
    }
  }
  const todas = [...facultades, ...porSuNombre, ...porSuFacultad];
  return { opciones: todas.slice(0, limite), total: todas.length };
}

const etiquetaPrograma = (p: ProgramaFiltro) => `${p.nombre} (${p.codigo})`;

/** Buscador (combobox) de facultades y programas de `jerarquia`; con `jerarquia` nula (aún cargando) avisa «Cargando…» en vez de «Sin coincidencias». */
export function BuscadorPoblacion({ idPrefijo, jerarquia, onSeleccion, onActivar }: {
  idPrefijo: string;
  jerarquia: readonly FacultadFiltro[] | null;
  onSeleccion: (s: SeleccionPoblacion) => void;
  /** Se llama al enfocar el campo: la pestaña puede cargar entonces la lista que aún no tiene. */
  onActivar?: () => void;
}) {
  const idLista = `${useId()}-lista`;
  const raiz = useRef<HTMLDivElement>(null);
  const [texto, setTexto] = useState("");
  const [abierta, setAbierta] = useState(false);
  const [activa, setActiva] = useState(0);
  const { opciones, total } = useMemo(() => buscarEnJerarquia(jerarquia, texto), [jerarquia, texto]);
  const buscando = normalizarBusqueda(texto).length >= BUSQUEDA_MINIMA;
  const visible = abierta && buscando;
  const idOpcion = (i: number) => `${idLista}-${i}`;

  // Un clic fuera cierra la lista.
  useEffect(() => {
    if (!abierta) return;
    const fuera = (e: PointerEvent) => { if (raiz.current && !raiz.current.contains(e.target as Node)) setAbierta(false); };
    document.addEventListener("pointerdown", fuera);
    return () => document.removeEventListener("pointerdown", fuera);
  }, [abierta]);

  // La opción activa siempre queda a la vista dentro de la lista con scroll.
  useEffect(() => {
    if (visible && opciones.length > 0) document.getElementById(`${idLista}-${activa}`)?.scrollIntoView?.({ block: "nearest" });
  }, [visible, activa, opciones.length, idLista]);

  function elegir(o: OpcionBusqueda) {
    onSeleccion(o.tipo === "facultad"
      ? { facultad: o.facultad, programa: null, nombrePrograma: null }
      : { facultad: o.facultad, programa: o.programa.codigo, nombrePrograma: o.programa.nombre });
    setTexto("");
    setAbierta(false);
    setActiva(0);
  }

  function alTeclear(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!buscando || opciones.length === 0) return;
      e.preventDefault();
      if (!abierta) { setAbierta(true); return; }
      const paso = e.key === "ArrowDown" ? 1 : -1;
      setActiva((a) => (a + paso + opciones.length) % opciones.length);
    } else if (e.key === "Enter") {
      if (visible && opciones[activa]) { e.preventDefault(); elegir(opciones[activa]); }
    } else if (e.key === "Escape") {
      if (visible) { e.preventDefault(); setAbierta(false); }
    } else if (e.key === "Tab") {
      setAbierta(false);
    }
  }

  const aviso = !buscando ? "" : jerarquia === null ? TX.buscadorCargando : total === 0 ? llenar(TX.buscadorSinResultados, { texto: texto.trim() })
    : total === 1 ? TX.buscadorUnResultado : llenar(TX.buscadorResultados, { n: String(total) });
  return (
    <div ref={raiz} className="relative min-w-0 sm:max-w-md">
      <label htmlFor={`${idPrefijo}-buscar`} className={ETIQUETA_CAMPO}>{TX.buscador}</label>
      <input
        id={`${idPrefijo}-buscar`} type="text" role="combobox" autoComplete="off" spellCheck={false}
        aria-expanded={visible} aria-controls={idLista} aria-autocomplete="list" aria-haspopup="listbox"
        aria-activedescendant={visible && opciones.length > 0 ? idOpcion(activa) : undefined}
        placeholder={TX.buscadorAyuda} value={texto}
        className="h-11 w-full min-w-0 rounded border border-[var(--boveda-linea-fuerte)] bg-[var(--boveda-madera)] px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 hover:border-white/20 focus:border-[var(--portal-cyan)]"
        onChange={(e) => { setTexto(e.target.value); setAbierta(true); setActiva(0); }}
        onFocus={() => { setAbierta(true); onActivar?.(); }} onKeyDown={alTeclear}
      />
      <div role="status" aria-live="polite" className="sr-only">{aviso}</div>
      {visible ? (
        <div className="absolute left-0 right-0 z-20 mt-1 overflow-hidden rounded border border-[var(--boveda-linea-fuerte)] bg-[var(--boveda-madera)] shadow-lg">
          <ul id={idLista} role="listbox" aria-label={TX.buscador} className="m-0 max-h-72 list-none overflow-y-auto p-0">
            {opciones.map((o, i) => (
              <li
                key={o.tipo === "facultad" ? `f-${o.facultad}` : `p-${o.facultad}-${o.programa.codigo}`}
                id={idOpcion(i)} role="option" aria-selected={i === activa}
                className={`min-h-11 cursor-pointer break-words px-3 py-2 text-sm text-slate-100 ${i === activa ? "bg-white/10" : "hover:bg-white/5"}`}
                onMouseDown={(e) => e.preventDefault()} onMouseEnter={() => setActiva(i)} onClick={() => elegir(o)}
              >
                {o.tipo === "facultad" ? (
                  <>
                    <span className="block font-semibold">{o.facultad}</span>
                    <span className="block text-xs text-[var(--portal-muted)]">{TX.buscadorFacultad}</span>
                  </>
                ) : (
                  <>
                    <span className="block">{etiquetaPrograma(o.programa)}</span>
                    <span className="block text-xs text-[var(--portal-muted)]">{o.facultad}</span>
                  </>
                )}
              </li>
            ))}
          </ul>
          {total === 0 ? <p className="m-0 px-3 py-3 text-sm text-[var(--portal-muted)]">{aviso}</p> : null}
          {total > opciones.length ? (
            <p className="m-0 border-t border-[var(--boveda-linea)] px-3 py-2 text-xs text-[var(--portal-muted)]">
              {llenar(TX.buscadorMas, { n: String(total - opciones.length) })}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Una línea arriba de una pestaña que no usa la población elegida; con Toda la UCN no se muestra (sería ruido). */
export function AvisoSeccionSinPoblacion({ seleccion }: { seleccion: SeleccionPoblacion }) {
  if (seleccion.facultad === UCN && seleccion.programa === null) return null;
  return <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">{TX.seccionSinPoblacion}</p>;
}

export function NeuralSelectorPoblacion({ idPrefijo, jerarquia, seleccion, onSeleccion, programaSinDatos, facultadSinDatos, children }: {
  idPrefijo: string;
  jerarquia: readonly FacultadFiltro[] | null;
  seleccion: SeleccionPoblacion;
  onSeleccion: (s: SeleccionPoblacion) => void;
  programaSinDatos: boolean;
  facultadSinDatos: boolean;
  children?: ReactNode;
}) {
  const facultades = (jerarquia ?? []).map((f) => f.facultad);
  if (!facultades.includes(UCN)) facultades.unshift(UCN);
  if (!facultades.includes(seleccion.facultad)) facultades.push(seleccion.facultad);
  const programas = jerarquia?.find((f) => f.facultad === seleccion.facultad)?.programas ?? [];
  const valorPrograma = seleccion.programa !== null && programas.some((p) => p.codigo === seleccion.programa) ? seleccion.programa : "";
  return (
    <section className={`${CARD} space-y-3`} aria-label={TX.etiqueta}>
      <BuscadorPoblacion idPrefijo={idPrefijo} jerarquia={jerarquia} onSeleccion={onSeleccion} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-56 sm:max-w-xs">
          <label htmlFor={`${idPrefijo}-facultad`} className={ETIQUETA_CAMPO}>{TX.facultad}</label>
          <select
            id={`${idPrefijo}-facultad`} className={SELECT} value={seleccion.facultad}
            onChange={(e) => onSeleccion({ facultad: e.target.value, programa: null, nombrePrograma: null })}
          >
            {facultades.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        {seleccion.facultad !== UCN && programas.length > 0 ? (
          <div className="min-w-0 flex-1 basis-56 sm:max-w-md">
            <label htmlFor={`${idPrefijo}-programa`} className={ETIQUETA_CAMPO}>{TX.programa}</label>
            <select
              id={`${idPrefijo}-programa`} className={SELECT} value={valorPrograma}
              onChange={(e) => {
                const p = programas.find((x) => x.codigo === e.target.value);
                onSeleccion({ facultad: seleccion.facultad, programa: p ? p.codigo : null, nombrePrograma: p ? p.nombre : null });
              }}
            >
              <option value="">{TX.todaFacultad}</option>
              {programas.map((p) => <option key={p.codigo} value={p.codigo}>{etiquetaPrograma(p)}</option>)}
            </select>
          </div>
        ) : null}
        {children}
      </div>
      {facultadSinDatos ? (
        <p role="status" className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">
          {llenar(TX.sinDatosFacultad, { facultad: seleccion.facultad })}
        </p>
      ) : null}
      {programaSinDatos ? (
        <p role="status" className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">
          {llenar(seleccion.facultad === UCN ? TX.sinDatosProgramaUcn : TX.sinDatosPrograma, { programa: seleccion.nombrePrograma ?? seleccion.programa ?? "El programa elegido" })}
        </p>
      ) : null}
    </section>
  );
}
