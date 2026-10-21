"use client";

// Panel de Percepción de la Comunidad UCN.
// Lee la tabla de hechos del worker vía /percepcion/*. Barra de filtros GLOBAL
// (rango × sede × facultad × departamento × tema) que reconfigura TODO el tablero.
// Estilado con el sistema de la Torre (portal oscuro).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EChartsChart, type EChartsInstance } from "./EChartsChart";
import { PercepcionAlertas } from "./PercepcionAlertas";
import { PercepcionCalendarioDatos } from "./PercepcionCalendarioDatos";
import { PercepcionDominantes } from "./PercepcionDominantes";
import { PercepcionCalidad } from "./PercepcionCalidad";
import { PercepcionComparar } from "./PercepcionComparar";
import { PercepcionFranjaEventos, categoriaDeTipo } from "./PercepcionFranjaEventos";
import { PercepcionSimulacion } from "./PercepcionSimulacion";
import { PercepcionCuracion } from "./PercepcionCuracion";
import { PercepcionNube } from "./PercepcionNube";
import { PercepcionResumen } from "./PercepcionResumen";
import { PercepcionRevision } from "./PercepcionRevision";
import {
  CARD,
  COLOR_COPPER,
  COLOR_CYAN,
  COLOR_NEG,
  COLOR_NEU,
  COLOR_POS,
  RotuloMetodo,
  SELECT,
  SubPestanas,
  colorIndice,
  fmt,
  labelEmocion,
  nro,
} from "./PercepcionUI";
import {
  esAdmin,
  esEquipoDai,
  percepcionApi,
  type ComentarioReciente,
  type ComentariosFiltro,
  type EmocionItem,
  type EventoItem,
  type EventoPayload,
  type Filtro,
  type FiltrosResponse,
  type OpcionesScoring,
  type ResumenPercepcion,
  type PuntoEvolucion,
  type SerieEvolucion,
  type TipoEventoOpcion,
} from "../lib/percepcion";

// Los colores, `colorIndice`, `fmt` y `labelEmocion` viven en ./PercepcionUI:
// estaban triplicados acá, en la Síntesis y en la Nube, y un mismo índice tiene
// que verse igual en las cuatro pestañas o el lector cree que son métricas
// distintas.

const DEFAULT_DIAS = 36500;

// Espejo de las categorías de `PercepcionFranjaEventos`. Dos criterios que conviene
// no perder si alguien retoca esto:
//   * EMERGENCIA no es rojo. Una amenaza de tiroteo no es una movilización, y en
//     abril de 2025 fueron dos hechos consecutivos y distintos (la suspensión
//     institucional y el paro posterior por cómo se gestionó). Con el mismo color se
//     leían como uno solo.
//   * FIESTAS PATRIAS comparte el azul del receso: para la percepción son lo mismo,
//     no hay clases. Antes usaba el verde del semestre y se confundía con él.
/** Las dos preguntas de Conversación. Fue la primera pestaña en partirse, y su UI
 *  estaba escrita a mano acá; ahora usa el mismo `SubPestanas` que el resto para
 *  que no se separen de a poco. Los hints pasaron de `title` (tooltip que solo
 *  descubre quien ya sabe que está) a texto visible. */
const SUB_CONVERSACION = [
  {
    id: "tiempo",
    label: "¿Cuándo pasó?",
    hint:
      "La evolución del índice con los eventos del calendario encima, y los comentarios " +
      "de cada día: al hacer clic en una fecha del gráfico, la lista de abajo se filtra.",
  },
  {
    id: "palabras",
    label: "¿Con qué palabras?",
    hint: "El vocabulario crudo de la conversación y las emociones que la atraviesan.",
  },
  {
    // La tercera pata: sin ella, un movimiento del índice se atribuye a la etiqueta
    // del calendario y se concluye mal. Pasó dos veces en la auditoría de sept-2026
    // (el sorteo del 18 y el post de condolencias de agosto).
    id: "publicaciones",
    label: "¿Lo más hablado?",
    hint:
      "Las publicaciones que concentran la conversación del período. Es lo que explica " +
      "un movimiento del índice cuando el calendario no alcanza: una caída puede ser " +
      "descontento, un sorteo donde la gente etiqueta amigos, o un post de condolencias.",
  },
] as const;

/** Las tres tareas de Curación, en el orden en que hay que hacerlas.
 *
 * Los nombres viejos —«Calidad del modelo», «Cola de revisión», «Curación de
 * temas»— describen el artefacto, no el trabajo. Acá se nombran por la tarea, y
 * la primera es la que contesta si vale la pena hacer las otras dos. */
const SUB_CURACION = [
  {
    id: "calidad",
    label: "¿Cuánto le erra?",
    hint:
      "Qué tan seguido el modelo coincide con una persona, sobre los comentarios ya " +
      "revisados. Ningún número aparece sin su límite al lado: cuando el acuerdo no se " +
      "puede calcular, se dice por qué en vez de mostrar un 0 %.",
  },
  {
    id: "revisar",
    label: "Revisar comentarios",
    hint:
      "La cola para anotar a mano sentimiento, emoción, tema y postura. Es lo que produce " +
      "el dato con el que se mide lo anterior — sin esto, la calidad no tiene denominador.",
  },
  {
    id: "temas",
    label: "Corregir temas",
    hint:
      "Asignar a mano el tema de los comentarios y publicaciones que el clasificador dejó " +
      "en «otros», y crear temas nuevos cuando ninguno de los existentes sirve.",
  },
] as const;

const COLOR_EVENTO: Record<string, string> = {
  paro: "rgba(242,119,122,0.28)", toma: "rgba(242,119,122,0.28)",
  emergencia: "rgba(251,146,60,0.28)",
  semestre: "rgba(81,194,140,0.12)",
  examenes: "rgba(224,170,78,0.22)", receso: "rgba(79,156,240,0.20)",
  fiestas_patrias: "rgba(79,156,240,0.20)", cambio_calendario: "rgba(168,139,250,0.20)",
  resolucion: "rgba(168,139,250,0.20)", otro: "rgba(168,139,250,0.18)",
  // Duelo: gris pizarra, deliberadamente SIN la alarma del rojo de un paro. La
  // caída es real pero no es descontento, y el color es lo primero que se lee.
  duelo: "rgba(132,150,176,0.26)",
};

const COLOR_EVENTO_LINEA: Record<string, string> = {
  paro: "#f2777a", toma: "#f2777a", emergencia: "#fb923c",
  semestre: "#51c28c",
  examenes: "#e0aa4e", receso: "#4f9cf0",
  fiestas_patrias: "#4f9cf0", cambio_calendario: "#a88bfa",
  resolucion: "#a88bfa", otro: "#a88bfa", duelo: "#8496b0",
};

// ROLES VISUALES — la saturación no venía de CUÁNTOS eventos hay sino de que todos
// pesaban lo mismo. Doce semestres y un paro compitiendo con la misma tinta hacen
// que ninguno se lea. Cada rol tiene una representación distinta:
//
//   contexto  el ritmo académico (semestre, receso). Es el fondo sobre el que se
//             lee la serie, no algo a mirar: banda apenas perceptible.
//   overlay   lo que INTERRUMPE (paro, toma, emergencia). Cambia cómo hay que
//             interpretar la curva, así que se impone: banda marcada.
//   puntual   hitos administrativos (evaluaciones, matrícula, anuncios). Importan
//             para ubicarse, no para explicar el índice: tick corto en la base, sin
//             cruzar la serie.
type RolVisual = "contexto" | "overlay" | "puntual";

const ROL_POR_TIPO: Record<string, RolVisual> = {
  semestre: "contexto", receso: "contexto", fiestas_patrias: "contexto",
  // El DUELO no interrumpe la actividad, pero es overlay igual: el criterio del rol
  // no es "interrumpe" sino "cambia cómo hay que interpretar la curva", y una caída
  // de 6-9 puntos por condolencias se lee como crisis institucional si no se marca.
  // Medido: la semana del 17-08-2026 pasa de 63,9 a 57,5 por un post de despedida.
  paro: "overlay", toma: "overlay", emergencia: "overlay", duelo: "overlay",
  examenes: "puntual", otro: "puntual", cambio_calendario: "puntual", resolucion: "puntual",
};

const rolDe = (tipo: string): RolVisual => ROL_POR_TIPO[tipo] ?? "puntual";

// Opacidad del área por rol. La jerarquía completa vive en estos tres números: un
// contexto casi invisible, un overlay que se impone, y nada en el medio.
const OPACIDAD_AREA: Record<RolVisual, number> = {
  contexto: 0.09, overlay: 0.3, puntual: 0.22,
};

// Y lo mismo para los eventos que caen a línea por ser demasiado cortos: el rol
// manda sobre la forma. Un receso de cinco días es contexto aunque se dibuje como
// línea, y tiene que verse tan tenue como su banda.
const ANCHO_LINEA_ROL: Record<RolVisual, number> = {
  contexto: 2, overlay: 3, puntual: 2,
};
const OPACIDAD_LINEA: Record<RolVisual, number> = {
  contexto: 0.28, overlay: 0.75, puntual: 0.5,
};

// Altura del tick de un hito puntual, en unidades del eje Y (0-100). Va en la BASE:
// cruzar la serie de lado a lado por un cierre de matrícula es exactamente el ruido
// que hay que evitar.
const ALTO_TICK_PUNTUAL = 8;

// Un evento se dibuja como ÁREA solo si su duración ocupa al menos este porcentaje
// del rango visible; si no, como línea. Es lo que hace que la vista se adapte al
// zoom sin configuración: en «Todo» (4 años) un examen de 5 días es un tick, y al
// filtrar a 90 días el mismo examen pasa a ser una franja con su ancho real.
const MIN_PCT_PARA_AREA = 0.8;

/** Presets de visualización. Cada uno es un conjunto de tipos ENCENDIDOS. */
const PRESETS: { id: string; label: string; hint: string; tipos: string[] }[] = [
  { id: "limpia", label: "Serie limpia", hint: "Solo la curva, sin marcas", tipos: [] },
  {
    id: "contingencias", label: "Contingencias",
    hint: "Paros, tomas y emergencias: lo que interrumpió",
    tipos: ["paro", "toma", "emergencia"],
  },
  {
    id: "academico", label: "Calendario académico",
    hint: "El ritmo del año: semestres, recesos y evaluaciones",
    tipos: ["semestre", "receso", "fiestas_patrias", "examenes"],
  },
  {
    id: "completa", label: "Vista completa",
    hint: "Todo el calendario, incluidos los hitos administrativos",
    tipos: Object.keys(ROL_POR_TIPO),
  },
];

const PRESET_INICIAL = "contingencias";
const TODOS_LOS_TIPOS = Object.keys(ROL_POR_TIPO);
const ocultosDePreset = (id: string) => {
  const p = PRESETS.find((x) => x.id === id) ?? PRESETS[0];
  return new Set(TODOS_LOS_TIPOS.filter((t) => !p.tipos.includes(t)));
};

type EventoVisible = EventoItem & {
  inicioReal: string;
  finReal: string;
  inicioVisible: string;
  finVisible: string;
};

/**
 * Eventos que caen dentro del rango de la serie, con sus fechas REALES.
 *
 * ⚠️ Acá había un encaje a la grilla: `inicioVisible` era la primera fecha de la
 * serie ≥ el inicio del evento, y `finVisible` la última ≤ su fin. Con eje
 * CATEGÓRICO era obligatorio —había que apuntar a una categoría existente—, pero al
 * pasar el eje a `time` quedó como código muerto que además rompía los datos.
 *
 * Auditado sobre el corpus, que tiene 123 huecos: de 91 eventos, **83 quedaban
 * desplazados** de su fecha real (hasta 109 días) y **38 rangos perdían su duración**
 * al colapsar en un punto. El peor caso llegaba a invertirse: la Semana Mechona 2025
 * (05→10 de mayo) se dibujaba del 13 de mayo al 30 de abril, con el fin antes que el
 * inicio.
 *
 * Con eje temporal las fechas se usan tal cual: un evento que cae entero en un hueco
 * de la serie igual se dibuja donde corresponde, que es justamente cuando más
 * importa —el hueco suele SER el evento: en vacaciones nadie comenta—.
 */
function eventosVisiblesEnSerie(serie: SerieEvolucion, eventos: EventoItem[]): EventoVisible[] {
  const fechas = serie.puntos.map((p) => p.fecha);
  const desde = fechas[0];
  const hasta = fechas[fechas.length - 1];
  return desde == null || hasta == null
    ? []
    : eventos
        .filter((e) => e.fecha_fin >= desde && e.fecha_inicio <= hasta)
        .map((e) => {
          // Solo se recorta lo que se sale del eje; el interior no se toca.
          const inicioReal = e.fecha_inicio < desde ? desde : e.fecha_inicio;
          const finReal = e.fecha_fin > hasta ? hasta : e.fecha_fin;
          return { ...e, inicioReal, finReal, inicioVisible: inicioReal, finVisible: finReal };
        })
        .filter((e) => e.inicioVisible <= e.finVisible);
}

/* -------------------------------------------------------------------------- */
/* AGREGACIÓN ADAPTATIVA DE LA SERIE                                           */
/* -------------------------------------------------------------------------- */
//
// EL PROBLEMA, MEDIDO. El corpus tiene mediana de 5 comentarios por día, y de los
// ~7 puntos que varía el índice de una semana a otra, **unos 4 se explican solo
// por cuántos comentarios hubo**. Dibujar 564 puntos diarios sobre cuatro años no
// muestra una tendencia: muestra ruido de muestreo con forma de sierra. La curva
// sube y baja sin parar y no se puede leer nada.
//
// LA SOLUCIÓN NO ES SUAVIZAR EL DIBUJO, ES AGREGAR EL DATO. Una curva `smooth`
// sobre puntos ruidosos sigue siendo ruido, solo que con las esquinas redondeadas;
// además promete una precisión diaria que el dato no tiene. Acá se juntan los días
// en bloques y se promedia PONDERANDO POR VOLUMEN — un día de 3 comentarios no
// puede pesar igual que uno de 200.
//
// El paso sale del RANGO VISIBLE, no de una preferencia: lo que importa es cuántos
// puntos entran en pantalla. Con ~600 px de ancho útil, más de ~120 puntos ya se
// pisan entre sí.
const PASOS_SERIE = [
  { hastaDias: 45, dias: 1, etiqueta: "por día" },
  { hastaDias: 150, dias: 7, etiqueta: "promedio por semana" },
  { hastaDias: 400, dias: 14, etiqueta: "promedio por quincena" },
  { hastaDias: Infinity, dias: 30, etiqueta: "promedio por mes" },
];

function pasoDeSerie(dias: number) {
  return PASOS_SERIE.find((p) => dias <= p.hastaDias) ?? PASOS_SERIE[PASOS_SERIE.length - 1];
}

// El automático elige BIEN por defecto, pero elegir por vos no es lo mismo que
// elegir por vos SIN OPCIÓN: mirando cuatro años, el paso mensual es el legible y
// aun así alguien puede querer la semana para ubicar un episodio corto. `0` =
// automático, que sigue siendo el default.
const PASOS_ELEGIBLES = [
  { dias: 0, label: "Automático" },
  { dias: 1, label: "Por día" },
  { dias: 7, label: "Por semana" },
  { dias: 14, label: "Por quincena" },
  { dias: 30, label: "Por mes" },
];

// A partir de acá los puntos se pisan entre sí sobre ~600 px útiles. No se BLOQUEA
// la elección —el ruido de una serie densa se ve, y verlo es parte de entender por
// qué el automático agrega—, pero se dice cuántos puntos son.
const PUNTOS_APRETADOS = 150;

/** Junta los puntos diarios en bloques de `dias`, ponderando por volumen.
 *
 *  Los bloques se anclan a una ÉPOCA FIJA y no al primer punto de la serie: si
 *  dependieran del rango consultado, cambiar el filtro reagruparía los días de a
 *  bloques distintos y la curva se movería sin que cambie un solo dato. Es el mismo
 *  criterio que `EPOCA_BLOQUES` en la detección del backend.
 *
 *  `es_anomalia` y `severidad` se propagan con el MÁXIMO del bloque, no con el
 *  promedio: una quincena que contiene una semana marcada sigue estando marcada.
 *  Promediarlas apagaría justamente lo que hay que ver. */
const EPOCA_SERIE = Date.UTC(2022, 0, 3); // lunes, anterior a todo el corpus
const DIA_MS = 86_400_000;

function agruparSerie(puntos: PuntoEvolucion[], dias: number): PuntoEvolucion[] {
  if (dias <= 1 || puntos.length === 0) return puntos;
  const bloques = new Map<number, {
    num: number; den: number; n: number; anom: boolean; sev: number; motivos: Set<string>;
  }>();
  for (const p of puntos) {
    const ts = new Date(`${p.fecha}T00:00:00Z`).getTime();
    const idx = Math.floor((ts - EPOCA_SERIE) / (dias * DIA_MS));
    const b = bloques.get(idx) ?? {
      num: 0, den: 0, n: 0, anom: false, sev: 0, motivos: new Set<string>(),
    };
    // Ponderado por volumen: un día de 3 comentarios no pesa como uno de 200.
    if (p.indice != null && p.n_comentarios > 0) {
      b.num += p.indice * p.n_comentarios;
      b.den += p.n_comentarios;
    }
    b.n += p.n_comentarios;
    b.anom = b.anom || p.es_anomalia;
    b.sev = Math.max(b.sev, p.severidad ?? 0);
    for (const m of p.motivos ?? []) b.motivos.add(m);
    bloques.set(idx, b);
  }
  return [...bloques.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([idx, b]) => ({
      // La fecha del bloque es su INICIO: con eje temporal, poner el centro
      // desalinearía la curva de las bandas de eventos, que van por fecha real.
      fecha: new Date(EPOCA_SERIE + idx * dias * DIA_MS).toISOString().slice(0, 10),
      indice: b.den > 0 ? b.num / b.den : null,
      confianza: null,
      n_comentarios: b.n,
      es_anomalia: b.anom,
      severidad: b.sev,
      motivos: [...b.motivos],
    }));
}

function lineOption(
  serie: SerieEvolucion,
  eventos: EventoItem[],
  seleccion?: { desde?: string; hasta?: string },
  pasoDias = 1,
): Record<string, unknown> {
  // Se agrupa ANTES de armar nada: el resto de la función trabaja sobre la serie
  // ya agregada, así que la escala del eje, los marcadores de anomalía y el
  // tooltip quedan todos consistentes con lo que se dibuja.
  const puntos = agruparSerie(serie.puntos, pasoDias);
  serie = { ...serie, puntos };
  const fechas = serie.puntos.map((p) => p.fecha);
  // Pares [fecha, valor] porque el eje es TEMPORAL, no categórico. Ver la nota del
  // `xAxis` más abajo: con `category`, un salto de 126 días ocupaba lo mismo que uno
  // de un día.
  const valores: [string, number | null][] = serie.puntos.map((p) => [
    p.fecha,
    p.indice == null ? null : Number(p.indice.toFixed(1)),
  ]);
  // Anomalías: círculos sobre la curva, NO pins.
  //
  // Iban como `markPoint` con `symbol: "pin"` y `symbolSize: 32`. Con 26 anomalías en
  // 900 px de ancho, esos pines se superponían formando dos manchas rojas donde no se
  // distinguía ni cuántas eran ni dónde caían. Un círculo de 6-12 px escalado por
  // severidad ocupa una décima parte y además ordena: el tamaño ya dice cuál importa.
  const anomalias = serie.puntos
    .filter((p) => p.es_anomalia && p.indice != null)
    .map((p) => ({
      value: [p.fecha, Number((p.indice as number).toFixed(1))],
      severidad: p.severidad ?? 0,
      motivos: p.motivos ?? [],
      n: p.n_comentarios,
    }));
  const desde = fechas[0];
  const hasta = fechas[fechas.length - 1];
  // SOLO los eventos que interrumpen la actividad van SOBRE el gráfico.
  //
  // Antes iban todos, y con el calendario académico cargado (125 eventos) el gráfico
  // quedaba ilegible: cada evento dibujaba dos líneas verticales de 0 a 100 más dos
  // etiquetas, o sea 250 líneas encima de la serie. El ciclo regular —matrícula,
  // receso, exámenes, titulación— es CONTEXTO, y su lugar es la franja de abajo.
  // Un paro sí cambia cómo se lee la curva, y por eso se queda acá.
  // Cada evento se dibuja según su ROL y según cuánto ocupe del rango visible.
  //
  // El segundo criterio es el que hace que la vista se adapte al zoom sin ninguna
  // configuración: en «Todo» (4 años) un examen de cinco días no llega al mínimo y
  // sale como línea; al filtrar a 90 días, el mismo examen supera el umbral y pasa a
  // ser una franja con su ancho real.
  const todosVisibles = eventosVisiblesEnSerie(serie, eventos);
  const msRango = Math.max(1, new Date(hasta).getTime() - new Date(desde).getTime());
  const pctDelRango = (e: EventoVisible) =>
    ((new Date(e.finVisible).getTime() - new Date(e.inicioVisible).getTime()) / msRango) * 100;

  const eventosVisibles = todosVisibles.filter((e) => pctDelRango(e) >= MIN_PCT_PARA_AREA);
  const eventosPuntuales = todosVisibles.filter((e) => pctDelRango(e) < MIN_PCT_PARA_AREA);

  const bandas: unknown[] = eventosVisibles.map((e) => {
    const rol = rolDe(e.tipo);
    const base = COLOR_EVENTO_LINEA[e.tipo] ?? "#94a3b8";
    return [
      {
        xAxis: e.inicioVisible,
        itemStyle: {
          // El color sale del mismo hex de la categoría con la opacidad de su ROL:
          // así el contraste entre un semestre y un paro no depende de que alguien
          // acierte dos rgba() a mano en tablas separadas.
          color: `${base}${Math.round(OPACIDAD_AREA[rol] * 255).toString(16).padStart(2, "0")}`,
        },
        label: { show: false },
      },
      { xAxis: e.finVisible },
    ];
  });

  // Selección de fecha. Cuando es un RANGO (por ejemplo al hacer clic en un paro de
  // la banda de abajo) se pinta el ÁREA completa, no solo los dos bordes: la pregunta
  // que sigue a "seleccioné el paro" es "¿cómo venía la curva DURANTE el paro?", y
  // dos líneas sueltas obligan a seguirlas con el dedo para saber qué queda adentro.
  const marcas = Array.from(
    new Set([seleccion?.desde, seleccion?.hasta].filter((d): d is string => !!d && desde != null && d >= desde && d <= hasta)),
  );
  if (seleccion?.desde && seleccion?.hasta && seleccion.desde !== seleccion.hasta) {
    bandas.push([
      {
        xAxis: seleccion.desde,
        itemStyle: { color: "rgba(224,170,78,0.16)" },
        label: { show: false },
      },
      { xAxis: seleccion.hasta },
    ]);
  }
  const markLineData: Record<string, unknown>[] = [
    {
      yAxis: 50,
      label: { show: true, formatter: "Neutralidad 50", color: "rgba(203,213,225,0.8)", position: "insideEndTop" },
      lineStyle: { color: "rgba(203,213,225,0.38)", width: 1, type: "dashed" },
    },
  ];
  for (const d of marcas) {
    markLineData.push({
      xAxis: d,
      label: { show: true, formatter: fmtDiaCorto(d), color: COLOR_COPPER, position: "insideEndTop" },
      lineStyle: { color: COLOR_COPPER, width: 2.5, type: "solid" },
    });
  }
  // LOS EVENTOS DE UN DÍA, como línea vertical de altura completa.
  //
  // Un `markArea` de un día es un área de menos de un pixel: no se ve. Por eso los
  // puntuales van como línea de 0 a 100 en el color de su categoría — la misma
  // presencia que tiene la banda de un paro, que es lo que hace falta para saber que
  // ese día pasó algo.
  //
  // (Antes acá había punteados que iban del piso al 25% marcando SOLO el inicio de
  // eventos que además ya tenían su banda. Eso sí era ruido; esto es lo contrario:
  // la única marca de eventos que si no, no se verían.)
  const lineasEventos: Record<string, unknown>[] = eventosPuntuales.map((e) => ({
    type: "line",
    symbol: "none",
    silent: true,
    animation: false,
    name: e.nombre,
    // El ALTO es lo que separa un rol de otro. Un paro cruza toda la altura porque
    // cambia cómo se lee la curva; un cierre de matrícula se queda en la base porque
    // sirve para ubicarse y nada más. Antes todos cruzaban de 0 a 100 y por eso 21
    // hitos administrativos tapaban la serie.
    lineStyle: {
      color: COLOR_EVENTO_LINEA[e.tipo] ?? "#94a3b8",
      // Los tres roles, también acá. Un receso corto que cae a línea seguía cruzando
      // toda la altura al 50 % y pesaba como un paro, que es justo la confusión que
      // los roles vienen a resolver.
      width: ANCHO_LINEA_ROL[rolDe(e.tipo)],
      opacity: OPACIDAD_LINEA[rolDe(e.tipo)],
    },
    tooltip: { show: false },
    z: 3,
    data: [
      [e.inicioVisible, 0],
      [e.inicioVisible, rolDe(e.tipo) === "puntual" ? ALTO_TICK_PUNTUAL : 100],
    ],
  }));
  const etiquetasEventos: Record<string, unknown>[] = [];

  return {
    animation: true,
    animationDuration: 140,
    animationDurationUpdate: 120,
    animationEasing: "linear",
    animationEasingUpdate: "linear",
    tooltip: { trigger: "axis" },
    axisPointer: { snap: true, lineStyle: { color: COLOR_COPPER, width: 1, type: "dashed" } },
    // `top` bajó de 34 a 18: los pines de 32 px se salían por arriba y obligaban a
    // reservar ese aire. Con círculos ya no hace falta y la curva gana altura.
    grid: { left: 40, right: 24, top: 18, bottom: 26 },
    // EJE TEMPORAL, no categórico. Es la diferencia entre una línea de tiempo y una
    // secuencia de puntos.
    //
    // Con `category`, ECharts reparte las 227 fechas en 227 posiciones IGUALES, sin
    // mirar cuánto tiempo hay entre una y otra. Medido sobre el corpus: la serie
    // tiene 123 huecos, y el mayor mete **126 días en un solo paso del eje**
    // (2023-05-09 → 2023-09-12). Un tramo de cuatro meses sin datos ocupaba lo mismo
    // que un día con datos, así que la pendiente de la curva no significaba nada y
    // las bandas de eventos caían donde no correspondía.
    //
    // Con `time` el espacio es proporcional al tiempo real: los meses sin datos
    // quedan como un tramo continuo entre los que sí tienen, la línea los atraviesa,
    // y la banda del calendario —que se posiciona por fecha— por fin coincide con el
    // eje en TODO el rango y no solo en los extremos.
    xAxis: {
      type: "time",
      // `min`/`max` EXPLÍCITOS en los extremos de la serie. Sin esto ECharts estira
      // el eje hasta un corte redondo (el inicio del mes, por ejemplo), así que el
      // eje abarca un rango mayor que el de la banda de abajo —que se posiciona
      // entre la primera y la última fecha— y los eventos quedan corridos. Medido:
      // 4 px de desvío en el extremo derecho. Con los extremos fijos, 0.
      min: fechas[0],
      max: fechas[fechas.length - 1],
      // `hideOverlap` deja solo las etiquetas que entran sin pisarse; con eje
      // temporal ECharts además elige cortes redondos (meses, años) por su cuenta.
      axisLabel: { fontSize: 9, hideOverlap: true },
    },
    // 0-100 FIJO a propósito. Un eje automático haría que ±3 puntos de ruido de
    // muestreo llenaran la pantalla y parecieran un derrumbe; además dejaría la línea
    // de neutralidad fuera de cuadro. La escala comparable vale más que el detalle.
    yAxis: { type: "value", min: 0, max: 100, splitNumber: 4 },
    series: [
      {
        // `smooth` bajo (0.15) y no 0.36: ahora cada punto es un promedio real de
        // días, así que la curva ya no necesita que la redondeen para leerse — y
        // curvarla de más inventaría trayectorias entre puntos que no existen.
        type: "line", smooth: 0.15, showSymbol: false, data: valores,
        // La línea CRUZA los tramos sin datos en vez de cortarse. Con 123 huecos, una
        // línea partida se leería como 124 series sueltas; unida se ve la trayectoria,
        // y el hueco igual queda a la vista porque el eje es temporal: hay un tramo
        // largo y recto donde no se midió nada.
        connectNulls: true,
        lineStyle: { color: COLOR_CYAN, width: 2.4, cap: "round", join: "round" },
        areaStyle: { color: "rgba(79,156,240,0.10)" },
        emphasis: { focus: "series" },
        markLine: { silent: true, symbol: "none", data: markLineData },
        markArea: { silent: true, data: bandas },
      },
      {
        // Anomalías. Serie propia y no `markPoint` para poder darles tooltip: antes
        // el pin mostraba un "!" y había que ir a la pestaña Alertas para saber por qué.
        type: "scatter",
        name: "Anomalías",
        data: anomalias,
        symbolSize: (d: { severidad?: number }) => 6 + Math.round((d?.severidad ?? 0) * 6),
        // ANILLO HUECO Y BLANCO, no un punto rojo lleno.
        //
        // Iban en `COLOR_NEG`, que es EXACTAMENTE el rojo de paro y toma, así que
        // parecían marcas de conflicto sueltas y no se entendía qué eran ni por qué
        // aparecían lejos de las bandas. No son eventos: son cambios inusuales que
        // detecta el algoritmo sobre la serie. Un anillo hueco los separa de toda la
        // paleta del calendario —que es de bloques llenos— y comunica "medición",
        // no "hecho".
        itemStyle: { color: "transparent", borderColor: "#e2e8f0", borderWidth: 2 },
        z: 14,
        tooltip: {
          trigger: "item",
          formatter: (p: { data?: { value?: [string, number]; n?: number; motivos?: string[] } }) => {
            const d = p.data ?? {};
            const [fecha, idx] = d.value ?? ["", 0];
            const motivos = (d.motivos ?? []).join(", ");
            return `<b>${fmtDiaCorto(String(fecha))}</b> · índice ${idx}<br/>`
              + `${d.n ?? 0} comentarios`
              + (motivos ? `<br/><span style="opacity:.75">cambio inusual: ${motivos}</span>` : "");
          },
        },
      },
      ...lineasEventos,
      {
        type: "scatter",
        silent: true,
        data: etiquetasEventos,
        symbol: "roundRect",
        symbolSize: [82, 18],
        encode: { x: 0, y: 1 },
        itemStyle: { color: (params: { data?: { color?: string } }) => params.data?.color ?? "#94a3b8" },
        label: {
          show: true,
          formatter: (params: { data?: { label?: string } }) => params.data?.label ?? "",
          color: "#0b1424",
          fontSize: 10,
          fontWeight: 800,
        },
        z: 13,
        tooltip: { show: false },
      },
    ],
  };
}

function fmtDiaCorto(s: string): string {
  return new Date(`${s}T00:00:00`).toLocaleDateString("es-CL", { day: "2-digit", month: "short" });
}

const FILTRO_INICIAL: Filtro = { dias: DEFAULT_DIAS, pesoLikes: 1, vidaMedia: 30 };

// --------------------------------------------------------------------------- #
// NAVEGACIÓN ENTRE PANTALLAS — que un dato lleve a su evidencia.
// --------------------------------------------------------------------------- #
// El Resumen contesta «¿cómo estamos?» y las otras pestañas contestan «¿por qué?».
// Hasta ahora esas dos preguntas estaban en pantallas separadas y el puente había
// que cruzarlo a mano: leer «Organización estudiantil · 20 % adverso», cambiar de
// pestaña, buscar el filtro de tema, elegirlo. Cuatro pasos entre un dato y la
// conversación que lo sostiene, y por eso casi nadie los daba.
//
// Un salto lleva TRES cosas, y las tres hacen falta:
//   1. la vista destino,
//   2. el FILTRO que aísla lo que se venía mirando,
//   3. la SUB-PESTAÑA correcta — llevar a "Comparar" sin decir a cuál de sus tres
//      vistas deja al director buscando.
export type VistaPercepcion =
  | "resumen" | "alertas" | "comparar" | "conversacion" | "curacion" | "simulacion";
export type SubComparar = "estado" | "temas" | "movimiento";
export type SubConversacion = "tiempo" | "palabras" | "publicaciones";

export type Destino = {
  vista: VistaPercepcion;
  /** Patch al filtro global. Es lo que hace que el destino muestre ESE dato. */
  filtro?: Partial<Filtro>;
  sub?: SubComparar | SubConversacion;
  /** Qué se venía mirando. Se muestra al aterrizar; sin esto el salto es mudo. */
  desde?: string;
};

type Rastro = { desde: string; filtroPrevio: Filtro };

/** Barra que explica por qué esta pantalla muestra lo que muestra, y permite volver.
 *
 * Sin ella un salto con filtro es indistinguible de un tablero roto: el director ve
 * de golpe 400 comentarios en vez de 8.000 y no tiene forma de saber que fue él
 * quien lo pidió. Restaurar el filtro anterior —no "limpiar"— es lo que la vuelve
 * un botón de VOLVER y no un segundo "limpiar filtros".
 */
function RastroNavegacion({
  rastro, onVolver,
}: { rastro: Rastro; onVolver: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl border border-[var(--portal-cyan)]/30 bg-[var(--portal-cyan)]/[0.07] px-4 py-2 text-xs">
      <span className="text-slate-400">Viendo el detalle de</span>
      <strong className="text-[var(--portal-cyan)]">{rastro.desde}</strong>
      <button
        type="button"
        onClick={onVolver}
        className="ml-auto rounded-full border border-white/15 bg-white/[0.06] px-3 py-1 font-semibold text-slate-200 transition hover:bg-white/[0.12]"
      >
        ← Volver al resumen
      </button>
    </div>
  );
}

function FiltroSelect({
  label, value, onChange, children,
}: { label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    // `min-w-0` en el label además del select: sin él, el ancho intrínseco del
    // contenido gana igual dentro de un grid y el control vuelve a desbordarse.
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={SELECT}>
        {children}
      </select>
    </label>
  );
}

/**
 * Formulario de retroalimentación EXTERNO (Google Forms), si está configurado.
 *
 * Existe porque el formulario interno de la Torre vive en la rama de
 * integración, que va cientos de commits detrás de main: hasta que se porte y
 * se despliegue no hay ninguna pantalla donde un académico pueda responderlo, y
 * la fase de prueba no tiene por qué esperar a eso.
 *
 * Es una URL pública de Google Forms, no un secreto: va como variable de entorno
 * para poder cambiar el formulario —o apagar el botón dejándola vacía— sin tocar
 * el código ni recompilar. Cuando el formulario interno llegue a main basta con
 * no definirla y el botón vuelve solo al panel de Formularios.
 *
 * El generador del formulario es `scripts/crear_form_retroalimentacion_termometro.gs`.
 */
const URL_RETROALIMENTACION = (process.env.NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL ?? "").trim();

interface PercepcionPanelProps {
  /**
   * Lleva al formulario INTERNO de retroalimentación (pestaña Formularios).
   * Opcional: el panel se monta también fuera del shell (rutas de preview), y
   * ahí no hay adónde ir. Sin handler y sin `URL_RETROALIMENTACION` el botón NO
   * se dibuja, en vez de dibujarse muerto.
   *
   * `URL_RETROALIMENTACION` le gana: mientras la fase de prueba corra sobre
   * Google Forms, ese es el destino aunque el panel interno exista.
   */
  onIrAFormulario?: () => void;
}

export function PercepcionPanel({ onIrAFormulario }: PercepcionPanelProps = {}) {
  // Un solo literal para los DOS estados de filtro (el vivo y el estabilizado):
  // si arrancaran con objetos distintos, el primer render dispararía una carga de
  // más antes de que el debounce los sincronice.
  const [filtro, setFiltro] = useState<Filtro>(FILTRO_INICIAL);
  const [opciones, setOpciones] = useState<FiltrosResponse | null>(null);
  const [resumen, setResumen] = useState<ResumenPercepcion | null>(null);
  const [serie, setSerie] = useState<SerieEvolucion | null>(null);
  const [emociones, setEmociones] = useState<EmocionItem[]>([]);
  const [eventos, setEventos] = useState<EventoItem[]>([]);
  // Marcas de contexto: tipos APAGADOS en el gráfico (por defecto todos encendidos) +
  // el ABM (lista completa, catálogo de tipos y el formulario de alta/edición).
  // UN SOLO control para el gráfico y para la banda de abajo. Antes cada uno tenía
  // su propio estado y podían discrepar: la banda mostraba algo que el gráfico no, y
  // había que descubrir cuál de los dos controles mandaba.
  const [tiposOcultos, setTiposOcultos] = useState<Set<string>>(
    () => ocultosDePreset(PRESET_INICIAL),
  );
  // Qué preset coincide con el estado actual. No se guarda cuál se eligió: se DEDUCE,
  // así tocar un toggle suelto deja de resaltar el preset sin que haya que
  // sincronizar dos estados que pueden mentirse entre sí.
  const presetActivo = useMemo(() => {
    const encendidos = TODOS_LOS_TIPOS.filter((t) => !tiposOcultos.has(t)).sort().join("|");
    return PRESETS.find((p) => [...p.tipos].sort().join("|") === encendidos)?.id ?? null;
  }, [tiposOcultos]);
  const [tiposEvento, setTiposEvento] = useState<TipoEventoOpcion[]>([]);
  const [eventosTodos, setEventosTodos] = useState<EventoItem[]>([]);
  const [abmAbierto, setAbmAbierto] = useState(false);
  const [evtEdit, setEvtEdit] = useState<EventoItem | null>(null);
  // Dos "hojas" sobre el MISMO filtro global: el tablero (series y detalle) y la
  // síntesis ejecutiva. Separadas a propósito — responden preguntas distintas y
  // mezclarlas desordena la lectura.
  // Cinco pestañas, una PREGUNTA cada una:
  //   resumen      -> ¿cómo estamos?          (una pantalla, sin sliders ni z-scores)
  //   alertas      -> ¿qué requiere atención? (términos críticos + semanas anómalas)
  //   comparar     -> ¿dónde está el problema?(por tema y por área, UNA vez cada uno)
  //   conversacion -> ¿qué se está diciendo?  (evolución, comentarios, nube, emociones)
  //   curacion     -> corregir el modelo      (tarea de analista, no de dirección)
  //
  // "Explorar" se partió en COMPARAR y CONVERSACIÓN porque mezclaba dos preguntas
  // distintas —rankear entidades y leer la conversación— y era, de hecho, el viejo
  // Tablero con otro nombre: el cajón de lo que no entraba en ningún lado.
  //
  // La RECENCIA (peso por likes, vida del comentario) queda confinada a
  // Conversación, que es la única vista donde el tiempo importa. Resumen, Alertas
  // y Comparar leen todas "promedio del período", así que ya no hay dos números
  // para el mismo objeto: el tema "Otros" daba 58.7 en una pestaña y 64.3 en otra.
  const [vista, setVista] = useState<VistaPercepcion>("resumen");
  // ¿Mostrar las pestañas internas? Simulación: equipo DAI o administrador.
  // Curación (con «Revisar comentarios»): SOLO administradores, porque muestra texto
  // crudo de comentarios (ver `administrador` más abajo).
  //
  // Arranca en `false` y se resuelve DESPUÉS del montaje, no durante el render:
  // `localStorage` no existe en el servidor, y leerlo directo haría que el HTML
  // del servidor y el del cliente difieran (error de hidratación de Next). Partir
  // en `false` además es el lado correcto si algo falla: esconde de más.
  const [equipoDai, setEquipoDai] = useState(false);
  const [administrador, setAdministrador] = useState(false);
  useEffect(() => {
    setEquipoDai(esEquipoDai());
    setAdministrador(esAdmin());
  }, []);
  // Guía de lectura: siempre CERRADA al entrar, se abre a pedido.
  //
  // Llegó a abrirse sola la primera vez, con la apertura recordada en
  // localStorage. Se sacó: la guía ocupa media pantalla y el tablero es lo que la
  // persona vino a ver, así que abrirla sin que nadie la pida empuja el contenido
  // hacia abajo justo en el momento en que se está formando la primera impresión.
  // Quien la necesita la abre; quien no, no la pisa. Sin estado que recordar,
  // tampoco hay nada que persistir.
  const [guiaAbierta, setGuiaAbierta] = useState(false);
  // Sub-pestaña de COMPARAR. Vive acá y no adentro del componente porque un salto
  // desde el Resumen tiene que poder abrir la sub-pestaña correcta: llevar a
  // "Comparar" sin decir a cuál de sus tres vistas deja al director buscando.
  const [subComp, setSubComp] = useState<SubComparar>("estado");
  // Agregación de la línea de tiempo. 0 = automática según el rango.
  //
  // El default es SEMANA y no el automático: es la unidad en la que se lee la vida
  // universitaria —una semana de clases, una semana de paro— y mantenerla fija
  // hace comparables dos vistas con rangos distintos, que es lo que el automático
  // rompía al cambiar de mes a quincena sin avisar. El automático sigue disponible
  // como opción para quien prefiera la lectura más limpia de cada rango.
  const [pasoManual, setPasoManual] = useState(7);
  // De dónde vino el salto. Es lo que convierte un cambio de pestaña en una
  // NAVEGACIÓN: sin esto, al aterrizar en Conversación filtrada por un tema, el
  // tablero muestra menos datos y nadie sabe por qué. Ver `RastroNavegacion`.
  const [rastro, setRastro] = useState<Rastro | null>(null);
  // Subsección de Conversación: la línea de tiempo y la nube compiten por la
  // atención, así que se turnan en vez de apilarse.
  const [subConv, setSubConv] = useState<"tiempo" | "palabras" | "publicaciones">("tiempo");
  const [subCur, setSubCur] = useState<"calidad" | "revisar" | "temas">("calidad");
  // Copia del filtro que solo avanza cuando el usuario deja de mover controles
  // (ver el debounce más abajo). Es la que consumen el tablero y la síntesis.
  const [filtroEstable, setFiltroEstable] = useState<Filtro>(FILTRO_INICIAL);
  const [evtForm, setEvtForm] = useState<EventoPayload>({ nombre: "", tipo: "receso", fecha_inicio: "", fecha_fin: "" });
  const [evtMsg, setEvtMsg] = useState<string | null>(null);
  const [evtBusy, setEvtBusy] = useState(false);
  // Las anomalías se fueron a la pestaña Alertas junto con los términos críticos:
  // las dos responden "¿hay algo que mirar?" y estaban en pestañas distintas.
  const [comentarios, setComentarios] = useState<ComentarioReciente[]>([]);
  const [comFiltro, setComFiltro] = useState<ComentariosFiltro>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Corrección inline de un comentario (clickeás → editás sentimiento/emoción + por qué)
  const [opcScoring, setOpcScoring] = useState<OpcionesScoring>(
    { sentimientos: [], emociones: [], posturas: [] });
  const [editId, setEditId] = useState<number | null>(null);
  const [editSent, setEditSent] = useState("");
  const [editEmo, setEditEmo] = useState("");
  const [editJust, setEditJust] = useState("");
  const [editMsg, setEditMsg] = useState<string | null>(null);
  // Espejo de la serie para el manejador de clic del gráfico (evita capturar un valor
  // viejo: el handler se registra una sola vez en onReady y lee siempre lo último).
  const serieRef = useRef<SerieEvolucion | null>(null);
  serieRef.current = serie;

  useEffect(() => {
    percepcionApi.filtros().then(setOpciones).catch(() => setOpciones(null));
    percepcionApi.scoringOpciones().then(setOpcScoring).catch(() => undefined);
    percepcionApi.eventosTipos().then((r) => setTiposEvento(r.items)).catch(() => undefined);
  }, []);

  // ---- Marcas de contexto (ABM + toggles) ----
  const recargarEventos = useCallback(async () => {
    // El overlay del gráfico (ventana) y la lista completa del ABM son dos vistas
    // distintas de lo mismo: tras cada alta/baja hay que refrescar las dos.
    const [todos, deVentana] = await Promise.all([
      percepcionApi.eventosTodos().catch(() => ({ items: [] as EventoItem[] })),
      percepcionApi.eventos(36500).catch(() => ({ items: [] as EventoItem[] })),
    ]);
    setEventosTodos(todos.items);
    setEventos(deVentana.items);
  }, []);

  /** Apaga o prende TODOS los tipos de una categoría a la vez. */
  const toggleCategoria = (tipos: string[]) =>
    setTiposOcultos((prev) => {
      const next = new Set(prev);
      const encendida = tipos.some((t) => !next.has(t));
      // Si alguno está encendido, se apaga la categoría entera; si no, se prende toda.
      // Sin ese criterio, una categoría a medias dejaría el chip en un estado que no
      // corresponde a lo que se ve en el gráfico.
      for (const t of tipos) {
        if (encendida) next.add(t);
        else next.delete(t);
      }
      return next;
    });

  const nuevoEvento = () => {
    setEvtEdit(null);
    setEvtForm({ nombre: "", tipo: "receso", fecha_inicio: "", fecha_fin: "" });
    setEvtMsg(null);
    setAbmAbierto(true);
  };

  const editarEvento = (e: EventoItem) => {
    setEvtEdit(e);
    setEvtForm({
      nombre: e.nombre, tipo: e.tipo, fecha_inicio: e.fecha_inicio,
      fecha_fin: e.fecha_fin, descripcion: e.descripcion ?? "", ambito: e.ambito ?? "",
    });
    setEvtMsg(null);
    setAbmAbierto(true);
  };

  const guardarEvento = async () => {
    if (!evtForm.nombre.trim() || !evtForm.fecha_inicio) {
      setEvtMsg("Nombre y fecha de inicio son obligatorios.");
      return;
    }
    setEvtBusy(true);
    setEvtMsg(null);
    try {
      const payload: EventoPayload = { ...evtForm, fecha_fin: evtForm.fecha_fin || null };
      if (evtEdit?.id != null) await percepcionApi.actualizarEvento(evtEdit.id, payload);
      else await percepcionApi.crearEvento(payload);
      await recargarEventos();
      setEvtMsg(evtEdit ? "Marca actualizada." : "Marca creada.");
      setEvtEdit(null);
      setEvtForm({ nombre: "", tipo: "receso", fecha_inicio: "", fecha_fin: "" });
    } catch (err) {
      setEvtMsg(err instanceof Error ? err.message : "No se pudo guardar.");
    } finally {
      setEvtBusy(false);
    }
  };

  const borrarEvento = async (e: EventoItem) => {
    if (e.id == null) return;
    setEvtBusy(true);
    setEvtMsg(null);
    try {
      await percepcionApi.eliminarEvento(e.id);
      await recargarEventos();
      setEvtMsg("Marca eliminada.");
      if (evtEdit?.id === e.id) setEvtEdit(null);
    } catch (err) {
      setEvtMsg(err instanceof Error ? err.message : "No se pudo eliminar.");
    } finally {
      setEvtBusy(false);
    }
  };

  const abrirEdicion = (c: ComentarioReciente) => {
    setEditMsg(null);
    if (editId === c.id) { setEditId(null); return; }
    setEditId(c.id);
    setEditSent(c.sentimiento);
    setEditEmo(c.emocion ?? "sin_emocion");
    setEditJust("");
  };

  const guardarCorreccion = async (c: ComentarioReciente) => {
    const cambioSent = editSent !== c.sentimiento;
    const cambioEmo = editEmo !== (c.emocion ?? "sin_emocion");
    if (!cambioSent && !cambioEmo) { setEditMsg("No cambiaste nada."); return; }
    if (!editJust.trim()) { setEditMsg("Escribe el porqué antes de guardar."); return; }
    try {
      if (cambioSent) await percepcionApi.corregirSentimiento(c.id, editSent, editJust.trim());
      if (cambioEmo) await percepcionApi.corregirEmocion(c.id, editEmo, editJust.trim());
      setEditId(null);
      const com = await percepcionApi.comentarios(filtro, 20, comFiltro);
      setComentarios(com.items);
      void cargar(filtro);
    } catch (e) {
      setEditMsg(e instanceof Error ? e.message : "No se pudo guardar");
    }
  };

  const cargar = useCallback(async (f: Filtro) => {
    setLoading(true);
    setError(null);
    try {
      // Carga critica primero y con baja concurrencia. Si disparamos todos los
      // bloques juntos, el navegador puede abortar alguna request tras el preflight
      // y el tablero queda en falso "sin datos" aunque el backend tenga respuesta.
      const r = await percepcionApi.resumen(f);
      const e = await percepcionApi.evolucion(f);
      setResumen(r);
      setSerie(e);

      const fallas: string[] = [];
      try {
        const resp = await percepcionApi.emociones(f);
        setEmociones(resp.items);
      } catch {
        setEmociones([]);
        fallas.push("emociones");
      }
      try {
        const resp = await percepcionApi.eventos(Math.min(36500, Math.max(120, f.dias)));
        setEventos(resp.items);
      } catch {
        setEventos([]);
      }
      if (fallas.length > 0) {
        setError(`No se pudieron actualizar estos bloques: ${fallas.join(", ")}. Se muestran los datos disponibles.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar percepcion");
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounce: los sliders (peso/recencia) disparan onChange en cada pixel. Sin
  // esto, arrastrarlos lanzaría decenas de recargas × 8 endpoints → ráfaga que
  // gatilla el rate-limit del backend (429 sin CORS = "Failed to fetch"). Esperamos
  // a que el usuario pare (~350 ms) y recargamos UNA vez.
  //
  // El filtro ESTABILIZADO se comparte con la síntesis, que hace su propio fetch:
  // si cada vista debounceara por su cuenta, un solo arrastre dispararía dos
  // ráfagas y volvería el 429. Un único reloj para todo el panel.
  useEffect(() => {
    const t = setTimeout(() => setFiltroEstable(filtro), 350);
    return () => clearTimeout(t);
  }, [filtro]);

  // Explorar NO se recarga mientras se mira otra pestaña: son ~7 endpoints que
  // nadie está viendo y que igual gastan el rate-limit compartido.
  useEffect(() => {
    if (vista !== "conversacion") return;
    void cargar(filtroEstable);
  }, [cargar, filtroEstable, vista]);

  // Comentarios recientes: filtro LOCAL (sentimiento/emoción) que recarga SOLO la
  // lista, sin re-pegarle a los gráficos. También reacciona al filtro global.
  useEffect(() => {
    const t = setTimeout(() => {
      // Al leer un día/rango concreto queremos TODO lo que se dijo (incl. neutrales),
      // salvo que el usuario haya elegido un chip de sentimiento explícito.
      const hayFecha = !!(filtro.fechaDesde || filtro.fechaHasta);
      const cf = { ...comFiltro, incluirNeutrales: hayFecha && !comFiltro.sentimiento };
      percepcionApi.comentarios(filtro, hayFecha ? 100 : 20, cf)
        .then((r) => setComentarios(r.items))
        .catch(() => setComentarios([]));
    }, 650);
    return () => clearTimeout(t);
  }, [filtro, comFiltro]);

  const up = (patch: Partial<Filtro>) => setFiltro((prev) => ({ ...prev, ...patch }));

  /** Salta a la pantalla que SOSTIENE un dato: aplica su filtro y abre su sub-vista.
   *
   * Guarda el filtro previo para que «Volver» restaure lo que había, no un estado
   * limpio: quien saltó desde el Resumen con una sede elegida espera encontrarla
   * al volver. Ver `RastroNavegacion` y el tipo `Destino`.
   */
  const irA = useCallback((d: Destino) => {
    if (d.desde) setRastro((prev) => prev ?? { desde: d.desde!, filtroPrevio: filtro });
    else setRastro(null);
    if (d.filtro) setFiltro((prev) => ({ ...prev, ...d.filtro }));
    if (d.vista === "comparar" && d.sub) setSubComp(d.sub as SubComparar);
    if (d.vista === "conversacion" && d.sub) setSubConv(d.sub as SubConversacion);
    setVista(d.vista);
  }, [filtro]);

  const volverDelRastro = useCallback(() => {
    setRastro((r) => {
      if (r) setFiltro(r.filtroPrevio);
      return null;
    });
    setVista("resumen");
  }, []);

  // --- Filtro GLOBAL por FECHA (día puntual o rango) ---
  // Sincronizado: lo setea el selector Desde/Hasta Y el clic en el gráfico de evolución.
  const setFechaDesde = (v: string) =>
    setFiltro((p) => {
      const fechaDesde = v || undefined;
      let fechaHasta = p.fechaHasta;
      if (fechaDesde && fechaHasta && fechaHasta < fechaDesde) fechaHasta = fechaDesde; // ordena
      return { ...p, fechaDesde, fechaHasta };
    });
  const setFechaHasta = (v: string) =>
    setFiltro((p) => {
      const fechaHasta = v || undefined;
      let fechaDesde = p.fechaDesde;
      if (fechaDesde && fechaHasta && fechaHasta < fechaDesde) fechaDesde = fechaHasta;
      return { ...p, fechaDesde, fechaHasta };
    });
  const limpiarFecha = () => setFiltro((p) => ({ ...p, fechaDesde: undefined, fechaHasta: undefined }));

  // Clic en el gráfico de evolución → selecciona ESE día (mapea el pixel al día más
  // cercano del eje X). Se registra una sola vez; lee la serie viva vía serieRef.
  const onEvolucionReady = useCallback((chart: EChartsInstance) => {
    chart.getZr().on("click", (e) => {
      const pt = [e.offsetX, e.offsetY];
      if (!chart.containPixel({ gridIndex: 0 }, pt)) return;
      // OJO ECharts 5.5: convertFromPixel({xAxisIndex}) devuelve null; con {gridIndex}
      // sí invierte y da [índiceX, valorY]. Tomamos el índice de la categoría (día).
      const conv = chart.convertFromPixel({ gridIndex: 0 }, pt);
      if (!Array.isArray(conv)) return;
      // Con eje TEMPORAL, `conv[0]` ya no es el índice de una categoría sino un
      // timestamp en ms. Y como el clic puede caer en un hueco de la serie (hay 123),
      // se elige el día CON DATOS más cercano en vez de descartar el clic: si alguien
      // apunta a un tramo vacío, lo que quiere ver es lo que hay al lado.
      const ts = conv[0];
      const puntos = serieRef.current?.puntos ?? [];
      if (!puntos.length) return;
      let mejor = puntos[0];
      let dist = Infinity;
      for (const p of puntos) {
        const d = Math.abs(new Date(`${p.fecha}T00:00:00`).getTime() - ts);
        if (d < dist) {
          dist = d;
          mejor = p;
        }
      }
      const fecha = mejor?.fecha;
      if (fecha) setFiltro((p) => ({ ...p, fechaDesde: fecha, fechaHasta: fecha }));
    });
  }, []);

  const fmtDia = (s: string) =>
    new Date(`${s}T00:00:00`).toLocaleDateString("es-CL", { day: "2-digit", month: "short" });
  const rangoFechaLabel =
    filtro.fechaDesde && filtro.fechaHasta && filtro.fechaDesde !== filtro.fechaHasta
      ? `${fmtDia(filtro.fechaDesde)} - ${fmtDia(filtro.fechaHasta)}`
      : filtro.fechaDesde || filtro.fechaHasta
        ? fmtDia((filtro.fechaDesde || filtro.fechaHasta) as string)
        : null;

  // Máximo del slider de rango = antigüedad del comentario más viejo (crece con
  // los datos). En el tope, la ventana cubre todo el histórico.
  const spanMax = Math.max(1, opciones?.dias_span ?? 90);
  const diasEfectivo = Math.min(filtro.dias, spanMax);
  const esTodo = diasEfectivo >= spanMax;

  // Rangos rápidos. Solo los que CABEN en el histórico disponible: ofrecer
  // "2 años" con 8 meses de datos sería mentir.
  //
  // Los escalones van de UNA SEMANA a "Todo". Antes arrancaban en 30 días, y con
  // eso no había forma de mirar la última semana ni la última quincena — que es
  // justo la unidad en la que corre la detección de alertas. Pedir "¿qué pasó esta
  // semana?" y que el rango mínimo sean 30 días es incoherente.
  //
  // Cada escalón se muestra SOLO si cabe en el histórico: ofrecer "2 años" con ocho
  // meses de datos sería mentir. El último es siempre "Todo".
  //
  // ⚠️ Los rangos cortos existen para MIRAR, no para concluir. Una semana del corpus
  // tiene mediana de ~35 comentarios y muchas quedan por debajo del mínimo que el
  // módulo exige para afirmar algo: los bloques ya lo dicen cada uno por su cuenta
  // ("muestra insuficiente", "sin evidencia"), y por eso ampliar la lista hacia
  // abajo no rompe nada — lo que se ve con poca muestra ya viene rotulado.
  const marcasRango = useMemo(() => {
    const candidatas = [
      { dias: 7, label: "1 sem" },
      { dias: 14, label: "2 sem" },
      { dias: 30, label: "1 mes" },
      { dias: 60, label: "2 meses" },
      { dias: 90, label: "3 meses" },
      { dias: 180, label: "1 semestre" },
      { dias: 365, label: "1 año" },
      { dias: 730, label: "2 años" },
    ].filter((m) => m.dias < spanMax);
    return [...candidatas, { dias: spanMax, label: "Todo" }];
  }, [spanMax]);

  // Cuánto agrega la serie del gráfico. Sale del rango VISIBLE: lo que importa es
  // cuántos puntos entran en pantalla, no una preferencia. Ver `PASOS_SERIE`.
  // 0 = automático por rango (el default medido). Cualquier otro valor lo fuerza.
  const pasoSerie = useMemo(() => {
    if (pasoManual > 0) {
      const conocido = PASOS_SERIE.find((p) => p.dias === pasoManual);
      return conocido ?? { hastaDias: Infinity, dias: pasoManual, etiqueta: `cada ${pasoManual} d` };
    }
    return pasoDeSerie(diasEfectivo);
  }, [diasEfectivo, pasoManual]);

  // Cuántos puntos va a dibujar. Es lo que decide si la curva se lee o se pisa, y
  // por eso se muestra cuando el paso lo eligió una persona: el automático nunca
  // pasa el umbral, así que ahí el número sería ruido en pantalla.
  const puntosSerie = Math.ceil(diasEfectivo / Math.max(1, pasoSerie.dias));

  /** La serie TAL COMO SE DIBUJA. Es la fuente del eje, y por eso vive acá arriba.
   *
   * ⚠️ ESTO ARREGLA UNA DESINCRONIZACIÓN REAL entre el gráfico y la franja de
   * eventos de abajo. La franja tomaba sus extremos de `serie.puntos` —la serie
   * CRUDA, diaria— mientras el gráfico dibujaba la AGRUPADA. Y no son los mismos
   * extremos: `agruparSerie` ancla los bloques a `EPOCA_SERIE` (un lunes fijo,
   * anterior a todo el corpus) para que cambiar el rango no reagrupe los días, así
   * que el primer bloque EMPIEZA ANTES del primer punto crudo — hasta 6 días con
   * paso semanal y hasta 29 con paso mensual.
   *
   * El efecto era que un paro quedaba dibujado en la franja corrido respecto de la
   * caída del índice que lo acompaña, que es justamente la lectura que la franja
   * existe para permitir. Cuanto más grueso el paso, peor el corrimiento.
   */
  const serieDibujada = useMemo(
    () => (serie ? agruparSerie(serie.puntos, pasoSerie.dias) : []),
    [serie, pasoSerie.dias],
  );

  const rangoActivo = useMemo(
    () => marcasRango.find((m) => m.dias === diasEfectivo),
    [marcasRango, diasEfectivo],
  );

  // Extremos REALES de la ventana. Se anclan al comentario MÁS RECIENTE (igual
  // que el backend en `_rango`), no a hoy: si la ingesta se atrasa, "últimos 30
  // días" no son los 30 días previos a hoy y el tablero no debe fingir que sí.
  const [fechaDesdeLabel, fechaHastaLabel] = useMemo(() => {
    const hasta = opciones?.fecha_max ? new Date(`${opciones.fecha_max}T00:00:00`) : null;
    if (!hasta || Number.isNaN(hasta.getTime())) return ["—", "—"];
    const desde = new Date(hasta);
    desde.setDate(desde.getDate() - diasEfectivo);
    const fmt = (d: Date) =>
      d.toLocaleDateString("es-CL", { day: "2-digit", month: "2-digit", year: "numeric" });
    return [fmt(desde), fmt(hasta)];
  }, [opciones?.fecha_max, diasEfectivo]);
  const hayFiltroFecha = !!(filtro.fechaDesde || filtro.fechaHasta);
  // Toggles por TIPO: los tipos apagados no se dibujan (ni banda, ni líneas, ni chip).
  const eventosEncendidos = useMemo(
    () => eventos.filter((e) => !tiposOcultos.has(e.tipo)),
    [eventos, tiposOcultos],
  );
  // Toggles por CATEGORÍA, no por tipo crudo.
  //
  // Antes había un chip por cada uno de los nueve tipos, así que "Paro / movilización"
  // y "Toma" aparecían separados aunque para leer el tablero sean lo mismo, y "Fiestas
  // patrias" iba en el verde del semestre. Se agrupan con las MISMAS categorías y los
  // mismos colores que la franja de abajo — dos leyendas distintas para los mismos
  // eventos obligan a traducir mentalmente de una a la otra.
  const categoriasEnVentana = useMemo(() => {
    const vistas = new Map<string, { clave: string; label: string; color: string; tipos: string[] }>();
    for (const e of eventos) {
      const cat = categoriaDeTipo(e.tipo);
      const actual = vistas.get(cat.clave);
      if (actual) {
        if (!actual.tipos.includes(e.tipo)) actual.tipos.push(e.tipo);
      } else {
        vistas.set(cat.clave, { clave: cat.clave, label: cat.etiqueta, color: cat.color, tipos: [e.tipo] });
      }
    }
    return [...vistas.values()];
  }, [eventos]);
  return (
    <section className="portal-panel-strong space-y-5 p-6 md:p-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="portal-pill">Percepción</p>
          <h2 className="portal-title mt-3 text-2xl font-bold text-white">Percepción de la comunidad</h2>
          <p className="mt-1 text-sm text-slate-400">
            Sentimiento de publicaciones y comentarios de cuentas públicas UCN autorizadas.
          </p>
        </div>
      </header>

      {/* GUÍA DE LECTURA — cerrada por defecto, se abre a pedido.
          Va ANTES de los filtros porque el orden de la pantalla es el orden en que
          se aprende: primero qué estoy viendo, después con qué lo puedo mover.

          Está escrita para alguien que NO construyó el sistema. La versión anterior
          hablaba de comentarios "favorables" y "adversos" y de cuentas "autorizadas":
          ese es el vocabulario interno del módulo y a quien entra de afuera no le
          dice nada. Acá se explica con la palabra de todos los días, con un ejemplo
          numérico y con una escala dibujada, porque un rango de 0 a 100 sin un punto
          de referencia no se interpreta solo.

          La barra y el botón de retroalimentación quedan SIEMPRE visibles: son la
          puerta de entrada a la explicación y la de salida hacia el formulario, y
          esta pantalla está justamente en prueba. */}
      <section className="overflow-hidden rounded-2xl border border-[var(--portal-cyan)]/25 bg-[var(--portal-cyan)]/[0.05]">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <button
            type="button"
            onClick={() => setGuiaAbierta((v) => !v)}
            aria-expanded={guiaAbierta}
            className="flex items-center gap-2 text-left text-sm font-semibold text-[var(--portal-cyan)] transition hover:opacity-80"
          >
            <span aria-hidden="true" className={guiaAbierta ? "rotate-90 transition-transform" : "transition-transform"}>›</span>
            ¿Qué es esto y cómo se lee?
            <span className="font-normal text-slate-400">· 1 minuto de lectura</span>
          </button>
          {/* El destino se resuelve en cascada, de lo más específico a lo más
              general, y si no hay ninguno el botón NO se dibuja en vez de
              dibujarse muerto. */}
          {URL_RETROALIMENTACION ? (
            <a
              href={URL_RETROALIMENTACION}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/10 px-3 py-1.5 text-xs font-semibold text-[var(--portal-cyan)] transition hover:bg-[var(--portal-cyan)]/20"
            >
              Dar retroalimentación ↗
            </a>
          ) : onIrAFormulario ? (
            <button
              type="button"
              onClick={onIrAFormulario}
              className="rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/10 px-3 py-1.5 text-xs font-semibold text-[var(--portal-cyan)] transition hover:bg-[var(--portal-cyan)]/20"
            >
              Dar retroalimentación
            </button>
          ) : null}
        </div>

        {guiaAbierta ? (
          <div className="space-y-5 border-t border-white/10 px-4 py-4 text-sm leading-6 text-slate-300">
            <p className="text-slate-200">
              Esto mira, semana a semana, si lo que la gente escribe en redes sociales sobre la
              universidad suena más <strong>a favor</strong> o más <strong>en contra</strong>.
            </p>

            {/* La escala dibujada es la pieza que más ayuda: convierte un rango
                abstracto en algo que se mira una vez y queda entendido. */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                El número va de 0 a 100
              </p>
              <div className="mt-2 h-2 rounded-full bg-gradient-to-r from-rose-500/70 via-slate-500/50 to-emerald-500/70" />
              <div className="mt-1.5 flex justify-between text-[11px] text-slate-400">
                <span>0 · todo en contra</span>
                <span className="text-slate-200">50 · empate</span>
                <span>100 · todo a favor</span>
              </div>
              <p className="mt-3">
                <strong className="text-slate-100">50 es el empate</strong>: hay tanto comentario bueno
                como malo. Si de cada 100 comentarios 60 suenan buenos y 40 malos, el número queda
                alrededor de 60.
              </p>
              <p className="mt-2 text-slate-400">
                Los comentarios neutros —la mayoría, en la vida real— también se cuentan y empujan
                hacia el 50. Por eso el número casi nunca se va a los extremos.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Lo que importa es el cambio
                </p>
                <p className="mt-1">
                  Un 62 por sí solo no dice si vamos bien o mal: no existe una nota de aprobación.
                  Lo que informa es el <strong className="text-slate-100">movimiento</strong>. Un 62
                  que venía de 71 significa que algo se torció esa semana, y ahí vale la pena mirar
                  qué se estaba comentando.
                </p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  De dónde sale
                </p>
                <p className="mt-1">
                  De comentarios <strong className="text-slate-100">públicos</strong> en las cuentas de
                  redes sociales de la universidad: lo que cualquiera ve al entrar a esas
                  publicaciones. No se leen mensajes privados ni perfiles de nadie. Un programa
                  clasifica cada comentario como bueno, malo o neutro, y el número resume la mezcla.
                </p>
              </div>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Para qué no sirve
              </p>
              <p className="mt-1">
                <strong className="text-slate-100">No es una encuesta.</strong> A nadie se le preguntó.
                Los que comentan en redes son pocos y se eligen solos —suelen ser los más entusiastas
                y los más molestos—, así que esto no permite decir “el X % de la comunidad piensa tal
                cosa”.
              </p>
              <p className="mt-2">
                <strong className="text-slate-100">Tampoco prueba causas.</strong> Si el número baja la
                misma semana de un anuncio, eso es una coincidencia que vale la pena mirar, no una
                demostración de que el anuncio la produjo.
              </p>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Por dónde empezar
              </p>
              <ul className="mt-1 grid gap-1 sm:grid-cols-2">
                <li><strong className="text-slate-100">Resumen</strong> — el número de hoy y cómo veníamos.</li>
                <li><strong className="text-slate-100">Alertas</strong> — qué se movió más de lo normal.</li>
                <li><strong className="text-slate-100">Comparar</strong> — si está concentrado en una sede, facultad o tema.</li>
                <li><strong className="text-slate-100">Conversación</strong> — los comentarios reales que hay detrás.</li>
              </ul>
              <p className="mt-2 text-slate-400">
                Los filtros y los controles de abajo se aplican a las cuatro pestañas a la vez, así
                que siempre están hablando del mismo recorte.
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3">
              <p className="text-slate-400">
                Esta pantalla está <strong className="text-slate-200">en prueba</strong>. Nos sirve saber
                qué entendiste, qué te confundió y qué le falta para que te sea útil.
              </p>
              <button
                type="button"
                onClick={() => setGuiaAbierta(false)}
                className="whitespace-nowrap rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
              >
                Cerrar
              </button>
            </div>
          </div>
        ) : null}
      </section>
      {/* Barra de filtros GLOBAL.
          GRID, no flex-wrap: con `flex` cada select tomaba el ancho de su opción
          más larga y los cuatro quedaban desparejos —"Departamento" se salía del
          panel y "Sede" quedaba diminuto—. Cuatro controles del mismo rango tienen
          que verse iguales; el que manda el ancho es la grilla, no el contenido. */}
      <div className="grid grid-cols-2 items-end gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-3 sm:grid-cols-4 lg:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
        <FiltroSelect label="Sede" value={filtro.sede ?? ""} onChange={(v) => up({ sede: v || undefined })}>
          <option value="">Todas</option>
          {(opciones?.sedes ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
        </FiltroSelect>
        <FiltroSelect label="Facultad" value={filtro.facultad ?? ""} onChange={(v) => up({ facultad: v || undefined })}>
          <option value="">Todas</option>
          {(opciones?.facultades ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
        </FiltroSelect>
        <FiltroSelect label="Departamento" value={filtro.departamento ?? ""} onChange={(v) => up({ departamento: v || undefined })}>
          <option value="">Todos</option>
          {(opciones?.departamentos ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
        </FiltroSelect>
        <FiltroSelect label="Tema" value={filtro.tema ?? ""} onChange={(v) => up({ tema: v || undefined })}>
          <option value="">Todos</option>
          {(opciones?.temas ?? []).map((t) => <option key={t.tema} value={t.tema}>{t.etiqueta}</option>)}
        </FiltroSelect>
        {(filtro.sede || filtro.facultad || filtro.departamento || filtro.tema || filtro.dias !== DEFAULT_DIAS
          || filtro.pesoLikes !== 1 || filtro.vidaMedia !== 30 || filtro.fechaDesde || filtro.fechaHasta) ? (
          <button
            onClick={() => setFiltro({ dias: DEFAULT_DIAS, pesoLikes: 1, vidaMedia: 30 })}
            className="col-span-2 justify-self-start whitespace-nowrap rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-white/[0.08] hover:text-white sm:col-span-4 lg:col-span-1 lg:justify-self-end"
          >
            Limpiar filtros
          </button>
        ) : null}
      </div>

      {/* Controles GLOBALES: rango, peso por likes y recencia. Los tres afectan a
          todas las pestañas por igual.
          
          Estuvieron un tiempo escondidos fuera de Conversación, para evitar que
          una vista ponderara la recencia y otra no —que era el origen de que el
          mismo tema diera 58.7 en una pestaña y 64.3 en otra—. Pero ese problema
          venía de que la diferencia era FIJA e invisible, no del control en sí:
          con un control único que mueve todo a la vez, las pestañas siguen
          coherentes entre ellas y además el `RotuloMetodo` de cada bloque dice en
          qué modo está leyendo. La única excepción es ALERTAS, que ignora la
          recencia a propósito y lo declara: aplicándola, la detección se vuelve
          ciega (|z| máximo 1.98 contra umbral 2.5 en el paro de 2026). */}
      {/* Separadores verticales entre los tres controles: son mandos distintos que
          se leían como un bloque continuo. `divide-*` en vez de bordes propios para
          que no aparezca una línea colgando en el primero ni en el último. */}
      <div className="grid grid-cols-1 gap-4 divide-y divide-white/[0.07] rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 sm:grid-cols-3 sm:gap-0 sm:divide-x sm:divide-y-0">
        {/* RANGO — control segmentado, no slider.
            Los tableros que viven de series temporales (Grafana, Kibana, Datadog)
            resuelven esto con rangos rápidos discretos + un rango absoluto aparte,
            y ninguno usa un deslizador: con un histórico de años, nadie elige "743
            días" arrastrando, y el valor exacto no significa nada. Acá el rango
            arbitrario ya lo cubre el selector Desde/Hasta de más abajo, así que el
            deslizador solo agregaba ruido. */}
        {/* Los tres mandos REPARTEN su alto en vez de apilarse arriba.
            El rango es el más alto —tres filas de botones más la línea de fechas— y
            los dos deslizadores terminaban ~55 px antes, dejando el separador
            vertical colgando en vacío y las tres ayudas a alturas distintas.
            `justify-between` alinea las tres etiquetas arriba Y los tres pies de
            ayuda abajo, que es lo que hace que se lean como una sola barra. Centrar
            el bloque entero también llenaba el hueco, pero desalineaba las
            etiquetas, que son el ancla que dice cuántos mandos hay. */}
        <div className="flex flex-col justify-between gap-1.5 sm:pr-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Rango (ventana)
            </span>
            <span className="text-xs font-semibold tabular-nums text-slate-100">
              {rangoActivo?.label ?? (esTodo ? "Todo" : `${filtro.dias} d`)}
            </span>
          </div>
          {/* GRILLA de 3 columnas, no `flex-wrap`.
              Con nueve escalones, envolver dejaba cinco botones arriba y cuatro
              abajo, de anchos distintos según su texto: el control se leía como un
              amontonamiento. Tres columnas dan tres filas EXACTAS y todos los
              botones del mismo ancho, que es lo que hace que un segmentado se lea
              como un solo mando y no como nueve piezas sueltas.
              ⚠️ Si algún día se agrega o quita un escalón, conviene que la cuenta
              siga siendo múltiplo de 3 o la última fila vuelve a quedar coja. */}
          <div
            className="grid w-full grid-cols-3 gap-px overflow-hidden rounded-xl border border-white/10 bg-white/[0.06]"
            role="group"
            aria-label="Rango de tiempo"
          >
            {marcasRango.map((m) => {
              const activo = diasEfectivo === m.dias;
              return (
                <button
                  key={m.dias}
                  type="button"
                  onClick={() => up({ dias: m.dias })}
                  aria-pressed={activo}
                  className={`whitespace-nowrap px-1 py-1.5 text-[11px] font-semibold transition ${
                    activo
                      ? "bg-[var(--portal-cyan)] text-slate-950"
                      : "bg-[#0b1424] text-slate-400 hover:bg-white/[0.06] hover:text-slate-200"
                  }`}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
          <span className="text-[11px] text-slate-500">
            {/* El rango REAL en fechas: es lo que responde "¿qué estoy mirando?".
                Se ancla al comentario más reciente, no a hoy. */}
            {fechaDesdeLabel} → {fechaHastaLabel}
            {esTodo ? " · todo el histórico" : ` · ${diasEfectivo} días`}
          </span>
        </div>
        {/* Los VALORES de los tres controles van todos en el mismo gris claro.
            Antes eran cian, cian y cobre: tres colores para tres lecturas del mismo
            rango jerárquico, que hacía parecer que "30 d" significaba algo distinto
            de "100%". El acento queda para el estado ACTIVO de un control, que sí
            es información. */}
        <div className="flex flex-col justify-between gap-1.5 pt-3 sm:px-4 sm:pt-0">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Peso por likes
            </span>
            <span className="text-xs font-semibold tabular-nums text-slate-100">
              {Math.round(filtro.pesoLikes * 100)}%
            </span>
          </div>
          <input
            type="range" min={0} max={100} step={5}
            value={Math.round(filtro.pesoLikes * 100)}
            onChange={(e) => up({ pesoLikes: Number(e.target.value) / 100 })}
            className="w-full accent-[var(--portal-cyan)]"
            aria-label="Intensidad de ponderación por likes"
          />
          <span className="text-[11px] text-slate-500">
            {filtro.pesoLikes === 0
              ? "cada comentario pesa igual (ignora likes)"
              : filtro.pesoLikes === 1
                ? "ponderación completa por likes"
                : "mezcla: los virales pesan más, atenuado"}
          </span>
        </div>
        <div className="flex flex-col justify-between gap-1.5 pt-3 sm:pl-4 sm:pt-0">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Recencia (vida del comentario)
            </span>
            <span className="text-xs font-semibold tabular-nums text-slate-100">
              {filtro.vidaMedia === 0 ? "sin decaimiento" : `${filtro.vidaMedia} d`}
            </span>
          </div>
          <input
            type="range" min={0} max={90} step={1}
            value={filtro.vidaMedia}
            onChange={(e) => up({ vidaMedia: Number(e.target.value) })}
            className="w-full accent-[var(--portal-copper)]"
            aria-label="Recencia: días hasta que un comentario deja de contar"
          />
          <span className="text-[11px] text-slate-500">
            {filtro.vidaMedia === 0
              ? "sin decaimiento: todos los días pesan igual"
              : `baja parejo día a día; a los ${filtro.vidaMedia} días un comentario deja de contar`}
          </span>
        </div>
      </div>

      <div className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.08] px-4 py-2 text-xs leading-6 text-amber-100">
        <strong>Lectura con cuidado:</strong> este indicador mide la percepción{" "}
        <em>expresada en redes sociales</em>, que proviene de un grupo autoseleccionado y no
        representa a toda la comunidad universitaria. Las coincidencias con eventos institucionales
        son temporales, no causales.
      </div>

      {/* Aviso NO bloqueante: si una recarga falla (p.ej. rate-limit por mover un
          slider), mostramos el error arriba pero MANTENEMOS el tablero con los
          últimos datos, en vez de tirar todo abajo. */}
      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm text-rose-200">
          {error}{loading ? " · reintentando…" : ""}
        </div>
      ) : null}

      {/* Selector de pestaña. Todas comparten el MISMO filtro global de arriba.
          El subtítulo no es decorativo: dice qué PREGUNTA responde cada una, que
          es lo que faltaba cuando estaban ordenadas por tipo de gráfico. */}
      <div className="flex flex-wrap gap-2">
        {([
          { id: "resumen", label: "Resumen", hint: "¿Cómo estamos?", interna: false, soloAdmin: false },
          // El hint dice "antes" y no "ahora" a propósito: es la única pestaña que
          // mira hacia adelante, y es el objetivo del módulo. Medido, sus alarmas
          // se encienden con 28 días de mediana antes de un conflicto.
          { id: "alertas", label: "Alertas", hint: "¿Qué se viene?", interna: false, soloAdmin: false },
          { id: "comparar", label: "Comparar", hint: "¿Dónde está el problema?", interna: false, soloAdmin: false },
          { id: "conversacion", label: "Conversación", hint: "¿Qué se está diciendo?", interna: false, soloAdmin: false },
          // Antes decía solo "corregir lo que el modelo leyó mal", y la pestaña
          // tiene tres bloques: corregir, revisar una muestra y MEDIR el acierto.
          // Quien entraba buscando "¿le puedo creer al índice?" no tenía por qué
          // suponer que la respuesta estaba detrás de la palabra "curación".
          //
          // INTERNA: aquí se corrige el modelo comentario por comentario. Quien lee
          // el Termómetro para saber cómo está la universidad no tiene por qué
          // toparse con la herramienta que lo calibra — y menos tocarla.
          { id: "curacion", label: "Curación", hint: "¿Le puedo creer al modelo?", interna: true, soloAdmin: true },
          // Va ÚLTIMA y separada: las cuatro primeras cuentan datos observados, esta
          // propone modelos. Un pronóstico entre conteos se lee con una autoridad
          // que todavía no tiene.
          //
          // INTERNA: habla en MAE, error irreducible y baselines. Es la discusión de
          // si vale la pena construir un modelo, no una lectura de la percepción.
          { id: "simulacion", label: "Simulación", hint: "¿Qué pasaría si…? (en construcción)", interna: true, soloAdmin: false },
          // Las pestañas INTERNAS solo para el equipo DAI (Curación, además, SOLO para
          // administradores: muestra texto crudo de comentarios). Las otras cuatro cuentan
          // lo que pasó y cualquiera de la UCN puede leerlas; estas dos son las
          // herramientas con las que el equipo calibra y decide, y mezclarlas
          // convierte una lectura en una mesa de trabajo ajena.
          //
          // Es VISIBILIDAD, no autorización: el gate real vive en el backend. Acá
          // solo se decide qué se ofrece.
        ] as const).filter((v) => (!v.interna || equipoDai) && (!v.soloAdmin || administrador)).map((v) => (
          <button
            key={v.id}
            type="button"
            onClick={() => setVista(v.id)}
            title={v.hint}
            className={
              vista === v.id
                ? "rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/10 px-4 py-1.5 text-left text-sm font-semibold text-[var(--portal-cyan)]"
                : "rounded-full border border-white/10 bg-white/[0.03] px-4 py-1.5 text-left text-sm text-slate-400 transition hover:bg-white/[0.07]"
            }
          >
            {v.label}
            <span className="ml-2 text-[11px] font-normal opacity-70">{v.hint}</span>
          </button>
        ))}
      </div>

      {/* filtroEstable, no filtro: las hojas heredan el mismo debounce que el
          tablero, así un arrastre de slider no dispara una request por pixel. */}
      {/* El rastro va ARRIBA del contenido y no dentro de cada hoja: es información
          sobre la navegación, no sobre el dato, y repetirlo en cada componente lo
          haría fácil de olvidar en el próximo que se agregue. */}
      {rastro && vista !== "resumen" ? (
        <RastroNavegacion rastro={rastro} onVolver={volverDelRastro} />
      ) : null}

      {vista === "resumen" ? (
        <PercepcionResumen
          filtro={filtroEstable}
          onVerAlertas={() => setVista("alertas")}
          onVerComparar={() => setVista("comparar")}
          onIrA={irA}
        />
      ) : vista === "alertas" ? (
        <PercepcionAlertas filtro={filtroEstable} />
      ) : vista === "comparar" ? (
        <PercepcionComparar filtro={filtroEstable} sub={subComp} onSub={setSubComp} />
      ) : vista === "simulacion" && equipoDai ? (
        // Sin `filtro`: los bloques de simulación trabajan sobre la serie completa,
        // no sobre la ventana del tablero. Medir volatilidad o entrenar un baseline
        // con 30 días de datos no alcanza para separar señal de ruido.
        //
        // `&& equipoDai` acompaña al filtro del selector: esconder el BOTÓN no
        // alcanza. El primer render ocurre con `equipoDai` en `false` (se resuelve
        // tras el montaje), y una vista guardada o un salto interno podrían dejar
        // `vista` en una interna sin que nadie la haya elegido.
        <PercepcionSimulacion />
      ) : vista === "curacion" && administrador ? (
        <div className="space-y-4">
          {/* El ORDEN es deliberado y se conserva en las sub-pestañas: MEDIR →
              ANOTAR → CURAR. Primero se ve cuánto le erra el modelo, después se
              anota para poder medirlo, y al final se curan los temas. Al revés se
              corrige a ciegas, sin saber si el esfuerzo rinde ni en qué dirección.
              Por eso "¿Cuánto le erra?" es la que abre. */}
          <SubPestanas opciones={SUB_CURACION} activa={subCur} onCambio={setSubCur} />
          {subCur === "calidad" ? <PercepcionCalidad /> : null}
          {subCur === "revisar" ? (
            <PercepcionRevision onCambio={() => void cargar(filtro)} />
          ) : null}
          {subCur === "temas" ? (
            <PercepcionCuracion onCambio={() => void cargar(filtro)} />
          ) : null}
        </div>
      ) : loading && !resumen ? (
        <div className="py-12 text-center text-slate-500">Cargando percepción…</div>
      ) : !resumen?.hay_datos ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 text-sm text-slate-300">
          <p className="font-medium text-slate-200">No hay datos de percepción para este filtro.</p>
          <p className="mt-1">Prueba ampliar el rango o limpiar los filtros. Si no hay datos aún, pobla con el worker:</p>
          <pre className="mt-2 overflow-x-auto rounded-xl border border-white/10 bg-[#0b1424] p-3 text-xs text-slate-200">
{`python -m percepcion.cli simular --dias 90
python -m percepcion.cli scorear --scorer rule
python -m percepcion.cli temas
python -m percepcion.cli agregar`}
          </pre>
        </div>
      ) : (
        <>
          {/* AVISO DE MÉTODO. Es lo que resuelve el hallazgo de la auditoría: el
              mismo tema daba 58.7 acá y 64.3 en el Resumen —y "Organización
              estudiantil" cruzaba el neutro de una pestaña a otra— porque esta
              vista pondera la recencia y aquella no. Las dos lecturas son
              correctas; lo que faltaba era decirlo antes de que alguien compare
              dos números que no son comparables. */}
          <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-2 text-[11px] leading-5 text-slate-400">
            <RotuloMetodo vidaMedia={filtro.vidaMedia} />
            <span>
              Esta pestaña pondera la <strong className="text-slate-300">recencia</strong> con los
              controles de arriba, así que sus números pueden diferir de los del{" "}
              <strong className="text-slate-300">Resumen</strong>, que promedia todo el período por
              igual. Pon la recencia en <em>off</em> para que coincidan.
            </span>
          </div>

          {/* El GAUGE, los StatTiles y el donut de distribución se eliminaron: el
              Resumen ya da el índice con su lectura en palabras y la distribución
              en una barra apilada, que para porcentajes se lee mejor que un donut.
              Repetirlos acá era la cuarta duplicación de la vieja estructura. */}


          {/* SUBSECCIONES. La línea de tiempo y la nube son las dos cosas
              importantes de esta pestaña y, una debajo de la otra, la primera
              eclipsaba a la segunda: había que scrollear un gráfico grande, la
              lista de comentarios y el ABM de eventos para llegar a la nube.
              Separadas, cada una entra completa en pantalla.

              El corte no es arbitrario: los COMENTARIOS van con la línea de
              tiempo porque el clic en un día del gráfico filtra esa lista, y las
              EMOCIONES van con la nube porque las dos describen el CONTENIDO de
              lo que se dijo, no su distribución temporal. */}
          <SubPestanas opciones={SUB_CONVERSACION} activa={subConv} onCambio={setSubConv} />

          {subConv !== "tiempo" ? null : (
            <>
          {/* Evolución: el corazón de esta pestaña. */}
          <div className="grid grid-cols-1 gap-4">
            <div className={`${CARD} lg:col-span-2`}>
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-200">
                  Evolución diaria{" "}
                  {/* La leyenda va acá y no en un tooltip: los anillos se confundían
                      con marcas de conflicto por estar en el mismo rojo, y nadie va a
                      pasar el mouse por un punto para averiguar qué categoría es. */}
                  <span className="text-[11px] font-normal text-slate-500">
                    · bandas rojas = paros · <span className="text-slate-300">◦</span> anillos = cambios inusuales detectados
                    · el calendario, abajo
                  </span>
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  {/* La unidad se DECLARA Y SE ELIGE.
                      Declararla ya era necesario: sin esto el mismo gráfico muestra
                      días con 30 d y meses con "Todo", y nadie sabe qué mira ni por
                      qué la curva cambia de forma al mover el rango.
                      Pero era un chip PASIVO, y elegir bien por el usuario no es lo
                      mismo que elegir por él sin darle opción: sobre cuatro años el
                      mes es lo legible, y aun así alguien puede necesitar la semana
                      para ubicar un episodio corto. El automático sigue siendo el
                      default. */}
                  <label className="flex items-center gap-1.5">
                    <span className="text-[10px] uppercase tracking-wider text-slate-500">
                      Agregación
                    </span>
                    <select
                      value={pasoManual}
                      onChange={(e) => setPasoManual(Number(e.target.value))}
                      className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300 outline-none transition hover:border-white/20 focus:border-[var(--portal-cyan)]"
                      title="Cada cuánto se promedian los puntos de la línea de tiempo"
                    >
                      {PASOS_ELEGIBLES.map((p) => (
                        <option key={p.dias} value={p.dias}>
                          {p.dias === 0 ? `Automático · ${pasoDeSerie(diasEfectivo).etiqueta}` : p.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {/* Solo cuando lo eligió una persona: el automático nunca pasa el
                      umbral, así que ahí este número sería ruido en pantalla. */}
                  {pasoManual > 0 && puntosSerie > PUNTOS_APRETADOS ? (
                    <span
                      className="rounded-full border border-[var(--portal-copper)]/40 bg-[var(--portal-copper)]/10 px-2 py-0.5 text-[10px] text-[var(--portal-copper)]"
                      title="Con esta cantidad los puntos se pisan entre sí y buena parte de lo que se ve es ruido de muestreo, no tendencia."
                    >
                      {nro(puntosSerie)} puntos · se van a pisar
                    </span>
                  ) : null}
                  <span className="text-[11px] text-[var(--portal-cyan)]/80">
                    {pasoSerie.dias > 1
                      ? "Click en un punto para filtrar todo el tablero"
                      : "Click en un dia para filtrar todo el tablero"}
                  </span>
                  {hayFiltroFecha ? (
                    <button
                      type="button"
                      onClick={limpiarFecha}
                      className="rounded-full border border-[var(--portal-copper)]/40 bg-[var(--portal-copper)]/10 px-2.5 py-1 text-[11px] font-semibold text-[var(--portal-copper)] hover:bg-[var(--portal-copper)]/15"
                    >
                      Quitar filtro del gráfico
                    </button>
                  ) : null}
                </div>
              </div>
              {serie ? (
                <EChartsChart
                  option={lineOption(serie, eventosEncendidos,
                    { desde: filtro.fechaDesde, hasta: filtro.fechaHasta }, pasoSerie.dias)}
                  height={300}
                  ariaLabel="Evolución del índice con eventos"
                  onReady={onEvolucionReady}
                />
              ) : null}
              {/* El calendario completo, ABAJO y alineado al mismo eje. Encima de la
                  serie quedan solo los paros; todo lo demás se lee acá sin tapar nada. */}
              {serieDibujada.length ? (
                <PercepcionFranjaEventos
                  eventos={eventosEncendidos}
                  // Los extremos salen de la serie AGRUPADA, no de la cruda: es el
                  // eje que el gráfico dibuja de verdad. Ver `serieDibujada`.
                  desde={serieDibujada[0]?.fecha}
                  hasta={serieDibujada[serieDibujada.length - 1]?.fecha}
                  // El paso, para que la franja mida su tolerancia de agrupado en la
                  // MISMA unidad que el gráfico en vez de en píxeles sueltos.
                  pasoDias={pasoSerie.dias}
                  seleccion={{ desde: filtro.fechaDesde, hasta: filtro.fechaHasta }}
                  // Clic en una marca → el tablero entero se acota a ese período.
                  // Ver que hubo un paro y poder leer qué se dijo durante él son dos
                  // cosas distintas; antes había que copiar las fechas a mano.
                  onSeleccionRango={(d, h) =>
                    setFiltro((p) => ({ ...p, fechaDesde: d, fechaHasta: h }))
                  }
                />
              ) : null}
              {/* Marcas de contexto: toggles por TIPO + acceso al ABM. Apagar un tipo
                  saca sus bandas del gráfico (no borra nada de la base). */}
              {/* PRESETS: cuatro combinaciones que responden preguntas distintas.
                  Existen para que no haya que armar la vista toggle por toggle cada
                  vez — y sobre todo para que «ver la serie sin nada» sea un clic y no
                  seis. */}
              <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-white/5 pt-2.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Vista
                </span>
                {PRESETS.map((p) => {
                  const on = presetActivo === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setTiposOcultos(ocultosDePreset(p.id))}
                      title={p.hint}
                      aria-pressed={on}
                      className={
                        on
                          ? "rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/10 px-2.5 py-1 text-[11px] font-semibold text-[var(--portal-cyan)]"
                          : "rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-slate-400 transition hover:border-white/25 hover:text-white"
                      }
                    >
                      {p.label}
                    </button>
                  );
                })}
                {presetActivo === null ? (
                  <span className="text-[10px] text-slate-500">· combinación propia</span>
                ) : null}
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Marcas
                </span>
                {categoriasEnVentana.length === 0 ? (
                  <span className="text-[11px] text-slate-500">sin marcas en esta ventana</span>
                ) : (
                  categoriasEnVentana.map(({ clave, label, color: c, tipos }) => {
                    const on = tipos.some((t) => !tiposOcultos.has(t));
                    return (
                      <button
                        key={clave}
                        type="button"
                        onClick={() => toggleCategoria(tipos)}
                        aria-pressed={on}
                        title={on ? `Ocultar ${label} del gráfico` : `Mostrar ${label} en el gráfico`}
                        className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition"
                        style={{
                          borderColor: on ? `${c}66` : "rgba(148,163,184,0.25)",
                          background: on ? `${c}1f` : "transparent",
                          color: on ? c : "#64748b",
                        }}
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: on ? c : "transparent", border: `1px solid ${on ? c : "#64748b"}` }}
                        />
                        {label}
                      </button>
                    );
                  })
                )}
                <button
                  type="button"
                  onClick={() => { setAbmAbierto((v) => !v); if (!eventosTodos.length) void recargarEventos(); }}
                  className="ml-auto rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-semibold text-slate-300 transition hover:bg-white/[0.08]"
                >
                  {abmAbierto ? "Cerrar administración" : "Administrar marcas"}
                </button>
              </div>
              {/* Acá vivía un CHIP POR CADA EVENTO visible con su nombre y sus fechas.
                  Con el calendario académico cargado eran 112 chips debajo del gráfico,
                  o sea más superficie de pastillas que de datos. La franja de arriba
                  muestra lo mismo posicionado en el tiempo, que además informa MÁS:
                  una lista alfabética de fechas no deja ver cuándo se agrupan. */}

              {/* ABM de marcas: alta/edición + listado con borrar. */}
              {abmAbierto ? (
                <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                      {evtEdit ? `Editando: ${evtEdit.nombre}` : "Nueva marca de contexto"}
                    </span>
                    {evtEdit ? (
                      <button type="button" onClick={nuevoEvento}
                        className="text-[11px] font-semibold text-[var(--portal-cyan)] hover:underline">
                        + Crear otra
                      </button>
                    ) : null}
                  </div>

                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
                    <input
                      type="text" placeholder="Nombre (ej. Vacaciones de invierno)"
                      value={evtForm.nombre}
                      onChange={(e) => setEvtForm((p) => ({ ...p, nombre: e.target.value }))}
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-slate-100 outline-none focus:border-[var(--portal-cyan)]/50 lg:col-span-2"
                    />
                    <select
                      value={evtForm.tipo}
                      onChange={(e) => setEvtForm((p) => ({ ...p, tipo: e.target.value }))}
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-slate-100 outline-none focus:border-[var(--portal-cyan)]/50"
                      aria-label="Tipo de marca"
                    >
                      {tiposEvento.map((t) => (
                        <option key={t.tipo} value={t.tipo} className="bg-slate-900">{t.etiqueta}</option>
                      ))}
                    </select>
                    <input
                      type="date" value={evtForm.fecha_inicio}
                      onChange={(e) => setEvtForm((p) => ({ ...p, fecha_inicio: e.target.value }))}
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-slate-100 outline-none focus:border-[var(--portal-cyan)]/50"
                      aria-label="Fecha de inicio"
                    />
                    <input
                      type="date" value={evtForm.fecha_fin ?? ""}
                      onChange={(e) => setEvtForm((p) => ({ ...p, fecha_fin: e.target.value }))}
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-slate-100 outline-none focus:border-[var(--portal-cyan)]/50"
                      aria-label="Fecha de fin (vacía = un solo día)"
                    />
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <button
                      type="button" onClick={guardarEvento} disabled={evtBusy}
                      className="rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/15 px-3 py-1 text-[11px] font-semibold text-[var(--portal-cyan)] transition hover:bg-[var(--portal-cyan)]/25 disabled:opacity-50"
                    >
                      {evtBusy ? "Guardando…" : evtEdit ? "Guardar cambios" : "Crear marca"}
                    </button>
                    <span className="text-[11px] text-slate-500">
                      Fin vacío = marca de un solo día.
                    </span>
                    {evtMsg ? <span className="text-[11px] text-slate-300">{evtMsg}</span> : null}
                  </div>

                  {eventosTodos.length > 0 ? (
                    <div className="mt-3 max-h-52 overflow-y-auto">
                      <table className="w-full text-left text-[11px]">
                        <thead className="text-slate-500">
                          <tr>
                            <th className="pb-1 font-semibold">Marca</th>
                            <th className="pb-1 font-semibold">Tipo</th>
                            <th className="pb-1 font-semibold">Periodo</th>
                            <th className="pb-1" />
                          </tr>
                        </thead>
                        <tbody>
                          {eventosTodos.map((e) => {
                            const c = COLOR_EVENTO_LINEA[e.tipo] ?? "#94a3b8";
                            return (
                              <tr key={e.id} className="border-t border-white/5">
                                <td className="py-1.5 pr-2 text-slate-200">{e.nombre}</td>
                                <td className="py-1.5 pr-2">
                                  <span className="inline-flex items-center gap-1.5" style={{ color: c }}>
                                    <span className="h-2 w-2 rounded-full" style={{ background: c }} />
                                    {e.tipo_label ?? e.tipo}
                                  </span>
                                </td>
                                <td className="py-1.5 pr-2 text-slate-400">
                                  {fmtDiaCorto(e.fecha_inicio)} – {fmtDiaCorto(e.fecha_fin)}
                                </td>
                                <td className="py-1.5 text-right">
                                  <button type="button" onClick={() => editarEvento(e)} disabled={evtBusy}
                                    className="mr-2 text-[var(--portal-cyan)] hover:underline disabled:opacity-50">
                                    Editar
                                  </button>
                                  <button type="button" onClick={() => borrarEvento(e)} disabled={evtBusy}
                                    className="text-rose-300 hover:underline disabled:opacity-50">
                                    Borrar
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-3 text-[11px] text-slate-500">Todavía no hay marcas cargadas.</p>
                  )}
                </div>
              ) : null}
            </div>
          </div>

          {/* EL CALENDARIO CARGADO, junto a su propio ABM.
              Estaba en Simulación, o sea que el formulario para dar de alta un
              evento vivía en una pestaña y la lista de lo cargado —con cuántos son
              de fecha confirmada y cuántos disruptivos— en otra. La misma
              información en dos lugares es exactamente lo que la auditoría de
              pestañas había resuelto una vez; se cuela de nuevo cada vez que un
              bloque nuevo no encuentra dónde ir.
              Solo se muestra con la administración abierta: es material de quien
              carga y audita el calendario, no de quien mira la curva. */}
          {abmAbierto ? <PercepcionCalendarioDatos /> : null}

          {/* COMENTARIOS pegado a EVOLUCIÓN, y no al fondo de la pestaña: el
              clic en un día del gráfico filtra ESTA lista. Antes estaban
              separados por cinco bloques —emociones, facultad, tema, anomalías—
              así que al hacer clic arriba había que desplazar media pantalla
              para ver el resultado. */}
          {/* Comentarios recientes que están afectando la percepción */}
          <div className={CARD}>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium text-slate-200">Comentarios recientes</div>
              <span className="text-[11px] text-slate-500">clic en un comentario para corregir · autor anónimo</span>
            </div>

            {/* Filtros LOCALES: sentimiento (chips) + emoción (selector) */}
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {([
                { key: undefined, label: "Que afectan" },
                { key: "POS", label: "Positivos", c: COLOR_POS },
                { key: "NEU", label: "Neutros", c: COLOR_NEU },
                { key: "NEG", label: "Negativos", c: COLOR_NEG },
              ] as const).map((chip) => {
                const activo = comFiltro.sentimiento === chip.key;
                const col = "c" in chip ? chip.c : COLOR_CYAN;
                return (
                  <button
                    key={chip.label}
                    onClick={() => setComFiltro((p) => ({ ...p, sentimiento: chip.key }))}
                    className="rounded-full border px-3 py-1 text-xs font-semibold transition"
                    style={activo
                      ? { background: col + "22", color: col, borderColor: col + "55" }
                      : { background: "rgba(255,255,255,0.03)", color: "#94a3b8", borderColor: "rgba(255,255,255,0.1)" }}
                  >
                    {chip.label}
                  </button>
                );
              })}
              <select
                value={comFiltro.emocion ?? ""}
                onChange={(e) => setComFiltro((p) => ({ ...p, emocion: e.target.value || undefined }))}
                className={`${SELECT} ml-auto`}
              >
                <option value="">Todas las emociones</option>
                {emociones.map((e) => (
                  <option key={e.emocion} value={e.emocion}>{labelEmocion(e.emocion, e.etiqueta)} ({e.n})</option>
                ))}
              </select>
            </div>

            {/* Filtro por FECHA (día puntual o rango). Sincronizado con el clic en el
                gráfico de evolución: ambos escriben fechaDesde/fechaHasta. */}
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Fecha global</span>
              <label className="flex items-center gap-1.5 text-xs text-slate-400">
                Desde
                <input
                  type="date"
                  value={filtro.fechaDesde ?? ""}
                  min={opciones?.fecha_min ?? undefined}
                  max={opciones?.fecha_max ?? undefined}
                  onChange={(e) => setFechaDesde(e.target.value)}
                  className={SELECT}
                  style={{ colorScheme: "dark" }}
                />
              </label>
              <label className="flex items-center gap-1.5 text-xs text-slate-400">
                Hasta
                <input
                  type="date"
                  value={filtro.fechaHasta ?? ""}
                  min={filtro.fechaDesde ?? opciones?.fecha_min ?? undefined}
                  max={opciones?.fecha_max ?? undefined}
                  onChange={(e) => setFechaHasta(e.target.value)}
                  className={SELECT}
                  style={{ colorScheme: "dark" }}
                />
              </label>
              {rangoFechaLabel ? (
                <span className="flex items-center gap-2 rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/10 px-3 py-1 text-xs font-semibold text-[var(--portal-cyan)]">
                  Mostrando: {rangoFechaLabel}
                  <button onClick={limpiarFecha} className="text-slate-300 transition hover:text-white" aria-label="Limpiar filtro de fecha" type="button">✕</button>
                </span>
              ) : (
                <span className="text-[11px] text-slate-500">o hace clic en un dia del grafico para filtrar todo el tablero</span>
              )}
            </div>

            <p className="mt-2 text-[11px] text-slate-500">
              Por privacidad, los comentarios se muestran como etiquetas.
            </p>
            {comentarios.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {comentarios.map((c) => {
                  const color = c.sentimiento === "POS" ? COLOR_POS : c.sentimiento === "NEG" ? COLOR_NEG : COLOR_NEU;
                  const editando = editId === c.id;
                  return (
                    <li
                      key={c.id}
                      className={`rounded-2xl border bg-white/[0.02] p-3 transition ${editando ? "border-[var(--portal-cyan)]/40" : "border-white/5 hover:border-white/15"}`}
                    >
                      <div className="flex cursor-pointer items-start gap-3" onClick={() => abrirEdicion(c)} title="Clic para corregir sentimiento/emoción">
                        <span
                          className="mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold"
                          style={{ background: color + "1f", color, border: `1px solid ${color}33` }}
                        >
                          {c.sentimiento_label}
                        </span>
                        <div className="flex flex-1 flex-wrap items-center gap-2 text-sm text-slate-200">
                          {c.tema_label ? <span className="rounded-full bg-white/[0.06] px-2 py-0.5">{c.tema_label}</span> : <span className="text-slate-500">(sin tema)</span>}
                          {c.emocion_label ? <span className="rounded-full bg-white/[0.06] px-2 py-0.5">{labelEmocion(c.emocion, c.emocion_label)}</span> : null}
                          <span className="text-[11px] text-slate-500">neto {c.neto.toFixed(2)}</span>
                        </div>
                        <span className="mt-0.5 shrink-0 text-[11px] text-slate-500">{editando ? "▲" : "✎"}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                        <span>{c.fecha}</span>
                        {c.cuenta ? <span>· @{c.cuenta}</span> : null}
                        {c.unidad ? <span>· {c.unidad}</span> : null}
                        {c.cuenta_tipo ? <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-slate-400">{c.cuenta_tipo}</span> : null}
                        {c.n_likes > 0 ? <span>· ♥ {c.n_likes.toLocaleString("es-CL")}</span> : null}
                        <span className="ml-auto text-slate-600">impacto {c.impacto.toFixed(2)}</span>
                      </div>

                      {editando ? (
                        <div className="mt-3 rounded-2xl border border-[var(--portal-cyan)]/20 bg-[var(--portal-cyan)]/[0.05] p-3">
                          <div className="mb-2 text-[11px] font-semibold text-slate-300">Corregir y enseñarle al modelo</div>
                          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                            <label className="flex items-center gap-1">
                              Sentimiento:
                              <select className={SELECT} value={editSent} onChange={(e) => setEditSent(e.target.value)}>
                                {opcScoring.sentimientos.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}
                              </select>
                            </label>
                            <label className="flex items-center gap-1">
                              Emoción:
                              <select className={SELECT} value={editEmo} onChange={(e) => setEditEmo(e.target.value)}>
                                {opcScoring.emociones.map((o) => <option key={o.valor} value={o.valor}>{labelEmocion(o.valor, o.etiqueta)}</option>)}
                              </select>
                            </label>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <input
                              value={editJust}
                              onChange={(e) => setEditJust(e.target.value)}
                              placeholder="¿Por qué? (ej: sarcasmo, el modelo lo leyó literal)"
                              className={`${SELECT} min-w-[240px] flex-1`}
                            />
                            <button
                              onClick={() => guardarCorreccion(c)}
                              className="rounded-xl border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/15 px-3 py-1 text-sm font-semibold text-white transition hover:bg-[var(--portal-cyan)]/25"
                            >
                              Guardar
                            </button>
                            <button
                              onClick={() => setEditId(null)}
                              className="rounded-xl border border-white/10 px-3 py-1 text-sm text-slate-400 transition hover:bg-white/[0.05]"
                            >
                              Cancelar
                            </button>
                          </div>
                          {editMsg ? <div className="mt-2 text-[11px] text-amber-300">{editMsg}</div> : null}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="py-6 text-center text-sm text-slate-500">
                No hay comentarios para este filtro.
              </p>
            )}
          </div>

            </>
          )}

          {subConv !== "publicaciones" ? null : (
            <PercepcionDominantes filtro={filtroEstable} />
          )}

          {subConv !== "palabras" ? null : (
            <>
          {/* NUBE DE PALABRAS. Va acá y no en una pestaña propia: responde la
              misma pregunta que los comentarios —qué se está diciendo— pero
              agregado. Los TEMAS son 8 cajas del clasificador; la nube muestra el
              vocabulario CRUDO, que es como se detecta de qué se habla ANTES de
              que exista una categoría para eso. */}
          <PercepcionNube filtro={filtroEstable} />

          {/* Emociones */}
          {emociones.length > 0 ? (
            <div className={CARD}>
              <div className="mb-2 text-sm font-medium text-slate-200">Emociones predominantes</div>
              <div className="flex flex-wrap gap-2">
                {(() => {
                  const total = emociones.reduce((s, e) => s + e.n, 0) || 1;
                  const colorEmo: Record<string, string> = {
                    joy: COLOR_POS, anger: COLOR_NEG, sadness: COLOR_CYAN,
                    fear: "#a88bfa", surprise: COLOR_COPPER,
                    humor_ironia: "#f97316", empatia: "#c084fc", sin_emocion: COLOR_NEU,
                    disgust: "#c98a5a", others: COLOR_NEU,
                  };
                  return emociones.map((e) => {
                    const c = colorEmo[e.emocion] ?? COLOR_NEU;
                    return (
                      <span key={e.emocion} className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs" style={{ background: c + "1f", color: c, borderColor: c + "33" }}>
                        <span className="h-2 w-2 rounded-full" style={{ background: c }} />
                        {labelEmocion(e.emocion, e.etiqueta)} · {Math.round((e.n / total) * 100)}%
                      </span>
                    );
                  });
                })()}
              </div>
            </div>
          ) : null}

          {/* "Comparación por facultad" y "Sentimiento por tema" se fueron a la
              pestaña COMPARAR. Estaban DUPLICADOS: los mismos cortes vivían como
              tabla en el Resumen y como gráfico acá, con métodos distintos —el tema
              "Otros" daba 58.7 en una pestaña y 64.3 en la otra—. Ahora cada corte
              aparece una sola vez, con el gráfico y la tabla de la MISMA consulta. */}

          {/* Las SEMANAS FUERA DE LO HABITUAL se fueron a la pestaña Alertas,
              junto con los términos bajo vigilancia: las dos responden "¿hay algo
              que mirar?" y estaban en pestañas distintas. Acá quedaban al fondo,
              entre un gráfico de emociones y la cola de curación. */}


            </>
          )}
        </>
      )}
    </section>
  );
}

export default PercepcionPanel;
