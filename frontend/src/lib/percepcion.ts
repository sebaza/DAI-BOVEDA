// Cliente del feature Percepción (dashboard filtrable de percepción de la comunidad UCN).
// Aislado: solo depende de ./session (token y usuario de la sesión de la Bóveda DAI).
import { API_BASE_URL, SESSION_TOKEN_STORAGE_KEY, USER_STORAGE_KEY } from "./session";

function authHeaders(): Headers {
  const headers = new Headers();
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function getJson<T>(path: string): Promise<T> {
  // no-store: el dashboard refleja datos vivos; sin esto el navegador cachea GETs
  // (p.ej. /filtros) y sigue mostrando una respuesta vieja tras cambiar el backend.
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error((await res.text()) || `Error ${res.status}`);
  return res.json() as Promise<T>;
}

async function sendJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers = authHeaders();
  if (body !== undefined) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method, headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error((await res.text()) || `Error ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

// ---- Quién está mirando ----
/** Lee el usuario que la Bóveda guarda en localStorage al iniciar sesión. */
function usuarioGuardado(): { is_admin?: unknown; role?: unknown; modulos?: unknown } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as { is_admin?: unknown; role?: unknown; modulos?: unknown }) : null;
  } catch {
    return null;
  }
}

/**
 * ¿La sesión actual es de un ADMINISTRADOR de la Bóveda?
 *
 * La pestaña Curación (que incluye «Revisar comentarios») muestra texto crudo de
 * comentarios y corrige el modelo: es solo de administradores.
 *
 * ⚠️ Es visibilidad, NO autorización. El gate real vive en el backend: todo
 * `/percepcion/curacion/*` responde 403 si la sesión no es de un administrador.
 * Ante cualquier duda devuelve `false`, que es el lado conservador: esconde de
 * más, nunca de menos.
 */
export function esAdmin(): boolean {
  return usuarioGuardado()?.is_admin === true;
}

/**
 * ¿La sesión actual puede ESCRIBIR en Percepción (equipo DAI o administrador)?
 *
 * El panel lo necesita para decidir qué herramientas internas MOSTRAR (Simulación):
 * quien solo viene a leer el Termómetro no tiene por qué toparse con ellas.
 *
 * Se mira el rol en el módulo `percepcion` (`modulos`, resuelto por el backend desde la
 * base de accesos); un administrador lo tiene como `admin` en todos los módulos activos.
 *
 * ⚠️ Es visibilidad, NO autorización. El gate real vive en el backend: todo
 * POST/PUT/DELETE de /percepcion responde 403 si el rol no es equipo ni admin.
 * Ante cualquier duda devuelve `false`.
 */
export function esEquipoDai(): boolean {
  const modulos = usuarioGuardado()?.modulos;
  if (!Array.isArray(modulos)) return false;
  const percepcion = modulos.find((m) => (m as { id?: unknown })?.id === "percepcion") as
    | { rol?: unknown }
    | undefined;
  return percepcion?.rol === "equipo" || percepcion?.rol === "admin";
}

// ---- Filtro global ----
export interface Filtro {
  dias: number;
  sede?: string;
  facultad?: string;
  departamento?: string;
  tema?: string;
  fechaDesde?: string; // YYYY-MM-DD - seleccion global desde la evolucion
  fechaHasta?: string; // YYYY-MM-DD - seleccion global hasta la evolucion
  // Control de peso del índice (dos sliders del dashboard):
  pesoLikes: number; // 0 = ignora likes, 1 = pondera full (intensidad continua)
  vidaMedia: number; // días; 0 = sin decaimiento temporal
}

function qs(f: Filtro, extra?: Record<string, string>): string {
  const p = new URLSearchParams({ dias: String(f.dias) });
  if (f.sede) p.set("sede", f.sede);
  if (f.facultad) p.set("facultad", f.facultad);
  if (f.departamento) p.set("departamento", f.departamento);
  if (f.tema) p.set("tema", f.tema);
  if (f.fechaDesde) p.set("fecha_desde", f.fechaDesde);
  if (f.fechaHasta) p.set("fecha_hasta", f.fechaHasta);
  p.set("peso_likes", String(f.pesoLikes));
  p.set("vida_media", String(f.vidaMedia));
  for (const [k, v] of Object.entries(extra ?? {})) p.set(k, v);
  return p.toString();
}

// ---- Tipos (espejo de app/services/percepcion/schemas.py) ----
export interface Distribucion {
  positivo: number;
  neutral: number;
  negativo: number;
}

export interface ResumenPercepcion {
  indice_actual: number | null;
  indice_promedio: number | null;
  tendencia: number | null;
  n_comentarios: number;
  confianza_promedio: number | null;
  distribucion: Distribucion;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  hay_datos: boolean;
}

export interface PuntoEvolucion {
  fecha: string;
  indice: number | null;
  confianza: number | null;
  n_comentarios: number;
  /** Viene de la deteccion SEMANAL: se dibuja suave y se detecta crudo. Cada dia
   *  hereda el veredicto de SU semana, asi el tramo anomalo se ve como tramo. */
  es_anomalia: boolean;
  severidad: number;      // 0..1
  motivos: string[];      // "terminos" | "indice" | "negatividad"
}

export interface SerieEvolucion {
  nivel: string;
  dimension: string | null;
  puntos: PuntoEvolucion[];
}

export interface UnidadComparacion {
  nombre: string;
  indice_promedio: number | null;
  n_comentarios: number;
  confianza_promedio: number | null;
}

export interface ComparacionUnidades {
  nivel: string;
  unidades: UnidadComparacion[];
}

export interface TemaItem {
  tema: string;
  etiqueta: string;
  indice_promedio: number | null;
  confianza_promedio: number | null;
  n_comentarios: number;
  n_pos: number;
  n_neu: number;
  n_neg: number;
}

export interface ComparacionTemas {
  temas: TemaItem[];
}

export interface EmocionItem {
  emocion: string;
  etiqueta: string;
  n: number;
}

export interface EmocionesResponse {
  items: EmocionItem[];
}

export interface EventoItem {
  id?: number | null;          // presente en el ABM; ausente en el overlay del gráfico
  nombre: string;
  tipo: string;
  tipo_label?: string | null;
  fecha_inicio: string;
  fecha_fin: string;
  descripcion?: string | null;
  ambito: string | null;
  /**
   * confirmado | estimado | planificado. Ausente en eventos cargados a mano antes de
   * que existiera la columna; se lee como `estimado`, que es lo conservador.
   * Los `estimado` NO sirven para medir duración ni velocidad de recuperación.
   */
  confianza?: string | null;
}

export interface EventosResponse {
  items: EventoItem[];
}

export interface TipoEventoOpcion {
  tipo: string;
  etiqueta: string;
}

// Alta/edición de una marca de contexto (fecha_fin vacía = evento de un día).
export interface EventoPayload {
  nombre: string;
  tipo: string;
  fecha_inicio: string;
  fecha_fin?: string | null;
  descripcion?: string | null;
  ambito?: string | null;
}

/** Una SEMANA que se aparto de su historia reciente. `fecha` es el LUNES: la
 *  unidad de deteccion es la semana, no el dia (el corpus tiene mediana de 5
 *  comentarios diarios y un z diario es puro ruido). */
/** Una publicacion y cuanto de la conversacion del periodo concentra.
 *
 *  Existe porque en las seis caidas que reviso la auditoria de sept-2026, la
 *  explicacion salio siempre del mismo lugar: que publicacion juntaba los
 *  comentarios. Caso testigo: Fiestas Patrias 2025, donde DOS publicaciones del
 *  mismo sorteo juntaban el 88,8 % de la muestra con indice 50,5. */
export interface PublicacionDominante {
  publicacion_id: number;
  cuenta: string | null;
  cuenta_tipo: string | null;
  n_comentarios: number;
  /** Cuanto de la muestra del periodo es ESTA publicacion. */
  pct_del_periodo: number;
  indice: number | null;
  pct_neg: number | null;
  desde: string | null;
  hasta: string | null;
}

export interface PublicacionesDominantesResponse {
  items: PublicacionDominante[];
  n_comentarios: number;
  n_publicaciones: number;
  /** Proporcion que junta la publicacion MAS grande. Por encima de ~40 % el
   *  promedio del periodo describe a esa publicacion, no a la comunidad. */
  concentracion: number | null;
}

export interface AnomaliaItem {
  /** Lunes de la QUINCENA. La unidad de deteccion son 2 semanas, no una: medido
   *  sobre los 8 episodios del calendario, la quincena enciende en los 5 evaluables
   *  contra 4 de la semana, y con la mitad de falsas alarmas. */
  fecha: string;
  fecha_fin: string | null;   // ultimo dia del bloque, para mostrar "del X al Y"
  nivel: string;
  dimension: string | null;
  indice: number | null;
  z_score: number | null;
  motivos: string[];        // por que se marco; sin esto la alerta no se puede accionar
  severidad: number;        // 0..1, graduada: no todo lo marcado pesa igual
  z_indice: number | null;
  z_pct_neg: number | null;
  pct_neg: number | null;
  n_comentarios: number;
  n_terminos: number;       // menciones criticas serias de la semana
  n_terminos_neg: number;   // de esas, las negativas (el discriminante)
  /** Los dos niveles. `severidad` dice CUANTO se aparto la semana; `nivel_alerta`
   *  dice QUE HACER, y son cosas distintas:
   *    atencion  cubre  — %neg alto. 2 de 5 episodios, para MIRAR la semana.
   *    alerta    acierta — alguien nombra paro/toma/asamblea. Para AVISAR.
   *  Medido sobre los 4 anos reales: entre los dos anticipan 4 de los 5 episodios
   *  evaluables con 34 dias de mediana. El INDICE no enciende ninguno — durante un
   *  conflicto recibe apoyo y reclamo en el mismo post y el promedio los cancela. */
  nivel_alerta: "alerta" | "atencion" | null;
  /** Horizonte MEDIDO del nivel, no una prediccion de esta semana. Sin el, "hay una
   *  alerta" no se puede accionar: lo que decide actuar es "suele avisar con un mes". */
  lead_esperado_dias: number | null;
  lead_rango_dias: [number, number] | null;
  cobertura_medida: [number, number] | null;   // [detectados, evaluables]
}

/** Como esta configurada la deteccion, y que rendimiento se MIDIO con esa config.
 *
 *  Viaja con los datos porque `unidad_semanas` es ajustable por entorno y cambia lo
 *  que se ve: sin declararla, dos personas con distinta configuracion leen numeros
 *  distintos y ninguna sabe por que. `medicion` es null cuando la unidad activa no
 *  tiene medicion propia — solo se midieron 1 y 2 semanas—, y en ese caso el panel
 *  no debe prometer ningun rendimiento. */
export interface AnomaliasConfig {
  unidad_semanas: number;
  baseline_semanas: number;
  min_comentarios: number;
  medicion: {
    detecta: number;
    evaluables: number;
    falsas_anio: number;
    precision: number;      // 0..1
    lead_mediano: number;   // dias
  } | null;
}

export interface AnomaliasResponse {
  items: AnomaliaItem[];
  config?: AnomaliasConfig;
}

export interface ComentarioReciente {
  id: number;
  fecha: string;
  sentimiento: string; // POS | NEU | NEG
  sentimiento_label: string;
  neto: number;
  n_likes: number;
  tema: string | null;
  tema_label: string | null;
  emocion: string | null;
  emocion_label: string | null;
  unidad: string | null;
  cuenta: string | null;
  cuenta_tipo: string | null;
  impacto: number;
}

export interface ComentariosResponse {
  items: ComentarioReciente[];
}

export interface ConcentracionTema {
  tema: string;
  etiqueta: string;
  n: number;
  /** Gini de la prevalencia. NO se muestra: viaja sólo para poder auditarlo. */
  gini: number;
  /** El mismo dato en palabras: «Concentrado en una unidad», etc. */
  reparto: string;
  concentrado: boolean;
  unidad_top: string;
  /** % de los comentarios de esa unidad que son de este tema. */
  prevalencia_top: number;
  /** Lo mismo, promediado entre las unidades. La comparación ES la lectura. */
  prevalencia_media: number;
  veces_sobre_promedio: number | null;
  unidades_con_presencia: number;
}

/** ¿Cada tema es de una unidad o de toda la universidad?
 *
 * `cobertura_pct` NO es decoración: sólo un tercio de los comentarios tiene
 * facultad —las cuentas de más volumen son agrupaciones, no unidades— así que esto
 * describe la conversación DE LAS UNIDADES y hay que decirlo en pantalla. */
export interface ConcentracionResponse {
  hay_datos: boolean;
  motivo: string | null;
  nivel: string;
  items: ConcentracionTema[];
  unidades: number;
  n_comentarios: number;
  cobertura_pct: number;
  minimo_por_unidad: number;
  fecha_desde: string | null;
  fecha_hasta: string | null;
}

export interface PosturaTramo {
  postura: string;
  etiqueta: string;
  n: number;
  pct: number;
}

/** Postura institucional: si el comentario favorece o perjudica a la UCN.
 *
 * NO es el sentimiento. El sentimiento es el TONO; la postura es el efecto para la
 * institución. «¿Paro? 😍» tiene tono positivo y postura adversa; «qué lindo el
 * perrito» tiene tono positivo y postura neutral. Medido: la regla que sale del
 * tono solo acierta 66,7 %; mirando además el tema, 80,7 %. */
export interface PosturaInstitucionalResponse {
  hay_datos: boolean;
  n_comentarios: number;
  distribucion: PosturaTramo[];
  temas_adversos: { tema: string; etiqueta: string; n: number; pct: number }[];
  fecha_desde: string | null;
  fecha_hasta: string | null;
}

export interface ColaScoring {
  items: ComentarioScoring[];
  orden: string;
  /** Comentarios con la revisión TERMINADA (4 campos + tema vigente). */
  revisados: number;
  /** Los que faltan sobre el corpus entero. */
  pendientes: number;
}

export interface ComentariosFiltro {
  sentimiento?: string; // POS | NEU | NEG
  emocion?: string;     // joy | anger | ...
  fechaDesde?: string;  // YYYY-MM-DD — día puntual o inicio de rango (ignora la ventana)
  fechaHasta?: string;  // YYYY-MM-DD — fin de rango (inclusive)
  incluirNeutrales?: boolean; // al leer un día/rango: mostrar TODO lo dicho (incl. neutrales)
}

export interface TemaOpcion {
  tema: string;
  etiqueta: string;
}

export interface FiltrosResponse {
  sedes: string[];
  facultades: string[];
  departamentos: string[];
  temas: TemaOpcion[];
  fecha_min: string | null;
  fecha_max: string | null;
  dias_span: number; // antigüedad del comentario más viejo (máx del slider de rango)
}

// ---- Curación manual de temas ----
export interface PublicacionCurar {
  id: number;
  caption: string;
  cuenta: string | null;
  n_comentarios: number;
  n_otros: number;
}

export interface ComentarioCurar {
  id: number;
  texto: string;
  fecha: string;
  sentimiento: string;
  caption: string;
  cuenta: string | null;
}

export interface TemaAsignable {
  tema: string;
  etiqueta: string;
}

export interface AsignarTemaResponse {
  comentarios_actualizados: number;
  hechos: number;
}

// ---- Corrección de sentimiento / emoción ----
export interface ComentarioScoring {
  id: number;
  texto: string;
  fecha: string;
  sentimiento: string;
  sentimiento_label: string;
  emocion: string | null;
  emocion_label: string | null;
  tema: string | null;
  // Confianza del clasificador de temas. Mediana del corpus 0,45.
  tema_confianza: number;
  cuenta: string | null;
  // El post al que responde. La mediana del corpus es de 3 palabras: sin saber a
  // qué contesta, "no yapo" no se puede clasificar.
  caption: string;
  // Ventaja de la clase ganadora sobre la segunda. Chica = el modelo dudaba.
  margen: number;
  prob_pos: number;
  prob_neu: number;
  prob_neg: number;
  // Por qué sigue en la cola pese a estar anotado (null = nunca se revisó). Se
  // muestra en pantalla: sin el motivo, una cola que devuelve caras conocidas se
  // lee como que está rota.
  motivo_pendiente: string | null;
}

// De qué cola sale el caso a revisar. NO es cosmético: `duda` dirige al revisor a
// donde el modelo es peor (sirve para corregir, no para medir) y solo `aleatorio`
// permite estimar la calidad real.
export type OrdenScoring =
  | "duda" | "reciente" | "aleatorio" | "adversos" | "estratificado";

export interface OpcionValor {
  valor: string;
  etiqueta: string;
}

export interface OpcionesScoring {
  sentimientos: OpcionValor[];
  emociones: OpcionValor[];
  // Postura hacia la institución. NO es el tono: «Paro?😍» es POS y adverso.
  posturas: OpcionValor[];
}

export interface CorregirResponse {
  cambiado: boolean;
  hechos: number;
}

// ---- Calidad del modelo (A1) ----
export interface CalidadCelda {
  modelo: string;
  modelo_label: string;
  revisor: string;
  revisor_label: string;
  n: number;
  acuerdo: boolean;
}

export interface CalidadMargen {
  bucket: string;
  n: number;
  cambios: number;
}

export interface CalidadSesgo {
  clase: string;
  clase_label: string;
  n: number;
  de: number;
  proporcion: number;
  alerta: boolean;
}

export interface CalidadResumen {
  n: number;
  confirmaciones: number;
  cambios: number;
  // null (no 0) cuando no hay confirmaciones: el acuerdo es DESCONOCIDO, no cero.
  acuerdo: number | null;
  acuerdo_motivo: string | null;
  kappa: number | null;
  matriz: CalidadCelda[];
  sesgo_direccional: CalidadSesgo | null;
  por_margen: CalidadMargen[];
}

export interface CalidadGrupo extends CalidadResumen {
  clave: string;
}

export interface CalidadEstimacion extends CalidadResumen {
  suficiente: boolean;
}

export interface CalidadCampo extends CalidadResumen {
  // La ÚNICA lectura válida: humano + muestra aleatoria. El resto del campo mezcla
  // agente con humano y colas dirigidas con aleatorias.
  estimacion: CalidadEstimacion | null;
  por_autor: CalidadGrupo[];
  por_muestra: CalidadGrupo[];
  con_snapshot: number;
}

export interface CalidadAviso {
  nivel: "critico" | "atencion" | string;
  titulo: string;
  detalle: string;
}

export interface CalidadResponse {
  total_comentarios: number;
  comentarios_revisados: number;
  cobertura: number;
  campos: Record<string, CalidadCampo>;
  avisos: CalidadAviso[];
}

// ---- D · Leave-one-out word impacts ----
export interface PalabraImpacto {
  texto: string;
  // Cuánto MÁS se parecerían los dos períodos sin esta palabra. Alto = es la
  // responsable de que hayan cambiado.
  impacto: number;
  n_actual: number;
  n_previo: number;
  delta: number;
}

export interface ImpactoPalabrasResponse {
  hay_datos: boolean;
  similitud: number | null;
  vocabulario: number;
  periodo_actual: string[] | null;
  periodo_previo: string[] | null;
  palabras: PalabraImpacto[];
  motivo: string | null;
}

export interface CorreccionItem {
  comentario_id: number;
  campo: string;
  valor_original: string | null;
  valor_nuevo: string;
  justificacion: string | null;
  autor: string | null;
  autor_tipo: string | null;
  origen_muestra: string | null;
  confirmado: boolean | null;
}

// ---- Síntesis (capa 1: de qué hablan, con qué emoción, en qué área) ----
// "peor" = lo peor hablado primero (lectura directiva por defecto). En ambos
// órdenes las filas SIN evidencia suficiente caen al fondo: si no, una unidad de
// 1 comentario con índice pésimo encabezaría el listado.
export type OrdenSintesis = "peor" | "volumen";

export interface EmocionDominante {
  emocion: string;
  etiqueta: string;
  n: number;
  pct: number;          // % dentro de su tema/área, no del total
}

export interface AreaBreve {
  nombre: string;
  n_comentarios: number;
}

export interface TemaDominante {
  tema: string;
  etiqueta: string;
  n_comentarios: number;
}

/** Una palabra del vocabulario con su carga.
 *
 *  El vocabulario se valida sobre TODO el período y NO por área: es lo unico que
 *  separa las palabras reales de los handles de personas que el tokenizador no
 *  atrapa (letras puras, sin "_" ni digitos). Se probaron heuristicas por
 *  publicaciones y por autores distintos y las dos fallaron. */
export interface PalabraDestacada {
  texto: string;
  n: number;          // en cuantos COMENTARIOS aparece
  n_pos: number;
  n_neu: number;
  n_neg: number;
  pct_neg: number;
}

export interface MesSerie {
  mes: string;        // YYYY-MM-01
  indice: number | null;
  n_comentarios: number;
}

/** La emocion que mas gano terreno contra el periodo anterior. Se compara el
 *  SHARE y no el conteo: si el volumen se duplica, todas "crecen". */
export interface EmocionCambio {
  emocion: string;
  etiqueta: string;
  n: number;
  pct: number;
  pct_anterior: number;
  delta_pp: number;
  es_nueva: boolean;
}

/** Lo que el Resumen muestra de un vistazo. Son tres cosas que NO estan en
 *  ninguna otra pestaña, para no repetir. */
export interface DestacadosResponse {
  palabras: PalabraDestacada[];
  serie_mensual: MesSerie[];
  emocion_cambio: EmocionCambio | null;
  vocabulario_min: number;
  periodo_anterior: { desde: string; hasta: string } | null;
}

export interface SintesisTema {
  tema: string;
  etiqueta: string;
  n_comentarios: number;
  share_pct: number;
  indice: number | null;
  confianza: number;
  // n < n_min_evidencia ⇒ el índice es anecdótico. La UI DEBE marcarlo: sin esto
  // una fila de 7 comentarios se lee igual que una de 88.
  evidencia_suficiente: boolean;
  n_pos: number;
  n_neu: number;
  n_neg: number;
  emocion_dominante: EmocionDominante | null;
  areas_top: AreaBreve[];
  palabras_top: PalabraDestacada[];   // que se DICE literalmente en este tema
}

export interface SintesisArea {
  nombre: string;
  n_comentarios: number;
  share_pct: number;
  indice: number | null;
  confianza: number;
  evidencia_suficiente: boolean;
  n_pos: number;
  n_neu: number;
  n_neg: number;
  tema_dominante: TemaDominante | null;
  emocion_dominante: EmocionDominante | null;
  /** Reparto favorable / sin postura / adverso. null = la unidad no tiene datos. */
  postura: PosturaTramo[] | null;
  // Vacio cuando ninguna palabra alcanza el minimo GLOBAL o el LOCAL: es el
  // resguardo que impide publicar el nombre de una persona en un area chica.
  palabras_top: PalabraDestacada[];
}

/** Un tema que SE MOVIÓ contra el período anterior. Reemplaza a los "focos":
 *  con umbral fijo (índice < 50) el bloque quedaba vacío tras corregir la
 *  clasificación, y "lo más hablado" repite siempre los mismos temas. */
export interface SintesisCambio {
  tema: string;
  etiqueta: string;
  n_comentarios: number;
  n_anterior: number;
  delta_volumen_pct: number | null;   // null = sin base previa (tema nuevo)
  indice: number | null;
  indice_anterior: number | null;
  delta_indice: number | null;
  evidencia_suficiente: boolean;
  emocion_dominante: EmocionDominante | null;
  es_nuevo: boolean;
}

export interface SintesisResponse {
  hay_datos: boolean;
  periodo: { desde: string; hasta: string; dias: number } | null;
  global: {
    n_comentarios: number;
    indice: number | null;
    confianza: number;
    distribucion: Distribucion;
    emocion_dominante: EmocionDominante | null;
  } | null;
  nivel_area: string;
  orden: OrdenSintesis;
  tema_filtrado: string | null;   // el filtro global de tema aplica a áreas/focos
  // Qué parte de la conversación tiene área atribuida: las áreas suman MENOS que
  // el total (los hechos sin la dimensión se descartan del agrupado).
  cobertura_area: { n_con_area: number; n_total: number; pct: number };
  temas: SintesisTema[];
  areas: SintesisArea[];
  cambios: SintesisCambio[];
  periodo_anterior: { desde: string; hasta: string } | null;
  n_min_evidencia: number;
}

// ---- Nube de palabras ----
export interface PalabraNube {
  texto: string;
  n: number;              // en cuántos COMENTARIOS aparece (no cuántas veces)
  pos: number;
  neu: number;
  neg: number;
  sentimiento_dominante: "POS" | "NEU" | "NEG";
  tema_dominante: string | null;
  tema_etiqueta: string | null;
  emocion_dominante: string | null;
  emocion_etiqueta: string | null;
  variantes: string[];    // otras formas fundidas acá (p. ej. "curso" en "cursos")
}

export interface NubeResponse {
  hay_datos: boolean;
  palabras: PalabraNube[];
  n_comentarios: number;
  n_palabras_unicas: number;
  min_frecuencia: number;
  agrupar_variantes: boolean;
  n_variantes_agrupadas: number;
  truncado: boolean;
  periodo: { desde: string | null; hasta: string | null } | null;
}

// ---- Terminos bajo vigilancia (lexico de conflicto) ----
// Complementa a los TEMAS (8 cajas del clasificador) y a la NUBE (vocabulario
// crudo): cuenta un lexico institucional FIJO y auditable —paro, toma, petitorio,
// asamblea, movilizacion— que hoy queda repartido entre "academico",
// "organizacion estudiantil" y "otros", y por eso no se ve.
// NO interviene en el indice: la formula canonica queda intacta.
export interface TerminoTema {
  tema: string;
  etiqueta: string;
  n: number;
}

export interface TerminoSemana {
  semana: string;   // YYYY-MM-DD, lunes
  n: number;
  n_neg: number;
}

/** Comentario que disparo la familia. SIN autor: el hash nunca sale del backend. */
export interface TerminoEjemplo {
  fecha: string;
  sentimiento: string;
  sentimiento_label: string;
  emocion: string | null;
  emocion_label: string | null;
  tema: string | null;
  tema_label: string | null;
}

export interface TerminoFamilia {
  clave: string;
  etiqueta: string;
  n_menciones: number;
  // El humor se SEPARA, no se descarta: el modelo detecta ironia mal y un
  // "jajaja paro" puede ser sarcasmo amargo. Fuera del calculo, dentro de la vista.
  n_serio: number;
  n_humor: number;
  n_pos: number;
  n_neu: number;
  n_neg: number;
  indice: number | null;      // de los SERIOS: con que animo se habla de esto
  share_pct: number;
  temas: TerminoTema[];       // donde se esta hablando de esto
  primera_mencion: string | null;
  ultima_mencion: string | null;
  n_anterior: number;
  delta_menciones_pct: number | null;   // null = sin base previa
  es_nuevo: boolean;
  serie_semanal: TerminoSemana[];
  ejemplos: TerminoEjemplo[];
}

export interface TerminosResponse {
  hay_datos: boolean;
  periodo: { desde: string; hasta: string } | null;
  global: {
    n_comentarios: number;
    n_con_termino: number;
    pct: number;
    n_humor: number;
  } | null;
  familias: TerminoFamilia[];
  periodo_anterior: { desde: string; hasta: string } | null;
}

// ---- Resumen semanal por LLM ----
export type NivelResumenSemanal = "campus" | "facultad" | "global";

export interface CaracteristicaComunicacion {
  rasgo: string;
  etiqueta: string;
  n_con: number;
  n_sin: number;
  tasa_con: number;
  tasa_sin: number;
  efecto_crudo: number;
  margen: number;
  /** El que vale: cada cuenta comparada consigo misma. */
  efecto_intra: number | null;
  cuentas_comparables: number;
  cuentas_a_favor: number;
  p_signos: number | null;
  /** Supera las DOS pruebas: margen de error y control intra-cuenta. */
  solido: boolean;
}

export interface ComunicacionResponse {
  publicaciones: number;
  con_conversacion: number;
  tasa_base: number;
  min_por_lado: number;
  caracteristicas: CaracteristicaComunicacion[];
  avisos: string[];
}

export interface VentanaShock {
  etiqueta: string;
  desde: string;
  hasta: string;
  n: number;
  indice: number | null;
}

export interface EpisodioShock {
  nombre: string;
  tipo: string;
  desde: string;
  hasta: string | null;
  dias: number | null;
  ambito: string | null;
  confianza: string;
  /** Toma y paro de un mismo conflicto van fusionados; acá quedan las facetas. */
  componentes: string[];
  ventanas: VentanaShock[];
  indice_previo: number | null;
  indice_durante: number | null;
  caida: number | null;
  /** La misma comparación con la MEZCLA DE CUENTAS FIJA: entre la ventana previa y la
   *  del conflicto cambia quién comenta, no solo qué opina. En el paro grande, dos
   *  tercios de la caída cruda eran composición. */
  caida_estandarizada: number | null;
  /** caida − caida_estandarizada: cuánto de la caída fue puro cambio de mezcla. */
  composicion: number | null;
  /** Índice de la ventana con el peso por TEMA. Es el principal; `indice_durante`
   *  queda de referencia (mismo universo y mismo recorte por sede, sin pesos). */
  indice_ponderado: number | null;
  /** Solo canales donde la crítica existe: 19 cuentas nunca recibieron un negativo
   *  en cuatro años y su peso casi se duplica durante los conflictos. */
  indice_critico: number | null;
  /** Volumen crudo de adversos. Delata los episodios flacos: «+19,0» con 2 adversos
   *  de 47 no midió el conflicto, midió posteo normal. */
  n_adversos: number | null;
  pct_adversos: number | null;
  /** suficiente | parcial | insuficiente */
  evidencia: string;
  recuperado_en_semanas: number | null;
  /** «No recuperó» y «no medible» son distintos: este campo dice cuál de los dos. */
  motivo_recuperacion: string | null;
}

export interface ShockResponse {
  episodios: EpisodioShock[];
  total: number;
  medibles: number;
  n_min_por_semana: number;
  semanas_sosten: number;
  /** Solo con más de un caso medible. Con uno, un "rango" es ese caso disfrazado. */
  caida_rango: number[] | null;
  avisos: string[];
}

export interface BaselineModelo {
  nombre: string;
  descripcion: string;
  mae: number;
  rmse: number;
  n_predicciones: number;
  /** El modelo ya tocó el ruido del propio dato: no se le puede pedir más. */
  indistinguible_del_techo: boolean;
  /** Erra más que decir siempre el promedio histórico. */
  peor_que_no_hacer_nada: boolean;
}

export interface RasgoAplicado {
  rasgo: string;
  etiqueta: string;
  efecto?: number | null;
  motivo?: string | null;
}

export interface RasgoElegible {
  rasgo: string;
  etiqueta: string;
  solido: boolean;
  efecto_intra?: number | null;
}

export interface EnsayoResponse {
  /** null sin publicaciones: una probabilidad inventada es peor que ninguna. */
  probabilidad: number | null;
  /**
   * De dónde salió el número, y NO valen lo mismo:
   * "observado" = tasa real de las publicaciones con esa misma combinación (dato
   * contado); "estimado" = tasa base + efectos sumados (supone que no interactúan);
   * "base" = ningún rasgo movió el número.
   */
  fuente: string;
  margen: number;
  tasa_base: number;
  n_observado: number;
  publicaciones: number;
  aplicados: RasgoAplicado[];
  /** Elegidos que NO movieron el número: su efecto no se distingue del azar. */
  ignorados: RasgoAplicado[];
  rasgos: RasgoElegible[];
  avisos: string[];
}

export interface BaselinesResponse {
  semanas_con_datos: number;
  evaluadas: number;
  n_min_semana: number;
  /**
   * Sobre qué serie corrió el backtesting: "ponderada" (la del tablero, por defecto)
   * o "canonica" (conteos crudos). Se declara porque los MAE de una y otra NO son
   * comparables: distinta escala, distinto ruido, distinto techo.
   */
  serie: string;
  /** Piso de ruido de muestreo. Ningún modelo puede bajar de ahí. */
  error_irreducible: number | null;
  /** Lo que erraría decir siempre el promedio. */
  desvio_serie: number | null;
  modelos: BaselineModelo[];
  avisos: string[];
}

export interface UnidadVolatilidad {
  nombre: string;
  semanas: number;
  n_mediana: number;
  indice_medio: number | null;
  sd_observada: number;
  sd_ruido: number;
  /** null = la variación no supera al ruido. NO significa estable: significa que no se puede afirmar. */
  volatilidad_real: number | null;
  ratio: number | null;
  evidencia_suficiente: boolean;
}

export interface VolatilidadResponse {
  nivel: string;
  n_min_semana: number;
  min_semanas: number;
  unidades: UnidadVolatilidad[];
  sin_evidencia: string[];
  avisos: string[];
}

export interface SemanaDisponible {
  /** Lunes de la semana, YYYY-MM-DD. */
  semana: string;
  n_comentarios: number;
  /** false = ir ahí dispara una generación con costo. */
  tiene_resumen: boolean;
}

export interface ResumenSemanalResponse {
  hay_datos: boolean;
  texto: string | null;
  periodo: { desde: string; hasta: string } | null;
  alcance: { nivel: string; dimension: string | null; etiqueta: string };
  n_comentarios: number;
  indice: number | null;
  /** true = vino del caché: los datos no cambiaron y NO se llamó al modelo. */
  desde_cache: boolean;
  /** true = hay datos más nuevos que este texto y no se pudo regenerar. */
  desactualizado: boolean;
  /** Cifras del texto que no salen de los datos de la semana. Vacío = auditable. */
  cifras_dudosas: string[];
  aviso: string | null;
  modelo: string | null;
  costo_usd: number | null;
  generado_en: string | null;
}

// ---- API ----
export const percepcionApi = {
  filtros: (): Promise<FiltrosResponse> => getJson<FiltrosResponse>("/percepcion/filtros"),

  resumen: (f: Filtro): Promise<ResumenPercepcion> =>
    getJson<ResumenPercepcion>(`/percepcion/resumen?${qs(f)}`),

  evolucion: (f: Filtro): Promise<SerieEvolucion> =>
    getJson<SerieEvolucion>(`/percepcion/evolucion?${qs(f)}`),

  porTema: (f: Filtro): Promise<ComparacionTemas> =>
    getJson<ComparacionTemas>(`/percepcion/por-tema?${qs(f)}`),

  porUnidad: (nivel: "facultad" | "campus" | "departamento", f: Filtro): Promise<ComparacionUnidades> =>
    getJson<ComparacionUnidades>(`/percepcion/por-unidad?${qs(f, { nivel })}`),

  emociones: (f: Filtro): Promise<EmocionesResponse> =>
    getJson<EmocionesResponse>(`/percepcion/emociones?${qs(f)}`),

  /**
   * Resumen narrativo de una semana. NO usa el filtro global a propósito: es una
   * lectura de PERÍODO CERRADO (la semana completa), no de la ventana móvil del
   * tablero — si respetara `dias`, el texto cacheado dejaría de corresponder al
   * período que dice cubrir.
   *
   * El backend solo llama al modelo si los datos cambiaron; `forzar` es la única
   * forma de volver a pagar por los mismos datos.
   */
  resumenSemanal: (
    nivel: NivelResumenSemanal,
    dimension: string | null,
    semana?: string,
    forzar = false,
  ): Promise<ResumenSemanalResponse> => {
    const p = new URLSearchParams({ nivel });
    if (dimension) p.set("dimension", dimension);
    if (semana) p.set("semana", semana);
    if (forzar) p.set("forzar", "true");
    return getJson<ResumenSemanalResponse>(`/percepcion/resumen-semanal?${p.toString()}`);
  },

  /**
   * La vara de la fase 1: backtesting de los baselines triviales. No es un
   * pronóstico para consumir, es el piso que un modelo tiene que superar.
   */
  baselines: (): Promise<BaselinesResponse> =>
    getJson<BaselinesResponse>("/percepcion/baselines"),

  /**
   * C · respuesta a shock. Devuelve CASOS, no un promedio: la mayoría de los
   * episodios no tiene corpus alrededor con el cual medir nada.
   */
  /**
   * B · qué rasgos de una publicación se asocian con generar conversación. Cada uno
   * viene con su efecto crudo y con el controlado por cuenta; solo el segundo vale.
   */
  comunicacion: (): Promise<ComunicacionResponse> =>
    getJson<ComunicacionResponse>("/percepcion/comunicacion"),

  /**
   * B · El ENSAYO: «¿una publicación así va a generar conversación?».
   *
   * Devuelve `fuente` para poder decir en pantalla de dónde salió el número:
   * "observado" es la tasa contada de las publicaciones con esa misma combinación
   * y "estimado" es una suma de efectos. No valen lo mismo y el panel lo declara.
   */
  ensayo: (rasgos: string[]): Promise<EnsayoResponse> => {
    const p = new URLSearchParams();
    for (const r of rasgos) p.append("rasgos", r);
    return getJson<EnsayoResponse>(`/percepcion/ensayo?${p.toString()}`);
  },

  shock: (soloConfirmados = false): Promise<ShockResponse> =>
    getJson<ShockResponse>(
      `/percepcion/shock${soloConfirmados ? "?solo_confirmados=true" : ""}`,
    ),

  /**
   * Volatilidad estructural por unidad. NO usa el filtro global: la volatilidad es
   * una propiedad de la serie completa, no de una ventana de 30 días.
   */
  volatilidad: (
    nivel: "campus" | "facultad" | "departamento" = "facultad",
  ): Promise<VolatilidadResponse> =>
    getJson<VolatilidadResponse>(`/percepcion/volatilidad?nivel=${nivel}`),

  /**
   * Semanas navegables (solo las que tienen datos), de la más nueva a la más vieja.
   * Lectura pura: no gasta tokens.
   */
  semanasResumen: (
    nivel: NivelResumenSemanal = "global",
    dimension: string | null = null,
    limite = 52,
  ): Promise<{ semanas: SemanaDisponible[] }> => {
    const p = new URLSearchParams({ nivel, limite: String(limite) });
    if (dimension) p.set("dimension", dimension);
    return getJson<{ semanas: SemanaDisponible[] }>(
      `/percepcion/resumen-semanal/semanas?${p.toString()}`,
    );
  },

  // Capa 1 del resumen ejecutivo: trae los DOS cortes (temas y áreas) + focos en
  // una sola llamada, para no cruzar N endpoints en el cliente.
  sintesis: (
    nivel: "facultad" | "campus" | "departamento",
    orden: OrdenSintesis,
    f: Filtro,
  ): Promise<SintesisResponse> =>
    getJson<SintesisResponse>(`/percepcion/sintesis?${qs(f, { nivel, orden })}`),

  nube: (
    f: Filtro,
    limite = 120,
    minFrecuencia = 2,
    excluir: string[] = [],
    agruparVariantes = true,
  ): Promise<NubeResponse> => {
    const extra: Record<string, string> = {
      limite: String(limite),
      min_frecuencia: String(minFrecuencia),
      agrupar_variantes: String(agruparVariantes),
    };
    if (excluir.length > 0) extra.excluir = excluir.join(",");
    return getJson<NubeResponse>(`/percepcion/nube?${qs(f, extra)}`);
  },

  destacados: (f: Filtro): Promise<DestacadosResponse> =>
    getJson<DestacadosResponse>(`/percepcion/destacados?${qs(f)}`),

  terminos: (f: Filtro): Promise<TerminosResponse> =>
    getJson<TerminosResponse>(`/percepcion/terminos?${qs(f)}`),

  eventos: (dias = 120): Promise<EventosResponse> =>
    getJson<EventosResponse>(`/percepcion/eventos?dias=${dias}`),

  // ---- ABM de marcas de contexto ----
  eventosTodos: (): Promise<EventosResponse> =>
    getJson<EventosResponse>("/percepcion/eventos/todos"),
  eventosTipos: (): Promise<{ items: TipoEventoOpcion[] }> =>
    getJson<{ items: TipoEventoOpcion[] }>("/percepcion/eventos/tipos"),
  crearEvento: (payload: EventoPayload): Promise<EventoItem> =>
    postJson<EventoItem>("/percepcion/eventos", payload),
  actualizarEvento: (id: number, payload: EventoPayload): Promise<EventoItem> =>
    sendJson<EventoItem>("PUT", `/percepcion/eventos/${id}`, payload),
  eliminarEvento: (id: number): Promise<{ eliminado: boolean; id: number }> =>
    sendJson<{ eliminado: boolean; id: number }>("DELETE", `/percepcion/eventos/${id}`),

  publicacionesDominantes: (f: Filtro, limite = 10): Promise<PublicacionesDominantesResponse> =>
    getJson<PublicacionesDominantesResponse>(
      `/percepcion/publicaciones-dominantes?${qs(f, { limite: String(limite) })}`),
  anomalias: (f: Filtro): Promise<AnomaliasResponse> =>
    getJson<AnomaliasResponse>(`/percepcion/anomalias?${qs(f)}`),

  comentarios: (f: Filtro, limite = 20, cf: ComentariosFiltro = {}): Promise<ComentariosResponse> => {
    const extra: Record<string, string> = { limite: String(limite) };
    if (cf.sentimiento) extra.sentimiento = cf.sentimiento;
    if (cf.emocion) extra.emocion = cf.emocion;
    if (cf.fechaDesde) extra.fecha_desde = cf.fechaDesde;
    if (cf.fechaHasta) extra.fecha_hasta = cf.fechaHasta;
    if (cf.incluirNeutrales) extra.incluir_neutrales = "true";
    return getJson<ComentariosResponse>(`/percepcion/comentarios?${qs(f, extra)}`);
  },

  // Curación manual
  curacionTemas: (): Promise<{ items: TemaAsignable[] }> =>
    getJson<{ items: TemaAsignable[] }>("/percepcion/curacion/temas"),
  curacionPublicaciones: (): Promise<{ items: PublicacionCurar[] }> =>
    getJson<{ items: PublicacionCurar[] }>("/percepcion/curacion/publicaciones"),
  curacionComentarios: (): Promise<{ items: ComentarioCurar[] }> =>
    getJson<{ items: ComentarioCurar[] }>("/percepcion/curacion/comentarios"),
  asignarTemaPublicacion: (id: number, tema: string): Promise<AsignarTemaResponse> =>
    postJson<AsignarTemaResponse>(`/percepcion/curacion/publicacion/${id}`, { tema }),
  asignarTemaComentario: (id: number, tema: string): Promise<AsignarTemaResponse> =>
    postJson<AsignarTemaResponse>(`/percepcion/curacion/comentario/${id}`, { tema }),
  crearTema: (etiqueta: string, keywords: string[]): Promise<TemaAsignable> =>
    postJson<TemaAsignable>("/percepcion/curacion/tema", { etiqueta, keywords }),

  // Corrección de sentimiento / emoción
  scoringOpciones: (): Promise<OpcionesScoring> =>
    getJson<OpcionesScoring>("/percepcion/curacion/scoring/opciones"),
  // `revisados`/`pendientes` los calcula el servidor sobre COMENTARIOS CUBIERTOS
  // (los cuatro campos anotados y el tema vigente), no sobre correcciones guardadas.
  // La diferencia no es cosmética: el contador anterior contaba clicks, así que
  // subía igual cuando la cola devolvía los mismos comentarios una y otra vez —por
  // eso nadie notó durante días que la cola no avanzaba.
  concentracion: (f: Filtro, nivel: string): Promise<ConcentracionResponse> =>
    getJson<ConcentracionResponse>(`/percepcion/concentracion?${qs(f, { nivel })}`),

  postura: (f: Filtro): Promise<PosturaInstitucionalResponse> =>
    getJson<PosturaInstitucionalResponse>(`/percepcion/postura?${qs(f)}`),

  /**
   * Volumen adverso del período y si su variación resiste el cambio de ventana.
   * Complementa al índice con lo que un promedio no puede dar: cuántos comentarios
   * adversos hubo, y cuánto depende el resultado de con qué se lo compare.
   */
  conflicto: (f: Filtro): Promise<ConflictoResponse> =>
    getJson<ConflictoResponse>(`/percepcion/conflicto?${qs(f)}`),

  comentariosScoring: (
    limite = 50, cf: ComentariosFiltro = {}, orden: OrdenScoring = "duda",
  ): Promise<ColaScoring> => {
    const p = new URLSearchParams({ limite: String(limite), orden });
    if (cf.sentimiento) p.set("sentimiento", cf.sentimiento);
    if (cf.emocion) p.set("emocion", cf.emocion);
    return getJson<ColaScoring>(`/percepcion/curacion/scoring?${p.toString()}`);
  },
  // `origenMuestra` viaja con cada corrección: sin él no se puede separar después
  // lo anotado al azar (sirve para medir) de lo anotado por duda (no sirve).
  corregirSentimiento: (
    id: number, valor: string, justificacion: string, origenMuestra?: OrdenScoring,
  ): Promise<CorregirResponse> =>
    postJson<CorregirResponse>(`/percepcion/curacion/sentimiento/${id}`,
      { valor, justificacion, origen_muestra: origenMuestra ?? null }),
  corregirEmocion: (
    id: number, valor: string, justificacion: string, origenMuestra?: OrdenScoring,
  ): Promise<CorregirResponse> =>
    postJson<CorregirResponse>(`/percepcion/curacion/emocion/${id}`,
      { valor, justificacion, origen_muestra: origenMuestra ?? null }),
  // OJO: no es `asignarTemaComentario`. Aquella PISA el tema sin dejar rastro; esta
  // registra la revisión, que es lo que permite medir el clasificador de temas.
  corregirTema: (
    id: number, valor: string, justificacion: string, origenMuestra?: OrdenScoring,
  ): Promise<CorregirResponse> =>
    postJson<CorregirResponse>(`/percepcion/curacion/tema/${id}`,
      { valor, justificacion, origen_muestra: origenMuestra ?? null }),
  // Dimensión EN OBSERVACIÓN: no toca el índice ni los hechos.
  corregirPostura: (
    id: number, valor: string, justificacion: string, origenMuestra?: OrdenScoring,
  ): Promise<CorregirResponse> =>
    postJson<CorregirResponse>(`/percepcion/curacion/postura/${id}`,
      { valor, justificacion, origen_muestra: origenMuestra ?? null }),

  // D · qué palabras movieron la conversación respecto del período anterior
  impactoPalabras: (f: Filtro): Promise<ImpactoPalabrasResponse> =>
    getJson<ImpactoPalabrasResponse>(`/percepcion/impacto-palabras?${qs(f)}`),

  // Calidad del modelo (A1)
  calidad: (): Promise<CalidadResponse> =>
    getJson<CalidadResponse>("/percepcion/curacion/calidad"),
  correcciones: (limite = 100): Promise<{ items: CorreccionItem[] }> =>
    getJson<{ items: CorreccionItem[] }>(`/percepcion/curacion/correcciones?limite=${limite}`),
};

// ---- Señal de conflicto: el volumen adverso y su robustez ----
export interface VentanaConflicto {
  n: number;
  indice: number | null;
  n_adversos: number;
  pct_adversos: number | null;
}

export interface ComparacionConflicto {
  dias_previos: number;
  n_previo: number;
  pct_adversos_previo: number | null;
  indice_previo: number | null;
  delta_adversos: number | null;
  delta_indice: number | null;
  signo: string;
}

export interface ConflictoResponse {
  hay_datos: boolean;
  periodo: { desde: string; hasta: string } | null;
  actual: VentanaConflicto | null;
  comparaciones: ComparacionConflicto[];
  /** sube | baja | igual. null cuando el barrido no da un signo estable. */
  tendencia: string | null;
  /** false NO significa que no pase nada: significa que depende de la ventana. */
  consistente: boolean;
  delta_tipico: number | null;
  explicacion: string | null;
  avisos: string[];
}
