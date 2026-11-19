// Datos de la pestaña «Modelo por facultad»: para cada tarea T1 a T6, los grupos por facultad o programa de su vista principal.
// Solo agregados: el servidor entrega todos los grupos (los de menos de 10 personas con la marca pocos_casos);
// aquí no se recalcula nada, solo se reúnen las seis tareas y se ordenan por facultad.
import {
  neuralApi, type EstadoTarea, type GrupoTarea, type PronosticoAgregado, type TareaId, type VistaTarea,
} from "./neural";
import { ES_MODELO_EN_USO } from "./neuralLenguaSimple";
import { TAREAS } from "./neuralGraficosTareas";

export interface DatosTareaFacultad {
  tarea: TareaId;
  estado: EstadoTarea;
  /** Vista de la que salen las cifras (la principal, o la primera con facultades si la principal no las tiene). */
  vista: VistaTarea;
  /** True si la vista principal no tiene cifras por facultad y se usó otra evaluación de la misma tarea. */
  alternativa: boolean;
  pronostico: PronosticoAgregado;
  /** Clave del grupo -> grupo (facultad: su nombre; programa: su código). Vacío si la tarea no tiene cifras en ese nivel. */
  porGrupo: Map<string, GrupoTarea>;
}

export interface DatosFacultades {
  tareas: DatosTareaFacultad[];
  /** Facultades con cifras en al menos una tarea, en orden alfabético. */
  facultades: string[];
}

/** Orden en que se prueban las vistas: la principal; luego las del mismo corte (el modelo en uso primero); luego el resto. */
export function ordenVistas(vistas: readonly VistaTarea[]): VistaTarea[] {
  const principal = vistas.find((v) => v.principal) ?? vistas[0];
  if (!principal) return [];
  const resto = vistas.filter((v) => v !== principal);
  const puntaje = (v: VistaTarea) => (v.corte_k === principal.corte_k ? 0 : 2) + (ES_MODELO_EN_USO(v.variante) ? 0 : 1);
  return [principal, ...resto.sort((a, b) => puntaje(a) - puntaje(b))];
}

export type NivelVista = "facultad" | "programa";

const MAX_INTENTOS = 4;

async function cargarTarea(tarea: TareaId, nivel: NivelVista, signal: AbortSignal): Promise<DatosTareaFacultad | null> {
  const detalle = await neuralApi.modelosTarea(tarea, signal);
  const candidatas = ordenVistas(detalle.vistas).slice(0, MAX_INTENTOS);
  if (candidatas.length === 0) return null;
  let primera: DatosTareaFacultad | null = null;
  for (const [i, vista] of candidatas.entries()) {
    const g = await neuralApi.modelosGrupos(tarea, nivel, vista.variante, vista.corte_k, signal);
    // En T2 cada grupo viene repetido por banda de nota; la cifra de la facultad es la de reprobar.
    const grupos = g.grupos.filter((x) => (tarea === "t2" ? x.categoria === "reprobado" : true));
    const datos: DatosTareaFacultad = {
      tarea, estado: detalle.tarea.estado, vista, alternativa: i > 0, pronostico: vista.pronostico_agregado,
      porGrupo: new Map(grupos.map((x) => [nivel === "programa" ? x.grupo : x.nombre, x])),
    };
    if (i === 0) primera = datos;
    if (grupos.length > 0) return datos;
  }
  // Ninguna vista tiene cifras en este nivel: se informa con la vista principal.
  return primera;
}

/** Carga las seis tareas en paralelo. */
export async function cargarFacultades(signal: AbortSignal): Promise<DatosFacultades> {
  const lista = await Promise.all(TAREAS.map((t) => cargarTarea(t, "facultad", signal)));
  const tareas = lista.filter((x): x is DatosTareaFacultad => x != null);
  const nombres = new Set<string>();
  for (const t of tareas) for (const f of t.porGrupo.keys()) nombres.add(f);
  return { tareas, facultades: [...nombres].sort((a, b) => a.localeCompare(b, "es")) };
}

/** Facultad con cifras en más tareas (desempata por orden alfabético): sirve de selección inicial. */
export function facultadInicial(d: DatosFacultades): string {
  let mejor = "";
  let max = -1;
  for (const f of d.facultades) {
    const n = d.tareas.filter((t) => t.porGrupo.has(f)).length;
    if (n > max) { mejor = f; max = n; }
  }
  return mejor;
}

// ---------------------------------------------------------------------------
// Nivel programa
// ---------------------------------------------------------------------------
export interface ProgramaInfo { codigo: string; nombre: string; facultad: string }

export interface DatosProgramas {
  tareas: DatosTareaFacultad[];
  /** Programas con cifras en al menos una tarea, ordenados por facultad y nombre. */
  programas: ProgramaInfo[];
}

/** Carga las seis tareas por programa; la lista es la unión de los programas con cifras en alguna tarea. */
export async function cargarProgramas(signal: AbortSignal): Promise<DatosProgramas> {
  const lista = await Promise.all(TAREAS.map((t) => cargarTarea(t, "programa", signal)));
  const tareas = lista.filter((x): x is DatosTareaFacultad => x != null);
  const mapa = new Map<string, ProgramaInfo>();
  for (const t of tareas) {
    for (const [codigo, g] of t.porGrupo) {
      if (!mapa.has(codigo)) mapa.set(codigo, { codigo, nombre: g.nombre, facultad: g.facultad ?? "Sin facultad" });
    }
  }
  const programas = [...mapa.values()].sort((a, b) => a.facultad.localeCompare(b.facultad, "es") || a.nombre.localeCompare(b.nombre, "es"));
  return { tareas, programas };
}

/** Programa con cifras en más tareas (desempata por el orden de la lista): selección inicial. */
export function programaInicial(d: DatosProgramas): string {
  let mejor = "";
  let max = -1;
  for (const p of d.programas) {
    const n = d.tareas.filter((t) => t.porGrupo.has(p.codigo)).length;
    if (n > max) { mejor = p.codigo; max = n; }
  }
  return mejor;
}

/** Programa por nombre y código entre paréntesis, como en el resto del módulo. */
export const etiquetaPrograma = (p: ProgramaInfo) => `${p.nombre} (${p.codigo})`;
