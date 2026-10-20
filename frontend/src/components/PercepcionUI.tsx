"use client";

// Primitivas visuales COMPARTIDAS del feature Percepción.
//
// Por qué existe: los colores, `colorIndice`, `fmt` y las barras estaban
// copiados en PercepcionPanel, PercepcionSintesis y PercepcionNube. Un mismo
// índice tiene que tener el MISMO color y el MISMO redondeo en las cuatro
// pestañas, o el lector cree que son métricas distintas. Con tres copias eso
// dependía de que nadie tocara una sola.
//
// Acá va solo lo que se usa en más de un lado. Lo específico de una vista
// (opciones de ECharts, controles de la nube) se queda en su componente.

import type { ReactNode } from "react";

export const CARD = "rounded-3xl border border-white/10 bg-[#0b1424] p-4";
// `w-full` + `min-w-0` es lo que evita que un <select> se desborde de su celda.
// Sin eso cada uno toma el ancho de su opción más larga, y en la barra de filtros
// "Departamento" se salía del panel mientras "Sede" quedaba diminuto: cuatro
// controles del mismo rango visual con cuatro anchos distintos. El contenedor
// decide el ancho, no el contenido.
export const SELECT =
  "w-full min-w-0 truncate rounded-xl border border-white/10 bg-[#0b1424] px-3 py-1.5 " +
  "text-sm text-slate-200 outline-none transition focus:border-[var(--portal-cyan)] " +
  "hover:border-white/20";

export const COLOR_POS = "#51c28c";
export const COLOR_NEU = "#8aa0c0";
export const COLOR_NEG = "#f2777a";
export const COLOR_CYAN = "#4f9cf0";
export const COLOR_COPPER = "#e0aa4e";

const EMOCION_LABEL_UI: Record<string, string> = {
  joy: "Alegría",
  sadness: "Tristeza",
  anger: "Enojo",
  fear: "Miedo",
  surprise: "Sorpresa",
  humor_ironia: "Humor e ironía",
  empatia: "Empatía",
  sin_emocion: "Sin emoción",
  disgust: "Asco",
  others: "Otra emoción",
};

export function labelEmocion(valor?: string | null, etiqueta?: string | null): string {
  if (!valor) return etiqueta ?? "—";
  const limpia = etiqueta && !etiqueta.includes("_") ? etiqueta.replace(" / ", " e ") : null;
  return limpia ?? EMOCION_LABEL_UI[valor] ?? valor.replaceAll("_", " ");
}

export function colorIndice(v: number | null): string {
  if (v == null) return COLOR_NEU;
  if (v < 40) return COLOR_NEG;
  if (v < 60) return COLOR_COPPER;
  return COLOR_POS;
}

export function fmt(v: number | null | undefined, dec = 1): string {
  return v == null ? "—" : v.toFixed(dec);
}

/** 57.5 → "Favorable". El número solo no le dice nada a quien no vive el tablero. */
export function lecturaIndice(v: number | null): string {
  if (v == null) return "Sin señal";
  if (v < 40) return "Desfavorable";
  if (v < 50) return "Bajo el neutro";
  if (v < 60) return "Neutro";
  return "Favorable";
}

export function fechaCorta(iso?: string | null): string {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}

export function nro(v: number): string {
  return v.toLocaleString("es-CL");
}

/**
 * RÓTULO DE MÉTODO. Es la pieza que resuelve el hallazgo de la auditoría.
 *
 * El mismo tema daba 58.7 en el Tablero y 64.3 en la Síntesis —y "Organización
 * estudiantil" cruzaba el neutro de una pestaña a otra— porque una vista pondera
 * la recencia y la otra no. Las dos decisiones son correctas por separado; lo que
 * faltaba era decirlo en pantalla. Cada pestaña declara con cuál de las dos lee.
 */
export function RotuloMetodo({
  vidaMedia = 0, ignoraRecencia = false,
}: {
  /** Valor del control global de recencia, en días. 0 = sin decaimiento. */
  vidaMedia?: number;
  /** El bloque NO usa recencia aunque el control esté activo (la detección de
   *  anomalías, que se rompe si se la aplica). Se dice, no se esconde. */
  ignoraRecencia?: boolean;
}) {
  const conRecencia = !ignoraRecencia && vidaMedia > 0;
  const texto = ignoraRecencia
    ? "sin recencia (detección)"
    : conRecencia
      ? `recencia ${vidaMedia} d`
      : "promedio del período";
  const ayuda = ignoraRecencia
    ? "Este bloque ignora el control de recencia a propósito. La detección de " +
      "anomalías corre sin decaimiento porque, aplicándolo, el evento se reparte y " +
      "deja de destacar: medido sobre el paro de 2026, el |z| máximo caía a 1.98 " +
      "contra un umbral de 2.5, o sea CERO detecciones."
    : conRecencia
      ? `Lo más reciente pesa más: el peso baja día a día y a los ${vidaMedia} días un ` +
        "comentario deja de contar. Una unidad sin actividad en ese lapso queda sin " +
        "índice — no es un error, es que no habló últimamente."
      : "Cada comentario del período pesa igual, sin importar si es de hoy o de hace un " +
        "mes. Responde “de qué se habló en este período”.";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
        conRecencia
          ? "border-[var(--portal-copper)]/30 bg-[var(--portal-copper)]/10 text-[var(--portal-copper)]"
          : "border-white/10 bg-white/[0.04] text-slate-400"
      }`}
      title={ayuda}
    >
      {texto}
    </span>
  );
}

/** Índice ausente por recencia: la unidad tiene comentarios pero ninguno entra en
 *  la ventana. Decirlo con palabras — un guion mudo se lee como "falta el dato". */
export function SinActividadReciente({ dias }: { dias: number }) {
  return (
    <span
      className="text-[11px] text-slate-500"
      title={`Tiene comentarios en el período, pero ninguno dentro de los últimos ${dias} días que pondera la recencia. Pon la recencia en "off" para ver su índice del período completo.`}
    >
      sin actividad reciente
    </span>
  );
}

/** Índice + su lectura en palabras. Atenuado cuando la muestra no alcanza. */
export function Indice({ valor, evidencia }: { valor: number | null; evidencia: boolean }) {
  return (
    <div className="flex items-baseline gap-2">
      <span
        className="text-lg font-bold tabular-nums"
        style={{ color: colorIndice(valor), opacity: evidencia ? 1 : 0.45 }}
      >
        {fmt(valor)}
      </span>
      <span className="text-[11px] text-slate-500">{lecturaIndice(valor)}</span>
    </div>
  );
}

/**
 * Confianza del índice (0..1) como barra + porcentaje.
 *
 * Combina volumen y certeza del modelo: min(1, n/30) · (Σ suma_ganadora / n).
 * Tiene lectura OPERATIVA además de estadística: una unidad con muchos
 * comentarios pero confianza baja suele significar que falta ingestar su cuenta
 * de Instagram, no que la unidad "no tenga opinión".
 */
export function BarraConfianza({ valor }: { valor: number }) {
  const pct = Math.round(100 * Math.max(0, Math.min(1, valor)));
  const color = pct < 30 ? COLOR_NEG : pct < 60 ? COLOR_COPPER : COLOR_POS;
  return (
    <span
      className="flex items-center gap-2"
      title={
        `Confianza ${pct}%. Combina cuántos comentarios hay (satura en 30) con ` +
        "qué tan seguro estuvo el modelo. Por debajo de 30% el índice es referencial."
      }
    >
      <span className="h-1.5 w-12 shrink-0 overflow-hidden rounded-full bg-white/[0.06]">
        <span className="block h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </span>
      <span className="text-[11px] tabular-nums" style={{ color }}>
        {pct}%
      </span>
    </span>
  );
}

/**
 * Variación contra el período anterior, con signo y color.
 *
 * El color NO es "verde = bueno": para el VOLUMEN subir no es bueno ni malo, es
 * movimiento. Por eso el volumen va neutro y solo el índice se colorea, que es
 * donde subir sí significa mejor.
 */
export function Delta({
  valor, sufijo, titulo,
}: {
  valor: number | null;
  sufijo: string;
  titulo: string;
}) {
  if (valor == null) {
    return (
      <span className="w-16 text-right text-[11px] text-slate-600" title={`Sin ${titulo} previo`}>
        —
      </span>
    );
  }
  const esIndice = titulo === "índice";
  const color = !esIndice
    ? COLOR_NEU
    : valor > 0
      ? COLOR_POS
      : valor < 0
        ? COLOR_NEG
        : COLOR_NEU;
  const flecha = valor > 0 ? "▲" : valor < 0 ? "▼" : "—";
  return (
    <span
      className="w-16 text-right text-[11px] font-semibold tabular-nums"
      style={{ color }}
      title={`Variación de ${titulo} contra el período anterior`}
    >
      {flecha} {valor > 0 ? "+" : ""}{valor}{sufijo}
    </span>
  );
}

export function SinEvidencia({ n, minimo }: { n: number; minimo: number }) {
  return (
    <span
      className="rounded-full border border-amber-400/25 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold text-amber-200"
      title={`Solo ${n} comentarios (se necesitan ${minimo} para leer el índice como tendencia). La cifra es referencial.`}
    >
      muestra insuficiente
    </span>
  );
}

/**
 * Barra 100% apilada pos/neu/neg con ETIQUETADO DIRECTO del porcentaje.
 *
 * Se evaluó la diverging stacked bar (canónica para escalas Likert, con el
 * neutral partido al medio) y se descartó: para mostrar PORCENTAJES la 100%
 * apilada aprovecha mejor el espacio y el etiquetado directo resuelve la lectura.
 *
 * El porcentaje va DENTRO de cada segmento y solo si entra: por debajo de ~12%
 * de ancho el número no cabe y ensucia más de lo que informa. Esos casos se leen
 * igual en el tooltip y en la fila de conteos.
 */
const ANCHO_MINIMO_ETIQUETA = 12; // % de la barra

export function BarraSentimiento({
  pos, neu, neg, alta = false,
}: {
  pos: number;
  neu: number;
  neg: number;
  /** Barra gruesa con etiquetas; la fina (default) va sin texto. */
  alta?: boolean;
}) {
  const total = pos + neu + neg || 1;
  const partes = [
    { n: pos, color: COLOR_POS, label: "positivo" },
    { n: neu, color: COLOR_NEU, label: "neutral" },
    { n: neg, color: COLOR_NEG, label: "negativo" },
  ];
  return (
    <div
      className={`flex w-full overflow-hidden rounded-full bg-white/[0.06] ${alta ? "h-5" : "h-2"}`}
      title={`${pos} positivos · ${neu} neutrales · ${neg} negativos`}
      role="img"
      aria-label={
        `${Math.round((100 * pos) / total)}% positivo, ` +
        `${Math.round((100 * neu) / total)}% neutral, ` +
        `${Math.round((100 * neg) / total)}% negativo`
      }
    >
      {partes.map((p) => {
        const ancho = (100 * p.n) / total;
        return (
          <div
            key={p.label}
            className="flex items-center justify-center"
            style={{ width: `${ancho}%`, background: p.color }}
          >
            {alta && ancho >= ANCHO_MINIMO_ETIQUETA ? (
              <span className="text-[10px] font-bold tabular-nums" style={{ color: "#0b1424" }}>
                {Math.round(ancho)}%
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

/** Encabezado de bloque: título + rótulo de método opcional + bajada. */
export function TituloBloque({
  titulo, vidaMedia, ignoraRecencia, children, extra,
}: {
  titulo: string;
  /** Días del control global de recencia. Omitir = el bloque no lleva rótulo. */
  vidaMedia?: number;
  ignoraRecencia?: boolean;
  /** Bajada explicativa. Una línea, en criollo. */
  children?: ReactNode;
  extra?: ReactNode;
}) {
  return (
    <>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-200">{titulo}</span>
        {vidaMedia === undefined ? null : (
          <RotuloMetodo vidaMedia={vidaMedia} ignoraRecencia={ignoraRecencia} />
        )}
        {extra}
      </div>
      {children ? <p className="mb-3 text-[11px] leading-5 text-slate-500">{children}</p> : null}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* SUB-PESTAÑAS — un solo patrón para todas las secciones.                     */
/* -------------------------------------------------------------------------- */
//
// POR QUÉ EXISTE: Conversación fue la primera en partirse en sub-secciones y su
// UI quedó escrita a mano dentro del Panel. Cuando el resto de las pestañas
// necesitó lo mismo, copiar ese bloque cuatro veces habría dejado cuatro
// implementaciones que se van separando de a poco. Acá vive una sola.
//
// LAS DOS DECISIONES QUE HACEN QUE ESTO SIRVA A UN DIRECTOR
// ---------------------------------------------------------
// 1. **El hint se VE, no se esconde en un `title`.** Un tooltip solo lo descubre
//    quien ya sabe que está ahí — o sea, quien no lo necesita. Debajo de los
//    botones va, en texto plano, qué contesta la sub-sección elegida.
// 2. **Los nombres son lo que el bloque RESPONDE, no cómo se llama por dentro.**
//    "Qué se está diciendo de un paro" en vez de "Léxico de vigilancia";
//    "Quincenas fuera de lo normal" en vez de "Detección de anomalías". Quien
//    entra al panel busca una respuesta, no un módulo.
//
// ⚠️ NO subdividir una sección de DOS bloques que se leen juntos. Partir por
// partir esconde: obliga a un clic para ver algo que estaba a la vista. Conviene
// cuando los bloques compiten por la atención o cuando apilados no entran en
// pantalla — que fue la razón medida para partir Conversación.

export interface SubSeccion<T extends string = string> {
  id: T;
  /** Lo que el director ve en el botón. Corto. */
  label: string;
  /** Qué contesta. Se muestra debajo, no es un tooltip. */
  hint: string;
}

export function SubPestanas<T extends string>({
  opciones,
  activa,
  onCambio,
}: {
  opciones: readonly SubSeccion<T>[];
  activa: T;
  onCambio: (id: T) => void;
}) {
  const sel = opciones.find((o) => o.id === activa);
  return (
    <div className="space-y-2">
      {/* SUBRAYADO, no píldoras. Las pestañas de sección ya son píldoras cian, y dos
          filas de píldoras una encima de la otra se leen como un solo grupo de seis
          botones: nadie tiene por qué deducir que la segunda fila depende de la
          primera. El subrayado es una familia visual distinta y la jerarquía se lee
          sola — cambia la FORMA, no solo el color. */}
      <div className="flex flex-wrap items-end gap-x-5 gap-y-1 border-b border-white/10"
           role="tablist">
        {opciones.map((o) => (
          <button
            key={o.id}
            type="button"
            role="tab"
            aria-selected={activa === o.id}
            onClick={() => onCambio(o.id)}
            className={
              "-mb-px border-b-2 px-0.5 pb-2 text-xs transition " +
              (activa === o.id
                ? "border-[var(--portal-cyan)] font-semibold text-slate-100"
                : "border-transparent text-slate-500 hover:border-white/20 hover:text-slate-300")
            }
          >
            {o.label}
          </button>
        ))}
      </div>
      {sel ? <p className="text-[11px] leading-5 text-slate-500">{sel.hint}</p> : null}
    </div>
  );
}
