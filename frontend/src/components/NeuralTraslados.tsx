"use client";

// Vista «Traslados»: paso de personas entre programas de pregrado (P61). Solo agregados; llegan todos los flujos y los
// grupos de menos de 10 personas traen la marca «pocos casos»: el gráfico muestra los más grandes y la tabla lista todos.
import { useEffect, useMemo, useRef, useState } from "react";

import {
  neuralApi, type BalancePrograma, type FlujoTraslado, type ParamsTraslados, type ResumenTraslados, type TipoTraslado,
  type TrasladosPrograma,
} from "../lib/neural";
import {
  COLOR_TIPO, ETIQUETA_TIPO, opcionBalance, opcionBalanceAnios, opcionSankey, opcionTipoPorAnio, recortar, valoresBalance,
} from "../lib/neuralGraficosTraslados";
import { limpiarCodigos } from "../lib/neuralLenguaSimple";
import { EChartsChart } from "./EChartsChart";
import { UCN, type SeleccionPoblacion } from "./NeuralSelectorPoblacion";
import {
  Aviso, BOTON, CARD, Carga, ETIQUETA_CAMPO, ErrorCarga, FILA, Insignia, LeyendaPocosCasos, MarcoGrafico, Metrica, Notas, PocosCasos,
  SELECT, Segmentado, TD, TH, TablaScroll, Titulo, Vacio, entero, useAncho, useCarga,
} from "./NeuralUI";

const TIPOS: readonly TipoTraslado[] = [
  "cambio_carrera", "traslado_otro", "traslado_sede", "eleccion_especialidad", "continuacion_estudios", "cambio_ciclo",
];

/** Cuántos flujos grafica el diagrama (los más grandes); la tabla de abajo lista todos. */
const FLUJOS_GRAFICO = [15, 30, 60] as const;
const PASO_FILAS = 25;

/** Cifra con la marca «pocos casos» cuando el grupo tiene menos de 10 personas. */
function Celda({ v, pocos = false }: { v: number; pocos?: boolean }) {
  return <>{entero(v)}{pocos ? <> <PocosCasos /></> : null}</>;
}

function Neto({ v }: { v: number }) {
  const color = v > 0 ? "text-[var(--ucn-azul-claro)]" : v < 0 ? "text-ucn-tierra-clara" : "text-[var(--portal-muted)]";
  return <span className={`font-semibold ${color}`}>{v > 0 ? "+" : ""}{entero(v)}</span>;
}

function Punto({ tipo }: { tipo: TipoTraslado }) {
  return <span aria-hidden="true" className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm align-baseline" style={{ background: COLOR_TIPO[tipo] }} />;
}

// ---------------------------------------------------------------------------
// Vista principal
// ---------------------------------------------------------------------------
/**
 * El programa elegido en el módulo (la población compartida) abre aquí su detalle, arriba del resumen; «Ver detalle» en el balance
 * cambia ese programa para todas las pestañas. Se escribe como Toda la UCN con el programa: cada pestaña lo ubica en su facultad.
 */
// Build-time switch (see docs/github-pages.md); literal on purpose so the bundler folds it.
const MODO_PAGES = process.env.NEXT_PUBLIC_MODO === "pages";

/** Pages: only these periods are published (no free ranges). The id is how many years back from the last one. */
type Periodo = "todos" | "10" | "5";
const PERIODOS: readonly { id: Periodo; label: string }[] = [
  { id: "todos", label: "Todos los años" },
  { id: "10", label: "Últimos 10" },
  { id: "5", label: "Últimos 5" },
];

export function NeuralTraslados({ seleccion, onSeleccion }: {
  seleccion: SeleccionPoblacion;
  onSeleccion: (s: SeleccionPoblacion) => void;
}) {
  const [desde, setDesde] = useState<number | null>(null);
  const [hasta, setHasta] = useState<number | null>(null);
  const [periodo, setPeriodo] = useState<Periodo>("todos");
  // Last available year reported by the server; remembered so «Últimos N» does not depend on the current filter.
  const [ultimoAnio, setUltimoAnio] = useState<number | null>(null);
  const [tipo, setTipo] = useState<TipoTraslado | "">("");
  const [soloAbandono, setSoloAbandono] = useState(false);
  const [sinEleccion, setSinEleccion] = useState(false);
  const elegido = seleccion.programa;
  // Al elegir desde la tabla del balance (al final de la página), se lleva la vista hasta el detalle, que queda arriba.
  const irAlDetalle = useRef(false);
  const detalleRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!irAlDetalle.current || elegido === null) return;
    irAlDetalle.current = false;
    detalleRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    detalleRef.current?.focus({ preventScroll: true });
  }, [elegido]);
  const elegir = (cod: string | null, nombre: string | null = null) => {
    if (cod === null) { onSeleccion({ ...seleccion, programa: null, nombrePrograma: null }); return; }
    irAlDetalle.current = true;
    onSeleccion({ facultad: UCN, programa: cod, nombrePrograma: nombre });
  };
  const soloFacultad = seleccion.programa === null && seleccion.facultad !== UCN;

  // Pages: the period replaces both selects and only sets `anio_desde` (`anio_hasta` is never sent).
  const desdeEf = MODO_PAGES
    ? (periodo === "todos" || ultimoAnio === null ? null : ultimoAnio - (periodo === "10" ? 9 : 4))
    : desde;
  const hastaEf = MODO_PAGES ? null : hasta;
  const params = useMemo<ParamsTraslados>(
    () => ({ anioDesde: desdeEf, anioHasta: hastaEf, tipo: tipo || null, soloAbandono }),
    [desdeEf, hastaEf, tipo, soloAbandono],
  );
  const estado = useCarga((s) => neuralApi.trasladosResumen(params, s), [desdeEf, hastaEf, tipo, soloAbandono]);
  // Los filtros y el resultado anterior siguen visibles mientras llega la nueva consulta (sin parpadeo ni pérdida de foco).
  const [previo, setPrevio] = useState<ResumenTraslados | null>(null);
  useEffect(() => {
    if (estado.fase === "ok") {
      setPrevio(estado.datos);
      if (MODO_PAGES) setUltimoAnio((u) => u ?? estado.datos.anios_disponibles.hasta);
    }
  }, [estado]);
  const d = estado.fase === "ok" ? estado.datos : previo;

  return (
    <div className="space-y-5">
      <Aviso titulo="Qué es un traslado">
        Es el paso de una persona de un programa de pregrado a otro. Los cambios de carrera y de sede cuentan como abandono del
        programa de origen; la elección de especialidad desde un plan común, no. Se muestran solo agregados y todos los grupos: los de menos de 10 personas llevan la marca «pocos casos».
      </Aviso>
      {d == null ? (
        <Carga estado={estado} filas={5} alto="h-8">{() => null}</Carga>
      ) : (
        <div className={`space-y-5 transition-opacity ${estado.fase === "cargando" ? "opacity-60" : ""}`} aria-busy={estado.fase === "cargando"}>
          <Filtros d={d} desde={desde} hasta={hasta} tipo={tipo} soloAbandono={soloAbandono}
            onDesde={setDesde} onHasta={setHasta} onTipo={setTipo} onSoloAbandono={setSoloAbandono}
            periodo={periodo} onPeriodo={setPeriodo} />
          {estado.fase === "error" ? <ErrorCarga mensaje={estado.mensaje} status={estado.status} onReintentar={estado.reintentar} /> : null}
          {soloFacultad ? (
            <p className="max-w-3xl text-xs leading-5 text-[var(--portal-muted)]">
              Los traslados se ven por programa, no por facultad: el resumen es de toda la UCN. Elige un programa en el balance de abajo, o en
              otra pestaña, para ver los suyos.
            </p>
          ) : null}
          {elegido ? (
            <section ref={detalleRef} tabIndex={-1} className={`${CARD} scroll-mt-24 focus:outline-none`} aria-label="Detalle del programa elegido">
              <p className="mb-3 text-xs leading-5 text-[var(--portal-muted)]">
                Programa elegido en el módulo; se mantiene en las demás pestañas. El resumen de abajo es de toda la UCN.
              </p>
              <DetallePrograma key={elegido} cod={elegido} params={params} onCerrar={() => elegir(null)} />
            </section>
          ) : null}
          <Indicadores d={d} />
          <Tipos d={d} />
          <Flujos d={d} />
          <PorAnio d={d} />
          <Balance d={d} sinEleccion={sinEleccion} onModo={setSinEleccion} elegido={elegido} onElegir={elegir} />
          <Notas notas={d.notas} titulo="Cómo se cuenta cada traslado" />
        </div>
      )}
    </div>
  );
}

function Filtros({
  d, desde, hasta, tipo, soloAbandono, onDesde, onHasta, onTipo, onSoloAbandono, periodo, onPeriodo,
}: {
  d: ResumenTraslados; desde: number | null; hasta: number | null; tipo: TipoTraslado | ""; soloAbandono: boolean;
  onDesde: (v: number | null) => void; onHasta: (v: number | null) => void; onTipo: (v: TipoTraslado | "") => void;
  onSoloAbandono: (v: boolean) => void;
  periodo: Periodo; onPeriodo: (v: Periodo) => void;
}) {
  const { desde: min, hasta: max } = d.anios_disponibles;
  const anios = min != null && max != null ? Array.from({ length: max - min + 1 }, (_, i) => min + i) : [];
  const num = (v: string) => (v === "" ? null : Number(v));
  return (
    <section className={CARD} aria-label="Filtros de traslados">
      <div className={MODO_PAGES
        ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-[auto_minmax(0,16rem)_auto] lg:items-end"
        : "grid gap-3 sm:grid-cols-2 lg:grid-cols-[10rem_10rem_minmax(0,16rem)_auto] lg:items-end"}>
        {MODO_PAGES ? (
          <div>
            <span className={ETIQUETA_CAMPO}>Período</span>
            <Segmentado
              etiqueta="Período"
              valor={max == null ? "todos" : periodo}
              onCambio={onPeriodo}
              opciones={max == null ? PERIODOS.slice(0, 1) : PERIODOS}
            />
          </div>
        ) : (
          <>
            <div>
              <label htmlFor="tras-desde" className={ETIQUETA_CAMPO}>Año desde</label>
              <select id="tras-desde" className={SELECT} value={desde ?? ""} onChange={(e) => onDesde(num(e.target.value))}>
                <option value="">{min ?? "—"} (primero)</option>
                {anios.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="tras-hasta" className={ETIQUETA_CAMPO}>Año hasta</label>
              <select id="tras-hasta" className={SELECT} value={hasta ?? ""} onChange={(e) => onHasta(num(e.target.value))}>
                <option value="">{max ?? "—"} (último)</option>
                {anios.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </>
        )}
        <div>
          <label htmlFor="tras-tipo" className={ETIQUETA_CAMPO}>Tipo de traslado</label>
          <select id="tras-tipo" className={SELECT} value={tipo} onChange={(e) => onTipo(e.target.value as TipoTraslado | "")}>
            <option value="">Todos los tipos</option>
            {TIPOS.map((t) => <option key={t} value={t}>{ETIQUETA_TIPO[t]}</option>)}
          </select>
        </div>
        <label className="flex h-9 cursor-pointer items-center gap-2 text-sm text-[var(--portal-fg)]">
          <input type="checkbox" checked={soloAbandono} onChange={(e) => onSoloAbandono(e.target.checked)} className="h-4 w-4 accent-[var(--ucn-azul)]" />
          Solo los que cuentan como abandono
        </label>
      </div>
      <p className="mt-2 text-xs text-[var(--portal-muted)]">
        {MODO_PAGES
          ? `El año es el de ingreso al programa de destino. Años mostrados: ${periodo === "todos" || max == null ? min ?? "—" : max - (periodo === "10" ? 9 : 4)} a ${max ?? "—"}.`
          : `El año es el de ingreso al programa de destino. Rango disponible: ${min ?? "—"} a ${max ?? "—"}.`}
      </p>
    </section>
  );
}

function Indicadores({ d }: { d: ResumenTraslados }) {
  const abandono = d.por_tipo.filter((t) => t.cuenta_abandono);
  const abandonoTotal = abandono.reduce((s, t) => s + t.n, 0);
  const eleccion = d.por_tipo.find((t) => t.tipo === "eleccion_especialidad")?.n ?? 0;
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Metrica etiqueta="Traslados" valor={entero(d.total)} detalle="entre programas de pregrado" />
      <Metrica etiqueta="Cuentan como abandono" valor={entero(abandonoTotal)} detalle="cambio de carrera, de sede y otros" />
      <Metrica etiqueta="Elección de especialidad" valor={entero(eleccion)} detalle="no es pérdida del origen" />
      <Metrica etiqueta="Excluidos por ambiguos" valor={entero(d.ambiguos_excluidos)} detalle="empieza otro programa en la misma ventana: no se sabe cuál es el destino" />
    </dl>
  );
}

function Tipos({ d }: { d: ResumenTraslados }) {
  return (
    <section className={CARD} aria-label="Cómo se cuenta cada tipo">
      <Titulo sub="Cada traslado se clasifica en un solo tipo, en este orden de prioridad.">Cómo se cuenta cada tipo</Titulo>
      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {d.por_tipo.map((t) => (
          <li key={t.tipo} className="rounded-md border border-[var(--boveda-linea)] p-3" style={{ borderLeft: `3px solid ${COLOR_TIPO[t.tipo]}` }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--portal-fg)]">{t.etiqueta}</p>
              <p className={`text-lg font-semibold text-[var(--portal-fg)] ${t.pocos_casos ? "opacity-60" : ""}`}><Celda v={t.n} pocos={t.pocos_casos} /></p>
            </div>
            <div className="mt-1"><Insignia tono={t.cuenta_abandono ? "aviso" : "azul"}>{t.cuenta_abandono ? "Cuenta como abandono" : "No es pérdida"}</Insignia></div>
            <p className="mt-2 text-xs leading-5 text-[var(--portal-muted)]">{limpiarCodigos(t.descripcion)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Flujos({ d }: { d: ResumenTraslados }) {
  const [refSankey, anchoSankey] = useAncho<HTMLDivElement>();
  const [tope, setTope] = useState<(typeof FLUJOS_GRAFICO)[number]>(15);
  const graficados = useMemo(() => d.flujos.slice(0, tope), [d.flujos, tope]);
  const sankey = useMemo(() => opcionSankey(graficados, anchoSankey), [graficados, anchoSankey]);
  const enGrafico = graficados.reduce((s, f) => s + f.n, 0);
  return (
    <section className={CARD} aria-label="Flujos entre programas">
      <Titulo sub="El diagrama dibuja los flujos más grandes; la tabla de abajo los lista todos. El color indica el tipo principal del flujo.">
        Flujos entre programas
      </Titulo>
      {d.flujos.length === 0 ? (
        <Vacio titulo="Sin flujos">Con estos filtros no hay traslados entre programas.</Vacio>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <Segmentado
              etiqueta="Cuántos flujos graficar"
              valor={String(tope)}
              onCambio={(v) => setTope(Number(v) as (typeof FLUJOS_GRAFICO)[number])}
              opciones={FLUJOS_GRAFICO.map((n) => ({ id: String(n), label: `Los ${n} mayores` }))}
            />
            <span className="text-xs text-[var(--portal-muted)]">
              Se grafican {entero(graficados.length)} de {entero(d.flujos.length)} flujos ({entero(enGrafico)} de {entero(d.total)} personas).
            </span>
          </div>
          <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--portal-muted)]" aria-label="Leyenda de tipos">
            {TIPOS.filter((t) => graficados.some((f) => f.tipo_principal === t)).map((t) => (
              <span key={t}><Punto tipo={t} />{ETIQUETA_TIPO[t]}</span>
            ))}
          </div>
          <div ref={refSankey}>
            <MarcoGrafico descripcion="Diagrama de flujo de personas desde el programa de origen (izquierda) al de destino (derecha).">
              <EChartsChart option={sankey.option} height={sankey.alto} ariaLabel="Diagrama de flujo de traslados entre programas." />
            </MarcoGrafico>
          </div>
          <div className="mt-4"><TablaFlujos flujos={d.flujos} /></div>
        </>
      )}
    </section>
  );
}

function TablaFlujos({ flujos }: { flujos: readonly FlujoTraslado[] }) {
  const [visibles, setVisibles] = useState(PASO_FILAS);
  const nombre = (n: string | null, cod: string) => n ?? cod;
  return (
    <div className="space-y-2">
      <TablaScroll etiqueta="Todos los flujos entre programas">
        <table className="w-full">
          <caption className="sr-only">Cada flujo de personas entre un programa de origen y uno de destino, de mayor a menor</caption>
          <thead>
            <tr>
              <th className={TH}>Origen</th><th className={TH}>Destino</th><th className={TH}>Tipo principal</th>
              <th className={`${TH} text-right`}>Personas</th>
            </tr>
          </thead>
          <tbody>
            {flujos.slice(0, visibles).map((f) => (
              <tr key={`${f.cod_origen}>${f.cod_destino}`} className={FILA}>
                <td className={TD}>{nombre(f.nombre_origen, f.cod_origen)}</td>
                <td className={TD}>{nombre(f.nombre_destino, f.cod_destino)}</td>
                <td className={TD}>{f.tipo_principal ? <><Punto tipo={f.tipo_principal} />{ETIQUETA_TIPO[f.tipo_principal]}</> : "—"}</td>
                <td className={`${TD} text-right ${f.pocos_casos ? "opacity-60" : ""}`}><Celda v={f.n} pocos={f.pocos_casos} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaScroll>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-[var(--portal-muted)]">Mostrando {entero(Math.min(visibles, flujos.length))} de {entero(flujos.length)} flujos.</span>
        {visibles < flujos.length ? (
          <>
            <button type="button" className={BOTON} onClick={() => setVisibles((v) => v + 50)}>Mostrar 50 más</button>
            <button type="button" className={BOTON} onClick={() => setVisibles(flujos.length)}>Mostrar todos</button>
          </>
        ) : null}
      </div>
      <LeyendaPocosCasos unidad="traslados" />
    </div>
  );
}

function PorAnio({ d }: { d: ResumenTraslados }) {
  const option = useMemo(() => opcionTipoPorAnio(d.por_anio), [d.por_anio]);
  if (d.por_anio.length === 0) return null;
  return (
    <section className={CARD} aria-label="Traslados por año">
      <Titulo sub="Año de ingreso al programa de destino. Los tramos más claros son grupos de menos de 10 traslados.">Traslados por año y tipo</Titulo>
      <MarcoGrafico descripcion="Barras apiladas por año y tipo de traslado.">
        <EChartsChart option={option} height={300} ariaLabel="Traslados por año, apilados por tipo." />
      </MarcoGrafico>
      {d.por_anio.some((f) => f.pocos_casos) ? <div className="mt-2"><LeyendaPocosCasos grafico unidad="traslados" /></div> : null}
    </section>
  );
}

function Balance({
  d, sinEleccion, onModo, elegido, onElegir,
}: {
  d: ResumenTraslados; sinEleccion: boolean; onModo: (v: boolean) => void; elegido: string | null;
  onElegir: (cod: string | null, nombre?: string | null) => void;
}) {
  const grafico = useMemo(() => opcionBalance(d.balance, sinEleccion, 15), [d.balance, sinEleccion]);
  const filas = useMemo(
    () => d.balance
      .map((b) => ({ b, v: valoresBalance(b, sinEleccion) }))
      .filter(({ v }) => v.ganados + v.perdidos > 0)
      .sort((a, c) => (c.v.ganados + c.v.perdidos) - (a.v.ganados + a.v.perdidos)),
    [d.balance, sinEleccion],
  );
  return (
    <section className={CARD} aria-label="Balance por programa">
      <Titulo sub="Ganados: personas que llegan desde otro programa. Perdidos: personas que se van a otro programa. Neto = ganados − perdidos.">
        Balance por programa
      </Titulo>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Segmentado
          etiqueta="Elección de especialidad en el balance"
          valor={sinEleccion ? "sin" : "con"}
          onCambio={(v) => onModo(v === "sin")}
          opciones={[{ id: "con", label: "Con elección de especialidad" }, { id: "sin", label: "Sin elección de especialidad" }]}
        />
        <span className="text-xs text-[var(--portal-muted)]">
          {sinEleccion ? "Quita el paso de un plan común a su especialidad, que no es una pérdida real." : "Incluye todos los traslados."}
        </span>
      </div>
      {filas.length === 0 ? (
        <Vacio titulo="Sin movimiento">Con estos filtros ningún programa gana ni pierde personas.</Vacio>
      ) : (
        <>
          <MarcoGrafico descripcion="Barras de personas ganadas y perdidas por programa, con el neto como marca.">
            <EChartsChart option={grafico.option} height={grafico.alto} ariaLabel="Ganados y perdidos por programa; el rombo es el neto." />
          </MarcoGrafico>
          <p className="mt-1 text-xs text-[var(--portal-muted)]">Se grafican los {grafico.n} programas con más movimiento; la tabla los lista todos ({entero(filas.length)}).</p>
          <div className="mt-4">
            <TablaBalance filas={filas} elegido={elegido} onElegir={onElegir} />
          </div>
        </>
      )}
    </section>
  );
}

function TablaBalance({
  filas, elegido, onElegir,
}: {
  filas: { b: BalancePrograma; v: { ganados: number; perdidos: number; neto: number } }[];
  elegido: string | null; onElegir: (cod: string | null, nombre?: string | null) => void;
}) {
  const [visibles, setVisibles] = useState(PASO_FILAS);
  return (
    <div className="space-y-2">
    <TablaScroll etiqueta="Balance por programa">
      <table className="w-full">
        <caption className="sr-only">Ganados, perdidos y neto por programa</caption>
        <thead>
          <tr>
            <th className={TH}>Programa</th><th className={`${TH} text-right`}>Ganados</th><th className={`${TH} text-right`}>Perdidos</th>
            <th className={`${TH} text-right`}>Neto</th><th className={TH}><span className="sr-only">Acción</span></th>
          </tr>
        </thead>
        <tbody>
          {filas.slice(0, visibles).map(({ b, v }) => (
            <tr key={b.cod_programa} className={`${FILA} ${elegido === b.cod_programa ? "bg-[var(--ucn-azul-suave)]" : ""}`}>
              <td className={TD}>
                <span className="font-medium">{b.nombre_programa ?? b.cod_programa}</span>
                <span className="ml-2 text-xs text-[var(--portal-subtle)]">{b.cod_programa}</span>
              </td>
              <td className={`${TD} text-right`}><Celda v={v.ganados} /></td>
              <td className={`${TD} text-right`}><Celda v={v.perdidos} /></td>
              <td className={`${TD} text-right`}><Neto v={v.neto} /></td>
              <td className={`${TD} text-right`}>
                <button
                  type="button"
                  onClick={() => (elegido === b.cod_programa ? onElegir(null) : onElegir(b.cod_programa, b.nombre_programa))}
                  aria-pressed={elegido === b.cod_programa}
                  className="rounded border border-[var(--boveda-linea-fuerte)] px-3 py-1 text-xs font-semibold text-[var(--portal-fg)] hover:bg-white/[0.06]"
                >
                  {elegido === b.cod_programa ? "Ocultar" : "Ver detalle"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TablaScroll>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-[var(--portal-muted)]">Mostrando {entero(Math.min(visibles, filas.length))} de {entero(filas.length)} programas.</span>
        {visibles < filas.length ? (
          <>
            <button type="button" className={BOTON} onClick={() => setVisibles((v) => v + 50)}>Mostrar 50 más</button>
            <button type="button" className={BOTON} onClick={() => setVisibles(filas.length)}>Mostrar todos</button>
          </>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detalle de un programa (también se usa dentro de la vista de cohortes)
// ---------------------------------------------------------------------------
export function DetallePrograma({
  cod, params, onCerrar, compacto = false,
}: {
  cod: string; params: ParamsTraslados; onCerrar?: () => void; compacto?: boolean;
}) {
  const estado = useCarga((s) => neuralApi.trasladosPrograma(cod, params, s), [cod, params.anioDesde, params.anioHasta, params.tipo, params.soloAbandono]);
  return (
    <Carga estado={estado} filas={4}>
      {(d) => <ContenidoPrograma d={d} onCerrar={onCerrar} compacto={compacto} />}
    </Carga>
  );
}

function ContenidoPrograma({ d, onCerrar, compacto }: { d: TrasladosPrograma; onCerrar?: () => void; compacto: boolean }) {
  const b = d.balance;
  const anios = useMemo(() => opcionBalanceAnios(d.por_anio), [d.por_anio]);
  const hayAnios = d.por_anio.length > 0;
  const hayMovimiento = b.ganados_total > 0 || b.perdidos_total > 0;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <Titulo sub={`Programa ${d.cod_programa}`}>Traslados de {d.nombre_programa ?? d.cod_programa}</Titulo>
        {onCerrar ? (
          <button type="button" onClick={onCerrar} className="rounded border border-[var(--boveda-linea-fuerte)] px-3 py-1 text-xs font-semibold text-[var(--portal-fg)] hover:bg-white/[0.06]">
            Cerrar
          </button>
        ) : null}
      </div>
      {!hayMovimiento ? (
        <Vacio titulo="Sin movimiento">Con estos filtros el programa no gana ni pierde personas.</Vacio>
      ) : null}
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metrica etiqueta="Ganados" valor={<Celda v={b.ganados_total} />} detalle={<>sin elección: <Celda v={b.ganados_sin_eleccion} /></>} />
        <Metrica etiqueta="Perdidos" valor={<Celda v={b.perdidos_total} />} detalle={<>sin elección: <Celda v={b.perdidos_sin_eleccion} /></>} />
        <Metrica etiqueta="Neto" valor={<Neto v={b.neto_total} />} detalle="con elección de especialidad" />
        <Metrica etiqueta="Neto sin elección" valor={<Neto v={b.neto_sin_eleccion} />} detalle="sin el paso plan común → especialidad" />
      </dl>
      <div className="grid gap-4 lg:grid-cols-2">
        <TiposLista titulo="Llegan por" filas={d.entradas_por_tipo} />
        <TiposLista titulo="Se van por" filas={d.salidas_por_tipo} />
      </div>
      {!compacto ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Contrapartes titulo="Orígenes" filas={d.origenes} vacio="Ninguna persona llegó desde otro programa." />
          <Contrapartes titulo="Destinos" filas={d.destinos} vacio="Ninguna persona se fue a otro programa." />
        </div>
      ) : null}
      {hayAnios ? (
        <MarcoGrafico descripcion="Ganados, perdidos y neto por año.">
          <EChartsChart option={anios} height={260} ariaLabel="Ganados, perdidos y neto por año." />
        </MarcoGrafico>
      ) : null}
    </div>
  );
}

function TiposLista({ titulo, filas }: { titulo: string; filas: { tipo: TipoTraslado; etiqueta: string; n: number; pocos_casos: boolean }[] }) {
  return (
    <div className="rounded-md border border-[var(--boveda-linea)] p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{titulo}</p>
      <ul className="space-y-1 text-sm">
        {filas.map((f) => (
          <li key={f.tipo} className="flex items-center justify-between gap-3">
            <span className="min-w-0 truncate"><Punto tipo={f.tipo} />{f.etiqueta}</span>
            <span className={`shrink-0 font-medium ${f.pocos_casos ? "opacity-60" : ""}`}><Celda v={f.n} pocos={f.pocos_casos} /></span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Contrapartes({ titulo, filas, vacio }: { titulo: string; filas: { cod_programa: string; nombre_programa: string | null; n: number; pocos_casos: boolean }[]; vacio: string }) {
  const [todas, setTodas] = useState(false);
  const mostradas = todas ? filas : filas.slice(0, 10);
  return (
    <div className="rounded-md border border-[var(--boveda-linea)] p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{titulo} ({entero(filas.length)})</p>
      {filas.length === 0 ? (
        <p className="text-xs text-[var(--portal-muted)]">{vacio}</p>
      ) : (
        <>
          <ul className="space-y-1 text-sm">
            {mostradas.map((f) => (
              <li key={f.cod_programa} className="flex items-center justify-between gap-3">
                <span className="min-w-0 truncate" title={f.nombre_programa ?? f.cod_programa}>{recortar(f.nombre_programa ?? f.cod_programa, 44)}</span>
                <span className={`shrink-0 font-medium ${f.pocos_casos ? "opacity-60" : ""}`}><Celda v={f.n} pocos={f.pocos_casos} /></span>
              </li>
            ))}
          </ul>
          {filas.length > 10 ? (
            <button type="button" className="mt-2 text-xs font-semibold text-[var(--ucn-azul-claro)] underline-offset-4 hover:underline" onClick={() => setTodas((v) => !v)}>
              {todas ? "Ver solo los 10 mayores" : `Ver los ${entero(filas.length)}`}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}

/** Sección para la vista de cohortes: balance de traslados del programa elegido, con enlace a la vista completa. */
export function TrasladosDelPrograma({ cod, onVerTodo }: { cod: string; onVerTodo?: () => void }) {
  const params: ParamsTraslados = useMemo(() => ({}), []);
  return (
    <section className={CARD} aria-label="Traslados del programa">
      <DetallePrograma cod={cod} params={params} compacto />
      {onVerTodo ? (
        <button type="button" onClick={onVerTodo} className="mt-3 text-sm font-semibold text-[var(--ucn-azul-claro)] underline-offset-4 hover:underline">
          Ver todos los traslados entre programas →
        </button>
      ) : null}
    </section>
  );
}
