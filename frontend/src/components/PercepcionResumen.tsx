"use client";

// RESUMEN — "¿cómo estamos?". La vista del director, en UNA pantalla.
//
// Tiene exactamente tres cosas: el estado general, si hay algo que revisar, y
// qué se movió respecto del período anterior. Nada más.
//
// Lo que se fue, y por qué:
//   * "De qué se habla" y "Cómo está cada área" -> pestaña COMPARAR. No son un
//     resumen: son un ranking de 9 facultades y 8 temas, y además estaban
//     DUPLICADOS con los gráficos de la vieja pestaña Explorar, con números que
//     ni siquiera coincidían (el tema "Otros" daba 58.7 en una y 64.3 en otra).
//   * Los sliders de método y los z-scores -> Conversación / Alertas. Un director
//     no decide la vida media de un comentario para saber cómo está la universidad.
//
// Lectura: "promedio del período" (sin decaimiento). Cada comentario del período
// pesa igual; la temperatura reciente vive en Conversación, donde el tiempo importa.

import { useCallback, useEffect, useState } from "react";

import type {
  AnomaliaItem,
  DestacadosResponse,
  Filtro,
  ImpactoPalabrasResponse,
  MesSerie,
  PalabraDestacada,
  PosturaInstitucionalResponse,
  SintesisResponse,
} from "../lib/percepcion";
import { percepcionApi } from "../lib/percepcion";
import type { Destino } from "./PercepcionPanel";
import { PercepcionConflicto } from "./PercepcionConflicto";
import { PercepcionResumenSemanal } from "./PercepcionResumenSemanal";
import {
  BarraSentimiento,
  CARD,
  COLOR_COPPER,
  COLOR_NEG,
  COLOR_NEU,
  COLOR_POS,
  Delta,
  Indice,
  RotuloMetodo,
  SubPestanas,
  TituloBloque,
  colorIndice,
  fechaCorta,
  fmt,
  labelEmocion,
  lecturaIndice,
  nro,
} from "./PercepcionUI";

/** "2026-06-01" -> "jun 26". El eje necesita etiquetas cortas o no entran. */
function mesCorto(iso?: string): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("es-CL", { month: "short", year: "2-digit" }).replace(".", "");
}

/**
 * CÓMO FUE CAMBIANDO — la silueta del índice, mes a mes.
 *
 * NO repite la evolución de Conversación: esa es diaria, trailing, interactiva,
 * con bandas de eventos y clic-en-fecha. Esta responde una sola pregunta —
 * "¿veníamos subiendo o bajando?"— y se lee sin tocar nada.
 *
 * La escala es RELATIVA al rango de la serie, no 0-100: el índice se mueve entre
 * 55 y 70, así que barras desde cero serían doce rectángulos casi idénticos y no
 * se vería el movimiento, que es justamente lo único que este bloque aporta.
 */
function ComoFueCambiando({ meses }: { meses: MesSerie[] }) {
  const conDato = meses.filter((m) => m.indice != null);
  if (conDato.length < 2) return null;
  const valores = conDato.map((m) => m.indice as number);
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const rango = Math.max(max - min, 1);
  const ultimos = meses.slice(-18);
  const primero = conDato[0];
  const ultimo = conDato[conDato.length - 1];
  const delta = (ultimo.indice as number) - (primero.indice as number);

  return (
    <div className="mt-4 border-t border-white/5 pt-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Cómo fue cambiando
        </span>
        <span className="text-[11px] text-slate-500">
          {mesCorto(primero.mes)} → {mesCorto(ultimo.mes)} ·{" "}
          <strong style={{ color: delta > 0 ? COLOR_POS : delta < 0 ? COLOR_NEG : COLOR_NEU }}>
            {delta > 0 ? "▲ +" : delta < 0 ? "▼ " : "— "}
            {delta.toFixed(1)} pts
          </strong>
        </span>
      </div>
      <div className="flex h-14 items-end gap-[3px]">
        {ultimos.map((m) => {
          const alto = m.indice == null ? 0 : 12 + (88 * ((m.indice as number) - min)) / rango;
          return (
            <span
              key={m.mes}
              className="flex-1 rounded-t"
              style={{
                height: `${alto}%`,
                background: m.indice == null ? "transparent" : colorIndice(m.indice),
                opacity: m.indice == null ? 0 : 0.85,
              }}
              title={
                m.indice == null
                  ? `${mesCorto(m.mes)}: sin datos`
                  : `${mesCorto(m.mes)}: índice ${m.indice.toFixed(1)} · ${nro(m.n_comentarios)} comentarios`
              }
            />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-600">
        <span>{mesCorto(ultimos[0]?.mes)}</span>
        <span>escala {min.toFixed(0)}–{max.toFixed(0)}</span>
        <span>{mesCorto(ultimos[ultimos.length - 1]?.mes)}</span>
      </div>
    </div>
  );
}

/**
 * PALABRAS QUE MÁS PESAN — el vocabulario cargado, no el más frecuente.
 *
 * "La palabra más dicha" no informa: medido sobre el corpus real es
 * `felicitaciones` (121 apariciones, 0% negativo), y va a serlo todos los meses.
 * Lo que informa es `estudiantes` (n=37, 41% negativo) o `universidad` (n=34,
 * 26%): cuando alguien las nombra, buena parte de las veces es para quejarse.
 *
 * El vocabulario se valida sobre TODO el período, lo que además deja afuera los
 * handles de personas que el tokenizador no atrapa (ver la nota en el backend).
 */
/**
 * D · QUÉ CAMBIÓ, no qué se dice.
 *
 * Leave-one-out word impacts (Rieger et al., Text2Story'26 §3.2): se comparan las
 * dos ventanas por su vector de conteos y se mide cuánto MÁS se parecerían sin cada
 * palabra. La que más sube el parecido al sacarla es la que movió la conversación.
 *
 * Convive con «Las palabras que más pesan», que responde otra cosa: aquella ordena
 * por carga negativa (qué duele hoy), esta por CAMBIO respecto del período anterior.
 * Verificado sobre el corpus real: el ranking es estable ante corrimientos de la
 * ventana (75 % de solapamiento a 30 días, 90 % a 90).
 */
function QueCambio({ data }: { data: ImpactoPalabrasResponse }) {
  if (!data.hay_datos || !data.palabras.length) {
    return (
      <p className="text-xs text-slate-500">
        {data.motivo ?? "Sin período anterior comparable en esta ventana."}
      </p>
    );
  }
  const max = Math.max(...data.palabras.map((p) => Math.abs(p.impacto))) || 1;
  return (
    <>
      <ul className="space-y-1">
        {data.palabras.map((p) => {
          const subio = p.delta > 0;
          return (
            <li key={p.texto} className="flex items-center gap-2 text-xs">
              <span className="w-28 shrink-0 truncate text-slate-200">{p.texto}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                <span
                  className={`block h-full rounded-full ${
                    subio ? "bg-[var(--portal-cyan)]/70" : "bg-[var(--portal-copper)]/70"
                  }`}
                  style={{ width: `${(Math.abs(p.impacto) / max) * 100}%` }}
                />
              </span>
              <span className="w-24 shrink-0 text-right text-slate-500">
                {nro(p.n_previo)} → {nro(p.n_actual)}
              </span>
              <span
                className={`w-10 shrink-0 text-right font-semibold ${
                  subio ? "text-[var(--portal-cyan)]" : "text-[var(--portal-copper)]"
                }`}
              >
                {subio ? "+" : ""}{p.delta}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
        Sobre {nro(data.vocabulario)} palabras presentes en los dos períodos
        {data.similitud === null ? null : ` · parecido entre períodos ${data.similitud.toFixed(2)}`}.
        Solo entran las que se dicen en ambos: una palabra que aparece de la nada
        daría el impacto máximo por el solo hecho de ser nueva.
      </p>
    </>
  );
}

function PalabrasQuePesan({
  palabras, minimo, vidaMedia,
}: {
  palabras: PalabraDestacada[];
  minimo: number;
  vidaMedia: number;
}) {
  if (palabras.length === 0) return null;
  return (
    <div className={CARD}>
      <TituloBloque titulo="Las palabras que más pesan" ignoraRecencia vidaMedia={vidaMedia}>
        No las más repetidas —esas son siempre “felicitaciones” y “gracias”— sino las que
        arrastran más comentarios <strong className="text-slate-400">negativos</strong>. Solo
        entran palabras dichas en al menos {minimo} comentarios del período.
      </TituloBloque>
      <ul className="space-y-1.5">
        {palabras.map((p) => (
          <li key={p.texto} className="flex flex-wrap items-center gap-3">
            <span className="w-32 shrink-0 truncate text-sm font-semibold text-slate-100">
              {p.texto}
            </span>
            <span className="min-w-[120px] flex-1">
              <BarraSentimiento pos={p.n_pos} neu={p.n_neu} neg={p.n_neg} />
            </span>
            <span className="shrink-0 text-[11px] tabular-nums text-slate-500">
              {nro(p.n)} comentarios
            </span>
            <span
              className="w-24 shrink-0 text-right text-[11px] font-semibold tabular-nums"
              style={{ color: p.pct_neg >= 30 ? COLOR_NEG : COLOR_NEU }}
            >
              {p.pct_neg}% negativo
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * ALERTAS ACTIVAS — el puente al detalle.
 *
 * El director no tiene que acordarse de ir a mirar otra pestaña: si hay algo, se
 * lo decimos acá con un número y un botón. Si no hay nada, también se lo decimos
 * — "sin alertas" es información, no un bloque vacío.
 */
function AlertasActivas({
  anomalias, nFamilias, nMenciones, onVerAlertas,
}: {
  anomalias: AnomaliaItem[];
  nFamilias: number;
  nMenciones: number;
  onVerAlertas?: () => void;
}) {
  const hay = anomalias.length > 0 || nFamilias > 0;
  const top = [...anomalias].sort((a, b) => b.severidad - a.severidad).slice(0, 2);
  return (
    <div className={`${CARD} ${hay ? "border-amber-400/25" : "border-emerald-400/20"}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-200">
            {hay ? "Hay señales para revisar" : "Sin alertas en este período"}
          </div>
          <div className="mt-1 text-[11px] leading-5 text-slate-400">
            {hay ? (
              <>
                {anomalias.length > 0 ? (
                  <>
                    <strong className="text-amber-200">{anomalias.length}</strong>{" "}
                    {anomalias.length === 1 ? "semana se apartó" : "semanas se apartaron"} de su
                    historia reciente
                  </>
                ) : null}
                {anomalias.length > 0 && nFamilias > 0 ? " · " : ""}
                {nFamilias > 0 ? (
                  <>
                    <strong className="text-amber-200">{nro(nMenciones)}</strong> menciones de
                    términos bajo vigilancia en {nFamilias}{" "}
                    {nFamilias === 1 ? "categoría" : "categorías"}
                  </>
                ) : null}
                {top.length > 0 ? (
                  <> · la más marcada: {top.map((a) => fechaCorta(a.fecha)).join(", ")}</>
                ) : null}
              </>
            ) : (
              "Ninguna semana se apartó de su historia reciente y no hay menciones del léxico crítico."
            )}
          </div>
        </div>
        {onVerAlertas ? (
          <button
            type="button"
            onClick={onVerAlertas}
            className="shrink-0 rounded-full border border-[var(--portal-cyan)]/40 bg-[var(--portal-cyan)]/10 px-4 py-1.5 text-sm font-semibold text-[var(--portal-cyan)] transition hover:bg-[var(--portal-cyan)]/20"
          >
            Ver alertas →
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** POSTURA INSTITUCIONAL — la pregunta que el tablero no podía contestar.
 *
 * Va JUSTO DEBAJO del titular de sentimiento y no mezclada con él, porque la
 * gracia es poder comparar las dos lecturas: el tono dice cómo se habla, la
 * postura dice a quién le sirve. En este corpus el 73 % de los comentarios tiene
 * tono positivo pero sólo el 45 % es favorable a la UCN — esa brecha es el dato.
 *
 * ⚠️ NO entra en el índice. El índice mide temperatura de la conversación y está
 * ponderado por probabilidad; meter la postura adentro volvería a fusionar dos
 * constructos, que es exactamente el error que esta dimensión vino a corregir.
 */
function PosturaInstitucional({
  data, onIrA,
}: { data: PosturaInstitucionalResponse; onIrA?: (d: Destino) => void }) {
  if (!data.hay_datos || !data.distribucion.length) return null;
  // PALETA PROPIA, distinta a la del sentimiento A PROPÓSITO.
  //
  // El sentimiento usa verde/gris/rojo. Si la postura usara los mismos colores se
  // leería como "otro gráfico de lo mismo", y es justo al revés: la gracia de este
  // bloque es que mide OTRA COSA. Azul/naranja lo despega de un vistazo.
  //
  // De yapa, azul-naranja es un par seguro para daltonismo rojo-verde, que es
  // precisamente el que la paleta de sentimiento no cubre.
  const COLOR: Record<string, string> = {
    favorable: "#4d9de0",
    neutral: "#8895a8",
    adverso: "#f0a04b",
  };
  return (
    <div className={CARD}>
      <TituloBloque titulo="Postura hacia la UCN" ignoraRecencia>
        Distinta del tono: «¿paro? 😍» es positivo y adverso a la vez. Se deduce del
        tono y del tema — acierta el 80,7 % contra tu anotación, y nunca confunde
        favorable con adverso.
      </TituloBloque>

      {/* Barra apilada: el reparto se lee de un vistazo y los porcentajes suman 100. */}
      <div className="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-slate-800">
        {data.distribucion.map((d) =>
          d.pct > 0 ? (
            <div
              key={d.postura}
              style={{ width: `${d.pct}%`, background: COLOR[d.postura] ?? "#8aa0c0" }}
              title={`${d.etiqueta}: ${nro(d.n)} (${d.pct}%)`}
            />
          ) : null,
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {data.distribucion.map((d) => (
          <span key={d.postura} className="flex items-center gap-1.5 text-slate-400">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: COLOR[d.postura] ?? "#8aa0c0" }}
            />
            {d.etiqueta} <span className="text-slate-200">{d.pct}%</span>
            <span className="text-slate-600">({nro(d.n)})</span>
          </span>
        ))}
      </div>

      {data.temas_adversos.length > 0 && (
        <div className="mt-3 border-t border-slate-800 pt-2">
          {/* La pregunta que sigue SIEMPRE al titular es «¿de dónde sale lo adverso?».
              Sin esto habría que abrir la lista de comentarios para contestarla. */}
          <p className="text-[11px] text-slate-500">
            De dónde sale lo adverso
            {/* Sin voseo: español latinoamericano neutro (regla de Alberto, 2026-08-07). */}
            {onIrA ? <span className="text-slate-600"> · toca un tema para leerlo</span> : null}
          </p>
          {/* CADA TEMA ES UN SALTO a la conversación que lo sostiene.
              Es la pregunta que sigue siempre a este bloque —«¿y qué dicen?»— y
              hasta ahora había que cruzar a mano: cambiar de pestaña, encontrar el
              filtro de tema, elegirlo. Cuatro pasos entre el dato y su evidencia,
              y por eso casi nadie los daba. Va a "publicaciones" y no a la línea de
              tiempo porque lo que se busca acá son los POSTS concretos. */}
          <ul className="mt-1 space-y-0.5">
            {data.temas_adversos.map((t) => {
              const fila = (
                <>
                  <span className="text-slate-300 group-hover:text-white">{t.etiqueta}</span>
                  <span className="text-slate-500">{nro(t.n)} comentarios</span>
                  {/* Mismo naranja que la barra: el número habla de lo adverso y
                      tiene que leerse como parte de esa serie, no como un acento suelto. */}
                  <span className="ml-auto" style={{ color: COLOR.adverso }}>
                    {t.pct}% del tema
                  </span>
                </>
              );
              if (!onIrA) {
                return (
                  <li key={t.tema} className="flex items-baseline gap-2 text-[11px]">{fila}</li>
                );
              }
              return (
                <li key={t.tema}>
                  <button
                    type="button"
                    onClick={() =>
                      onIrA({
                        vista: "conversacion",
                        sub: "publicaciones",
                        filtro: { tema: t.tema },
                        desde: `${t.etiqueta} · ${t.pct}% adverso`,
                      })
                    }
                    className="group -mx-1.5 flex w-[calc(100%+0.75rem)] items-baseline gap-2 rounded-lg px-1.5 py-1 text-left text-[11px] transition hover:bg-white/[0.06]"
                    title={`Ver de qué se habla en «${t.etiqueta}»`}
                  >
                    {fila}
                    <span className="text-slate-600 transition group-hover:text-slate-300">→</span>
                  </button>
                </li>
              );
            })}
          </ul>
          {/* El otro destino natural de este bloque. Un tema adverso lleva a lo que
              se DIJO (Conversación); el reparto entre áreas lleva a dónde DUELE
              (Comparar). Son las dos mitades de «¿por qué?» y conviene que las dos
              salgan del mismo lugar. */}
          {onIrA ? (
            <button
              type="button"
              onClick={() => onIrA({ vista: "comparar", sub: "temas" })}
              className="mt-2 text-[11px] text-slate-500 underline decoration-slate-700 underline-offset-2 transition hover:text-slate-300 hover:decoration-slate-500"
            >
              Ver cómo se reparte entre áreas →
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** Las dos preguntas del Resumen.
 *
 * ⚠️ EL CORTE NO ES POR LARGO, ES POR MOMENTO. El Resumen es la pestaña de "un
 * vistazo": es lo primero que abre un director y esconder el estado detrás de un
 * clic iría contra su propósito. Por eso "Cómo estamos" se queda con TODO lo que
 * contesta esa pregunta —el párrafo semanal, el índice, el conflicto, la postura
 * y el aviso de alertas activas— y lo único que se corre a la segunda es el
 * DETALLE del movimiento, que se consulta después de saber cómo estamos.
 *
 * Si alguna vez hay que sacarle algo a la primera, que no sea el índice ni las
 * alertas activas: son las dos cosas por las que alguien entra acá. */
const SUB_RESUMEN = [
  {
    id: "estado",
    label: "¿Cómo estamos?",
    hint:
      "El estado del período: el resumen en palabras, el índice con su distribución, los " +
      "comentarios adversos y si hay algo que requiera atención.",
  },
  {
    id: "cambio",
    label: "¿Qué cambió?",
    hint:
      "El movimiento respecto del período anterior: qué temas se movieron, qué emoción " +
      "ganó terreno y qué palabras pesan más en la conversación.",
  },
] as const;

export function PercepcionResumen({
  filtro, onVerAlertas, onVerComparar, onIrA,
}: {
  filtro: Filtro;
  /** Salta a la pestaña Alertas. Opcional para poder montar el bloque solo. */
  onVerAlertas?: () => void;
  /** Salta a la pestaña Comparar, que es donde vive el detalle por tema y área. */
  onVerComparar?: () => void;
  /** Salto CON CONTEXTO: lleva el filtro y la sub-pestaña del dato que se tocó.
   *
   * Es la diferencia entre cambiar de pestaña y navegar. `onVerComparar` deja al
   * director en Comparar mirando todo; esto lo deja mirando exactamente el tema
   * del que venía. Opcional: sin él las filas se renderizan como texto plano y el
   * componente sigue montándose suelto. */
  onIrA?: (d: Destino) => void;
}) {
  const [sub, setSub] = useState<"estado" | "cambio">("estado");
  const [data, setData] = useState<SintesisResponse | null>(null);
  const [anomalias, setAnomalias] = useState<AnomaliaItem[]>([]);
  const [nFamilias, setNFamilias] = useState(0);
  const [nMenciones, setNMenciones] = useState(0);
  const [dest, setDest] = useState<DestacadosResponse | null>(null);
  const [impacto, setImpacto] = useState<ImpactoPalabrasResponse | null>(null);
  const [postura, setPostura] = useState<PosturaInstitucionalResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      // nivel/orden fijos: los cortes por tema y área se muestran en Comparar,
      // que es quien tiene los selectores. Acá solo se usan el titular y los cambios.
      const [s, a, t, d, imp, pos] = await Promise.all([
        percepcionApi.sintesis("facultad", "peor", filtro),
        percepcionApi.anomalias(filtro).catch(() => null),
        percepcionApi.terminos(filtro).catch(() => null),
        percepcionApi.destacados(filtro).catch(() => null),
        percepcionApi.impactoPalabras(filtro).catch(() => null),
        percepcionApi.postura(filtro).catch(() => null),
      ]);
      setData(s);
      setPostura(pos);
      setDest(d);
      setImpacto(imp);
      setAnomalias(a?.items ?? []);
      setNFamilias(t?.familias.length ?? 0);
      setNMenciones(t?.global?.n_con_termino ?? 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el resumen.");
    } finally {
      setCargando(false);
    }
  }, [filtro]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  if (!data && cargando) {
    return (
      <div className={CARD}>
        <p className="py-6 text-center text-sm text-slate-500">Cargando resumen…</p>
      </div>
    );
  }
  // El error solo tapa la vista si NO hay nada que mostrar. Con datos previos en
  // pantalla se avisa arriba y se deja el contenido: que una recarga fallida
  // vacíe el tablero es peor que el error.
  if (error && !data) {
    return (
      <div className={CARD}>
        <p className="text-sm text-[#f2777a]">{error}</p>
      </div>
    );
  }
  if (!data || !data.hay_datos || !data.global) {
    return (
      <div className={CARD}>
        <p className="py-6 text-center text-sm text-slate-500">
          No hay datos de percepción para este filtro.
        </p>
      </div>
    );
  }

  const g = data.global;
  const min = data.n_min_evidencia;

  return (
    <div
      className="space-y-4 transition-opacity duration-200"
      /* Señal de refresco DELIBERADAMENTE tenue: un atenuado leve en vez de un
         spinner o un vaciado. Con el debounce de 350 ms la recarga dura poco y
         parpadear en cada cambio de filtro cansa la vista. */
      style={{ opacity: cargando ? 0.55 : 1 }}
      aria-busy={cargando}
    >
      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm text-rose-200">
          {error}
          {cargando ? " · reintentando…" : ""}
        </div>
      ) : null}

      <SubPestanas opciones={SUB_RESUMEN} activa={sub} onCambio={setSub} />

      {sub !== "estado" ? null : (
      <>
      {/* Resumen semanal en prosa. Va PRIMERO porque es la pregunta que se hace antes
          que "cuánto": el número dice cómo estamos, el párrafo dice qué pasó. Se monta
          aparte y con su propia carga para que un fallo de OpenAI no arrastre al resto
          del resumen, que es todo determinista.

          NO recibe `filtro` a propósito: es a nivel universidad y por semana cerrada
          (ver el docstring del componente). */}
      <PercepcionResumenSemanal />

      {/* Titular: el estado general en una línea. */}
      <div className={CARD}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Percepción del período
          </span>
          <RotuloMetodo vidaMedia={filtro.vidaMedia} />
        </div>
        <div className="mt-1 flex items-baseline gap-3">
          <span className="text-4xl font-bold" style={{ color: colorIndice(g.indice) }}>
            {fmt(g.indice)}
          </span>
          <span className="text-base text-slate-300">{lecturaIndice(g.indice)}</span>
        </div>
        <div className="mt-1 text-[11px] text-slate-500">
          {nro(g.n_comentarios)} comentarios · {fechaCorta(data.periodo?.desde)} –{" "}
          {fechaCorta(data.periodo?.hasta)}
          {g.emocion_dominante ? (
            <>
              {" "}· emoción predominante:{" "}
              <strong className="text-slate-300">
                {labelEmocion(g.emocion_dominante.emocion, g.emocion_dominante.etiqueta)}
              </strong>{" "}
              ({g.emocion_dominante.pct}%)
            </>
          ) : null}
        </div>
        <div className="mt-3">
          <BarraSentimiento
            pos={g.distribucion.positivo}
            neu={g.distribucion.neutral}
            neg={g.distribucion.negativo}
            alta
          />
          <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: COLOR_POS }} />
              Positivo ({nro(g.distribucion.positivo)})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: COLOR_NEU }} />
              Neutral ({nro(g.distribucion.neutral)})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: COLOR_NEG }} />
              Negativo ({nro(g.distribucion.negativo)})
            </span>
          </div>
        </div>
        {/* La silueta va DENTRO del titular: un número sin su trayectoria no
            dice si estamos bien o si veníamos peor. */}
        {dest ? <ComoFueCambiando meses={dest.serie_mensual} /> : null}
      </div>

      {/* PEGADO al índice, y a propósito. El índice es un promedio de tono: sobre
          cientos de mensajes amables, una decena de mensajes duros no lo mueve. Leerlo
          solo durante un conflicto es cómo se llega a la conclusión contraria. */}
      <PercepcionConflicto filtro={filtro} />

      {postura ? <PosturaInstitucional data={postura} onIrA={onIrA} /> : null}

      {/* Las alertas van antes que el movimiento: si hay conversación de paro,
          eso pesa más que la variación de un tema. */}
      <AlertasActivas
        anomalias={anomalias}
        nFamilias={nFamilias}
        nMenciones={nMenciones}
        onVerAlertas={onVerAlertas}
      />
      </>
      )}

      {sub !== "cambio" ? null : (
      <>

      {/* QUÉ CAMBIÓ: es lo que no se sabía antes de abrir el tablero. Reemplazó a
          "Focos de atención" (índice < 50), que quedó vacío apenas se corrigió la
          clasificación — y "lo más hablado" habría repetido siempre Académico y
          Eventos. Lo informativo es el movimiento. */}
      <div className={CARD}>
        <TituloBloque titulo="Qué cambió" ignoraRecencia vidaMedia={filtro.vidaMedia}>
          {data.periodo_anterior ? (
            <>
              Comparado con el período anterior ({fechaCorta(data.periodo_anterior.desde)} –{" "}
              {fechaCorta(data.periodo_anterior.hasta)}). Solo temas con al menos {min}{" "}
              comentarios: con menos, una variación del 300% es ruido.
            </>
          ) : (
            <>Elige un rango acotado (30 d, 90 d, 1 año…) para comparar contra el período previo.</>
          )}
        </TituloBloque>
        {/* La emoción que más creció va DENTRO de "Qué cambió": es la misma
            pregunta (¿qué se movió?) mirada por otro lado. El bloque de temas
            responde "en qué se habla distinto"; esta línea, "con qué ánimo". */}
        {dest?.emocion_cambio ? (
          <p className="mb-3 rounded-2xl border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] leading-5 text-slate-300">
            La emoción que más ganó terreno es{" "}
            <strong style={{ color: COLOR_COPPER }}>
              {labelEmocion(dest.emocion_cambio.emocion, dest.emocion_cambio.etiqueta)}
            </strong>
            : pasó de {dest.emocion_cambio.pct_anterior}% a {dest.emocion_cambio.pct}% de la
            conversación{" "}
            <strong className="text-slate-400">(+{dest.emocion_cambio.delta_pp} pts)</strong>
            {dest.emocion_cambio.es_nueva ? " — no aparecía en el período anterior" : ""}.
          </p>
        ) : null}
        {data.cambios.length > 0 ? (
          <ul className="space-y-2">
            {data.cambios.map((c) => (
              <li
                key={c.tema}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/5 bg-white/[0.02] px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-100">{c.etiqueta}</span>
                    {c.es_nuevo ? (
                      <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-200">
                        nuevo este período
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-0.5 text-[11px] text-slate-400">
                    {nro(c.n_comentarios)} comentarios
                    {!c.es_nuevo ? ` (antes ${nro(c.n_anterior)})` : ""}
                    {c.emocion_dominante
                      ? ` · ${labelEmocion(c.emocion_dominante.emocion, c.emocion_dominante.etiqueta)}`
                      : ""}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <Delta valor={c.delta_volumen_pct} sufijo="%" titulo="volumen" />
                  <Delta valor={c.delta_indice} sufijo=" pts" titulo="índice" />
                  <Indice valor={c.indice} evidencia />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-4 text-center text-sm text-slate-500">
            {data.periodo_anterior
              ? `Ningún tema alcanza los ${min} comentarios en este período.`
              : "Con el rango en “Todo” no hay período previo contra el cual comparar."}
          </p>
        )}
      </div>

      {/* Qué se dice, literalmente. Es lo único de "vocabulario" que aparece en
          el Resumen: la nube completa vive en Conversación. */}
      {dest ? (
        <PalabrasQuePesan
          palabras={dest.palabras}
          minimo={dest.vocabulario_min}
          vidaMedia={filtro.vidaMedia}
        />
      ) : null}

      {/* Y qué CAMBIÓ. Es la otra mitad de la pregunta: el bloque de arriba dice
          qué duele hoy (ordena por carga negativa), este dice qué se movió
          respecto del período anterior. Van juntos y no se reemplazan. */}
      {impacto ? (
        <div className={CARD}>
          <TituloBloque titulo="Qué cambió respecto del período anterior">
            Palabras que más movieron la conversación: las que, si se quitaran, harían
            que los dos períodos se parecieran más. En <span className="text-[var(--portal-cyan)]">cian</span>{" "}
            las que crecieron, en <span className="text-[var(--portal-copper)]">cobre</span> las que se retrajeron.
          </TituloBloque>
          <QueCambio data={impacto} />
        </div>
      ) : null}

      {/* Puente a COMPARAR. El desglose por tema y por área no está acá a
          propósito —es un ranking, no un resumen— pero el director tiene que
          saber dónde encontrarlo. */}
      {onIrA || onVerComparar ? (
        <button
          type="button"
          // Con `onIrA` abre además la SUB-pestaña: dejar al director en Comparar
          // sin decirle en cuál de sus tres vistas lo obliga a buscar de nuevo lo
          // que venía siguiendo. `onVerComparar` queda de respaldo.
          onClick={() =>
            onIrA
              ? onIrA({ vista: "comparar", sub: "estado" })
              : onVerComparar?.()
          }
          className="w-full rounded-3xl border border-white/10 bg-white/[0.02] px-4 py-3 text-left transition hover:border-white/20 hover:bg-white/[0.05]"
        >
          <span className="text-sm font-medium text-slate-200">
            ¿Dónde está el problema? →
          </span>
          <span className="mt-0.5 block text-[11px] text-slate-500">
            El desglose por tema y por facultad, departamento o sede está en{" "}
            <strong className="text-slate-400">Comparar</strong>.
          </span>
        </button>
      ) : null}
      </>
      )}
    </div>
  );
}

export default PercepcionResumen;
