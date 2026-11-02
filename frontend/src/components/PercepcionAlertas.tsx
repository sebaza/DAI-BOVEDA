"use client";

// ALERTAS — "¿hay algo que mirar?".
//
// Junta las dos cosas que responden esa pregunta y que antes vivían separadas:
// los TÉRMINOS BAJO VIGILANCIA (estaban como sexto bloque de una Síntesis que ya
// tenía cinco) y las SEMANAS FUERA DE LO HABITUAL (estaban al fondo del Tablero,
// entre un gráfico de emociones y una cola de curación). Las dos nacen del mismo
// motor: el léxico crítico alimenta la severidad de la anomalía.
//
// Lectura: SIN ponderación por recencia. Una alerta es un hecho del período, no
// una temperatura — que un paro sea de hace tres semanas no lo hace menos cierto.
// Por eso el rótulo de método dice "promedio del período" y los sliders del
// tablero no viven acá.

import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";

import type {
  AnomaliaItem,
  AnomaliasConfig,
  Filtro,
  TerminoFamilia,
  TerminosResponse,
} from "../lib/percepcion";
import { esCancelacion, percepcionApi } from "../lib/percepcion";
import {
  BarraSentimiento,
  CARD,
  COLOR_COPPER,
  COLOR_NEG,
  COLOR_NEU,
  COLOR_POS,
  Delta,
  Indice,
  TituloBloque,
  SubPestanas,
  colorIndice,
  fechaCorta,
  fmt,
  nro,
} from "./PercepcionUI";

// Por qué se marcó una semana. Sin esto el directivo ve una alerta y no sabe qué
// mirar: "z = -2.7" no le dice nada a nadie que no viva en el tablero.
const MOTIVO_LABEL: Record<string, string> = {
  terminos: "menciones críticas",
  indice: "índice",
  negatividad: "negatividad",
};
const MOTIVO_AYUDA: Record<string, string> = {
  terminos:
    "Menciones de paro, toma, petitorio, asamblea o movilización, dichas en serio " +
    "(el humor no cuenta). Es la señal que mejor separa: mediana 0 en el histórico.",
  indice:
    "El índice cayó respecto de la mediana de su historia reciente. Suma severidad, " +
    "pero NO enciende un nivel: medido sobre los episodios del calendario, el índice " +
    "no anticipa ninguno. Durante un conflicto recibe apoyo y reclamo en la misma " +
    "publicación y el promedio los cancela.",
  negatividad:
    "El porcentaje de comentarios negativos subió sobre su historia reciente. Es la " +
    "señal que enciende el nivel ATENCIÓN: cubre más episodios que ninguna otra, a " +
    "cambio de alguna falsa alarma.",
};

/** Menciones por semana. Barras rojas = semanas con carga negativa. */
function Sparkline({ semanas }: { semanas: TerminoFamilia["serie_semanal"] }) {
  const ultimas = semanas.slice(-14);
  if (ultimas.length < 2) return null;
  const max = Math.max(...ultimas.map((s) => s.n), 1);
  return (
    <span className="flex h-6 items-end gap-[2px]" aria-hidden="true">
      {ultimas.map((s) => (
        <span
          key={s.semana}
          className="w-[3px] rounded-sm"
          style={{
            height: `${Math.max(10, (100 * s.n) / max)}%`,
            background: s.n_neg > 0 ? COLOR_NEG : COLOR_NEU,
            opacity: s.n_neg > 0 ? 1 : 0.5,
          }}
          title={`Semana del ${fechaCorta(s.semana)}: ${s.n} menciones (${s.n_neg} negativas)`}
        />
      ))}
    </span>
  );
}

/**
 * SEÑALES BAJO VIGILANCIA — el léxico de conflicto, contado aparte.
 *
 * Existe porque el clasificador reparte los comentarios en 8 temas y la
 * conversación de conflicto no tiene caja propia: se diluye entre "Académico",
 * "Organización estudiantil" y "Otros". Medido sobre el corpus real, el
 * 21/04/2026 —seis semanas ANTES del paro del 03/06— hubo en un solo día rumor
 * de paro, rechazo, petitorios pendientes y convocatoria a asamblea. El tablero
 * no mostraba nada de eso.
 *
 * Dos decisiones de lectura:
 *  1. El número grande es lo dicho EN SERIO. El humor va al lado, atenuado y
 *     visible — no se esconde, porque el modelo detecta ironía mal y un
 *     "jajaja paro" puede ser sarcasmo amargo que alguien quiera revisar.
 *  2. Los EJEMPLOS están a un clic. Un contador que no se puede auditar no lo
 *     cree nadie, y con razón.
 */
function SenalesVigilancia({ data, vidaMedia }: { data: TerminosResponse; vidaMedia: number }) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const g = data.global;
  if (!g) return null;

  return (
    <div className={`${CARD} border-[var(--alerta-media)]`}>
      <TituloBloque
        titulo="Señales bajo vigilancia"
        ignoraRecencia
        vidaMedia={vidaMedia}
        extra={
          <span className="rounded border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-2 py-0.5 text-xs font-semibold text-ucn-tierra-clara">
            léxico fijo y auditable
          </span>
        }
      >
        Menciones de <strong className="text-slate-400">paro, toma, petitorio, asamblea y
        movilización</strong>, contadas aparte del clasificador temático —donde hoy quedan
        repartidas entre “Académico”, “Organización estudiantil” y “Otros”, y no se ven.
        {" "}<strong className="text-slate-400">No intervienen en el índice</strong>: la
        fórmula del Termómetro queda intacta.
      </TituloBloque>

      {data.familias.length === 0 ? (
        <p className="py-4 text-center text-sm text-slate-500">
          Ninguna mención del léxico crítico en este período
          {g.n_comentarios > 0 ? ` (${nro(g.n_comentarios)} comentarios revisados).` : "."}
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm text-ucn-tierra-clara">
            {nro(g.n_con_termino)} de {nro(g.n_comentarios)} comentarios ({g.pct}%) mencionan
            alguno de estos términos
            {g.n_humor > 0 ? `, ${g.n_humor} en tono de broma` : ""}.
          </p>
          <ul className="space-y-2">
            {data.familias.map((f) => {
              // Piso de privacidad (wh-api): con pocas menciones solo se publica el conteo.
              if (f.detalle_suprimido) {
                return (
                  <li key={f.clave} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-slate-100">{f.etiqueta}</span>
                      <span className="text-lg font-bold tabular-nums" style={{ color: COLOR_COPPER }}>
                        {f.n_menciones}
                      </span>
                      <span className="text-sm text-slate-500">
                        {f.n_menciones === 1 ? "mención" : "menciones"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">Pocas menciones: detalle oculto por privacidad</p>
                  </li>
                );
              }
              const nSerio = f.n_serio ?? 0;
              return (
              <li key={f.clave} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-slate-100">{f.etiqueta}</span>
                      <span className="text-lg font-bold tabular-nums" style={{ color: COLOR_COPPER }}>
                        {nSerio}
                      </span>
                      <span className="text-sm text-slate-500">
                        {nSerio === 1 ? "mención en serio" : "menciones en serio"}
                      </span>
                      {(f.n_humor ?? 0) > 0 ? (
                        <span
                          className="rounded border border-white/10 px-2 py-0.5 text-xs text-slate-500"
                          title="El modelo las leyó como humor o ironía. No entran en el cálculo, pero se muestran: la ironía se detecta mal y puede ser sarcasmo amargo."
                        >
                          +{f.n_humor} en broma
                        </span>
                      ) : null}
                      {f.es_nuevo ? (
                        <span className="rounded border border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)] px-2 py-0.5 text-xs font-semibold text-ucn-azul-claro">
                          nuevo este período
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-1 text-sm text-slate-400">
                      {f.temas.length > 0 ? (
                        <>Se habla en {f.temas.map((t) => `${t.etiqueta} (${t.n})`).join(", ")}</>
                      ) : (
                        "Sin tema asignado"
                      )}
                      {f.primera_mencion ? (
                        <> · {fechaCorta(f.primera_mencion)} – {fechaCorta(f.ultima_mencion)}</>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-4">
                    <Sparkline semanas={f.serie_semanal} />
                    <Delta valor={f.delta_menciones_pct} sufijo="%" titulo="volumen" />
                    <Indice valor={f.indice} evidencia={nSerio > 0} />
                  </div>
                </div>

                {nSerio > 0 ? (
                  <div className="mt-2 flex items-center gap-3">
                    <BarraSentimiento pos={f.n_pos ?? 0} neu={f.n_neu ?? 0} neg={f.n_neg ?? 0} />
                    <span className="shrink-0 text-xs tabular-nums text-slate-500">
                      {f.n_pos ?? 0}/{f.n_neu ?? 0}/{f.n_neg ?? 0}
                    </span>
                  </div>
                ) : null}

                {f.ejemplos.length > 0 ? (
                  <>
                    <button
                      type="button"
                      className="mt-2 text-sm text-ucn-azul-claro hover:underline"
                      onClick={() => setAbierta(abierta === f.clave ? null : f.clave)}
                      aria-expanded={abierta === f.clave}
                    >
                      {abierta === f.clave ? "Ocultar" : "Ver"} qué se dijo ({f.ejemplos.length})
                    </button>
                    {abierta === f.clave ? (
                      <ul className="mt-2 space-y-1.5">
                        {f.ejemplos.map((e, i) => (
                          <li
                            key={`${f.clave}-${i}`}
                            className="rounded-xl border border-white/5 bg-[var(--boveda-madera)] px-3 py-2 text-sm leading-5 text-slate-400"
                          >
                            <span
                              className="mr-2 font-semibold"
                              style={{
                                color:
                                  e.sentimiento === "NEG"
                                    ? COLOR_NEG
                                    : e.sentimiento === "POS"
                                      ? COLOR_POS
                                      : COLOR_NEU,
                              }}
                            >
                              {e.sentimiento_label}
                            </span>
                            {e.emocion_label ? <span className="mr-2 rounded bg-white/[0.04] px-2 py-0.5">{e.emocion_label}</span> : null}
                            <span className="text-slate-500">
                              · {fechaCorta(e.fecha)}
                              {e.tema_label ? ` · ${e.tema_label}` : ""}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </>
                ) : null}
              </li>
              );
            })}
          </ul>
          <p className="mt-3 text-sm leading-4 text-slate-500">
            Por privacidad, los comentarios se muestran como etiquetas (sentimiento, tema, emoción), sin texto ni autor. El léxico está versionado en
            el código y se revisa como cualquier otro cambio.
          </p>
        </>
      )}
    </div>
  );
}

/**
 * SEMANAS FUERA DE LO HABITUAL.
 *
 * La unidad es la SEMANA, no el día: el corpus tiene mediana de 5 comentarios
 * diarios y un z-score diario es ruido. La detección corre sobre una serie
 * distinta de la que se grafica en Explorar — se dibuja suave y se detecta crudo.
 */
/** Los dos niveles, con su horizonte MEDIDO a la vista.
 *
 * Por qué el lead va en el chip y no escondido en un tooltip de ayuda: "hay una
 * alerta" no se puede accionar; "esto suele avisar con un mes" sí. Y por qué se
 * muestra también la cobertura al lado: un nivel que avisa con 35 días pero toma
 * 2 de 5 episodios no se lee igual que uno que toma 4, y sin ese número la
 * precisión se sobreentiende de más.
 *
 * ALERTA va en rojo y ATENCIÓN en cobre a propósito: son acciones distintas —una
 * es avisar, la otra es mirar— y el color es lo primero que se lee.
 */
/** Las dos preguntas de Alertas, en el idioma de quien las lee.
 *
 * «Señales bajo vigilancia» y «Semanas fuera de lo habitual» son nombres del
 * módulo, no de un director: describen CÓMO se calcula cada bloque, no qué
 * contesta. Acá se nombran por la respuesta. */
const SUB_ALERTAS = [
  {
    id: "dicho",
    label: "¿Se está hablando de paro?",
    hint:
      "Menciones de paro, toma, petitorio, asamblea y movilización, contadas aparte del " +
      "clasificador. Es la señal más precisa que tiene el módulo: cuando aparece, casi " +
      "siempre hubo conflicto.",
  },
  {
    id: "periodos",
    label: "¿Qué quincena se salió de lo normal?",
    hint:
      "Períodos de dos semanas que se apartaron de su historia reciente, con el nivel de " +
      "alerta y con cuánta anticipación suele avisar cada uno.",
  },
] as const;

function ChipNivel({ a }: { a: AnomaliaItem }) {
  if (!a.nivel_alerta) {
    return <span className="text-sm text-slate-500">—</span>;
  }
  const esAlerta = a.nivel_alerta === "alerta";
  const rango = a.lead_rango_dias;
  const cob = a.cobertura_medida;
  const ayuda = [
    esAlerta
      ? "Alguien nombra paro, toma o asamblea en un comentario negativo."
      : "La negatividad de la semana se apartó de su historia reciente.",
    a.lead_esperado_dias != null
      ? `Suele avisar con ${a.lead_esperado_dias} días de anticipación` +
        (rango ? ` (rango medido ${rango[0]}–${rango[1]}).` : ".")
      : "",
    cob ? `Anticipó ${cob[0]} de los ${cob[1]} episodios evaluables del histórico.` : "",
    esAlerta
      ? "Es el nivel preciso: cuando suena, casi siempre hubo conflicto."
      : "Es el nivel que cubre: no detecta paros, detecta semanas en que algo anda mal.",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className="flex flex-col gap-0.5" title={ayuda}>
      <span
        className="w-fit rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide"
        style={{
          color: esAlerta ? COLOR_NEG : COLOR_COPPER,
          background: esAlerta ? `${COLOR_NEG}1f` : `${COLOR_COPPER}1f`,
          border: `1px solid ${esAlerta ? COLOR_NEG : COLOR_COPPER}55`,
        }}
      >
        {esAlerta ? "Alerta" : "Atención"}
      </span>
      {a.lead_esperado_dias != null ? (
        <span className="text-xs tabular-nums text-slate-500">
          ~{a.lead_esperado_dias} d antes
        </span>
      ) : null}
    </span>
  );
}

/** Qué tan bien anda ESTA configuración, medido — no prometido.
 *
 * Va acá arriba y no en un tooltip porque es lo que le da (o le quita) crédito a
 * todo lo de abajo: una alarma sin saber cuántas veces acierta no se puede usar
 * para decidir nada. Y si la unidad activa no tiene medición propia, se dice —
 * mostrar el rendimiento de otra configuración sería reportar algo que el lector
 * no está mirando.
 */
function RendimientoMedido({ cfg }: { cfg?: AnomaliasConfig }) {
  if (!cfg) return null;
  const m = cfg.medicion;
  const base =
    "mb-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm leading-relaxed text-slate-400";
  if (!m) {
    return (
      <p className={base}>
        Con unidad de {cfg.unidad_semanas} semanas <strong className="text-slate-400">no hay
        medición propia</strong>: solo se calibraron 1 y 2 semanas contra los episodios del
        calendario. Las alarmas se calculan igual, pero no se puede decir con cuánta
        anticipación ni con qué tasa de acierto.
      </p>
    );
  }
  return (
    <p className={base}>
      <strong className="text-slate-400">Medido sobre 4 años</strong> con esta configuración:
      enciende en <strong className="text-slate-400">{m.detecta} de los {m.evaluables}</strong>{" "}
      episodios de conflicto con ventana evaluable, con{" "}
      <strong className="text-slate-400">{m.lead_mediano} días</strong> de anticipación mediana,{" "}
      <strong className="text-slate-400">{m.falsas_anio.toFixed(1)}</strong> falsas alarmas por
      año y <strong className="text-slate-400">{Math.round(100 * m.precision)}%</strong> de
      precisión. Encender no siempre es anticipar: dos de esos episodios se marcan el mismo
      día — un shock externo no se gesta en los comentarios.
    </p>
  );
}

function SemanasAnomalas({
  items,
  vidaMedia,
  cfg,
}: {
  items: AnomaliaItem[];
  vidaMedia: number;
  cfg?: AnomaliasConfig;
}) {
  return (
    <div className={CARD}>
      <TituloBloque
        titulo={cfg && cfg.unidad_semanas === 1 ? "Semanas fuera de lo habitual" : "Quincenas fuera de lo habitual"}
        vidaMedia={vidaMedia}
        ignoraRecencia
      >
        La unidad son{" "}
        <strong className="text-slate-400">
          {cfg ? `${cfg.unidad_semanas} ${cfg.unidad_semanas === 1 ? "semana" : "semanas"}` : "2 semanas"}
        </strong>
        , comparadas contra la mediana de{" "}
        <strong className="text-slate-400">{cfg ? `${cfg.baseline_semanas} semanas` : "medio año"}</strong>{" "}
        hacia atrás. El <strong className="text-slate-400">nivel</strong> dice qué hacer y la{" "}
        <strong className="text-slate-400">severidad</strong>, cuánto se apartó el período.
        Coincidencia no es causalidad.
      </TituloBloque>
      <RendimientoMedido cfg={cfg} />
      {items.length === 0 ? (
        <p className="py-4 text-center text-sm text-slate-500">
          Ninguna semana se apartó de su historia reciente en este período.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-1 pr-4">Quincena</th>
                <th className="py-1 pr-4">Nivel</th>
                <th className="py-1 pr-4">Severidad</th>
                <th className="py-1 pr-4">Por qué</th>
                <th className="py-1 pr-4">Índice</th>
                <th className="py-1 pr-4">% neg.</th>
                <th className="py-1">Menciones críticas</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 12).map((a, i) => (
                <tr key={i} className="border-t border-white/5 text-slate-400">
                  <td className="py-1.5 pr-4 whitespace-nowrap">
                    {fechaCorta(a.fecha)}
                    {/* El bloque son dos semanas: mostrar solo el lunes hace creer
                        que la alarma es de ese día. */}
                    {a.fecha_fin ? (
                      <span className="text-slate-500"> – {fechaCorta(a.fecha_fin)}</span>
                    ) : null}
                  </td>
                  <td className="py-1.5 pr-4"><ChipNivel a={a} /></td>
                  <td className="py-1.5 pr-4">
                    <span
                      className="flex items-center gap-2"
                      title={`Severidad ${Math.round(100 * a.severidad)}%`}
                    >
                      <span className="h-1.5 w-12 shrink-0 overflow-hidden rounded-full bg-white/[0.06]">
                        <span
                          className="block h-full rounded-full"
                          style={{
                            width: `${Math.round(100 * a.severidad)}%`,
                            background: a.severidad >= 0.8 ? COLOR_NEG : COLOR_COPPER,
                          }}
                        />
                      </span>
                      <span className="text-xs tabular-nums text-slate-400">
                        {a.severidad.toFixed(2)}
                      </span>
                    </span>
                  </td>
                  <td className="py-1.5 pr-4">
                    <span className="flex flex-wrap gap-1">
                      {a.motivos.map((m) => (
                        <span
                          key={m}
                          className="rounded border border-white/10 bg-white/[0.04] px-2 py-0.5 text-xs text-slate-400"
                          title={MOTIVO_AYUDA[m] ?? m}
                        >
                          {MOTIVO_LABEL[m] ?? m}
                        </span>
                      ))}
                    </span>
                  </td>
                  <td className="py-1.5 pr-4 tabular-nums" style={{ color: colorIndice(a.indice) }}>
                    {fmt(a.indice)}
                    {a.z_indice != null ? (
                      <span className="ml-1 text-sm text-slate-500">z {fmt(a.z_indice, 1)}</span>
                    ) : null}
                  </td>
                  <td className="py-1.5 pr-4 tabular-nums text-slate-400">
                    {a.pct_neg == null ? "—" : `${a.pct_neg.toFixed(1)}%`}
                  </td>
                  {/* Negativas sobre el total de menciones serias: es el
                      discriminante real. Con cero negativas igual se escribe
                      "0 de N" — un guion seguido de "de 1" no se entiende. */}
                  <td className="py-1.5 tabular-nums text-slate-400">
                    {a.n_terminos === 0 ? (
                      "—"
                    ) : (
                      <>
                        <span style={{ color: a.n_terminos_neg > 0 ? COLOR_NEG : undefined }}>
                          {a.n_terminos_neg} neg.
                        </span>
                        <span className="ml-1 text-sm text-slate-500">de {a.n_terminos}</span>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function PercepcionAlertas({ filtro }: { filtro: Filtro }) {
  const [terminos, setTerminos] = useState<TerminosResponse | null>(null);
  const [sub, setSub] = useState<"dicho" | "periodos">("dicho");
  const [anomalias, setAnomalias] = useState<AnomaliaItem[]>([]);
  // La configuracion viene con los datos: la unidad de deteccion es ajustable
  // por entorno y el panel tiene que declarar con cual esta mirando.
  const [cfgAnomalias, setCfgAnomalias] = useState<AnomaliasConfig | undefined>();
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      // Cada bloque falla por su cuenta: que la vigilancia se caiga no tiene por
      // qué llevarse puestas las semanas anómalas, ni al revés.
      const [t, a] = await Promise.all([
        percepcionApi.terminos(filtro, opts).catch(() => null),
        percepcionApi.anomalias(filtro, opts).catch(() => null),
      ]);
      if (ctrl.signal.aborted) return;
      if (t === null && a === null) throw new Error("No se pudieron cargar las alertas.");
      setTerminos(t);
      setAnomalias(a?.items ?? []);
      setCfgAnomalias(a?.config);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudieron cargar las alertas.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [filtro, nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  if (!terminos && cargando) {
    return (
      <div className={CARD}>
        <p className="py-6 text-center text-sm text-slate-500">Cargando alertas…</p>
      </div>
    );
  }
  if (error && !terminos) {
    return (
      <div className={CARD}>
        <p className="text-sm text-ucn-tierra-clara">{error}</p>
      </div>
    );
  }

  const nAlertas = anomalias.length;
  const nFamilias = terminos?.familias.length ?? 0;

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

      {nAlertas === 0 && nFamilias === 0 ? (
        <div className={`${CARD} border-[var(--ucn-azul-borde)]`}>
          <div className="py-6 text-center">
            <p className="text-sm font-medium text-slate-100">Sin alertas en este período</p>
            <p className="mt-1 text-sm text-slate-500">
              Ninguna semana se apartó de su historia reciente y no hay menciones del léxico
              crítico. Amplía el rango si quieres revisar más atrás.
            </p>
          </div>
        </div>
      ) : null}

      {/* Dos preguntas distintas, y por eso se turnan. Los dos bloques son largos
          —el léxico lista cinco familias con sus ejemplos, la detección lista hasta
          doce quincenas— y apilados obligan a scrollear uno entero para llegar al
          otro. El orden no es alfabético: primero lo que se está DICIENDO, que es
          la señal más precisa (86 % de acierto) y la que un director puede leer
          sin saber estadística. */}
      <SubPestanas opciones={SUB_ALERTAS} activa={sub} onCambio={setSub} />

      {sub === "dicho" && terminos ? (
        <SenalesVigilancia data={terminos} vidaMedia={filtro.vidaMedia} />
      ) : null}
      {sub === "dicho" && !terminos ? (
        <div className={CARD}>
          <p className="py-6 text-center text-sm text-slate-500">
            Sin menciones del léxico de conflicto en este período.
          </p>
        </div>
      ) : null}
      {sub === "periodos" ? (
        <SemanasAnomalas items={anomalias} vidaMedia={filtro.vidaMedia} cfg={cfgAnomalias} />
      ) : null}
    </div>
  );
}

export default PercepcionAlertas;
