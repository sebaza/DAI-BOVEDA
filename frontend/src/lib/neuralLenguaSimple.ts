// Lenguaje llano para las páginas por tarea (T1 a T6) de la vista «Modelos»: pregunta en palabras simples, semáforo, qué significa
// cada corte «k», etiquetas de las evaluaciones y las frases del resultado principal. Funciones y tablas puras: todos los textos
// que explican un corte, un semáforo o una evaluación salen de aquí, para que se digan igual en la tarjeta y en la página.
// Las cifras de las frases salen siempre de lo que ya trae la vista (recall_10, precision_10, c_12, tasas); nada se inventa.
import type { EstadoTarea, ModeloTarea, ParticionTarea, TareaId, VistaTarea } from "./neural";

const coma = (v: number, dec = 1) => v.toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });

// ---------------------------------------------------------------------------
// Semáforo. Se parte del estado exportado (exploratorio = rojo; dato en revisión = nunca verde) y, para distinguir dentro de
// «benchmark completo», de la lectura de los informes (docs/08 a 12 y D88, D104, D113 de docs/00_plan.md).
// ---------------------------------------------------------------------------
export type NivelSemaforo = "usable" | "cautela" | "no_aun";

export interface FichaSimple {
  /** Nombre corto en palabras del tema. */
  tema: string;
  /** La pregunta que responde, sin tecnicismos. */
  pregunta: string;
  /** A quiénes se mira. */
  quienes: string;
  nivel: NivelSemaforo;
  /** Una o dos frases: qué significa en la práctica. */
  significado: string;
  /** La misma idea en una sola línea (tarjetas de la vista por facultad). */
  resumen: string;
  /** Cómo se dice el evento en una frase («hoy no continúa 1 de cada N estudiantes»). */
  base: (tasa: string) => string;
  /** Cómo se dice, en pasado y para el conjunto, quién cumplió el evento (cierra la frase de la revisión del 10 %). */
  eventoPasado: string;
  sujeto: string;
}

export const FICHA_SIMPLE: Record<TareaId, FichaSimple> = {
  t1: {
    tema: "Continuidad de estudios",
    pregunta: "¿Qué estudiantes tienen más riesgo de no seguir matriculados en la UCN el año siguiente?",
    quienes: "Estudiantes de pregrado que siguen matriculados al terminar el primer semestre o el primer año.",
    nivel: "cautela",
    significado: "El modelo ordena bien quién tiene más riesgo de no continuar, pero se apoya en cómo le fue a la persona en el semestre que ya terminó: sirve para priorizar el apoyo, no como alerta temprana. «No continuar» incluye traslados a otras instituciones y errores de registro.",
    resumen: "Ordena bien quién tiene más riesgo de no continuar; sirve para priorizar apoyo, no como alerta temprana.",
    base: (t) => `En el período evaluado no continuó ${t} estudiantes`,
    eventoPasado: "no continuaron",
    sujeto: "estudiantes",
  },
  t2: {
    tema: "Aprobación de ramos",
    pregunta: "¿Qué ramos que cursa una persona tienen más riesgo de reprobarse?",
    quienes: "Cada ramo que un estudiante de pregrado cursa en un semestre regular; se estima antes de que comience el semestre.",
    nivel: "cautela",
    significado: "El modelo ordena los ramos por riesgo de reprobar bastante mejor que una regla simple, sobre todo gracias a la historia del propio curso. Pero la reprobación cambia de un año a otro y el modelo la subestima, así que conviene leerlo como orden de riesgo y no como porcentaje exacto.",
    resumen: "Ordena los ramos por riesgo de reprobar; léelo como un orden de riesgo, no como un porcentaje exacto.",
    base: (t) => `En el período evaluado se reprobó ${t} ramos cursados`,
    eventoPasado: "reprobaron",
    sujeto: "ramos",
  },
  t3: {
    tema: "Tiempo hasta el egreso",
    pregunta: "¿Cuántos semestres tardará cada estudiante en egresar y cuáles tienen más probabilidad de salir antes?",
    quienes: "Estudiantes de pregrado de las cohortes 2015 en adelante, desde el ingreso o tras uno o dos años de estudios.",
    nivel: "usable",
    significado: "Es la tarea con el resultado más sólido: el modelo anticipa bien quién egresará antes que otra persona, y mejora a medida que se conoce más de la trayectoria. Antes de citar probabilidades exactas conviene recalibrarlo, porque las cohortes recientes egresan más rápido.",
    resumen: "Es el resultado más sólido: anticipa bien quién egresará antes que otra persona.",
    base: (t) => `En el período de evaluación ya egresó ${t} estudiantes`,
    eventoPasado: "egresaron",
    sujeto: "estudiantes",
  },
  t4: {
    tema: "Cambio de programa",
    pregunta: "¿Qué estudiantes cambiarán de programa en los dos semestres siguientes?",
    quienes: "Estudiantes de pregrado matriculados al terminar el primer o el segundo año. Elegir especialidad desde el Plan Común no cuenta como cambio.",
    nivel: "no_aun",
    significado: "Aún no es útil: los cambios de programa son pocos y difíciles de anticipar. Con los datos de ingreso, ningún modelo supera con claridad la tasa histórica del programa, y el pronóstico por programa y facultad no es confiable.",
    resumen: "Aún no es útil: los cambios de programa son pocos y difíciles de anticipar.",
    base: (t) => `En el período evaluado cambió de programa ${t} estudiantes`,
    eventoPasado: "cambiaron de programa",
    sujeto: "estudiantes",
  },
  t5: {
    tema: "Eliminación académica",
    pregunta: "¿Qué estudiantes serán eliminados por razones académicas en los dos semestres siguientes?",
    quienes: "Los mismos estudiantes de la tarea de cambio de programa: matriculados al terminar el primer o el segundo año.",
    nivel: "cautela",
    significado: "El modelo detecta bien a quienes tienen más riesgo, gracias al rendimiento académico ya observado. Pero desde 2024 el registro de eliminaciones está incompleto, así que las cifras recientes pueden quedar subestimadas.",
    resumen: "Detecta bien el riesgo, pero desde 2024 el registro de eliminaciones está incompleto.",
    base: (t) => `En el período evaluado recibió eliminación académica ${t} estudiantes`,
    eventoPasado: "fueron eliminados",
    sujeto: "estudiantes",
  },
  t6: {
    tema: "Postgrado en la UCN",
    pregunta: "¿Cuánto tarda en matricularse en un postgrado de la UCN quien egresó del pregrado?",
    quienes: "Personas que egresaron del pregrado (cohortes 2015 en adelante) y aún no tenían matrícula de postgrado.",
    nivel: "no_aun",
    significado: "Es un análisis exploratorio: hay muy pocos casos para sacar conclusiones firmes, y solo se ve el postgrado de la UCN, no el que se estudia en otras instituciones. A 1 año el perfil de ingreso ayuda algo; a 2 años el resultado no es concluyente.",
    resumen: "Es exploratorio: hay muy pocos casos para sacar conclusiones firmes.",
    base: (t) => `En el período observado se matriculó en un postgrado UCN ${t} egresados`,
    eventoPasado: "se matricularon en postgrado",
    sujeto: "egresados",
  },
};

export const SEMAFORO: Record<NivelSemaforo, { titulo: string; color: string; ayuda: string }> = {
  usable: { titulo: "Útil", color: "#6fae86", ayuda: "El resultado es sólido para usar a nivel de conjuntos." },
  cautela: { titulo: "Útil con cautela", color: "#d1a84b", ayuda: "Sirve, pero con límites que conviene conocer antes de citarlo." },
  no_aun: { titulo: "Aún no es útil", color: "#d2705f", ayuda: "Todavía es exploratorio: no recomendado para decidir." },
};

/** Nivel del semáforo, derivado del estado exportado de la tarea y de su lectura en los informes. */
export function nivelTarea(tarea: TareaId, estado: EstadoTarea): NivelSemaforo {
  const base = FICHA_SIMPLE[tarea].nivel;
  if (estado === "exploratorio") return "no_aun";
  if (estado === "dato_en_revision" && base === "usable") return "cautela";
  return base;
}

// ---------------------------------------------------------------------------
// Cortes «k»
// ---------------------------------------------------------------------------
export interface TextoCorte { selector: string; frase: string }

const CORTES: Partial<Record<TareaId, Record<number, TextoCorte>>> = {
  t1: {
    1: { selector: "k = 1 · primer semestre", frase: "k = 1 · al terminar el primer semestre: se mira a cada estudiante con su primer semestre ya cerrado y se estima si seguirá matriculado un año después." },
    2: { selector: "k = 2 · primer año", frase: "k = 2 · al terminar el primer año (dos semestres): se mira a cada estudiante con su primer año ya cerrado y se estima si seguirá matriculado un año después." },
    4: { selector: "k = 4 · segundo año", frase: "k = 4 · al terminar el segundo año (cuatro semestres): se mira a cada estudiante con dos años cerrados y se estima si seguirá matriculado un año después." },
  },
  t3: {
    0: { selector: "k = 0 · al ingreso", frase: "k = 0 · al ingresar: solo se conoce el perfil de ingreso, aún no hay notas." },
    2: { selector: "k = 2 · primer año", frase: "k = 2 · tras el primer año (dos semestres): se suma lo que el estudiante rindió en su primer año." },
    4: { selector: "k = 4 · segundo año", frase: "k = 4 · tras el segundo año (cuatro semestres): se suma lo que el estudiante rindió en dos años." },
  },
  t4: {
    2: { selector: "k = 2 · primer año", frase: "k = 2 · al terminar el primer año (dos semestres): se estima qué ocurrirá en los dos semestres siguientes." },
    4: { selector: "k = 4 · segundo año", frase: "k = 4 · al terminar el segundo año (cuatro semestres): se estima qué ocurrirá en los dos semestres siguientes." },
  },
};
CORTES.t5 = CORTES.t4;

const SIN_CORTE: Partial<Record<TareaId, string>> = {
  t2: "No hay cortes por año: cada ramo se evalúa antes de que comience el semestre en que se cursa.",
  t6: "No hay corte «k»: se mira a quienes ya egresaron y se cuenta el tiempo que pasa desde el egreso.",
};

/** Texto de un corte «k» (el mismo en el selector, la tarjeta y la página). */
export function textoCorte(tarea: TareaId, k: number): TextoCorte | null {
  const t = CORTES[tarea]?.[k];
  return t ?? (CORTES[tarea] ? { selector: `k = ${k}`, frase: `k = ${k} · tras ${k} semestres.` } : null);
}
export const textoSinCorte = (tarea: TareaId): string | null => SIN_CORTE[tarea] ?? null;

/** Etiqueta corta del corte para tarjetas y subtítulos («k = 1 · primer semestre»); vacía si la tarea no usa «k». */
export function etiquetaCorte(tarea: TareaId, k: number): string {
  return textoCorte(tarea, k)?.selector ?? "";
}

// ---------------------------------------------------------------------------
// Evaluaciones (variantes de una misma tarea)
// ---------------------------------------------------------------------------
export const ETIQUETA_EVALUACION: Record<string, string> = {
  base: "Evaluación histórica (2022-2023)",
  beneficios: "Con beneficios estudiantiles (ensayo, no adoptado)",
  beneficios_corte: "Modelo oficial desde la cohorte 2024 (con beneficios al corte)",
  extension_k4: "Extensión a dos años (k = 4)",
  actual: "Eliminación registrada (como hoy)",
  efectiva: "Eliminación efectiva (sin contar reintegros)",
  sin_dudosos: "Sin los años con registro dudoso",
  h2: "A 1 año del egreso",
  h4: "A 2 años del egreso",
};

/** Una línea que dice qué cambia en cada evaluación; solo se muestra cuando hay más de una. */
export const AYUDA_EVALUACION: Record<string, string> = {
  base: "Es la evaluación principal: el modelo se prueba con cohortes que nunca usó para aprender.",
  beneficios: "Prueba de agregar becas y gratuidad. Para el primer semestre no se puede adoptar, porque esa información no estaba completa en el momento del corte.",
  beneficios_corte: "Es el modelo que se usa para las cohortes desde 2024: incluye los beneficios que tenía cada estudiante justo al terminar el semestre.",
  extension_k4: "Mira dos años de estudios en vez de uno; es una extensión secundaria.",
  actual: "Cuenta la eliminación tal como está registrada hoy.",
  efectiva: "No cuenta a quienes fueron eliminados y luego reintegrados.",
  sin_dudosos: "Deja fuera los años recientes en que el registro de eliminaciones está incompleto.",
  h2: "Mira si la persona se matricula en un postgrado UCN dentro del primer año tras egresar.",
  h4: "Mira dentro de los dos primeros años tras egresar; hay muy pocos casos y el resultado no es concluyente.",
};

export const etiquetaEvaluacion = (variante: string, etiquetaServidor?: string): string =>
  ETIQUETA_EVALUACION[variante] ?? (etiquetaServidor || variante);

/** La variante «modelo oficial desde la cohorte 2024» se señala como el modelo en uso. */
export const ES_MODELO_EN_USO = (variante: string) => variante === "beneficios_corte";

// ---------------------------------------------------------------------------
// Frases del resultado
// ---------------------------------------------------------------------------
export const unaDeCada = (tasa: number | null | undefined): string | null => {
  if (tasa == null || !(tasa > 0)) return null;
  const n = Math.round(1 / tasa);
  return n <= 1 ? "casi todos" : `1 de cada ${n.toLocaleString("es-CL")}`;
};
const deCada10 = (v: number) => `${coma(v * 10, 1)} de cada 10`;

export interface FrasesResultado {
  /** La base: cuánto ocurre hoy, en palabras. */
  base: string | null;
  /** Qué tan bien funciona el modelo, en una o dos frases. */
  titular: string | null;
  /** Segunda frase, si los datos la permiten. */
  complemento: string | null;
  /** Qué se comparó (para no confundir al lector). */
  nota: string | null;
}

const valor = (m: ModeloTarea | undefined, id: string) => m?.metricas[id]?.valor ?? null;

/** Construye las frases del resultado de una vista solo con los datos que la vista trae. */
export function frasesResultado(
  tarea: TareaId, vista: VistaTarea, modelos: readonly ModeloTarea[], particiones: readonly ParticionTarea[],
): FrasesResultado {
  const ficha = FICHA_SIMPLE[tarea];
  const enVista = modelos.filter((m) => m.variante === vista.variante && m.corte_k === vista.corte_k);
  const cons = enVista.find((m) => m.modelo === vista.conservado_modelo);
  const ref = enVista.find((m) => m.modelo === vista.referencia_modelo);
  const prueba = particiones.find((p) => p.variante === vista.variante && p.corte_k === vista.corte_k && (p.particion === "test" || p.particion === "todas"));
  const tasa = unaDeCada(prueba?.tasa);
  const base = tasa ? `${ficha.base(tasa)}.` : null;

  if (tarea === "t3") {
    const c = valor(cons, "c_12");
    if (c == null) return { base, titular: null, complemento: null, nota: null };
    const cr = valor(ref, "c_12");
    return {
      base,
      titular: `Al comparar a dos estudiantes, el modelo anticipa correctamente a cuál egresa primero en ${deCada10(c)} comparaciones.`,
      complemento: cr != null ? `Una regla simple basada solo en el programa acierta ${deCada10(cr)}; al azar sería 5 de cada 10.` : "Al azar acertaría 5 de cada 10.",
      nota: "Es una medida de orden (C a 12 semestres): no dice cuántos semestres tardará cada persona.",
    };
  }
  if (tarea === "t2") {
    const r1 = valor(cons, "recall_at_1");
    if (r1 == null) return { base, titular: null, complemento: null, nota: null };
    const rr = valor(ref, "recall_at_1");
    return {
      base,
      titular: `Cuando un estudiante cursa varios ramos y reprueba alguno, el modelo ubica ese ramo como el de mayor riesgo en ${deCada10(r1)} casos.`,
      complemento: rr != null ? `La regla simple (tasa histórica del curso) lo logra en ${deCada10(rr)}.` : null,
      nota: null,
    };
  }
  const rec = valor(cons, "recall_10");
  const pre = valor(cons, "precision_10");
  if (rec == null) return { base, titular: null, complemento: null, nota: null };
  const refRec = valor(ref, "recall_10");
  return {
    base,
    titular: `Si la DAI revisa al 10 % de ${ficha.sujeto} con mayor riesgo, encuentra a ${deCada10(rec)} de quienes ${ficha.eventoPasado}.`,
    complemento: [
      pre != null ? `De cada 10 personas revisadas, ${coma(pre * 10, 1)} efectivamente ${ficha.eventoPasado}.` : null,
      refRec != null ? `Con la tasa histórica del programa se encontraría a ${deCada10(refRec)}; al azar, 1 de cada 10.` : "Al azar se encontraría a 1 de cada 10.",
    ].filter(Boolean).join(" "),
    nota: null,
  };
}

// ---------------------------------------------------------------------------
// Glosario del detalle técnico
// ---------------------------------------------------------------------------
export const GLOSARIO: readonly { termino: string; definicion: string }[] = [
  { termino: "k", definicion: "Momento de la trayectoria en que se hace la predicción, contado en semestres desde el ingreso (k = 1: tras el primer semestre; k = 2: tras el primer año)." },
  { termino: "Conjunto de prueba", definicion: "Los casos más recientes, que el modelo nunca vio para aprender ni para elegirse. Es la forma honesta de medir cuánto acierta." },
  { termino: "Intervalo del 95 %", definicion: "Rango en que probablemente está el valor real. Si el intervalo de una diferencia incluye el cero, no se puede asegurar que haya mejora." },
  { termino: "AP (precisión promedio)", definicion: "Qué tan arriba quedan, en la lista ordenada por riesgo, las personas que sí tuvieron el evento. Más alto es mejor; se lee frente a la referencia." },
  { termino: "ROC-AUC", definicion: "Probabilidad de que el modelo ponga a una persona que tuvo el evento por encima de otra que no. 0,5 es azar; 1 es perfecto." },
  { termino: "Brier", definicion: "Error promedio de las probabilidades que entrega el modelo. Menor es mejor." },
  { termino: "ECE", definicion: "Cuánto se alejan las probabilidades del modelo de lo que realmente ocurrió. Menor es mejor." },
  { termino: "C(12)", definicion: "Entre dos estudiantes, probabilidad de ordenar bien a cuál egresa primero, a 12 semestres desde el ingreso. 0,5 es azar; 1 es perfecto." },
  { termino: "IBS", definicion: "Error de las probabilidades a lo largo de todo el tiempo de seguimiento. Menor es mejor." },
  { termino: "Diferencia pareada", definicion: "Comparación de dos modelos sobre exactamente los mismos casos; es la forma válida de decir si uno mejora a otro." },
  { termino: "Escalera de ablación", definicion: "Serie de modelos que van sumando información (primero el perfil de ingreso, luego el rendimiento académico, luego la secuencia por semestre), para ver qué aporta cada paso." },
  { termino: "Recall al 10 %", definicion: "De todas las personas que tuvieron el evento, qué fracción queda dentro del 10 % con mayor riesgo." },
  { termino: "Precisión al 10 %", definicion: "Dentro del 10 % con mayor riesgo, qué fracción efectivamente tuvo el evento." },
];

// ---------------------------------------------------------------------------
// Propósito de cada pestaña (una frase) y cómo leerla. Un solo lugar para que el texto no se repita ni se contradiga.
// ---------------------------------------------------------------------------
export interface PropositoVista { proposito: string; leer: string }

export const PROPOSITO_PESTANA = {
  historico: {
    proposito: "Muestra, en cantidades de estudiantes, lo que ya ocurrió: en qué semestre se pierden, cuántos siguieron, cuántos fueron eliminados y cuánto habría ayudado usar el modelo.",
    leer: "Cada bloque responde una pregunta, trae un número clave y una línea «Cómo usarlo». Elige una facultad, y luego un programa, para ver solo sus estudiantes.",
  },
  proyeccion: {
    proposito: "Muestra, en cantidades de estudiantes actuales, quiénes están cerca de la eliminación por reprobaciones, cuántos se espera que continúen, cuántos podrían ser eliminados y cuántos podrían egresar.",
    leer: "Las proyecciones (continuidad, eliminación y egreso) son un rango («entre … y …») con su fecha de corte, no un número exacto; el bloque del umbral es un conteo de hoy, no una proyección. Cada total indica de cuántos estudiantes sale, y los grupos de menos de 10 llevan la marca «pocos casos»; nunca se señala a un estudiante.",
  },
  modelos: {
    proposito: "Muestra qué tan bien pueden los modelos anticipar seis situaciones de la trayectoria de los estudiantes de pregrado y si ya sirven para apoyar decisiones.",
    leer: "Empieza por el semáforo de cada tarea: «Útil» se puede usar, «Útil con cautela» se cita con sus límites y «Aún no es útil» es solo exploratorio.",
  },
  facultad: {
    proposito: "Aquí se mide el modelo, no la historia: para cada tarea, qué porcentaje de estudiantes de una facultad o de un programa vivió la situación y cuánto lo anticipó el modelo. Para ver la historia de una facultad, usa Histórico.",
    leer: "Compara «Lo que ocurrió» con «Lo que anticipó el modelo»: si se parecen, el modelo describe bien a la facultad o al programa. Son porcentajes de conjuntos, nunca de personas.",
  },
  cohortes: {
    proposito: "Muestra qué pasó con cada generación de ingreso de un programa: cuántos siguen tras el primer año y cuántos se titulan a tiempo.",
    leer: "Busca o elige un programa; cada fila es una generación. «En curso» significa que aún no pasa el tiempo para saberlo, no que el resultado sea cero.",
  },
  traslados: {
    proposito: "Muestra cuántos estudiantes pasan de un programa de pregrado a otro y qué programas ganan o pierden estudiantes con esos movimientos.",
    leer: "Mira primero el balance por programa: un neto positivo (azul) recibe más de lo que pierde; uno negativo (naranjo) pierde más de lo que recibe.",
  },
  calidad: {
    proposito: "Indica si los datos que alimentan el módulo están completos y consistentes, y qué límites tienen.",
    leer: "Si todos los chequeos están aprobados no hay nada que hacer; las tablas técnicas están plegadas para quien las necesite.",
  },
} as const satisfies Record<string, PropositoVista>;

export const PROPOSITO_MODELOS = {
  panorama: "Las seis preguntas que se probaron, cada una con su semáforo. Entra a una tarea para ver el detalle.",
  tareas: "Una tarea a la vez: qué responde, qué tan bien lo hace el modelo y cómo le va a cada programa y facultad.",
  gru: "Explicación técnica de cómo funciona esta red; no hace falta para leer los resultados.",
  graphsage: "Explicación técnica de cómo funciona esta red; no hace falta para leer los resultados.",
  mlp: "Explicación técnica de cómo funciona esta red; no hace falta para leer los resultados.",
  catboost: "Explicación técnica del modelo de árboles con el que se comparan las redes; no hace falta para leer los resultados.",
} as const;

// ---------------------------------------------------------------------------
// Términos del módulo. Se usan siempre con el mismo sentido en todas las pestañas.
// ---------------------------------------------------------------------------
export const TERMINOS_MODULO: readonly { termino: string; definicion: string }[] = [
  { termino: "Egreso", definicion: "Terminar el plan de estudios. Es el evento de la tarea «Tiempo hasta el egreso»." },
  { termino: "Titulación", definicion: "Obtener el título, algún tiempo después del egreso. Es lo que mide la pestaña «Cohortes»; no es lo mismo que egresar." },
  { termino: "No continuidad", definicion: "No seguir matriculado en la UCN el año siguiente. No equivale a deserción: incluye traslados a otras instituciones, abandonos sin registro y errores de registro." },
  { termino: "Cohorte", definicion: "Generación: las personas que ingresaron a un programa en el mismo período." },
  { termino: "Traslado", definicion: "Paso de una persona de un programa de pregrado a otro de la UCN." },
  { termino: "Tarea (T1 a T6)", definicion: "Cada una de las seis preguntas que se probaron con los modelos: continuidad, aprobación de ramos, egreso, cambio de programa, eliminación y postgrado." },
  { termino: "k", definicion: "Momento en que se hace la estimación, contado en semestres desde el ingreso (k = 2 es al terminar el primer año)." },
  { termino: "Semáforo", definicion: "Juicio de utilidad de cada tarea: «Útil», «Útil con cautela» o «Aún no es útil». Siempre se muestra con texto, no solo con color." },
  { termino: "Datos agregados", definicion: "Cifras de grupos, siempre con el número de personas de que salen. Un grupo de menos de 10 se muestra con la marca «pocos casos»; no hay listas ni predicciones sobre una persona." },
];

// ---------------------------------------------------------------------------
// Códigos internos de decisiones y preguntas (P58, D113…): no se muestran en el texto ejecutivo.
// ---------------------------------------------------------------------------
const COD = "[PD]\\d{1,3}";
const RE_PAREN = new RegExp(`\\s*\\((?:DAI,\\s*)?${COD}(?:\\s*(?:,|y|;)\\s*${COD})*\\)`, "g");
const RE_INICIO = new RegExp(`(^|[.;]\\s+)${COD}(?:\\s*(?:,|y)\\s*${COD})*:\\s*`, "g");
const RE_REGLA = new RegExp(`\\bregla ${COD}\\b`, "g");
const RE_SUELTO = new RegExp(`(?:,\\s*|\\s+(?:por|según|de)\\s+|\\s+)${COD}\\b`, "g");

/** Quita las referencias internas (P58, D113, «regla D47») de un texto para el lector no técnico. */
export function limpiarCodigos(texto: string): string {
  const limpio = texto
    .replace(RE_PAREN, "")
    .replace(RE_INICIO, "$1")
    .replace(RE_REGLA, "regla institucional")
    .replace(RE_SUELTO, "")
    .replace(/\s+([.,;:])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
  // Si se quitó el código del inicio de una frase, la frase sigue empezando con mayúscula.
  return limpio === texto ? limpio : limpio.replace(/(^|[.!?]\s+)([a-záéíóúñ])/g, (_m, a: string, b: string) => a + b.toUpperCase());
}

// ---------------------------------------------------------------------------
// Vista por facultad
// ---------------------------------------------------------------------------
/** Qué se cuenta en cada tarea, en una frase corta y con el mismo verbo en todas las pestañas. */
export const EVENTO_FACULTAD: Record<TareaId, { evento: string; unidad: string; cabecera: string }> = {
  t1: { evento: "estudiantes que no siguen matriculados en la UCN al año siguiente", unidad: "estudiantes", cabecera: "No continúan" },
  t2: { evento: "ramos cursados que se reprueban", unidad: "ramos cursados", cabecera: "Reprueban el ramo" },
  t3: { evento: "estudiantes que egresan", unidad: "estudiantes", cabecera: "Egresan" },
  t4: { evento: "estudiantes que cambian de programa en los dos semestres siguientes", unidad: "estudiantes", cabecera: "Cambian de programa" },
  t5: { evento: "estudiantes eliminados por razones académicas en los dos semestres siguientes", unidad: "estudiantes", cabecera: "Son eliminados" },
  t6: { evento: "egresados que se matriculan en un postgrado de la UCN", unidad: "egresados", cabecera: "Cursan postgrado UCN" },
};

/** Marca de los grupos pequeños y formato de las métricas con intervalo (todo el módulo usa estos textos). */
export const POCOS_CASOS_TEXTOS = {
  etiqueta: "pocos casos",
  ayuda: "Menos de 10 casos: la cifra es real, pero cambia mucho con una sola persona.",
  leyendaTabla: "«Pocos casos»: el grupo tiene menos de 10 {unidad}; la cifra se muestra, pero es poco estable.",
  leyendaGrafico: "Más claro = pocos casos, menos de 10 {unidad}. Al tocar o pasar el cursor por una barra o un punto, el detalle dice «pocos casos».",
  noCalculable: "no calculable",
  intervalo: "Entre paréntesis va el intervalo de 95 %: el rango en que razonablemente cae la cifra dado el tamaño del grupo.",
} as const;

/** Textos de «Por programa y por facultad» y de la pestaña por facultad (los números salen siempre de los datos). */
export const GRUPOS_TEXTOS = {
  sub: "Cómo le fue a cada grupo. Se muestran todos, de cualquier tamaño: cada cifra trae el número de personas de que sale y los grupos de menos de 10 llevan la marca «pocos casos». Entre paréntesis va el intervalo de 95 %.",
  t6: "En postgrado cada fila suma las unidades de validación y de prueba de los egresados (no a toda la población), y «lo que anticipó el modelo» es el riesgo esperado del modelo conservado; no es la incidencia observada de todos los egresados.",
  niveles: {
    programa: "Por programa", facultad: "Por facultad", nivel_postgrado: "Por nivel de postgrado",
    sexo: "Por sexo", via: "Por vía de ingreso", tipo_colegio: "Por tipo de colegio",
  },
  columnaNivel: {
    programa: "Programa", facultad: "Facultad", nivel_postgrado: "Nivel",
    sexo: "Sexo", via: "Vía de ingreso", tipo_colegio: "Tipo de colegio",
  },
  vacio: "Con este nivel y esta vista no hay grupos.",
  grupos: "{n} grupos en esta vista; se muestran todos.",
  recortado: "El gráfico muestra los {max} grupos más grandes; la tabla lista todos ({n}).",
  notas: "Cómo leer estas cifras",
} as const;

/** Momento de la estimación en palabras simples («al terminar el primer año»). */
export function momentoSimple(tarea: TareaId, variante: string, k: number): string {
  if (tarea === "t2") return "antes de cada semestre";
  if (tarea === "t6") return variante === "h4" ? "a 2 años del egreso" : "a 1 año del egreso";
  if (k === 0) return "al ingresar";
  if (k === 1) return "al terminar el primer semestre";
  if (k === 2) return "al terminar el primer año";
  if (k === 4) return "al terminar el segundo año";
  return `tras ${k} semestres`;
}

/** Cómo se dice la diferencia entre lo anticipado y lo ocurrido, en puntos porcentuales. */
export function lecturaBrecha(esperada: number, observada: number): string {
  const d = (esperada - observada) * 100;
  if (Math.abs(d) < 0.5) return "prácticamente lo mismo que ocurrió";
  return `${coma(Math.abs(d), 1)} puntos ${d > 0 ? "más" : "menos"} que lo ocurrido`;
}

// ---------------------------------------------------------------------------
// Selector en cascada (Toda la UCN → facultad → programa), compartido por «Histórico» y «Proyecciones»
// ---------------------------------------------------------------------------
export const SELECTOR_TEXTOS = {
  etiqueta: "Elegir población",
  facultad: "Facultad",
  programa: "Programa",
  todaFacultad: "Toda la facultad",
  buscador: "Buscar facultad o programa",
  buscadorAyuda: "Escriba al menos 2 caracteres: nombre o código",
  buscadorCargando: "Cargando…",
  buscadorFacultad: "Facultad",
  buscadorUnResultado: "1 resultado",
  buscadorResultados: "{n} resultados",
  buscadorSinResultados: "Sin coincidencias para «{texto}»",
  buscadorMas: "y {n} más; escriba más caracteres",
  sinDatosFacultad: "{facultad} no tiene datos en esta pestaña: se muestra Toda la UCN. Tu elección de facultad se conserva para la otra pestaña.",
  sinDatosProgramaUcn: "{programa} no tiene datos en esta pestaña: se muestra Toda la UCN. Tu elección de programa se conserva para la otra pestaña.",
  sinDatosPrograma: "{programa} no tiene datos en esta pestaña: se muestra la facultad completa. Tu elección de programa se conserva para la otra pestaña.",
  /** Una línea arriba de las pestañas que no usan la población elegida (solo con una población distinta de Toda la UCN). */
  seccionSinPoblacion: "Esta sección no cambia con la población elegida.",
} as const;

// ---------------------------------------------------------------------------
// Pestañas «Cohortes» y «Modelo por facultad»: avisos cuando la selección compartida no calza con lo que la pestaña trae
// ---------------------------------------------------------------------------
export const COHORTES_TEXTOS = {
  elige: "Elige un programa",
  eligeAyuda: "Busca el programa por nombre o código, o elige una facultad y luego uno de sus programas, para ver sus cohortes.",
  eligeDeFacultad: "Elegiste {facultad}: falta elegir uno de sus programas para ver sus cohortes.",
  sinDatosFacultad: "{facultad} no tiene programas con cohortes en esta pestaña. Tu elección de facultad se conserva para las otras pestañas.",
  sinDatosPrograma: "{programa} no tiene cohortes en esta pestaña. Tu elección de programa se conserva para las otras pestañas.",
  otrosProgramas: "Otros programas",
} as const;

export const FACULTAD_TEXTOS = {
  sinDatosUcn: "Toda la UCN no se ve en esta pestaña: aquí el modelo se mide por facultad o por programa. Se muestra {otra}; elige otra arriba.",
  sinDatosFacultad: "{facultad} no tiene cifras por facultad en esta pestaña: se muestra {otra}. Tu elección se conserva para las otras pestañas.",
  sinDatosPrograma: "{programa} no está en esta pestaña; se muestra {otro}. Tu elección se conserva para las otras pestañas.",
  programaAFacultad: "{programa} no está en esta pestaña; se muestra su facultad, {facultad}. Tu elección se conserva para las otras pestañas.",
} as const;

// ---------------------------------------------------------------------------
// Modelo visible en cada conclusión (el código T1–T6 solo aparece en la etiqueta, junto al nombre de la tarea)
// ---------------------------------------------------------------------------
export const MODELO_TEXTOS = {
  observado: "Dato observado, sin modelo",
  corte: "corte al {corte}",
  varios: "Este bloque usa más de un modelo:",
  noCambia: "Describe cómo decide el modelo: no cambia con la población elegida.",
  comoSeCalculo: "Cómo se calculó",
  poblacion: "Población",
  particion: "Partición",
  calculo: "Cálculo",
  tipos: {
    esperado: "Esperado: lo que el modelo anticipaba para casos que no vio al entrenarse, frente a lo ocurrido.",
    proyeccion: "Proyección: el modelo aplicado a los estudiantes actuales al cierre del corte.",
  },
  columna: "Modelo",
} as const;

// ---------------------------------------------------------------------------
// Pestaña «Histórico»: texto de cada bloque (los números salen siempre de los datos, nunca de aquí)
// ---------------------------------------------------------------------------
export const HISTORICO_TEXTOS = {
  leyenda: "Cada cifra indica de cuántos estudiantes sale; los grupos de menos de 10 llevan la marca «pocos casos».",
  noDisponible: "Aún no hay datos de esta vista. Cuando se carguen, aparecerán aquí.",
  poblacion: {
    semestres: "Datos: cohortes {cohortes}, con 6 años de seguimiento.",
    modelo: "Datos: cohortes {cohortes}, evaluadas por el modelo sin haberlas visto al entrenarse.",
    eliminados: "Datos: años {anios}, todas las cohortes de pregrado.",
    primerSemestre: "Datos: cohortes {cohortes}, seguidas hasta el año siguiente.",
  },
  sinDatos: "Este grupo no tiene datos para este bloque.",
  semestres: {
    titulo: "¿En qué semestre se pierden más estudiantes?",
    definicion:
      "Cada barra es un semestre desde el ingreso (el 1.º es el de ingreso). Se mira a quienes ingresaron en las cohortes {cohortes}, que ya tienen 12 semestres cerrados, y se cuenta en qué semestre dejaron la carrera, como porcentaje de su cohorte. «Eliminado» es quien terminó con el estado Eliminado; «deja la UCN» es cualquier otra salida definitiva (renuncia, no continuidad o ausencia prolongada). Quien egresó no se cuenta como baja.",
  },
  siguieron: {
    titulo: "¿Cuántos pasaron al año siguiente?",
    definicion:
      "Estudiantes de las cohortes {cohortes} que terminaron su primer semestre; «siguió» quien seguía matriculado un año después. Son cohortes que el modelo nunca vio al entrenarse. «El modelo esperaba» es la suma de las probabilidades que dio a cada estudiante.",
    leyendaUcn: "Por facultad: ● ocurrió · ○ el modelo esperaba",
    leyendaFiltro: "Todas las facultades de la UCN; se resalta la del grupo elegido: ● ocurrió · ○ el modelo esperaba",
    descripcionUcn: "Porcentaje que siguió, ocurrido y esperado por el modelo, en cada facultad.",
    descripcionFiltro: "Porcentaje que siguió, ocurrido y esperado por el modelo, en todas las facultades de la UCN; se resalta la del grupo elegido.",
    comoUsar:
      "Si el punto lleno queda lejos del vacío, el modelo se equivoca en esa facultad: conviene mirar su detalle antes de usarlo allí.",
  },
  eliminados: {
    titulo: "¿Cuántos fueron eliminados cada año?",
    definicion:
      "La línea principal cuenta, por año calendario, a los estudiantes de pregrado de todas las cohortes que tuvieron un estado «Eliminado» (una vez por persona y programa). Las barras reparten esas eliminaciones según la causa del reglamento. El recuadro «Lo que el modelo anticipa» mira solo la eliminación en el 2.º año de la carrera: de quienes terminaron su 2.º semestre, cuántos fueron eliminados en los dos semestres siguientes; el año es el del primer semestre de ese período y el modelo solo se evalúa en los años de prueba ({prueba}).",
    avisoRegistro:
      "Desde 2024 el sistema registra menos estados «Eliminado» y la DAI lo está revisando: parte de la baja reciente puede ser de registro y no de lo que pasó con los estudiantes.",
  },
  alcance: {
    titulo: "Si se hubiera usado el modelo para elegir a quién apoyar",
    definicion:
      "Se ordena a los estudiantes de las cohortes {cohortes} de mayor a menor riesgo según el modelo. La curva muestra qué parte de quienes no continuaron habría quedado dentro del grupo apoyado, según cuántos se apoyen; la línea punteada es elegir al azar.",
    comoUsar:
      "Con un cupo fijo de tutorías, el modelo dice a qué grupo llegar primero. Son cifras de grupos: la lista por estudiante espera la aprobación institucional.",
  },
  tema: "Tema",
  temas: {
    permanencia: "Permanencia",
    ramos: "Rendimiento en asignaturas",
    egreso: "Egreso y eliminación",
    modelo: "Fundamentos del modelo",
  },
  ventana: "Período: {desde} a {hasta}.",
  soloUcn: "Este bloque se calcula para toda la UCN: no se abre por facultad.",
  perfil: {
    titulo: "¿Qué perfil de ingreso tiene más riesgo de no seguir?",
    definicion:
      "Estudiantes de las cohortes {cohortes} que terminaron su primer semestre, agrupados según cómo ingresaron: vía de admisión, tipo de colegio y quinto del puntaje ponderado. «Siguió» es quien seguía matriculado un año después; «el modelo esperaba» es lo que el modelo anticipó para ese mismo grupo. Muestra asociación, no causa. Cada porcentaje indica de cuántas personas sale; los grupos de menos de 10 llevan la marca «pocos casos».",
    dimensiones: {
      via: "Vía de ingreso",
      colegio: "Tipo de colegio",
      puntaje: "Puntaje de ingreso (quintos)",
    },
    comoUsar:
      "Sirve para saber a qué grupos conviene acompañar desde la bienvenida. Que un grupo siga menos no significa que su origen sea la causa: puede reflejar otras condiciones que comparte.",
  },
  primerSemestre: {
    titulo: "¿Cuánto pesa el primer semestre?",
    definicion:
      "Estudiantes de las cohortes {cohortes} que terminaron su primer semestre, según cuántos ramos reprobaron en él. Se muestra qué porcentaje seguía matriculado un año después. Muestra asociación, no causa. Cada porcentaje indica de cuántas personas sale; los grupos de menos de 10 llevan la marca «pocos casos».",
    comoUsar:
      "Si el porcentaje que sigue cae con cada ramo reprobado, el primer semestre es el momento para apoyar: conviene actuar apenas aparece el primer ramo reprobado, no al final del año.",
  },
  ramosReprobados: {
    titulo: "¿Cuál es el ramo más reprobado?",
    definicion:
      "Para cada ramo se cuentan las veces que fue cursado y las veces que se reprobó entre {desde} y {hasta}. Cada cifra cuenta inscripciones en el ramo (una persona que lo cursa dos veces cuenta dos veces). Se consideran todos los ramos con al menos una inscripción; el gráfico muestra los 10 mayores según el orden elegido y, si hay más, una tabla plegada los lista todos. Los de menos de 10 inscripciones llevan la marca «pocos casos». Un ramo masivo con un porcentaje medio puede pesar más que uno chico con un porcentaje alto: por eso se puede ordenar de las dos maneras. Cada porcentaje trae su intervalo de 95 % entre paréntesis, y el orden por porcentaje usa el límite inferior de ese intervalo: así se tiene en cuenta cuántas veces se cursó el ramo y uno con pocos intentos no sube al primer lugar solo por azar.",
    comoUsar:
      "Para dar más apoyo a un ramo, mire primero cuántas reprobaciones hay y luego el porcentaje: un ramo con menos porcentaje pero mucha matrícula puede necesitar más apoyo que uno pequeño.",
  },
  ramosEsperado: {
    titulo: "¿En qué ramos y departamentos se reprueba más de lo esperado?",
    definicion:
      "Compara cuántas inscripciones terminaron en reprobación con cuántas el modelo esperaba, dados el estudiante y el ramo. La diferencia se muestra con su rango: si todo el rango queda sobre cero, se reprueba más de lo esperado. Los años de prueba son los que el modelo no vio al entrenarse; los posteriores son más recientes. No hay cifras por sección ni por docente: solo ramo y departamento. El gráfico muestra los 12 con mayor diferencia y, si hay más, una tabla plegada los lista todos.",
    ventanas: { prueba: "Años de prueba", posterior: "Años posteriores" },
    comoUsar:
      "Un ramo que reprueba más de lo esperado es candidato para revisar su apoyo o su diseño. Un valor cercano a cero indica que el resultado es el que se anticipaba.",
  },
  cuellos: {
    titulo: "¿Qué ramos frenan el avance?",
    definicion:
      "Para cada ramo se multiplica el número de reprobaciones por la cantidad de ramos que dependen de él en la malla (los que lo piden como prerrequisito, directa o indirectamente). Un número alto indica un ramo que, al reprobarse, retrasa a muchas personas. Se consideran todos los ramos de los que depende otro ramo y que tienen al menos una inscripción; el gráfico muestra los 10 de mayor impacto y, si hay más, una tabla plegada los lista todos. Los de menos de 10 reprobaciones llevan la marca «pocos casos».",
    comoUsar:
      "Ayuda a elegir dónde poner tutorías para que menos estudiantes queden detenidos: un ramo que pocos reprueban pero del que dependen muchos puede importar más que uno muy reprobado sin dependientes.",
  },
  semestreMalla: {
    titulo: "¿En qué semestre de la malla se reprueba más?",
    definicion:
      "Porcentaje de ramos reprobados según el semestre de la malla en que está cada ramo (no el semestre de la persona). Cada porcentaje indica de cuántas inscripciones sale.",
    comoUsar:
      "Muestra en qué tramo de la carrera se concentra la reprobación, para ubicar el apoyo en esos semestres y no repartirlo parejo.",
  },
  causalesPrograma: {
    titulo: "¿Por qué causas se elimina en cada programa?",
    definicion:
      "Para cada {nivel} se reparten las eliminaciones de pregrado según la causa del reglamento entre {desde} y {hasta}. Cada fila indica cuántas eliminaciones suma, y las de menos de 10 llevan la marca «pocos casos». El motivo personal no existe en los datos: aquí solo aparece la causa que registra el reglamento.",
    nota: "Este período puede ser distinto al de «¿Cuántos fueron eliminados cada año?»: ese mira los años de la línea de arriba; este, el período indicado en este bloque.",
    sinDetalle: "Sin detalle por causa en los datos:",
    noGrafican: "No se grafican por espacio; se listan con su causa principal:",
    comoUsar:
      "Si la mayoría se elimina por la misma causa en un programa, el apoyo se puede dirigir a evitarla. Como el reglamento cambió en 2025, las causas de antes y después no se comparan directo.",
  },
  tiempo: {
    titulo: "¿Cuánto tardan en egresar?",
    definicion:
      "Para cada programa, el porcentaje de estudiantes que egresó dentro de la duración nominal, y el que había egresado con uno y con dos años de atraso (cada barra incluye a la anterior). Solo cohortes con seguimiento suficiente. Cada porcentaje indica de cuántos estudiantes sale; los programas de menos de 10 llevan la marca «pocos casos». El gráfico muestra los 12 programas con más estudiantes y, si hay más, una tabla plegada los lista todos.",
    comoUsar:
      "Un programa con pocos egresos a tiempo pero muchos con un año de atraso necesita apoyo en los últimos semestres. Compare programas con duración nominal parecida.",
  },
  senales: {
    titulo: "¿Qué mira el modelo para decidir?",
    definicion:
      "Para cada modelo se muestran las cinco señales que más pesan en su decisión, traducidas a lenguaje simple. Las señales describen lo que el modelo pondera, no lo que causa el resultado. En continuidad y en aprobación de ramos puede aparecer «Año de ingreso»: el modelo ajusta por la generación, no es una causa. Es una cifra de toda la UCN.",
    comoUsar:
      "Sirve para entender qué información usa el modelo y para detectar si se apoya en algo que no debería. No indica qué cambiar para que a un estudiante le vaya mejor.",
    peso: "Peso de cada señal, en porcentaje.",
    muestra: "Se midió con {n} estudiantes.",
    muestraInscripciones: "Se midió con {n} inscripciones en ramos.",
  },
  esperar: {
    titulo: "¿Cuánto se gana esperando un semestre?",
    definicion:
      "Compara dos momentos de anticipación del mismo modelo. Se ordena a los estudiantes de mayor a menor riesgo; se mira el 10 % de mayor riesgo y cuántos de cada 10 de quienes terminaron mal se alcanzan. Es una cifra de toda la UCN.",
    antes: "Antes",
    despues: "Después",
    poblaciones: "Los dos momentos no evalúan exactamente a las mismas personas: la comparación es orientativa.",
    comoUsar:
      "Si esperar un semestre mejora poco la cifra, conviene apoyar antes; si la mejora mucho, esperar permite elegir mejor a quién apoyar.",
  },
  comoUsarEtiqueta: "Cómo usarlo",
  /** Franja «Lo esencial» con que abre la pestaña. */
  esencial: {
    titulo: "Lo esencial",
    sinDatos: "sin datos",
    ver: "Ver el bloque",
    continuidad: { titulo: "Siguieron al año siguiente", detalle: "siguieron {siguieron} de {n} estudiantes" },
    bajas: { titulo: "Bajas en el primer año", detalle: "de {n} bajas, ocurren en el 1.er año (semestres 1 y 2)" },
    eliminados: { titulo: "Eliminados en {anio}", tituloSinDatos: "Eliminados en el último año completo", detalle: "estudiantes de pregrado eliminados en el último año completo" },
  },
  /** Listas de las que el gráfico muestra solo los mayores: el aviso y la tabla plegada con todas. */
  recorte: {
    aviso: "Se muestran los {n} mayores de {m} {que}. Todos están en la tabla «Ver los {m} {que}».",
    ver: "Ver los {m} {que}",
    etiqueta: "Todos los {que}",
    ramos: "ramos",
    departamentos: "departamentos",
    programas: "programas",
    col: {
      ramo: "Ramo", departamento: "Departamento", programa: "Programa", inscripciones: "Inscripciones", reprobados: "Reprobados",
      pctReprobado: "% reprobado (intervalo de 95 %)", reprobaron: "Reprobaron", esperados: "El modelo esperaba", diferencia: "Diferencia (rango)",
      reprobaciones: "Reprobaciones", dependientes: "Ramos que dependen", impacto: "Impacto", estudiantes: "Estudiantes",
      aTiempo: "A tiempo", mas1: "Con 1 año de atraso", mas2: "Con 2 años de atraso",
    },
  },
} as const;

export const llenar = (texto: string, valores: Record<string, string>): string =>
  texto.replace(/\{(\w+)\}/g, (_m, k: string) => valores[k] ?? "");

/** «202110» -> «1.er semestre 2021»; «202120» -> «2.º semestre 2021». Lo que no calza con un período se devuelve igual. */
export function periodoLegible(periodo: string): string {
  const m = /^(\d{4})([12])0$/.exec(periodo);
  return m ? `${m[2] === "1" ? "1.er" : "2.º"} semestre ${m[1]}` : periodo;
}

// ---------------------------------------------------------------------------
// Pestaña «Proyecciones»: texto de cada bloque (los números salen siempre de los datos, nunca de aquí)
// ---------------------------------------------------------------------------
export const PROYECCION_TEXTOS = {
  soloGrupos: "Cada cifra indica de cuántos estudiantes sale; los grupos de menos de 10 llevan la marca «pocos casos».",
  corte: "Corte: {corte}",
  sinDatos: "Este grupo no tiene datos para este bloque.",
  noDisponible: "Aún no hay una proyección publicada.",
  cohorteOtra: "Otras cohortes",
  rangoEtiqueta: "entre {lo} y {hi}",
  esperadoEtiqueta: "central {esperado}",
  sinCifra: "no disponible",
  sinProyeccion: "{n} estudiantes actuales no entran en ninguna de las poblaciones proyectadas con estos modelos, así que no están en los bloques de continuidad, eliminación y egreso.",
  notas: [
    "Son cifras de grupos, con el número de estudiantes de que salen; un grupo de menos de 10 lleva la marca «pocos casos». No hay listas ni datos por estudiante.",
    "Cada proyección es un rango, no un número exacto, y indica la fecha de corte de los datos: no se usa nada posterior al cierre de ese período.",
    "La eliminación proyectada es orientativa: el reglamento de 2025 (Art. 46) cambió las reglas y los modelos se construyeron con años anteriores; además, desde el 2.º semestre 2024 las eliminaciones se registran con atraso.",
  ],
  detalleCohortes: "Ver el detalle por cohorte",
  columnas: { cohorte: "Cohorte", corte: "Corte", hasta: "Hasta", estudiantes: "Estudiantes", esperado: "Esperado", rango: "Rango" },
  umbral: {
    titulo: "¿Quiénes están cerca de la eliminación por reprobaciones?",
    definicion:
      "Se aplica a todos los estudiantes actuales el reglamento vigente desde el 2.º semestre 2025 (Art. 46): una persona llega al umbral con 6 reprobaciones de ramos en segunda oportunidad a lo largo de la carrera, o con 2 ramos distintos reprobados en tercera oportunidad. Cada estudiante se cuenta en una sola categoría, según la que tenga más cerca: «en el umbral», «a 1» o «a 2» reprobaciones de llegar. Es un conteo de lo que ya ocurrió, no una proyección.",
    comoUsar: "Dónde poner tutorías este semestre.",
    clave: "estudiantes actuales ya están en el umbral",
    categorias: { en_umbral: "En el umbral", a_1: "A 1 reprobación", a_2: "A 2 reprobaciones" },
    lejos: "{n} estudiantes están a 3 o más reprobaciones del umbral.",
    p58: "Las cifras son un mínimo: los semestres del 2.º semestre 2019 y 1.er semestre 2020 no cuentan reprobaciones, así que algunas personas podrían estar más cerca de lo que se ve.",
    nota: "Conteo exacto, no un rango.",
    ejeY: "Estudiantes",
  },
  continuidad: {
    titulo: "¿Cuántos continuarán el próximo año?",
    definicion:
      "Para los estudiantes de las cohortes más recientes se estima cuántos seguirán matriculados un año después de su fecha de corte. El modelo da una probabilidad a cada estudiante; aquí solo se suman para el grupo, y el rango muestra cuánto puede variar esa suma.",
    comoUsar: "Si la continuidad esperada de un grupo es baja, el apoyo del primer año conviene fortalecerlo ahí.",
    clave: "de los estudiantes proyectados se espera que continúe",
    ejeX: "% del grupo",
    historial: "{n} estudiantes no tienen historial de beneficios; el modelo los proyecta con el resto de su información.",
  },
  eliminacion: {
    titulo: "¿Cuántos podrían ser eliminados?",
    definicion:
      "Para las cohortes 2024 y 2025 se estima cuántos serían eliminados en los dos semestres siguientes a su fecha de corte. Una parte de ese período ya ocurrió: eso se muestra aparte como «observado hasta hoy», y nunca se suma a lo esperado.",
    comoUsar: "Úselo como orden de magnitud para dimensionar el apoyo, no como una meta ni una lista de personas.",
    clave: "eliminaciones esperadas en los dos semestres siguientes al corte",
    observado: "Observado hasta hoy",
    observadoTexto: "eliminaciones ya registradas en {periodo}",
    observadoSeparado: "Se muestra aparte: no se suma a lo esperado.",
    aviso:
      "Cifra orientativa. El modelo no conoció el reglamento vigente desde el 2.º semestre 2025 (Art. 46), que cambió las causales de eliminación, y desde el 2.º semestre 2024 las eliminaciones se registran con atraso (subregistro). Por eso lo esperado puede quedar lejos de lo que ocurra.",
    avisoTitulo: "Cómo leer esta cifra",
    ejeX: "% del grupo",
  },
  egreso: {
    titulo: "¿Cuántos podrían egresar?",
    definicion:
      "Para las cohortes 2024, 2025 y 2026 se estima cuántos egresarían hasta el final de la duración nominal de su programa y hasta dos semestres después. Cada cifra trae el período calendario al que corresponde, porque cada cohorte parte desde un corte distinto; por eso los totales no se interpretan como una sola fecha.",
    comoUsar: "Sirve para dimensionar cuántos egresos esperar en cada ventana de años, no para saber quién egresará.",
    nominal: "A tiempo (duración nominal)",
    nominalMas2: "Con 2 semestres de atraso",
    clave: "egresos esperados",
    periodo: "Entre {desde} y {hasta}.",
    noDisponible: "Esta cifra no está disponible para este grupo.",
    yaPasado: "{n} estudiantes ya pasaron el final de este período sin egresar y no se cuentan.",
    truncado: "En {n} estudiantes el período proyectado quedó recortado.",
    ejeX: "% del grupo",
    reglaTitulo: "Cómo se cuenta cada ventana",
    regla:
      "Para cada cohorte se suma la probabilidad estimada de egresar desde su fecha de corte hasta el final de la duración nominal de su programa (primera ventana) y hasta dos semestres después (segunda ventana). Cada cifra indica el período calendario al que corresponde; como las cohortes parten de cortes distintos, el total junta períodos distintos.",
  },
} as const;

// ---------------------------------------------------------------------------
// Puerta de aceptación (declaración de confidencialidad). El texto de la declaración llega del servidor y se muestra tal cual.
// ---------------------------------------------------------------------------
export const ACEPTACION_TEXTOS = {
  titulo: "Antes de ver los datos",
  confirmacion: "Confirmo lo anterior",
  boton: "Aceptar y continuar",
  enviando: "Guardando…",
  errorGuardar: "No se pudo registrar la aceptación. Inténtalo nuevamente.",
  errorCargar: "No se pudo cargar la declaración de confidencialidad.",
  errorInconsistente: "El servidor registra la aceptación, pero rechazó la consulta de datos. Inténtalo nuevamente o avisa a la DAI.",
  versionCambio: "La declaración cambió. Léela y confírmala de nuevo.",
} as const;
