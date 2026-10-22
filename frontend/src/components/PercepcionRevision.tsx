"use client";

// COLA DE REVISIÓN (F′) — anotar comentarios para medir qué tan bien lee el modelo.
//
// POR QUÉ EXISTE ESTE ARCHIVO: el endpoint `/percepcion/curacion/scoring` existía
// desde siempre y **el frontend nunca lo llamaba**. Las correcciones se hacían inline
// en la lista de Conversación, que va por fecha. Consecuencias:
//
//   1. No había forma de pedir una muestra ALEATORIA, que es la única con la que se
//      puede estimar la calidad real del modelo (la cola por duda apunta a donde el
//      modelo es peor, así que mide un piso pesimista).
//   2. Peor: la edición inline **rechazaba** guardar si no cambiabas nada
//      ("No cambiaste nada"), o sea que era IMPOSIBLE registrar "el modelo acertó".
//      Por eso las 376 revisiones de la base real son 376 desacuerdos y el acuerdo
//      quedaba sin denominador.
//
// La confirmación es la función más importante de esta pantalla, aunque parezca la
// más aburrida: sin aciertos anotados no hay accuracy, solo un log de defectos.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import {
  esCancelacion,
  percepcionApi,
  type ComentarioScoring,
  type OpcionesScoring,
  type OrdenScoring,
  type TemaAsignable,
} from "../lib/percepcion";
import { CARD, SELECT, TituloBloque, labelEmocion, nro } from "./PercepcionUI";

// Espejo de `calidad.MIN_ANCLA`. Es el piso para que una muestra CUENTE como ancla;
// el objetivo práctico de una tanda de anotación es ~150.
const MIN_ANCLA = 30;
const OBJETIVO = 150;

// Espejo de `curacion.POSTURA_DESDE_SENTIMIENTO`: la suposición de que el tono ya
// dice la postura. Es la hipótesis nula que esta dimensión pone a prueba.
const POSTURA_DESDE_TONO: Record<string, string> = {
  POS: "favorable", NEU: "neutral", NEG: "adverso",
};

const ORDENES: { id: OrdenScoring; label: string; hint: string; sirve: string }[] = [
  {
    // LA COLA RECOMENDADA para destrabar la postura, y la única dirigida que
    // igual sirve para medir. Va primera porque hoy es donde está el cuello.
    //
    // El dilema que resuelve: `aleatorio` estima bien pero es caro (227
    // anotaciones para llegar a 50 adversos) y `adversos` es barato (83) pero no
    // sirve para estimar nada. Esta parte el corpus en dos estratos por el
    // puntaje de candidato adverso —rico: 711 comentarios con 35 % de adversos;
    // pobre: 7.463 con 10 %—, sobremuestrea el rico 70/30 y RE-PESA cada estrato
    // por su tamaño real. Insesgada, y bastan ~105 anotaciones.
    //
    // Validado: re-pesando por estrato los 164 casos aleatorios ya anotados da
    // 12,4 % de adversos contra 12,8 % observado directamente.
    id: "estratificado",
    label: "Estratificado (recomendado)",
    hint: "70 % de donde el adverso es probable, 30 % del resto — y se re-pesa",
    sirve:
      "La única cola dirigida que IGUAL sirve para medir: al re-pesar cada estrato " +
      "por su tamaño real, la estimación vuelve a ser insesgada. Llegar a 50 " +
      "adversos cuesta ~105 anotaciones acá contra 227 al azar. Es la que destraba " +
      "el lado adverso de la postura, que hoy frena todo el módulo.",
  },
  {
    id: "aleatorio",
    label: "Aleatorio",
    hint: "Muestra sin sesgo de todo el corpus, con semilla fija",
    sirve: "Sirve para MEDIR la calidad del modelo sin ninguna corrección. Reproducible: dos revisores ven lo mismo. Es el más caro para encontrar adversos.",
  },
  {
    id: "duda",
    label: "Donde el modelo dudó",
    hint: "Menor margen entre la clase ganadora y la segunda",
    sirve: "Es donde el trabajo RINDE más para corregir, pero NO sirve para medir: la muestra está dirigida a donde el modelo es peor.",
  },
  {
    id: "reciente",
    label: "Más recientes",
    hint: "Por fecha de comentario",
    sirve: "Útil para revisar lo que acaba de entrar. Tampoco sirve para medir.",
  },
  {
    // Existe por un cuello de botella medido: de las 150 anotaciones humanas de
    // postura, solo 21 son ADVERSOS, y con 21 casos no se puede calibrar ese lado
    // de la regla. Anotar al azar no lo arregla —el adverso es el 8,5 % del corpus,
    // así que 100 comentarios aleatorios dan ~8—. Esta cola concentra el trabajo:
    // medido, entrega 47 de cada 100 con léxico de conflicto contra 0 al azar.
    id: "adversos",
    label: "Candidatos a adversos",
    hint: "Comentarios que nombran conflicto, o que están en publicaciones de conflicto",
    sirve:
      "Para calibrar la POSTURA adversa, que hoy tiene solo 21 ejemplos anotados. " +
      "Prioriza los positivos y neutrales —«¿Paro? 😍» es tono positivo y postura " +
      "adversa— porque los negativos ya son adversos por regla. Dirigida: NO sirve " +
      "para medir la calidad global.",
  },
];

function Barra({ hecho, meta }: { hecho: number; meta: number }) {
  const pct = Math.min(100, (hecho / meta) * 100);
  return (
    <span className="h-1.5 w-24 overflow-hidden rounded-full bg-white/[0.08]">
      <span
        className={`block h-full rounded-full ${
          hecho >= meta ? "bg-[var(--dato-favorable)]" : "bg-[color-mix(in_srgb,var(--portal-cyan)_70%,transparent)]"
        }`}
        style={{ width: `${pct}%` }}
      />
    </span>
  );
}

function Ficha({
  c, opciones, temas, orden, onListo, onError,
}: {
  c: ComentarioScoring;
  opciones: OpcionesScoring;
  temas: TemaAsignable[];
  orden: OrdenScoring;
  onListo: (id: number, confirmado: boolean) => void;
  onError: (m: string) => void;
}) {
  const emocionActual = c.emocion ?? "sin_emocion";
  const temaActual = c.tema ?? "";
  // Suposición INGENUA: que el tono ya dice la postura. Es la hipótesis que esta
  // dimensión existe para poner a prueba — «Paro?😍» es POS y adverso a la UCN.
  const posturaIngenua = POSTURA_DESDE_TONO[c.sentimiento] ?? "neutral";
  const [sent, setSent] = useState(c.sentimiento);
  const [emo, setEmo] = useState(emocionActual);
  const [tema, setTema] = useState(temaActual);
  const [postura, setPostura] = useState(posturaIngenua);
  const [just, setJust] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cambioSent = sent !== c.sentimiento;
  const cambioEmo = emo !== emocionActual;
  const cambioTema = tema !== temaActual;
  const cambioPostura = postura !== posturaIngenua;
  const hayCambio = cambioSent || cambioEmo || cambioTema || cambioPostura;

  const enviar = async (confirmar: boolean) => {
    // Corregir exige el porqué; confirmar no: no hay nada que explicar cuando el
    // modelo acertó, y pedirlo solo lograría que nadie confirme.
    if (!confirmar && !just.trim()) {
      onError("Escribe el por qué antes de guardar la corrección.");
      return;
    }
    setGuardando(true);
    try {
      if (confirmar) {
        // Se manda el valor ACTUAL a propósito: el backend detecta que no cambió,
        // registra `confirmado=True`, NO toca el score y NO reagrega.
        // Se confirman los TRES campos: cada uno tiene su propio denominador y el
        // tema es justamente el que nunca se midió.
        await percepcionApi.corregirSentimiento(c.id, c.sentimiento, just.trim(), orden);
        await percepcionApi.corregirEmocion(c.id, emocionActual, just.trim(), orden);
        if (temaActual) await percepcionApi.corregirTema(c.id, temaActual, just.trim(), orden);
        await percepcionApi.corregirPostura(c.id, posturaIngenua, just.trim(), orden);
      } else {
        // SE MANDAN LOS CUATRO, cambien o no.
        //
        // ⚠️ BUCLE INFINITO DE LA COLA — no volver a mandar sólo los que cambiaron.
        // Antes esto era `if (cambioTema && tema) ...`, y un comentario cuyo tema
        // retirado (`eventos`) la reclasificación ya había renombrado mostraba el
        // tema nuevo: el revisor estaba de acuerdo, no cambiaba nada, no se
        // escribía corrección de tema, la última anotación humana seguía siendo la
        // del criterio anterior y el comentario VOLVÍA A LA COLA PARA SIEMPRE. No
        // había forma de sacarlo salvo con «Está bien ✓».
        //
        // Mandar un valor que no cambió no ensucia nada: el backend lo detecta y lo
        // registra como `confirmado=True`, que es justamente el dato que hace falta
        // para medir acuerdo. Es además la lectura honesta de lo que pasó: la
        // persona miró el comentario y afirmó estos cuatro valores.
        await percepcionApi.corregirSentimiento(c.id, sent, just.trim(), orden);
        await percepcionApi.corregirEmocion(c.id, emo, just.trim(), orden);
        if (tema) await percepcionApi.corregirTema(c.id, tema, just.trim(), orden);
        await percepcionApi.corregirPostura(c.id, postura, just.trim(), orden);
      }
      onListo(c.id, confirmar);
    } catch (e) {
      onError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <li className="rounded-md border border-white/5 bg-white/[0.02] p-3">
      {/* EL CAPTION VA PRIMERO, y no es decoración: la mediana del corpus es de 3
          palabras. "Q paso con los de geología" no se puede clasificar sin saber que
          responde a una convocatoria a pleno extraordinario. */}
      {c.caption ? (
        <p className="mb-1.5 border-l-2 border-white/10 pl-2 text-sm leading-4 text-slate-500">
          <span className="font-semibold text-slate-500">responde a: </span>
          {c.caption}
        </p>
      ) : null}

      <p className="text-sm text-slate-100">{c.texto}</p>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
        <span>{c.fecha}</span>
        {c.cuenta ? <span>· @{c.cuenta}</span> : null}
        <span className="rounded bg-white/[0.04] px-2 py-0.5 text-slate-400">
          {c.sentimiento_label}
        </span>
        {c.emocion_label ? (
          <span className="rounded bg-white/[0.04] px-2 py-0.5 text-slate-400">
            {labelEmocion(c.emocion, c.emocion_label)}
          </span>
        ) : null}
        <span
          className="ml-auto"
          title="Ventaja de la clase ganadora sobre la segunda. Chico = el modelo dudaba."
        >
          margen {c.margen.toFixed(3)}
        </span>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2 text-sm text-slate-400">
        <label className="flex items-center gap-1">
          Sentimiento:
          <select className={SELECT} value={sent} onChange={(e) => setSent(e.target.value)}>
            {opciones.sentimientos.map((o) => (
              <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1">
          Emoción:
          <select className={SELECT} value={emo} onChange={(e) => setEmo(e.target.value)}>
            {opciones.emociones.map((o) => (
              <option key={o.valor} value={o.valor}>{labelEmocion(o.valor, o.etiqueta)}</option>
            ))}
          </select>
        </label>
        {c.motivo_pendiente && (
          <span
            className="rounded bg-[color-mix(in_srgb,var(--portal-copper)_15%,transparent)] px-2 py-0.5 text-xs text-ucn-tierra-clara"
            title="Ya lo revisaste antes, pero esa revisión dejó de ser válida. Volver a guardarlo lo saca de la cola."
          >
            a rehacer · {c.motivo_pendiente}
          </span>
        )}

        {/* TEMA. Es la dimensión que NUNCA se midió: el clasificador es un matcher de
            palabras clave corriendo sobre comentarios de mediana 3 palabras, con
            confianza mediana 0,45 y el 89,5% por debajo de 0,7. La confianza va al
            lado para que se pueda juzgar si significa algo. */}
        <label className="flex items-center gap-1">
          Tema:
          <select className={SELECT} value={tema} onChange={(e) => setTema(e.target.value)}>
            <option value="">(sin tema)</option>
            {temas.map((t) => <option key={t.tema} value={t.tema}>{t.etiqueta}</option>)}
          </select>
          <span
            className={c.tema_confianza < 0.5 ? "text-ucn-tierra-clara" : "text-slate-500"}
            title="Confianza del clasificador de temas. Mediana del corpus: 0,45."
          >
            {c.tema_confianza.toFixed(2)}
          </span>
        </label>
      </div>

      {/* POSTURA — la dimensión que el tono NO captura.
          «Paro?😍» es positivo en tono y adverso a la institución. Medido: de 141
          comentarios sobre publicaciones de conflicto, 33 (23%) están marcados POS.
          Arranca con la suposición ingenua (tono→postura) para que cambiarla sea
          justamente el dato: cuánto se equivoca esa suposición. */}
      <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-2.5 py-1.5 text-sm text-slate-400">
        <span className="font-semibold text-slate-400">¿Postura hacia la UCN?</span>
        {opciones.posturas.map((p) => (
          <button
            key={p.valor}
            type="button"
            onClick={() => setPostura(p.valor)}
            className={
              postura === p.valor
                ? "rounded border border-[color-mix(in_srgb,var(--portal-cyan)_40%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_15%,transparent)] px-2.5 py-0.5 font-semibold text-ucn-azul-claro"
                : "rounded border border-white/10 px-2.5 py-0.5 transition hover:bg-white/[0.06]"
            }
          >
            {p.etiqueta}
          </button>
        ))}
        {cambioPostura ? (
          <span className="text-sm text-ucn-tierra-clara">
            ≠ tono ({c.sentimiento_label})
          </span>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input
          value={just}
          onChange={(e) => setJust(e.target.value)}
          placeholder={hayCambio ? "¿Por qué? (ej: sarcasmo, el modelo lo leyó literal)" : "Nota opcional"}
          className={`${SELECT} min-w-[220px] flex-1`}
        />
        {hayCambio ? (
          <button
            onClick={() => void enviar(false)}
            disabled={guardando}
            className="rounded-xl border border-[color-mix(in_srgb,var(--portal-copper)_40%,transparent)] bg-[color-mix(in_srgb,var(--portal-copper)_15%,transparent)] px-3 py-1.5 text-sm font-semibold text-slate-100 transition hover:bg-[color-mix(in_srgb,var(--portal-copper)_25%,transparent)] disabled:opacity-40"
          >
            Guardar corrección
          </button>
        ) : (
          <button
            onClick={() => void enviar(true)}
            disabled={guardando}
            className="rounded-xl border border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)] px-3 py-1.5 text-sm font-semibold text-ucn-azul-claro transition hover:bg-[var(--ucn-azul-suave)] disabled:opacity-40"
            title="Registra que el modelo acertó. Sin estos aciertos no hay denominador y el accuracy no se puede calcular."
          >
            Está bien ✓
          </button>
        )}
      </div>
    </li>
  );
}

/** Criterio de TEMA, a la vista mientras se anota.
 *
 * ⚠️ No es decoración. El criterio cambió a mitad de la anotación sin quedar
 * escrito en ningún lado y el resultado fue medible: de 135 comentarios anotados
 * más de una vez, 42 cambiaron de etiqueta y 31 de esos migraron a
 * `logros_reconocimientos`. Con dos criterios mezclados la métrica de tema no
 * significa nada — afinar el clasificador hacia uno sube su acuerdo (+6,2) y baja
 * el del otro (−6,4) en la misma proporción.
 *
 * Los cinco casos de acá son los que EFECTIVAMENTE aparecieron en la revisión, no
 * una lista teórica. Si el criterio vuelve a cambiar, actualizar esto Y
 * `curacion.CRITERIO_TEMA_DESDE`, que es lo que devuelve a la cola lo anotado con
 * el criterio anterior.
 */
function GuiaTema() {
  const reglas: [string, string][] = [
    ["El post destaca a una persona", "Logros y reconocimientos — aunque sea académica"],
    ["El comentario es solo emojis", "Hereda el tema del post; no es «Otros»"],
    ["Carrete, fonda, bienvenida", "Vida estudiantil"],
    ["Charla, seminario, congreso", "Académico"],
    ["Sala, trámite, matrícula, admisión", "Servicios y trámites"],
  ];
  return (
    <details className="mt-2 rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
      <summary className="cursor-pointer text-sm font-medium text-slate-400">
        Criterio de tema (vigente desde 19-08-2026)
      </summary>
      <ul className="mt-2 space-y-1">
        {reglas.map(([caso, regla]) => (
          <li key={caso} className="flex flex-wrap gap-x-2 text-sm leading-5">
            <span className="text-slate-500">{caso}</span>
            <span className="text-slate-500">→</span>
            <span className="text-slate-400">{regla}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm leading-5 text-slate-500">
        «Otros» significa <em>no hay señal</em>, no «no encaja del todo».
      </p>
    </details>
  );
}

export function PercepcionRevision({ onCambio }: { onCambio?: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [orden, setOrden] = useState<OrdenScoring>("aleatorio");
  const [items, setItems] = useState<ComentarioScoring[]>([]);
  const [opciones, setOpciones] = useState<OpcionesScoring>(
    { sentimientos: [], emociones: [], posturas: [] });
  const [temas, setTemas] = useState<TemaAsignable[]>([]);
  const [hechos, setHechos] = useState<Set<number>>(new Set());
  const [yaAnotadas, setYaAnotadas] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [porRevisar, setPorRevisar] = useState(0);

  const nueva = useSolicitudVigente();
  const recargar = useCallback(async (o: OrdenScoring) => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      const [cola, opc, tem, cal] = await Promise.all([
        percepcionApi.comentariosScoring(OBJETIVO, {}, o, opts),
        percepcionApi.scoringOpciones(opts),
        percepcionApi.curacionTemas(opts),
        percepcionApi.calidad(opts),
      ]);
      setItems(cola.items);
      setOpciones(opc);
      setTemas(tem.items);
      setHechos(new Set());
      // Progreso = COMENTARIOS CUBIERTOS, que es lo que informa el servidor.
      //
      // ⚠️ Acá estaba contando correcciones guardadas (`calidad.por_muestra.n`) y
      // eso hizo invisible un bug de días: la cola devolvía siempre los mismos
      // comentarios, pero el contador subía igual con cada click. El 19-08-2026 se
      // anotaron 109 comentarios y NINGUNO era nuevo. Contar clicks no es contar
      // cobertura.
      setYaAnotadas(cola.revisados);
      setPorRevisar(cola.pendientes);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar la cola de revisión");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => { if (abierto) void recargar(orden); }, [abierto, orden, recargar]);

  const pendientes = useMemo(() => items.filter((i) => !hechos.has(i.id)), [items, hechos]);
  const progreso = yaAnotadas + hechos.size;
  const meta = ORDENES.find((o) => o.id === orden);

  const marcar = (id: number, confirmado: boolean) => {
    setHechos((s) => new Set(s).add(id));
    setMsg(confirmado ? "Acierto registrado." : "Corrección guardada.");
    setError(null);
    if (!confirmado) onCambio?.();
  };

  return (
    <div className={CARD}>
      <button onClick={() => setAbierto((a) => !a)} className="flex w-full items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-100">
          Cola de revisión · anotar para medir el modelo
        </div>
        <span className="text-sm text-slate-500">{abierto ? "▲ ocultar" : "▼ abrir"}</span>
      </button>

      {abierto ? (
        <div className="mt-3 space-y-3">
          <TituloBloque titulo="Revisar comentarios">
            Confirmar que el modelo acertó vale tanto como corregirlo: sin aciertos
            registrados no hay denominador y el acuerdo no se puede calcular.
          </TituloBloque>

          {/* SELECTOR DE MUESTRA. Cada orden sirve para algo distinto y eso se dice:
              elegir mal acá invalida la medición sin que se note. */}
          <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                De qué muestra
              </span>
              {ORDENES.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  onClick={() => setOrden(o.id)}
                  title={o.hint}
                  className={
                    orden === o.id
                      ? "rounded border border-[color-mix(in_srgb,var(--portal-cyan)_40%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_10%,transparent)] px-3 py-1 text-sm font-semibold text-ucn-azul-claro"
                      : "rounded border border-white/10 bg-white/[0.03] px-3 py-1 text-sm text-slate-400 transition hover:bg-white/[0.07]"
                  }
                >
                  {o.label}
                </button>
              ))}
              <span className="ml-auto flex items-center gap-2 text-sm text-slate-400">
                <Barra hecho={progreso} meta={OBJETIVO} />
                {nro(progreso)}/{OBJETIVO}
                {progreso >= MIN_ANCLA ? (
                  <span className="text-dato-favorable">· ancla ✓</span>
                ) : (
                  <span className="text-slate-500">· mínimo {MIN_ANCLA}</span>
                )}
                {porRevisar > 0 && (
                  <span className="text-slate-500">
                    · quedan {nro(porRevisar)} sin revisar
                  </span>
                )}
              </span>
            </div>
            <p className="text-sm leading-5 text-slate-500">{meta?.sirve}</p>
            <GuiaTema />
          </div>

          {msg ? <div className="rounded-lg bg-[var(--ucn-azul-suave)] px-3 py-1.5 text-sm text-ucn-azul-claro">{msg}</div> : null}
          {error ? <div className="rounded-lg bg-[var(--ucn-tierra-suave)] px-3 py-1.5 text-sm text-ucn-tierra-clara">{error}</div> : null}

          {cargando ? (
            <p className="py-6 text-center text-sm text-slate-500">Cargando…</p>
          ) : pendientes.length ? (
            <ul className="space-y-2">
              {pendientes.slice(0, 25).map((c) => (
                <Ficha
                  key={c.id}
                  c={c}
                  opciones={opciones}
                  temas={temas}
                  orden={orden}
                  onListo={marcar}
                  onError={setError}
                />
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">
              No quedan comentarios en esta muestra. 🎉
            </p>
          )}

          {pendientes.length > 25 ? (
            <p className="text-center text-sm text-slate-500">
              Se muestran 25 de {nro(pendientes.length)}; a medida que anotas aparecen los siguientes.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default PercepcionRevision;
