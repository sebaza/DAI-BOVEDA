"use client";

// Nube de palabras de Percepción — el vocabulario CRUDO de los comentarios.
//
// Complementa la síntesis: los TEMAS son 8 categorías del clasificador; acá se ve
// qué se dice literalmente, incluso lo que todavía no tiene categoría.
//
// Por qué NO se usa una librería de wordcloud (echarts-wordcloud u otra):
//   * Sería otro <script> por CDN con su SRI, y la CSP del portal es estricta.
//   * Un canvas no es texto: no se puede seleccionar, ni buscar con Ctrl+F, ni
//     leer con lector de pantalla. Para un tablero institucional eso importa.
// El layout es CSS puro (flex-wrap) con el tamaño de fuente escalado por
// frecuencia. Queda menos apretado que un packing por espiral, pero es texto real.
//
// Sobre el COLOR (la duda que planteó la DAI, y con razón): colorear por EMOCIÓN
// no funciona con estos datos — el 57% es "Alegría" y el 36% "Sin emoción", o sea
// el 93% cae en dos colores y la nube queda plana. Por eso el criterio por defecto
// es SENTIMIENTO con los neutrales en gris tenue: el color solo "grita" donde hay
// polaridad real (~40% del corpus). Igual se puede cambiar desde el selector.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import { PALETA } from "@/lib/paleta";

import type { Filtro, NubeResponse, PalabraNube } from "../lib/percepcion";
import { esCancelacion, percepcionApi } from "../lib/percepcion";
import { CARD, COLOR_NEG, Esqueleto, COLOR_NEU, COLOR_POS, SELECT } from "./PercepcionUI";

type CriterioColor = "sentimiento" | "tema" | "mono";

// Paleta categórica para el coloreo por tema. Tonos bien separados en matiz para
// que se distingan sobre el fondo oscuro incluso en tamaños chicos.
//
// ⚠️ TIENE QUE CUBRIR LA TAXONOMIA COMPLETA. `colorDe` cae a COLOR_NEU (el gris de
// los neutrales) cuando falta una clave, o sea que un tema sin color acá NO rompe
// nada visible: se pinta gris y se confunde con "sin sentimiento". Ya pasó — quedó
// con las claves previas a la partición de `eventos` (2026-08-14) y 4 de los 8 temas
// se veían grises. Si cambia `taxonomy.ETIQUETAS` en el worker, actualizar acá.
const COLOR_TEMA: Record<string, string> = {
  academico: PALETA.azulClaro,
  vida_estudiantil: PALETA.serie3,
  organizacion_estudiantil: PALETA.tierraClara,
  servicios_institucionales: PALETA.azul,
  logros_reconocimientos: PALETA.adverso,
  bienestar_salud: PALETA.serie4,
  mascotas: PALETA.tierra,
  otros: PALETA.neutro,
  // Retirados: se conservan para que los datos históricos aún sin re-clasificar
  // no se pinten grises. Ver `taxonomy.RENOMBRES`.
  eventos: PALETA.serie3,
  charlas_seminarios: PALETA.azulClaro,
  infraestructura: PALETA.azul,
  tramites: PALETA.azul,
  matricula_aranceles: PALETA.azul,
  difusion_admision: PALETA.azul,
};

const TAM_MIN = 13;
const TAM_MAX = 52;

function colorDe(p: PalabraNube, criterio: CriterioColor): string {
  if (criterio === "mono") return PALETA.azulClaro;
  if (criterio === "tema") return COLOR_TEMA[p.tema_dominante ?? "otros"] ?? COLOR_NEU;
  if (p.sentimiento_dominante === "POS") return COLOR_POS;
  if (p.sentimiento_dominante === "NEG") return COLOR_NEG;
  return COLOR_NEU;
}

/** Los neutrales se atenúan: sin esto el 60% del corpus grita igual que la señal. */
function opacidadDe(p: PalabraNube, criterio: CriterioColor): number {
  if (criterio !== "sentimiento") return 1;
  return p.sentimiento_dominante === "NEU" ? 0.45 : 1;
}

/**
 * Escala raíz cuadrada, no lineal. Con frecuencias de 23 a 2, la lineal deja a
 * la mayoría de las palabras pegadas al mínimo y una sola gigante; la raíz
 * reparte mejor el rango visible.
 *
 * `largo` activa la CORRECCIÓN POR LONGITUD. La guía de visualización de datos
 * de la UE lo señala como el defecto principal de las nubes de palabras:
 *   "Long words draw much more attention than short ones, even though they
 *    might have the exact same frequency."
 * Pasa en estos datos: "felicitaciones" y "cursos" aparecen ambas en 12
 * comentarios, pero la primera ocupa más del doble de ancho y se lee como más
 * importante. Lo que el ojo compara es el ÁREA (≈ tamaño × cantidad de letras),
 * no la altura de la fuente.
 *
 * La corrección divide por el largo elevado a 0.35: un exponente suave, elegido
 * para descontar buena parte del sesgo sin invertirlo (con 1.0 las palabras
 * largas quedarían ridículamente chicas y el error sería el contrario).
 * Se normaliza contra un largo de referencia de 7 letras para que la escala
 * general no se desplace.
 */
const LARGO_REFERENCIA = 7;
const EXP_CORRECCION = 0.35;

function tamanoDe(n: number, min: number, max: number, largo?: number): number {
  if (max <= min) return (TAM_MIN + TAM_MAX) / 2;
  const t = Math.sqrt((n - min) / (max - min));
  const base = TAM_MIN + (TAM_MAX - TAM_MIN) * t;
  if (!largo) return base;
  const factor = (LARGO_REFERENCIA / Math.max(largo, 3)) ** EXP_CORRECCION;
  // Piso de legibilidad: corregir nunca debe dejar una palabra por debajo del
  // tamaño mínimo con el que se puede leer.
  return Math.max(TAM_MIN, base * factor);
}

/**
 * Ordena las palabras para que las MÁS FRECUENTES queden al CENTRO del bloque y
 * las menos frecuentes se vayan hacia los bordes, como en una nube clásica.
 *
 * Cómo: se toma la lista por frecuencia descendente y se reparte alternando a
 * izquierda y derecha desde el medio → [… 5º 3º 1º 2º 4º …]. Al fluir con
 * flex-wrap eso deja las grandes en el corazón del bloque.
 *
 * Es determinista (depende solo del orden de frecuencia, nunca de Math.random):
 * una nube que se reordena sola en cada refresco es imposible de leer.
 */
function ordenDesdeElCentro(palabras: PalabraNube[]): PalabraNube[] {
  const porFrecuencia = [...palabras].sort((a, b) =>
    b.n - a.n || a.texto.localeCompare(b.texto),
  );
  const izquierda: PalabraNube[] = [];
  const derecha: PalabraNube[] = [];
  porFrecuencia.forEach((p, i) => {
    if (i % 2 === 0) derecha.push(p);
    else izquierda.unshift(p);
  });
  return [...izquierda, ...derecha];
}

/**
 * Agrupa las palabras por TEMA en bloques contiguos. La guía de visualización de
 * datos de la UE lo recomienda explícitamente:
 *   "group semantically related words together rather than dispersing them
 *    randomly throughout the visualization."
 * Dispersas al azar, las palabras de un mismo asunto no se leen como conjunto y
 * la nube queda como una lista bonita sin estructura. Agrupadas, se ve de un
 * golpe qué bloque de conversación pesa más.
 *
 * Los bloques van ordenados por volumen total, y DENTRO de cada bloque se aplica
 * el mismo criterio centro-hacia-afuera.
 */
function agrupadoPorTema(palabras: PalabraNube[]): Array<{
  tema: string;
  etiqueta: string;
  total: number;
  palabras: PalabraNube[];
}> {
  const grupos = new Map<string, PalabraNube[]>();
  palabras.forEach((p) => {
    const clave = p.tema_dominante ?? "otros";
    const lista = grupos.get(clave);
    if (lista) lista.push(p);
    else grupos.set(clave, [p]);
  });
  return [...grupos.entries()]
    .map(([tema, lista]) => ({
      tema,
      etiqueta: lista.find((p) => p.tema_etiqueta)?.tema_etiqueta ?? tema,
      total: lista.reduce((s, p) => s + p.n, 0),
      palabras: ordenDesdeElCentro(lista),
    }))
    .sort((a, b) => b.total - a.total);
}

/** Una palabra de la nube. Extraída porque la usan los dos layouts. */
function Palabra({
  p, minN, maxN, criterio, verConteo, corregirLargo, barraProporcion, onExcluir,
}: {
  p: PalabraNube;
  minN: number;
  maxN: number;
  criterio: CriterioColor;
  verConteo: boolean;
  corregirLargo: boolean;
  barraProporcion: boolean;
  onExcluir: () => void;
}) {
  const tam = tamanoDe(p.n, minN, maxN, corregirLargo ? p.texto.length : undefined);
  return (
    <button
      type="button"
      onClick={onExcluir}
      title={
        `“${p.texto}” · ${p.n} comentarios\n` +
        `${p.pos} positivos · ${p.neu} neutrales · ${p.neg} negativos\n` +
        `Tema: ${p.tema_etiqueta ?? "—"} · Emoción: ${p.emocion_etiqueta ?? "—"}\n` +
        // La agrupación tiene que ser auditable: si el número incluye otras
        // formas, hay que poder ver cuáles sin salir de la vista.
        (p.variantes.length > 0 ? `Incluye: ${p.variantes.join(", ")}\n` : "") +
        "Clic para quitarla de la nube"
      }
      className="group cursor-pointer rounded px-1 font-semibold leading-tight transition hover:bg-white/[0.08]"
      style={{ opacity: opacidadDe(p, criterio) }}
    >
      <span
        className="block"
        style={{ fontSize: `${tam}px`, color: colorDe(p, criterio) }}
      >
        {p.texto}
        {verConteo ? (
          <sub
            className="ml-0.5 align-super font-normal tabular-nums opacity-70"
            /* Ligado al tamaño de la palabra pero con piso legible: si escalara
               libre, en las palabras chicas sería ilegible. */
            style={{ fontSize: `${Math.max(9, tam * 0.34)}px` }}
          >
            {p.n}
          </sub>
        ) : null}
      </span>
      {barraProporcion ? <BarraPalabra p={p} /> : null}
    </button>
  );
}

/**
 * Franja de proporción bajo la palabra: verde / gris / rojo según cuántos
 * comentarios de cada signo la contienen.
 *
 * Se evaluó pintar la PALABRA con un degradado (`background-clip: text`,
 * mitad verde y mitad roja). Es viable, pero no se puede leer: en una palabra
 * de 6 letras a 14 px, un 60/40 y un 50/50 son indistinguibles, y en los
 * tamaños chicos el texto deja de leerse. La barra separa las dos funciones —
 * la palabra queda de UN color legible (el dominante) y la proporción exacta
 * vive en la franja, que se lee de lejos como forma y de cerca como dato.
 */
function BarraPalabra({ p }: { p: PalabraNube }) {
  const total = p.pos + p.neu + p.neg || 1;
  const seg = (n: number, color: string, etiqueta: string) => (
    <span
      key={etiqueta}
      style={{ width: `${(100 * n) / total}%`, background: color }}
      className="block h-full"
    />
  );
  return (
    <span
      /* Media caña y centrada: a ancho completo competía con la palabra por la
         atención. A la mitad sigue leyéndose la proporción y la barra queda como
         lo que es, una nota al pie del dato. */
      className="mx-auto mt-0.5 flex h-[3px] w-1/2 overflow-hidden rounded-full bg-white/[0.06]"
      title={`${p.pos} positivos · ${p.neu} neutrales · ${p.neg} negativos`}
    >
      {seg(p.pos, COLOR_POS, "pos")}
      {seg(p.neu, COLOR_NEU, "neu")}
      {seg(p.neg, COLOR_NEG, "neg")}
    </span>
  );
}

/** Una fila del ranking. Compartida por la vista global y la agrupada por tema. */
function FilaRanking({
  p, puesto, tope, criterio,
}: {
  p: PalabraNube;
  puesto: number;
  tope: number;
  criterio: CriterioColor;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-4 shrink-0 text-right text-xs tabular-nums text-slate-500">
        {puesto}
      </span>
      <span
        className="w-28 shrink-0 truncate text-sm font-semibold"
        style={{ color: colorDe(p, criterio) }}
        title={p.texto}
      >
        {p.texto}
      </span>
      {/* Barra LINEAL contra el máximo, a propósito: la nube usa raíz cuadrada y
          comprime justo la diferencia que acá hay que poder distinguir. */}
      <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
        <span
          className="block h-full rounded-full"
          style={{ width: `${(100 * p.n) / tope}%`, background: colorDe(p, criterio) }}
        />
      </span>
      <span className="w-20 shrink-0 text-right text-xs tabular-nums text-slate-400">
        {p.n} coment.
      </span>
      <span className="hidden w-24 shrink-0 text-right text-xs tabular-nums text-slate-500 sm:block">
        {p.pos}/{p.neu}/{p.neg}
      </span>
    </div>
  );
}

export function PercepcionNube({ filtro }: { filtro: Filtro }) {
  const [criterio, setCriterio] = useState<CriterioColor>("sentimiento");
  const [minFrecuencia, setMinFrecuencia] = useState(2);
  const [limite, setLimite] = useState(120);
  // Conteo visible pegado a cada palabra. Por defecto ENCENDIDO: sin el número,
  // dos palabras de tamaño casi igual son indistinguibles y el lector no sabe si
  // una gana por 1 o por 10.
  const [verConteo, setVerConteo] = useState(true);
  // Corrección del sesgo por longitud (guía de visualización de la UE). Por
  // defecto ENCENDIDA: sin ella el tamaño compara mal palabras de igual frecuencia.
  const [corregirLargo, setCorregirLargo] = useState(true);
  // Franja de proporción pos/neu/neg bajo cada palabra. Resuelve "esta palabra
  // se dice tanto en positivo como en negativo" sin romper la legibilidad.
  const [barraProporcion, setBarraProporcion] = useState(true);
  // "libre" = una sola nube; "tema" = bloques semánticos, también recomendado
  // por la guía de la UE (agrupar lo relacionado en vez de dispersarlo).
  const [layout, setLayout] = useState<"libre" | "tema">("libre");
  // Funde singular/plural en una sola entrada ("curso" → "cursos"). Por defecto
  // ENCENDIDO: separadas, las variantes reparten el peso de un mismo concepto y
  // lo hunden en el ranking (en datos reales, cursos 12 + curso 3 = 15).
  const [agruparVariantes, setAgruparVariantes] = useState(true);
  // Exclusiones en vivo: un clic saca la palabra de la nube. Es la vía práctica
  // para limpiar nombres de usuario que el scraper dejó pegados al texto (PII) y
  // muletillas sin señal, sin tener que tocar el código.
  const [excluidas, setExcluidas] = useState<string[]>([]);
  const [data, setData] = useState<NubeResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.nube(filtro, limite, minFrecuencia, excluidas, agruparVariantes, opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar la nube de palabras.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [filtro, limite, minFrecuencia, excluidas, agruparVariantes, nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const nube = useMemo(() => {
    if (!data?.palabras.length) return [];
    return ordenDesdeElCentro(data.palabras);
  }, [data]);

  const bloques = useMemo(() => {
    if (!data?.palabras.length) return [];
    return agrupadoPorTema(data.palabras);
  }, [data]);

  // Los mismos bloques sirven de leyenda cuando se colorea por tema: ya vienen
  // ordenados por volumen y solo contienen temas realmente presentes.
  const temasPresentes = bloques;

  // Top del ranking: el indicador PRECISO. La nube comunica la forma general,
  // pero con escala raíz cuadrada la diferencia entre n=23 y n=20 es invisible —
  // "no se sabe si gana por 1 o por 10". Esta tabla responde eso exacto.
  const ranking = useMemo(() => {
    if (!data?.palabras.length) return [];
    return [...data.palabras].sort((a, b) => b.n - a.n).slice(0, 10);
  }, [data]);

  // Mismo ranking pero POR TEMA, para acompañar la disposición agrupada. No son
  // "las 10 globales repartidas": son las más dichas DE CADA tema — si no, un
  // tema dominante se llevaría todas las filas y los demás no aparecerían nunca.
  const rankingPorTema = useMemo(() => {
    if (!bloques.length) return [];
    return bloques.map((b) => ({
      ...b,
      top: [...b.palabras].sort((a, c) => c.n - a.n).slice(0, 5),
    }));
  }, [bloques]);

  // Máximo GLOBAL como referencia de las barras, también en el modo agrupado: si
  // cada bloque se escalara a su propio máximo, un tema de 5 menciones dibujaría
  // barras tan largas como uno de 23 y los bloques dejarían de ser comparables.
  const topeBarra = ranking[0]?.n || 1;

  const [minN, maxN] = useMemo(() => {
    if (!data?.palabras.length) return [0, 0];
    const ns = data.palabras.map((p) => p.n);
    return [Math.min(...ns), Math.max(...ns)];
  }, [data]);

  if (!data && cargando) {
    return (
      <Esqueleto etiqueta="Cargando nube de palabras…" bloques={[320]} />
    );
  }
  if (error && !data) {
    return (
      <div className={CARD}>
        <p className="text-sm text-ucn-tierra-clara">{error}</p>
      </div>
    );
  }

  return (
    <div
      className="space-y-4 transition-opacity duration-200"
      style={{ opacity: cargando ? 0.55 : 1 }}
      aria-busy={cargando}
    >
      {error ? (
        <div className="rounded-md border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-4 py-2 text-sm text-ucn-tierra-clara">
          {error}
          {cargando ? " · reintentando…" : ""}
        </div>
      ) : null}

      <div className={CARD}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            {/* El título dice "nube de palabras" explícitamente porque el
                componente dejó de ser una pestaña con nombre propio y ahora vive
                embebido en Conversación: sin esto, el bloque aparecía sin
                anunciarse y no se entendía qué se estaba mirando. */}
            <div className="text-sm font-medium text-slate-100">Nube de palabras</div>
            <p className="mt-1 text-sm leading-5 text-slate-500">
              El vocabulario <strong className="text-slate-400">crudo</strong> de los comentarios,
              sin pasar por las 8 categorías del clasificador: sirve para ver de qué se habla
              antes de que exista un tema para eso. El tamaño es en cuántos{" "}
              <strong className="text-slate-400">comentarios</strong> aparece la palabra (no
              cuántas veces se repite): quien la escribe cinco veces cuenta una sola.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {/* Disposición primero: decide la ESTRUCTURA de la vista, y el resto
                de los controles se leen dentro de esa decisión. */}
            <label className="flex items-center gap-2 text-sm text-slate-400">
              Disposición
              <select
                className={SELECT}
                value={layout}
                onChange={(e) => setLayout(e.target.value as typeof layout)}
                title="Agrupar por tema junta las palabras del mismo asunto, en vez de dispersarlas."
              >
                <option value="libre">Nube única</option>
                <option value="tema">Agrupada por tema</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-400">
              Color por
              <select
                className={SELECT}
                value={criterio}
                onChange={(e) => setCriterio(e.target.value as CriterioColor)}
              >
                <option value="sentimiento">Sentimiento</option>
                <option value="tema">Tema</option>
                <option value="mono">Sin color</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-400">
              Mínimo
              <select
                className={SELECT}
                value={minFrecuencia}
                onChange={(e) => setMinFrecuencia(Number(e.target.value))}
                title="Cuántos comentarios distintos deben contener la palabra."
              >
                <option value={2}>2 comentarios</option>
                <option value={3}>3 comentarios</option>
                <option value={5}>5 comentarios</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-400">
              Mostrar
              <select
                className={SELECT}
                value={limite}
                onChange={(e) => setLimite(Number(e.target.value))}
              >
                <option value={60}>60 palabras</option>
                <option value={120}>120 palabras</option>
                <option value={250}>250 palabras</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
          {/* Leyenda del criterio de color activo. Un color sin leyenda es
              decoración: el lector ve tonos distintos y no sabe qué codifican. */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-400">
            {criterio === "sentimiento" ? (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: COLOR_POS }} /> Positivo
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: COLOR_NEG }} /> Negativo
                </span>
                <span className="flex items-center gap-1.5 opacity-60">
                  <span className="h-2 w-2 rounded-full" style={{ background: COLOR_NEU }} /> Neutral
                  (atenuado)
                </span>
              </>
            ) : null}
            {/* Solo los temas PRESENTES en el resultado: listar los 8 fijos
                mostraría colores que no aparecen en pantalla. */}
            {criterio === "tema"
              ? temasPresentes.map((t) => (
                  <span key={t.tema} className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: COLOR_TEMA[t.tema] ?? COLOR_NEU }}
                    />
                    {t.etiqueta}
                    <span className="tabular-nums text-slate-500">({t.total})</span>
                  </span>
                ))
              : null}
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-400">
              <input
                type="checkbox"
                checked={verConteo}
                onChange={(e) => setVerConteo(e.target.checked)}
                className="accent-[var(--portal-cyan)]"
              />
              Mostrar el número
            </label>
            <label
              className="flex cursor-pointer items-center gap-2 text-sm text-slate-400"
              title={
                "Las palabras largas llaman más la atención aunque tengan la misma frecuencia: " +
                "“felicitaciones” y “cursos” aparecen en 12 comentarios cada una, pero la primera " +
                "ocupa el doble de ancho. Esto descuenta ese sesgo."
              }
            >
              <input
                type="checkbox"
                checked={corregirLargo}
                onChange={(e) => setCorregirLargo(e.target.checked)}
                className="accent-[var(--portal-cyan)]"
              />
              Corregir sesgo por largo de palabra
            </label>
            <label
              className="flex cursor-pointer items-center gap-2 text-sm text-slate-400"
              title={
                "Junta singular y plural en una sola palabra (curso → cursos). " +
                "Separadas, las variantes reparten el peso de un mismo concepto."
              }
            >
              <input
                type="checkbox"
                checked={agruparVariantes}
                onChange={(e) => setAgruparVariantes(e.target.checked)}
                className="accent-[var(--portal-cyan)]"
              />
              Agrupar singular y plural
              {data && data.n_variantes_agrupadas > 0 ? (
                <span className="text-slate-500">({data.n_variantes_agrupadas} fundidas)</span>
              ) : null}
            </label>
            <label
              className="flex cursor-pointer items-center gap-2 text-sm text-slate-400"
              title={
                "Franja bajo cada palabra con la proporción positivo/neutral/negativo. " +
                "Muestra las palabras que se dicen en los dos sentidos, que el color " +
                "dominante por sí solo esconde."
              }
            >
              <input
                type="checkbox"
                checked={barraProporcion}
                onChange={(e) => setBarraProporcion(e.target.checked)}
                className="accent-[var(--portal-cyan)]"
              />
              Barra de proporción
            </label>
          </div>
        </div>

        {/* Acá vivía una ESCALA de referencia ("Aa = 23 comentarios"). Se quitó al
            entrar la corrección por longitud: como ahora cada palabra ajusta su
            tamaño según cuántas letras tiene, un "Aa" de 2 letras ya no equivale
            al tamaño real de ninguna palabra del corpus — la referencia mentía.
            La lectura exacta la dan el número pegado a cada palabra y el ranking. */}
      </div>

      {/* La nube. */}
      <div className={CARD}>
        {nube.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">
            No hay palabras que aparezcan en al menos {minFrecuencia} comentarios con este filtro.
          </p>
        ) : layout === "libre" ? (
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 px-2 py-6">
            {nube.map((p) => (
              <Palabra
                key={p.texto}
                p={p}
                minN={minN}
                maxN={maxN}
                criterio={criterio}
                verConteo={verConteo}
                corregirLargo={corregirLargo}
                barraProporcion={barraProporcion}
                onExcluir={() => setExcluidas((prev) => [...prev, p.texto])}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-4 py-2">
            {bloques.map((b) => (
              <div key={b.tema} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                <div className="mb-2 flex items-baseline gap-2">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: COLOR_TEMA[b.tema] ?? COLOR_NEU }}
                  />
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {b.etiqueta}
                  </span>
                  <span className="text-xs tabular-nums text-slate-500">
                    {b.palabras.length} palabras · {b.total} menciones
                  </span>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
                  {b.palabras.map((p) => (
                    <Palabra
                      key={p.texto}
                      p={p}
                      minN={minN}
                      maxN={maxN}
                      criterio={criterio}
                      verConteo={verConteo}
                      corregirLargo={corregirLargo}
                      barraProporcion={barraProporcion}
                      onExcluir={() => setExcluidas((prev) => [...prev, p.texto])}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-2 border-t border-white/5 pt-2 text-sm text-slate-500">
          {data
            ? `${data.n_palabras_unicas.toLocaleString("es-CL")} palabras distintas sobre ` +
              `${data.n_comentarios.toLocaleString("es-CL")} comentarios · se muestran las ${nube.length} más frecuentes`
            : null}
          {data?.truncado ? " · corpus recortado por tamaño" : ""}
        </div>
      </div>

      {/* Ranking: la lectura EXACTA que la nube no puede dar. Sigue la misma
          disposición que la nube — si arriba se agrupó por tema, acá también. */}
      {ranking.length > 0 ? (
        <div className={CARD}>
          <div className="mb-1 text-sm font-medium text-slate-100">
            {layout === "tema" ? "Las más dichas de cada tema" : "Las 10 más dichas"}
          </div>
          <p className="mb-3 text-sm text-slate-500">
            La nube muestra la forma general; acá está la diferencia exacta entre una
            palabra y la siguiente.
            {layout === "tema"
              ? " Las barras se comparan contra el máximo global, así los temas se miden entre sí."
              : ""}
          </p>

          {layout === "tema" ? (
            <div className="space-y-4">
              {rankingPorTema.map((b) => (
                <div key={b.tema}>
                  <div className="mb-1.5 flex items-baseline gap-2">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ background: COLOR_TEMA[b.tema] ?? COLOR_NEU }}
                    />
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {b.etiqueta}
                    </span>
                    <span className="text-xs tabular-nums text-slate-500">
                      {b.total} menciones
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {b.top.map((p, i) => (
                      <FilaRanking
                        key={p.texto}
                        p={p}
                        puesto={i + 1}
                        tope={topeBarra}
                        criterio={criterio}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              {ranking.map((p, i) => (
                <FilaRanking
                  key={p.texto}
                  p={p}
                  puesto={i + 1}
                  tope={topeBarra}
                  criterio={criterio}
                />
              ))}
            </div>
          )}

          <p className="mt-2 text-sm text-slate-500">
            Última columna: positivos / neutrales / negativos.
          </p>
        </div>
      ) : null}

      {/* Exclusiones: visibles y reversibles — un filtro que no se ve es un filtro
          que miente sobre lo que la nube está mostrando. */}
      {excluidas.length > 0 ? (
        <div className={CARD}>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium text-slate-100">
              Palabras excluidas ({excluidas.length})
            </span>
            <button
              type="button"
              className="rounded border border-white/10 bg-white/[0.04] px-3 py-1 text-sm text-slate-400 transition hover:bg-white/[0.09]"
              onClick={() => setExcluidas([])}
            >
              Restaurar todas
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {excluidas.map((w) => (
              <button
                key={w}
                type="button"
                title="Clic para devolverla a la nube"
                className="rounded border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-xs text-slate-400 transition hover:bg-white/[0.09]"
                onClick={() => setExcluidas((prev) => prev.filter((x) => x !== w))}
              >
                {w} ✕
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <p className="px-1 text-sm text-slate-500">
        La nube muestra texto público tal cual se escribió. Puede contener nombres de usuario
        que el scraper dejó pegados al comentario o lenguaje ofensivo: usa el clic sobre una
        palabra para sacarla antes de mostrar el tablero.
      </p>
    </div>
  );
}

export default PercepcionNube;
