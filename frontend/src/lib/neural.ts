// Cliente tipado de DAI Neural (/neural/*). Modo local: token de la sesión de la Bóveda. Modo Pages: respuestas precalculadas de wh-api con el token del PIN.
// Los tipos espejan backend/app/services/neural/schemas.py. Solo agregados: el módulo no consulta registros de personas.
import { API_PAGES_URL, limpiarToken, obtenerToken } from "./accesoPages";
import { API_BASE_URL as API_LOCAL_URL, SESSION_TOKEN_STORAGE_KEY } from "./sesionClaves";

// Build-time switch (see docs/github-pages.md). Declared in-file, with the literal
// `process.env.NEXT_PUBLIC_MODO`, so the bundler folds it and drops the dead branches.
const MODO_PAGES = process.env.NEXT_PUBLIC_MODO === "pages";

// Modo Pages: datos desde wh-api con el token del PIN (sessionStorage), sin cookies.
const API_BASE_URL = MODO_PAGES ? API_PAGES_URL : API_LOCAL_URL;

/** Error de una respuesta no exitosa, con mensaje ya apto para mostrar (sin datos de personas). */
export class NeuralError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "NeuralError";
    this.status = status;
  }
}

/** 403 `aceptacion_requerida`: falta aceptar la versión vigente de la declaración de confidencialidad. */
export class AceptacionRequerida extends NeuralError {
  readonly version: string;
  constructor(version: string) {
    super(403, "Debes aceptar la declaración de confidencialidad para ver DAI Neural.");
    this.name = "AceptacionRequerida";
    this.version = version;
  }
}

/** True when the error comes from an aborted request (not a real failure). */
export function esCancelacion(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

function authHeaders(): Headers {
  const headers = new Headers();
  if (typeof window !== "undefined") {
    const token = MODO_PAGES ? obtenerToken() : window.localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function leerDetalle(res: Response): Promise<unknown> {
  try {
    return ((await res.json()) as { detail?: unknown }).detail;
  } catch {
    return null;
  }
}

function detalleFijo(detail: unknown): string | null {
  return typeof detail === "string" && detail.length <= 200 ? detail : null;
}

function aceptacionRequerida(detail: unknown): AceptacionRequerida | null {
  if (typeof detail !== "object" || detail === null) return null;
  const d = detail as { codigo?: unknown; version?: unknown };
  if (d.codigo !== "aceptacion_requerida") return null;
  return new AceptacionRequerida(typeof d.version === "string" ? d.version : "");
}

async function errorDeRespuesta(res: Response): Promise<NeuralError> {
  const detail = await leerDetalle(res);
  const detalle = detalleFijo(detail);
  // Modo Pages: un 401 es token vencido o revocado; se borra y reaparece la pantalla del PIN.
  // Un 403 (p. ej. wh-api aún sin /neural) no cierra la sesión: se informa en Neural y el Termómetro sigue.
  if (MODO_PAGES && res.status === 401) {
    limpiarToken();
    return new NeuralError(401, "Tu acceso venció. Ingresa el PIN nuevamente.");
  }
  switch (res.status) {
    case 401:
      return new NeuralError(401, "Tu sesión venció. Vuelve a ingresar.");
    case 403:
      return aceptacionRequerida(detail) ?? new NeuralError(403, "Tu cuenta no tiene acceso a DAI Neural.");
    case 404:
      // Modo Pages: «Esta combinación no está publicada…» viene en el detalle del servidor.
      return new NeuralError(404, (MODO_PAGES ? detalle : null) ?? "No se encontró lo solicitado.");
    case 409:
      return new NeuralError(409, "La declaración cambió. Recarga la página para ver la versión vigente.");
    case 422:
      return new NeuralError(422, "La solicitud no es válida.");
    case 503:
      return new NeuralError(503, detalle ?? "El módulo DAI Neural no está configurado o sus datos no están disponibles.");
    default:
      return new NeuralError(res.status, "No se pudo completar la consulta. Intenta nuevamente.");
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(), cache: "no-store", signal, credentials: MODO_PAGES ? "omit" : undefined });
  if (!res.ok) throw await errorDeRespuesta(res);
  return res.json() as Promise<T>;
}

// ---- Tipos (espejo de schemas.py) ----
export interface EstadisticaComparacion {
  n_episodios: number;
  n_activos: number;
  n_promedio: number;
  /** n < 10 (lo calcula el servidor): se muestra con la marca «pocos casos». */
  pocos_casos: boolean;
  creditos_p25: number | null;
  creditos_p50: number | null;
  creditos_p75: number | null;
  promedio_p25: number | null;
  promedio_p50: number | null;
  promedio_p75: number | null;
}

export interface ProgramaResumen {
  cod_programa: string;
  nombre_programa: string | null;
  n_episodios: number;
  primera_cohorte: string | null;
  ultima_cohorte: string | null;
}

export interface CohorteResultado {
  cohorte: string;
  n_ingreso: number;
  pocos_casos: boolean;
  duracion: number | null;
  duracion_anios: number | null;
  censurado_d: boolean;
  censurado_d1: boolean;
  censurado_d2: boolean;
  titulados_d: number | null;
  titulados_d1: number | null;
  titulados_d2: number | null;
  censurado_retencion: boolean;
  n_retencion_obs: number | null;
  n_retenidos: number | null;
}

export interface CohorteSemestre extends EstadisticaComparacion { cohorte: string; semestre_k: number }
export interface ProgramaSemestre extends EstadisticaComparacion { semestre_k: number }

export interface CohortesPrograma {
  cod_programa: string;
  nombre_programa: string | null;
  resultados: CohorteResultado[];
  semestres_por_cohorte: CohorteSemestre[];
  semestres_programa: ProgramaSemestre[];
  notas: string[];
}

export interface CargaFuente {
  fuente: string;
  carga_wh: string | null;
  filas_origen: number | null;
  filas_insertadas: number | null;
  terminado_en: string | null;
  estado: string;
}

export interface ChequeoFallido {
  chequeo: string;
  valor_esperado: string | null;
  valor_obtenido: string | null;
  explicacion: string | null;
}

export interface ConstruccionMart {
  mart: string;
  filas: number;
  construido_en: string;
  periodo_maximo: string | null;
}

export interface Calidad {
  cargas: CargaFuente[];
  auditoria: { total: number; ok: number; fallidos: ChequeoFallido[] };
  marts: ConstruccionMart[];
  cobertura: string[];
}


// ---- Traslados entre programas (P61): solo agregados; todo se entrega y los grupos de menos de 10 llevan pocos_casos ----
export type TipoTraslado =
  | "eleccion_especialidad" | "cambio_ciclo" | "continuacion_estudios" | "cambio_carrera" | "traslado_sede" | "traslado_otro";
export interface TipoTrasladoResumen { tipo: TipoTraslado; etiqueta: string; descripcion: string; cuenta_abandono: boolean; n: number; pocos_casos: boolean }
export interface TrasladoAnio { anio: number; tipo: TipoTraslado; n: number; pocos_casos: boolean }
export interface FlujoTraslado { cod_origen: string; nombre_origen: string | null; cod_destino: string; nombre_destino: string | null; n: number; tipo_principal: TipoTraslado | null; pocos_casos: boolean }
export interface BalancePrograma {
  cod_programa: string; nombre_programa: string | null;
  ganados_total: number; perdidos_total: number; neto_total: number;
  ganados_sin_eleccion: number; perdidos_sin_eleccion: number; neto_sin_eleccion: number;
}
export interface FiltrosTraslado { anio_desde: number | null; anio_hasta: number | null; tipo: TipoTraslado | null; solo_abandono: boolean }
export interface ResumenTraslados {
  filtros: FiltrosTraslado;
  anios_disponibles: { desde: number | null; hasta: number | null };
  total: number; ambiguos_excluidos: number;
  por_tipo: TipoTrasladoResumen[]; por_anio: TrasladoAnio[]; flujos: FlujoTraslado[];
  balance: BalancePrograma[]; notas: string[];
}
export interface TipoConteo { tipo: TipoTraslado; etiqueta: string; n: number; pocos_casos: boolean }
export interface ProgramaContraparte { cod_programa: string; nombre_programa: string | null; n: number; pocos_casos: boolean }
export interface BalanceAnio { anio: number; ganados: number; perdidos: number; neto: number }
export interface TrasladosPrograma {
  cod_programa: string; nombre_programa: string | null; filtros: FiltrosTraslado; balance: BalancePrograma;
  entradas_por_tipo: TipoConteo[]; salidas_por_tipo: TipoConteo[]; origenes: ProgramaContraparte[]; destinos: ProgramaContraparte[];
  por_anio: BalanceAnio[]; notas: string[];
}
export interface ParamsTraslados { anioDesde?: number | null; anioHasta?: number | null; tipo?: TipoTraslado | null; soloAbandono?: boolean }

// ---- Modelos: métricas agregadas de los benchmarks (jamás predicciones individuales) ----
export type TareaModelo = "t1" | "t2" | "t3";
export interface MetricaModelo { valor: number | null; ic_inf: number | null; ic_sup: number | null }
export interface ModeloResultado {
  tarea: TareaId; corte_k: number; modelo: string; nombre: string; familia: string;
  escalon: number; escalon_nombre: string; n_evaluacion: number | null; metricas: Record<string, MetricaModelo>;
}
export type Veredicto = "mejora" | "sin_diferencia" | "empeora";
export interface ComparacionModelos {
  tarea: TareaModelo; corte_k: number; modelo_a: string; modelo_b: string; metrica: string;
  delta: number | null; ic_inf: number | null; ic_sup: number | null; veredicto: Veredicto;
}
export interface ParametroModelo { tarea: TareaModelo; corte_k: number; modelo: string; clave: string; valor_num: number | null; valor_texto: string | null }
export interface TitularModelos { tarea: TareaModelo; orden: number; clave: string; texto: string }
export interface ResumenModelos {
  disponible: boolean; generado_en: string | null; aviso: string; modelos: ModeloResultado[];
  comparaciones: ComparacionModelos[]; arquitectura: ParametroModelo[]; titulares: TitularModelos[]; notas: string[];
}

// ---- Modelos por tarea (T1-T6): una página por tarea, siempre agregados ----
export type TareaId = "t1" | "t2" | "t3" | "t4" | "t5" | "t6";
export type EstadoTarea = "completo" | "exploratorio" | "dato_en_revision";
export type PronosticoAgregado = "confiable" | "descriptivo" | "no_confiable" | "no_disponible";
export type NivelGrupo = "programa" | "facultad" | "nivel_postgrado" | "sexo" | "via" | "tipo_colegio";
export interface FichaTarea {
  tarea: TareaId; orden: number; nombre: string; pregunta: string; poblacion: string; evento: string;
  estado: EstadoTarea; estado_etiqueta: string; veredicto_redes: string; metrica_titular: string; metrica_secundaria: string | null;
}
export interface ModeloDestacado { modelo: string; nombre: string; metrica: MetricaModelo; metrica_secundaria: MetricaModelo | null }
export interface TarjetaTarea {
  tarea: TareaId; orden: number; nombre: string; pregunta: string; evento: string; estado: EstadoTarea; estado_etiqueta: string;
  veredicto_redes: string; metrica: string; metrica_secundaria: string | null; variante: string; corte_k: number; etiqueta_vista: string;
  concluyente: boolean; conservado: ModeloDestacado | null; referencia: ModeloDestacado | null; n_prueba: number | null; tasa_prueba: number | null;
}
export interface ResumenTareas { disponible: boolean; generado_en: string | null; aviso: string; tareas: TarjetaTarea[]; notas: string[] }
export interface NotaTarea { tipo: "dato" | "pendiente" | "limite"; orden: number; texto: string }
export interface VistaTarea {
  variante: string; corte_k: number; etiqueta: string; principal: boolean; conservado_modelo: string | null; referencia_modelo: string | null;
  metrica_titular: string; metrica_secundaria: string | null; concluyente: boolean; pronostico_agregado: PronosticoAgregado; nota: string | null;
}
export interface ParticionTarea {
  variante: string; corte_k: number; particion: string; n: number; eventos: number | null; tasa: number | null;
  tasa_inf: number | null; tasa_sup: number | null;
}
export interface ModeloTarea {
  variante: string; corte_k: number; modelo: string; nombre: string; familia: string; escalon: number; escalon_nombre: string;
  n_evaluacion: number | null; conservado: boolean; metricas: Record<string, MetricaModelo>;
}
export interface ComparacionTarea {
  variante: string; corte_k: number; modelo_a: string; modelo_b: string; metrica: string;
  delta: number | null; ic_inf: number | null; ic_sup: number | null; veredicto: Veredicto;
}
export interface CalibracionTarea {
  variante: string; corte_k: number; modelo: string; decil: number; n: number; pocos_casos: boolean; riesgo_medio: number | null; tasa_observada: number | null;
}
export interface DetalleTarea {
  tarea: FichaTarea; aviso: string; notas: NotaTarea[]; vistas: VistaTarea[]; particiones: ParticionTarea[];
  modelos: ModeloTarea[]; comparaciones: ComparacionTarea[]; calibracion: CalibracionTarea[];
}
export interface GrupoTarea {
  categoria: string; grupo: string; nombre: string; facultad: string | null; n: number; eventos: number | null;
  observada: number | null; obs_inf: number | null; obs_sup: number | null; esperada: number | null; esp_inf: number | null;
  esp_sup: number | null; referencia: number | null; ap: number | null; roc_auc: number | null;
  /** Intervalos de 95 % (nulos cuando no se pueden calcular). */
  ap_lo: number | null; ap_hi: number | null; auc_lo: number | null; auc_hi: number | null;
  tasa_lo: number | null; tasa_hi: number | null; esperado_lo: number | null; esperado_hi: number | null;
  /** n < 10 (lo calcula el servidor). */
  pocos_casos: boolean;
}
export interface ResumenGrupoTarea {
  categoria: string; grupos_total: number | null; mae_modelo: number | null; mae_base: number | null; spearman: number | null;
}
export interface GruposTarea {
  tarea: TareaId; nivel: NivelGrupo; variante: string; corte_k: number; evento: string; pronostico_agregado: PronosticoAgregado;
  grupos: GrupoTarea[]; resumen: ResumenGrupoTarea[]; notas: string[];
}

export interface NodoMallaEjemplo { codigo: string; nombre: string | null; semestre: number; creditos: number | null }
export interface MallaEjemplo {
  cod_programa: string | null; nombre_programa: string | null; catalogo: string | null; semestre_max: number;
  nodos: NodoMallaEjemplo[]; aristas: { desde: string; hacia: string }[]; notas: string[];
}

/** Filtro de las dos vistas: una facultad o un programa, nunca ambos (el servidor responde 422); sin ninguno, toda la UCN. */
export interface FiltroVista { facultad: string | null; programa: string | null }

function paramsFiltro(f: FiltroVista): string {
  if (f.programa) return `?programa=${encodeURIComponent(f.programa)}`;
  return f.facultad ? `?facultad=${encodeURIComponent(f.facultad)}` : "";
}

function paramsTraslados(p: ParamsTraslados): string {
  const q = new URLSearchParams();
  if (p.anioDesde != null) q.set("anio_desde", String(p.anioDesde));
  if (p.anioHasta != null) q.set("anio_hasta", String(p.anioHasta));
  if (p.tipo) q.set("tipo", p.tipo);
  if (p.soloAbandono) q.set("solo_abandono", "true");
  const s = q.toString();
  return s ? "?" + s : "";
}

/** Estado de la declaración de confidencialidad (espejo de AceptacionEstado en schemas.py). */
export interface EstadoAceptacion {
  version: string; texto: string; aceptada: boolean;
}

/** Fecha de la última publicación al sitio (solo modo Pages); `respuestas` no se usa aquí. */
export interface PublicacionNeural {
  publicado_en: string;
}

async function postAceptacion(version: string): Promise<void> {
  // Modo Pages: la aceptación no se registra en el servidor (solo lectura); nunca se envía un POST.
  if (MODO_PAGES) return;
  const headers = authHeaders();
  headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_BASE_URL}/neural/aceptacion`, {
    method: "POST", headers, cache: "no-store", body: JSON.stringify({ version }),
  });
  if (!res.ok) throw await errorDeRespuesta(res);
}

// ---- Endpoints ----
export const neuralApi = {
  aceptacion: (signal?: AbortSignal) => getJson<EstadoAceptacion>("/neural/aceptacion", signal),
  aceptar: (version: string) => postAceptacion(version),
  publicacion: (signal?: AbortSignal) => getJson<PublicacionNeural>("/neural/publicacion", signal),
  programas: (signal?: AbortSignal) => getJson<ProgramaResumen[]>("/neural/programas", signal),
  cohortes: (cod: string, signal?: AbortSignal) =>
    getJson<CohortesPrograma>(`/neural/programa/${encodeURIComponent(cod)}/cohortes`, signal),
  calidad: (signal?: AbortSignal) => getJson<Calidad>("/neural/calidad", signal),
  trasladosResumen: (p: ParamsTraslados, signal?: AbortSignal) =>
    getJson<ResumenTraslados>(`/neural/traslados/resumen${paramsTraslados(p)}`, signal),
  trasladosPrograma: (cod: string, p: ParamsTraslados, signal?: AbortSignal) =>
    getJson<TrasladosPrograma>(`/neural/traslados/programa/${encodeURIComponent(cod)}${paramsTraslados(p)}`, signal),
  mallaEjemplo: (cod: string | null, semestreMax: number, signal?: AbortSignal) =>
    getJson<MallaEjemplo>(`/neural/modelos/malla-ejemplo?semestre_max=${semestreMax}${cod ? `&cod_programa=${encodeURIComponent(cod)}` : ""}`, signal),
  historico: (filtro: FiltroVista, signal?: AbortSignal) => getJson<HistoricoVista>(`/neural/historico${paramsFiltro(filtro)}`, signal),
  proyeccion: (filtro: FiltroVista, signal?: AbortSignal) => getJson<ProyeccionVista>(`/neural/proyeccion${paramsFiltro(filtro)}`, signal),
  modelosResumen: (signal?: AbortSignal) => getJson<ResumenModelos>("/neural/modelos/resumen", signal),
  modelosTareas: (signal?: AbortSignal) => getJson<ResumenTareas>("/neural/modelos/tareas", signal),
  modelosTarea: (tarea: TareaId, signal?: AbortSignal) => getJson<DetalleTarea>(`/neural/modelos/tarea/${tarea}`, signal),
  modelosGrupos: (tarea: TareaId, nivel: NivelGrupo, variante: string, corte: number, signal?: AbortSignal) =>
    getJson<GruposTarea>(
      `/neural/modelos/tarea/${tarea}/grupos?nivel=${nivel}&variante=${encodeURIComponent(variante)}&corte=${corte}`, signal),
};

// ---- Modelo visible y filtro en cascada (espejo de ModeloVisible, ConModelo y FacultadFiltro en schemas.py) ----
/** El modelo conservado detrás de un bloque o de una cohorte. `tipo` es «esperado» o «proyeccion»; `corte` ya viene en español («1.er semestre»). */
export interface ModeloVisible {
  tarea: string; tarea_nombre: string; modelo: string; modelo_nombre: string; k: number; corte: string; particion: string; tipo: string;
}
/** Un bloque con su etiqueta: `modelo` nulo sin `modelos` es un dato observado; nulo con `modelos` es un bloque de varios modelos.
 *  `modelo_no_identificado`: el documento traía un modelo que no se pudo leer; no se muestra ninguna etiqueta (y menos «Dato observado»). */
export interface ConModelo { modelo?: ModeloVisible | null; modelos?: ModeloVisible[] | null; modelo_no_identificado?: boolean }
export interface ProgramaFiltro { codigo: string; nombre: string }
export interface FacultadFiltro { facultad: string; programas: ProgramaFiltro[] }
export interface ProgramaElegido extends ProgramaFiltro { facultad: string }

// ---- «Histórico» (espejo de HistoricoVista en schemas.py): todas las cifras; los bloques de menos de 10 llevan pocos_casos ----
export interface HistSemestre {
  semestre: number; dejan: number | null; eliminados: number | null; pct_dejan: number | null; pct_eliminados: number | null;
}
export interface HistSemestres extends ConModelo {
  n: number; pocos_casos: boolean; bajas: number | null; bajas_primer_anio: number | null; pct_bajas_primer_anio: number | null; pct_bajas: number | null;
  filas: HistSemestre[];
}
export interface HistSiguieron extends ConModelo {
  n: number; pocos_casos: boolean; siguieron: number; esperados: number; pct_siguieron: number; pct_esperado: number; diferencia: number;
}
export interface HistPuntoFacultad { facultad: string; n: number; pocos_casos: boolean; pct_siguieron: number; pct_esperado: number }
export interface HistAnio {
  anio: number; n: number; pocos_casos: boolean; eliminados: number; tasa: number; parcial: boolean; esperados: number | null; tasa_esperada: number | null;
}
export interface HistCausal { grupo: string; etiqueta: string; n: number | null; pct: number | null }
export interface HistEliminados extends ConModelo {
  anios: HistAnio[]; anio_reglamento: number;
  /** Total de eliminados de pregrado por año calendario (todas las cohortes). */
  totales: { anio: number; eliminados: number }[];
  clave: { anio: number; eliminados: number } | null;
  causales: { total: number; filas: HistCausal[] } | null;
}
export interface HistAlcance extends ConModelo {
  n: number; pocos_casos: boolean; eventos: number; fraccion_apoyo: number; apoyados: number; alcanzados: number; pct_alcanzado: number;
  de_cada_10: number; al_azar_de_cada_10: number; curva: { apoyados: number; alcanzados: number }[];
}
export interface HistPerfilFila { grupo: string; etiqueta: string; n: number; pocos_casos: boolean; pct_siguieron: number | null; pct_esperado: number | null }
export interface HistPerfilDimension { dimension: string; filas: HistPerfilFila[] }
export interface HistPerfil extends ConModelo { n: number; pocos_casos: boolean; nota_asociacion: boolean; dimensiones: HistPerfilDimension[] }
export interface HistPrimerSemestreFila { reprobaciones: string; n: number; pocos_casos: boolean; pct_siguieron: number | null }
export interface HistPrimerSemestre extends ConModelo { n: number; pocos_casos: boolean; nota_asociacion: boolean; filas: HistPrimerSemestreFila[] }
export interface HistRamoFila { codigo: string; nombre: string; depto: string | null; intentos: number; reprobados: number; tasa: number; lo: number | null; hi: number | null }
export interface HistRamos extends ConModelo { desde: string; hasta: string; por_tasa: HistRamoFila[]; por_volumen: HistRamoFila[] }
export interface HistEsperadoCifras { intentos: number; observados: number; esperados: number; diferencia: number; lo: number; hi: number }
export interface HistEsperadoRamo extends HistEsperadoCifras { codigo: string; nombre: string }
export interface HistEsperadoDepto extends HistEsperadoCifras { depto: string; depto_desc: string }
export interface HistEsperadoVentana { desde: string; hasta: string; ramos: HistEsperadoRamo[]; deptos: HistEsperadoDepto[] }
export interface HistEsperado extends ConModelo { ventanas: Record<string, HistEsperadoVentana> }
export interface HistCuelloFila { codigo: string; nombre: string; reprobados: number; dependientes: number; impacto: number }
export interface HistCuellos extends ConModelo { filas: HistCuelloFila[] }
export interface HistSemestreMallaFila { semestre: number; intentos: number; reprobados: number | null; tasa: number | null }
export interface HistSemestreMalla extends ConModelo { filas: HistSemestreMallaFila[] }
export interface HistCausalPrograma { grupo: string; etiqueta: string; n: number }
export interface HistProgramaCausales { cod_programa: string | null; programa: string; total: number; pocos_casos: boolean; causales: HistCausalPrograma[] | null }
export interface HistCausalesPrograma extends ConModelo { desde: string; hasta: string; nivel: string; filas: HistProgramaCausales[] }
export interface HistTiempoFila {
  cod_programa: string; programa: string; n: number; pocos_casos: boolean; duracion_nominal_sem: number;
  pct_a_tiempo: number | null; pct_mas_1: number | null; pct_mas_2: number | null;
}
export interface HistTiempo extends ConModelo { regla_duracion: string; filas: HistTiempoFila[] }
export interface HistSenal { familia: string; etiqueta: string; peso_pct: number; caida_ap: number }
export interface HistSenalesTarea { tarea: string; k: number; modelo: string; n_muestra: number; senales: HistSenal[] }
export interface HistSenales extends ConModelo { aplica_a_poblacion?: boolean; tareas: HistSenalesTarea[] }
export interface HistEsperarComparacion {
  tarea: string; k_antes: number; k_despues: number; de_cada_10_antes: number | null; de_cada_10_despues: number | null;
}
export interface HistEsperar extends ConModelo { aplica_a_poblacion?: boolean; comparaciones: HistEsperarComparacion[]; nota_poblaciones: boolean }
export interface HistoricoVista {
  disponible: boolean; filtro: string; filtros: string[]; cohortes: Record<string, [number, number] | null>;
  /** Presente cuando el filtro es un programa. */
  programa?: ProgramaElegido | null;
  /** Las facultades con los programas que se pueden elegir en ESTA vista (la lista cambia entre Histórico y Proyecciones). */
  jerarquia?: FacultadFiltro[];
  modelos?: Record<string, ModeloVisible | ModeloVisible[] | null>;
  periodo_causales_desde: string | null; modelo_t1: string | null; modelo_t5: string | null;
  semestres: HistSemestres | null; siguieron: HistSiguieron | null; por_facultad: HistPuntoFacultad[];
  eliminados: HistEliminados | null; alcance: HistAlcance | null;
  perfil_ingreso?: HistPerfil | null; primer_semestre?: HistPrimerSemestre | null; ramos_reprobados?: HistRamos | null;
  ramos_esperado?: HistEsperado | null; cuellos_botella?: HistCuellos | null; semestre_malla?: HistSemestreMalla | null;
  causales_programa?: HistCausalesPrograma | null; tiempo_egreso?: HistTiempo | null; senales?: HistSenales | null;
  esperar_semestre?: HistEsperar | null;
  aviso: string; notas: string[];
}

// ---- «Proyecciones» (espejo de ProyeccionVista en schemas.py): proyección de los estudiantes actuales, siempre como rango ----
export interface ProyRango { esperados: number; lo: number; hi: number }
export interface ProyHito extends ProyRango { desde: string; hasta: string }
export interface ProyCohorte extends ProyRango {
  cohorte: number | string; k: number | null; modelo: ModeloVisible | null; corte: string | null; horizonte: string | null;
  horizonte_desde?: string | null; n: number; pocos_casos: boolean; sin_historial_beneficios?: number | null;
}
export interface ProyCohorteEgreso {
  cohorte: number | string; k: number | null; modelo: ModeloVisible | null; corte: string | null; horizonte: string | null; n: number; pocos_casos: boolean;
  nominal: ProyHito | null; nominal_mas_2: ProyHito | null;
}
export interface ProyContinuidad extends ProyRango, ConModelo { n: number; pocos_casos: boolean; por_cohorte: ProyCohorte[] }
export interface ProyEliminacion extends ProyRango, ConModelo {
  n: number; pocos_casos: boolean; por_cohorte: ProyCohorte[]; observados_hasta_hoy: number | null; periodo_observado: string; orientativo: boolean;
}
export interface ProyEgreso extends ConModelo {
  n: number; pocos_casos: boolean; regla: string; nominal: ProyHito | null; nominal_mas_2: ProyHito | null;
  ya_pasado_nominal: number | null; ya_pasado_nominal_mas_2: number | null; horizonte_truncado: number | null;
  por_cohorte: ProyCohorteEgreso[];
}
export interface ProyUmbral extends ConModelo {
  n: number; pocos_casos: boolean; en_umbral: number | null; a_1: number | null; a_2: number | null; lejos: number | null;
  nota_p58: boolean;
}
export interface ProyeccionVista {
  disponible: boolean; filtro: string; filtros: string[]; programa?: ProgramaElegido | null; jerarquia?: FacultadFiltro[];
  modelos?: Record<string, ModeloVisible | ModeloVisible[] | null>; corte: string | null; sin_proyeccion: { n: number } | null;
  continuidad: ProyContinuidad | null; eliminacion: ProyEliminacion | null; egreso: ProyEgreso | null; umbral: ProyUmbral | null;
  aviso: string; notas: string[];
}
