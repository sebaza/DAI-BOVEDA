"use client";

// COMPARAR — "¿dónde está el problema?".
//
// Por qué existe esta pestaña: antes los dos cortes que sirven para comparar
// —por TEMA y por ÁREA— estaban DUPLICADOS. Vivían como tabla en el Resumen
// (sin ponderar recencia) y como gráfico en Explorar (ponderando recencia), y
// los números no coincidían: el tema "Otros" daba 58.7 en una pestaña y 64.3 en
// la otra, y "Organización estudiantil" cruzaba el neutro de una a la otra.
//
// Acá cada corte aparece UNA sola vez, con el gráfico y la tabla alimentados por
// la MISMA llamada (`/percepcion/sintesis`, que devuelve temas y áreas juntos).
// No es una preferencia estética: mientras sean dos fuentes, tarde o temprano
// vuelven a divergir y nadie se entera.
//
// Lectura: "promedio del período" (sin decaimiento). Comparar entidades entre sí
// pide que cada comentario del período pese igual; la temperatura reciente vive
// en Conversación, que es donde el tiempo importa.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import { PALETA } from "@/lib/paleta";

import { EChartsChart } from "./EChartsChart";
import { PercepcionVolatilidad } from "./PercepcionVolatilidad";
import type {
  ConcentracionResponse,
  Filtro,
  PosturaTramo,
  OrdenSintesis,
  PalabraDestacada,
  SintesisArea,
  SintesisResponse,
  SintesisTema,
} from "../lib/percepcion";
import { esCancelacion, percepcionApi } from "../lib/percepcion";
import {
  BarraConfianza,
  CARD,
  COLOR_NEG,
  COLOR_NEU,
  COLOR_POS,
  Indice,
  SELECT,
  SinActividadReciente,
  SinEvidencia,
  SubPestanas,
  TituloBloque,
  colorIndice,
  fmt,
  labelEmocion,
  nro,
  Esqueleto,
} from "./PercepcionUI";

/**
 * Barras del índice por área, peor arriba.
 *
 * Las filas SIN evidencia suficiente van semitransparentes: si se dibujan igual
 * que las demás, una unidad de 7 comentarios encabeza el gráfico y se lee como
 * "la peor facultad". La opacidad hace el mismo trabajo que la etiqueta
 * "muestra insuficiente" de la tabla, pero de un vistazo.
 */
function opcionAreas(areas: SintesisArea[], minimo: number): Record<string, unknown> {
  // Orden DESCENDENTE a propósito: en un eje de categorías, ECharts dibuja el
  // primer elemento ABAJO. Ordenando de mejor a peor, la peor unidad queda
  // ARRIBA, que es donde tiene que estar en una pestaña que responde "¿dónde está
  // el problema?". Con el orden natural (ascendente) lo peor caía al pie del
  // gráfico y había que barrer con la vista para encontrarlo.
  const orden = [...areas].sort((a, b) => (b.indice ?? 0) - (a.indice ?? 0));
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 8, right: 34, top: 10, bottom: 10, containLabel: true },
    xAxis: { type: "value", min: 0, max: 100 },
    yAxis: { type: "category", data: orden.map((a) => a.nombre), axisLabel: { fontSize: 12 } },
    series: [
      {
        type: "bar",
        data: orden.map((a) => ({
          // `null` y no 0: sin índice por recencia NO es "índice cero". Con 0 la
          // barra se dibujaría al tope del ranking de lo peor, que es justo lo
          // contrario de lo que significa (no habló últimamente).
          value: a.indice == null ? null : Number(a.indice.toFixed(1)),
          itemStyle: {
            color: colorIndice(a.indice),
            borderRadius: [0, 1, 1, 0],
            opacity: a.evidencia_suficiente ? 1 : 0.35,
          },
        })),
        label: { show: true, position: "right", formatter: "{c}", color: PALETA.muted },
        barMaxWidth: 20,
      },
    ],
    // El umbral de evidencia, dicho en el propio gráfico.
    graphic: [
      {
        type: "text",
        right: 4,
        top: 0,
        style: {
          text: `atenuadas: menos de ${minimo} comentarios`,
          fill: PALETA.subtle,
          fontSize: 12,
        },
      },
    ],
  };
}

/** Barras apiladas pos/neu/neg por tema, el más comentado abajo. */
function opcionTemas(temas: SintesisTema[]): Record<string, unknown> | null {
  // Temas con detalle suprimido no tienen n_pos/neu/neg: dibujarlos daría barras 0/0/0 falsas.
  const visibles = temas.filter((t) => !t.detalle_suprimido);
  if (visibles.length === 0) return null;
  const orden = [...visibles].sort((a, b) => a.n_comentarios - b.n_comentarios);
  const serie = (key: "n_pos" | "n_neu" | "n_neg", color: string, nombre: string) => ({
    name: nombre,
    type: "bar",
    stack: "sent",
    data: orden.map((t) => t[key] ?? 0),
    itemStyle: { color },
    barMaxWidth: 22,
  });
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: PALETA.muted } },
    grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
    xAxis: { type: "value" },
    yAxis: { type: "category", data: orden.map((t) => t.etiqueta), axisLabel: { fontSize: 12 } },
    series: [
      serie("n_pos", COLOR_POS, "Positivo"),
      serie("n_neu", COLOR_NEU, "Neutral"),
      serie("n_neg", COLOR_NEG, "Negativo"),
    ],
  };
}

/**
 * QUÉ SE DICE — las palabras propias de un área o un tema.
 *
 * Cada palabra se colorea por su carga NEGATIVA dentro de esa área, no por la
 * global: lo interesante es que "clases" sea neutro en una facultad y cargado en
 * otra.
 *
 * Cuando viene vacío se dice "sin evidencia" y no se deja el hueco. Hay dos
 * motivos posibles y los dos importan: o ninguna palabra del área alcanzó el
 * mínimo GLOBAL —el resguardo que impide publicar el nombre de una persona en un
 * departamento chico— o ninguna se dijo lo suficiente ahí como para representarlo.
 */
function Palabras({ palabras }: { palabras: PalabraDestacada[] }) {
  if (palabras.length === 0) {
    return (
      <span
        className="text-sm text-slate-500"
        title={
          "Ninguna palabra de esta área alcanza el mínimo. Se exige un piso de " +
          "apariciones en todo el período (que además evita mostrar nombres de " +
          "personas) y un piso dentro del área."
        }
      >
        sin evidencia
      </span>
    );
  }
  return (
    <span className="flex flex-wrap gap-1">
      {palabras.map((p) => {
        const cargada = p.n_neg > 0 && p.pct_neg >= 30;
        return (
          <span
            key={p.texto}
            className="rounded border px-2 py-0.5 text-xs"
            style={{
              borderColor: cargada ? `${COLOR_NEG}55` : PALETA.lineaFuerte,
              background: cargada ? `${COLOR_NEG}14` : PALETA.linea,
              color: cargada ? COLOR_NEG : PALETA.muted,
            }}
            title={`${p.n} comentarios · ${p.n_pos} positivos, ${p.n_neu} neutrales, ${p.n_neg} negativos (${p.pct_neg}% negativo)`}
          >
            {p.texto}
            <span className="ml-1 opacity-60">{p.n}</span>
          </span>
        );
      })}
    </span>
  );
}

/** Postura de una unidad: UN glifo y UN número.
 *
 * ⚠️ TERCERA VERSIÓN, y las dos anteriores fallaron por lo mismo: METER DEMASIADO
 * EN UNA CELDA. Primero fue una barra apilada de tres tramos + el % adverso suelto
 * (sin leyenda no se sabía qué color era cuál). Después, una barra divergente + la
 * lectura mayoritaria + el adverso comparado: más correcto y aún así ilegible, tres
 * elementos visuales y dos renglones de texto en una celda que se escanea.
 *
 * Una tabla se recorre con la vista de arriba abajo. Lo que sirve ahí es un dato
 * que signifique LO MISMO en todas las filas y se compare sin leer.
 *
 * SALDO = % favorable − % adverso. Positivo, la unidad le suma a la UCN; negativo,
 * le resta; cerca de cero, no se inclina. Un saldo chico ya dice «no genera
 * postura», así que no hace falta un tercer estado: Humanidades da −2,9 y esa
 * cercanía a cero ES la lectura. El desglose completo va en el tooltip, para quien
 * lo necesite; en la celda no.
 */
const COLOR_POSTURA: Record<string, string> = {
  favorable: PALETA.favorable,
  neutral: PALETA.neutro,
  adverso: PALETA.adverso,
};

function PosturaCelda({ tramos }: { tramos: PosturaTramo[] | null }) {
  if (!tramos) return <span className="text-slate-500">—</span>;
  const pct = (k: string) => tramos.find((t) => t.postura === k)?.pct ?? 0;
  const saldo = Math.round(pct("favorable") - pct("adverso"));
  // Bajo ±3 puntos la dirección no significa nada: se muestra plano en vez de
  // dibujar una flecha que insinúa una tendencia inexistente.
  const plano = Math.abs(saldo) < 3;
  const color = plano
    ? PALETA.muted
    : saldo > 0
      ? COLOR_POSTURA.favorable
      : COLOR_POSTURA.adverso;

  return (
    <span
      className="flex items-center gap-1.5 tabular-nums"
      style={{ color }}
      title={tramos.map((t) => `${t.etiqueta}: ${t.pct}%`).join(" · ")}
      aria-label={
        plano
          ? "Sin inclinación"
          : saldo > 0
            ? `Favorable a la UCN, saldo ${saldo}`
            : `Adverso a la UCN, saldo ${saldo}`
      }
    >
      <span aria-hidden="true" className="text-sm leading-none">
        {plano ? "—" : saldo > 0 ? "▲" : "▼"}
      </span>
      <span className="text-sm">{saldo > 0 ? `+${saldo}` : saldo}</span>
    </span>
  );
}

/** ¿ES MÍO O ES DE TODOS? — concentración de cada tema entre unidades.
 *
 * El tablero mostraba VOLUMEN por unidad, y eso confunde dos cosas distintas:
 * «este tema pesa acá» con «esta unidad comenta mucho de todo». El Gini se calcula
 * sobre la PREVALENCIA (comentarios del tema ÷ comentarios de la unidad), y esa
 * división es justamente la que las separa.
 *
 * ⚠️ La cobertura va A LA VISTA. Sólo un tercio de los comentarios tiene facultad
 * —las cuentas de más volumen son agrupaciones, no unidades académicas— así que
 * esto describe la conversación DE LAS UNIDADES. Presentarlo como si fuera del
 * corpus entero sería mentir por omisión.
 */
function Concentracion({ data }: { data: ConcentracionResponse }) {
  if (!data.hay_datos) {
    return data.motivo ? (
      <p className="text-sm leading-5 text-slate-500">{data.motivo}</p>
    ) : null;
  }
  return (
    <>
      <ul className="mt-3 flex flex-col gap-4">
        {data.items.map((i) => (
          <li key={i.tema} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-sm text-slate-100">{i.etiqueta}</span>
              <span
                className={
                  i.concentrado
                    ? "rounded bg-[color-mix(in_srgb,var(--portal-copper)_15%,transparent)] px-2 py-0.5 text-xs font-medium text-ucn-tierra-clara"
                    : "rounded bg-slate-700/40 px-2 py-0.5 text-xs font-medium text-slate-400"
                }
              >
                {i.reparto}
              </span>
            </div>

            {/* LA FRASE ES EL DATO. Antes acá decía «Gini 0,70», que no le dice nada
                a quien tiene que decidir algo con esto. Un porcentaje sobre el total
                de la unidad, comparado con el promedio, se lee sin glosario. */}
            <p className="text-sm leading-5 text-slate-400">
              En <span className="text-slate-100">{i.unidad_top}</span> es el{" "}
              <span className="text-slate-100">{i.prevalencia_top}%</span> de lo que se
              comenta
              {i.veces_sobre_promedio ? (
                <>
                  {" "}—{" "}
                  <span className="text-slate-100">{i.veces_sobre_promedio}×</span> más
                  que en una unidad promedio ({i.prevalencia_media}%)
                </>
              ) : null}
              .
            </p>

            {/* Dos barras a la misma escala: la unidad que más lo trata contra el
                promedio. La diferencia de largo ES la concentración, sin números. */}
            <div className="flex flex-col gap-1">
              {[
                { et: i.unidad_top, v: i.prevalencia_top, fuerte: true },
                { et: "Promedio de unidades", v: i.prevalencia_media, fuerte: false },
              ].map((b) => (
                <div key={b.et} className="flex items-center gap-2">
                  <span className="w-40 flex-none truncate text-sm text-slate-500">
                    {b.et}
                  </span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                    <span
                      className="block h-full rounded-full"
                      style={{
                        width: `${Math.min(100, b.v)}%`,
                        background: b.fuerte
                          ? i.concentrado
                            ? "var(--portal-copper)"
                            : "var(--portal-cyan)"
                          : PALETA.subtle,
                      }}
                    />
                  </span>
                  <span className="w-10 flex-none text-right text-xs tabular-nums text-slate-500">
                    {b.v}%
                  </span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-4 border-t border-slate-800 pt-2 text-sm leading-5 text-slate-500">
        Se comparan {data.unidades} unidades con {data.minimo_por_unidad} o más
        comentarios ({nro(data.n_comentarios)} comentarios, el {data.cobertura_pct}% del
        período). El resto viene de cuentas sin unidad asignada —agrupaciones, centros
        de estudiantes— y no entra en esta comparación.
      </p>
    </>
  );
}

/** Las tres preguntas de Comparar, nombradas por lo que contestan.
 *
 * Las tres comparan unidades entre sí, pero por cosas distintas: cómo está cada
 * una, de qué habla cada una, y cuál se mueve más. Apiladas eran tres bloques
 * largos —dos con gráfico y tabla— que obligaban a scrollear el primero entero
 * para descubrir que existía el tercero. */
const SUB_COMPARAR = [
  {
    id: "estado",
    label: "¿Cómo está cada área?",
    hint:
      "El índice de cada facultad, departamento o sede, y si el problema está concentrado " +
      "en una unidad o es de toda la universidad.",
  },
  {
    id: "temas",
    label: "¿De qué se habla?",
    hint: "Los temas de la conversación, con cuánto pesa cada uno y con qué carga.",
  },
  {
    id: "movimiento",
    label: "¿Qué unidad se mueve más?",
    hint:
      "Cuánto varía el índice de cada unidad semana a semana, descontando lo que se " +
      "explica solo por tener pocos comentarios. Una unidad estable y una sin datos " +
      "suficientes no son lo mismo, y acá se distinguen.",
  },
] as const;

export function PercepcionComparar({
  filtro, sub: subExterna, onSub,
}: {
  filtro: Filtro;
  /** Sub-pestaña CONTROLADA desde el panel. Existe para que un salto desde el
   *  Resumen pueda aterrizar en la vista correcta: llevar a "Comparar" sin decir a
   *  cuál de sus tres vistas deja al director buscando el dato que venía siguiendo. */
  sub?: "estado" | "temas" | "movimiento";
  onSub?: (s: "estado" | "temas" | "movimiento") => void;
}) {
  // Estado propio como respaldo: el componente sigue funcionando montado suelto
  // (tests, preview) sin obligar a quien lo use a manejarle la sub-pestaña.
  const [subLocal, setSubLocal] = useState<"estado" | "temas" | "movimiento">("estado");
  const sub = subExterna ?? subLocal;
  const setSub = onSub ?? setSubLocal;
  const [nivel, setNivel] = useState<"facultad" | "campus" | "departamento">("facultad");
  const [orden, setOrden] = useState<OrdenSintesis>("peor");
  const [data, setData] = useState<SintesisResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conc, setConc] = useState<ConcentracionResponse | null>(null);

  const nueva = useSolicitudVigente();
  const cargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      const [sint, cc] = await Promise.all([
        percepcionApi.sintesis(nivel, orden, filtro, opts),
        percepcionApi.concentracion(filtro, nivel, opts).catch(() => null),
      ]);
      if (ctrl.signal.aborted) return;
      setConc(cc);
      setData(sint);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar la comparación.");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nivel, orden, filtro, nueva]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const optAreas = useMemo(
    () => (data ? opcionAreas(data.areas, data.n_min_evidencia) : null),
    [data],
  );
  const optTemas = useMemo(() => (data ? opcionTemas(data.temas) : null), [data]);

  if (!data && cargando) {
    return (
      <Esqueleto etiqueta="Cargando comparación…" bloques={[120, 340, 300]} />
    );
  }
  if (error && !data) {
    return (
      <div className={CARD}>
        <p className="text-sm text-ucn-tierra-clara">{error}</p>
      </div>
    );
  }
  if (!data || !data.hay_datos) {
    return (
      <div className={CARD}>
        <p className="py-6 text-center text-sm text-slate-500">
          No hay datos de percepción para este filtro.
        </p>
      </div>
    );
  }

  const min = data.n_min_evidencia;
  const areasSinCobertura = data.areas.filter((a) => !a.detalle_suprimido && (!a.evidencia_suficiente || (a.confianza ?? 0) < 0.3));

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

      {/* Controles del corte. Van arriba porque afectan a los DOS bloques. */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] px-4 py-2.5">
        <p className="text-sm leading-5 text-slate-400">
          El gráfico y la tabla de cada bloque salen de la{" "}
          <strong className="text-slate-400">misma consulta</strong>: no pueden mostrar números
          distintos.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400">
            Ordenar por
            <select
              className={SELECT}
              value={orden}
              onChange={(e) => setOrden(e.target.value as OrdenSintesis)}
              title="Las filas con muestra insuficiente quedan al final en ambos órdenes."
            >
              <option value="peor">Peor hablado primero</option>
              <option value="volumen">Más comentado primero</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-400">
            Agrupar áreas por
            <select
              className={SELECT}
              value={nivel}
              onChange={(e) => setNivel(e.target.value as typeof nivel)}
            >
              <option value="facultad">Facultad</option>
              <option value="departamento">Departamento</option>
              <option value="campus">Sede</option>
            </select>
          </label>
        </div>
      </div>

      <SubPestanas opciones={SUB_COMPARAR} activa={sub} onCambio={setSub} />

      {/* ───────────── POR ÁREA ───────────── */}
      {sub !== "estado" ? null : (
      <>
      <div className={CARD}>
        <TituloBloque
          titulo="Cómo está cada área"
          vidaMedia={filtro.vidaMedia}
          extra={
            data.tema_filtrado ? (
              <span className="rounded border border-[color-mix(in_srgb,var(--portal-cyan)_30%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_10%,transparent)] px-2 py-0.5 text-xs font-semibold text-ucn-azul-claro">
                solo tema:{" "}
                {data.temas.find((t) => t.tema === data.tema_filtrado)?.etiqueta ?? data.tema_filtrado}
              </span>
            ) : null
          }
        >
          El área es la CUENTA institucional donde se comentó, no la unidad de quien comenta.
          Cubre {nro(data.cobertura_area.n_con_area)} de {nro(data.cobertura_area.n_total)}{" "}
          comentarios ({data.cobertura_area.pct}%): el resto no tiene esta dimensión asignada.
        </TituloBloque>

        {data.areas.length > 0 && optAreas ? (
          <>
            <EChartsChart
              option={optAreas}
              height={Math.max(160, data.areas.length * 34)}
              ariaLabel="Índice por área"
            />
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-1 pr-4">Área</th>
                    <th className="py-1 pr-4">Comentarios</th>
                    {/* La confianza va ANTES del índice a propósito: se lee
                        primero cuánto vale el número y recién después el número. */}
                    <th className="py-1 pr-4">Confianza</th>
                    <th className="py-1 pr-4">Índice</th>
                    {/* Postura al lado del índice para que la brecha entre los dos
                        se lea sin buscar: tono positivo no es lo mismo que
                        favorable a la institución. */}
                    <th
                      className="py-1 pr-4"
                      title="Saldo: % favorable menos % adverso. ▲ la unidad le suma a la UCN, ▼ le resta, — no se inclina. Pasa el cursor sobre cada valor para ver el desglose."
                    >
                      Postura
                    </th>
                    <th className="py-1 pr-4">Tema principal</th>
                    <th className="py-1 pr-4">Emoción</th>
                    <th className="py-1">Qué se dice</th>
                  </tr>
                </thead>
                <tbody>
                  {data.areas.map((a: SintesisArea) => (
                    <tr key={a.nombre} className="border-t border-white/5 text-slate-400">
                      <td className="py-1.5 pr-4">
                        <span className={a.evidencia_suficiente ? "" : "opacity-60"}>{a.nombre}</span>
                        {!a.evidencia_suficiente ? (
                          <span className="ml-2">
                            <SinEvidencia n={a.n_comentarios} minimo={min} />
                          </span>
                        ) : null}
                      </td>
                      <td className="py-1.5 pr-4 tabular-nums">{nro(a.n_comentarios)}</td>
                      <td className="py-1.5 pr-4">
                        {a.confianza == null ? (
                          <span className="text-slate-500">—</span>
                        ) : (
                          <BarraConfianza valor={a.confianza} />
                        )}
                      </td>
                      <td className="py-1.5 pr-4">
                        {a.detalle_suprimido ? (
                          <span className="text-slate-500">Detalle oculto: pocos comentarios</span>
                        ) : a.indice == null && a.n_comentarios > 0 && filtro.vidaMedia > 0 ? (
                          <SinActividadReciente dias={filtro.vidaMedia} />
                        ) : (
                          <span
                            className="font-semibold tabular-nums"
                            style={{
                              color: colorIndice(a.indice),
                              opacity: a.evidencia_suficiente ? 1 : 0.45,
                            }}
                          >
                            {fmt(a.indice)}
                          </span>
                        )}
                      </td>
                      <td className="py-1.5 pr-4">
                        <PosturaCelda tramos={a.postura} />
                      </td>
                      <td className="py-1.5 pr-4 text-slate-400">
                        {a.tema_dominante ? a.tema_dominante.etiqueta : "—"}
                      </td>
                      <td className="py-1.5 pr-4 text-slate-400">
                        {a.detalle_suprimido
                          ? "Detalle oculto: pocos comentarios"
                          : a.emocion_dominante
                            ? labelEmocion(a.emocion_dominante.emocion, a.emocion_dominante.etiqueta)
                            : "—"}
                      </td>
                      <td className="py-1.5">
                        {a.detalle_suprimido ? (
                          <span className="text-sm text-slate-500">Detalle oculto: pocos comentarios</span>
                        ) : (
                          <Palabras palabras={a.palabras_top} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Lectura OPERATIVA de la confianza: una unidad con comentarios pero
                confianza baja no es una unidad "sin opinión" — suele ser una
                cuenta que falta capturar en la ingesta. */}
            {areasSinCobertura.length > 0 ? (
              <p className="mt-3 rounded-md border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-3 py-2 text-sm leading-5 text-ucn-tierra-clara">
                <strong>
                  Cobertura insuficiente en {areasSinCobertura.length}{" "}
                  {areasSinCobertura.length === 1 ? "área" : "áreas"}:
                </strong>{" "}
                {areasSinCobertura.slice(0, 6).map((a) => a.nombre).join(", ")}
                {areasSinCobertura.length > 6 ? ` y ${areasSinCobertura.length - 6} más` : ""}. Con
                menos de {min} comentarios o confianza bajo 30%, su índice es referencial. Suele
                indicar que falta ingestar la cuenta de esa unidad.
              </p>
            ) : null}
          </>
        ) : (
          <p className="py-6 text-center text-sm text-slate-500">
            Sin áreas para el filtro actual.
          </p>
        )}
      </div>

      {/* ───────────── ¿ES MÍO O ES DE TODOS? ───────────── */}
      {conc ? (
        <div className={CARD}>
          <TituloBloque titulo="¿Es de una unidad o de toda la universidad?" ignoraRecencia>
            Cada tema se compara por cuánto PESA dentro de cada unidad, no por cuántos
            comentarios junta: así una unidad que comenta mucho de todo no aparece como
            si el tema fuera suyo.
          </TituloBloque>
          <Concentracion data={conc} />
        </div>
      ) : null}
      </>
      )}

      {/* ───────────── POR TEMA ───────────── */}
      {sub !== "temas" ? null : (
      <div className={CARD}>
        <TituloBloque titulo="De qué se habla" vidaMedia={filtro.vidaMedia}>
          {orden === "peor"
            ? "Peor hablado primero en la tabla; el gráfico ordena por volumen."
            : "Más comentado primero."}{" "}
          Este desglose no se acota por el filtro de tema (mostraría una sola fila).
        </TituloBloque>

        {data.temas.length > 0 ? (
          <>
            {optTemas ? (
              <EChartsChart
                option={optTemas}
                height={Math.max(180, data.temas.filter((t) => !t.detalle_suprimido).length * 40)}
                ariaLabel="Sentimiento por tema"
              />
            ) : null}
            {data.temas.some((t) => t.detalle_suprimido) ? (
              <p className="mt-2 text-xs text-slate-500">
                Los temas con detalle oculto (pocos comentarios) no aparecen en el gráfico.
              </p>
            ) : null}
            <div className="mt-3 space-y-2">
              {data.temas.map((t: SintesisTema) => (
                <div key={t.tema} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-slate-100">{t.etiqueta}</span>
                        <span className="text-sm text-slate-400">
                          {nro(t.n_comentarios)} · {t.share_pct}% de la conversación
                        </span>
                        {!t.evidencia_suficiente ? (
                          <SinEvidencia n={t.n_comentarios} minimo={min} />
                        ) : null}
                      </div>
                      <div className="mt-1 text-sm text-slate-400">
                        {t.detalle_suprimido ? (
                          "Detalle oculto: pocos comentarios"
                        ) : t.emocion_dominante ? (
                          <>
                            Predomina{" "}
                            <strong className="text-slate-400">
                              {labelEmocion(
                                t.emocion_dominante.emocion,
                                t.emocion_dominante.etiqueta,
                              )}
                            </strong>{" "}
                            ({t.emocion_dominante.pct}%)
                          </>
                        ) : (
                          "Sin emoción registrada"
                        )}
                        {t.areas_top.length > 0 ? (
                          <> · sobre todo en {t.areas_top.map((a) => a.nombre).join(", ")}</>
                        ) : null}
                      </div>
                      {!t.detalle_suprimido && t.palabras_top.length > 0 ? (
                        <div className="mt-1.5">
                          <Palabras palabras={t.palabras_top} />
                        </div>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      {t.detalle_suprimido ? null : (
                        <span className="text-xs tabular-nums text-slate-500">
                          {t.n_pos}/{t.n_neu}/{t.n_neg}
                        </span>
                      )}
                      <Indice valor={t.indice} evidencia={t.evidencia_suficiente} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="py-6 text-center text-sm text-slate-500">
            Sin temas para el filtro actual.
          </p>
        )}
      </div>
      )}

      {/* VOLATILIDAD — va última y en esta pestaña, no en Simulación.
          Los dos bloques de arriba dicen CÓMO ESTÁ cada unidad; este dice CUÁNTO SE
          MUEVE, que es la otra mitad de "¿dónde está el problema?": una unidad con
          índice mediocre y estable pide una conversación distinta que una con buen
          promedio y vaivenes. Estaba montada en Simulación aunque su propio
          docstring decía que vivía acá. */}
      {sub !== "movimiento" ? null : <PercepcionVolatilidad />}
    </div>
  );
}

export default PercepcionComparar;
