"use client";

// Página de una tarea (T1 a T6) de la vista «Modelos». Primero lo que entiende cualquier lector (pregunta, semáforo, qué significa y
// el resultado en palabras); después el detalle por programa y facultad; y, cerrado por defecto, el «Detalle técnico» con la
// escalera de modelos, las diferencias pareadas, la calibración y el glosario de métricas.
// Todo agregado (conjunto de prueba, intervalos del 95 %): nunca una predicción sobre una persona.
import { useMemo, useState, type ReactNode } from "react";

import { neuralApi, type DetalleTarea, type TareaId, type VistaTarea } from "../lib/neural";
import { COLOR_FAMILIA, ETIQUETA_FAMILIA, opcionEscalera, textoIntervalo } from "../lib/neuralGraficosModelos";
import {
  ETIQUETA_PARTICION, METRICAS_PAGINA, modelosDeVista, opcionCalibracion,
} from "../lib/neuralGraficosTareas";
import {
  AYUDA_EVALUACION, ES_MODELO_EN_USO, FICHA_SIMPLE, GLOSARIO, etiquetaEvaluacion, frasesResultado, limpiarCodigos, textoCorte, textoSinCorte,
} from "../lib/neuralLenguaSimple";
import { PALETA } from "../lib/paleta";
import { EChartsChart } from "./EChartsChart";
import { SeccionGrupos } from "./NeuralModelosGrupos";
import { FilaComparacion } from "./NeuralModelosResultados";
import { Semaforo } from "./NeuralModelosSemaforo";
import {
  Aviso, CARD, Carga, FILA, Insignia, LeyendaPocosCasos, Metrica, MarcoGrafico, Notas, Segmentado, TD, TH, TablaScroll, Titulo, Vacio, entero, pct,
  useAncho, useCarga,
} from "./NeuralUI";

const clave = (v: Pick<VistaTarea, "variante" | "corte_k">) => `${v.variante}|${v.corte_k}`;

export function PaginaTarea({ tarea }: { tarea: TareaId }) {
  const estado = useCarga((s) => neuralApi.modelosTarea(tarea, s), [tarea]);
  return (
    <Carga estado={estado} filas={6} alto="h-8">
      {(d) => (d.vistas.length === 0
        ? <Vacio titulo="Sin resultados exportados">Esta tarea aún no tiene vistas exportadas. Ejecuta el exportador del resumen de modelos.</Vacio>
        : <Contenido key={tarea} tarea={tarea} d={d} />)}
    </Carga>
  );
}

function Contenido({ tarea, d }: { tarea: TareaId; d: DetalleTarea }) {
  const principal = d.vistas.find((v) => v.principal) ?? d.vistas[0];
  const [seleccion, setSeleccion] = useState(clave(principal));
  const [tecnicoAbierto, setTecnicoAbierto] = useState(false);
  const vista = d.vistas.find((v) => clave(v) === seleccion) ?? principal;
  const variantes = [...new Map(d.vistas.map((v) => [v.variante, v.etiqueta])).entries()];
  const cortes = d.vistas.filter((v) => v.variante === vista.variante).map((v) => v.corte_k);

  const elegirVariante = (variante: string) => {
    const mismo = d.vistas.find((v) => v.variante === variante && v.corte_k === vista.corte_k);
    setSeleccion(clave(mismo ?? d.vistas.find((v) => v.variante === variante) ?? principal));
  };
  const elegirCorte = (k: number) => setSeleccion(clave({ variante: vista.variante, corte_k: k }));
  const corte = textoCorte(tarea, vista.corte_k);
  const ayuda = AYUDA_EVALUACION[vista.variante];

  return (
    <div className="space-y-5">
      <Encabezado tarea={tarea} d={d} />
      {variantes.length > 1 || cortes.length > 1 ? (
        <div className="flex flex-wrap items-center gap-3" aria-label="Elegir la vista de la tarea">
          {variantes.length > 1 ? (
            <Segmentado etiqueta="Qué se evalúa" valor={vista.variante} onCambio={elegirVariante}
              opciones={variantes.map(([id, label]) => ({ id, label: etiquetaEvaluacion(id, label) }))} />
          ) : null}
          {cortes.length > 1 ? (
            <Segmentado etiqueta="Momento de la predicción" valor={String(vista.corte_k)} onCambio={(v) => elegirCorte(Number(v))}
              opciones={cortes.map((k) => ({ id: String(k), label: textoCorte(tarea, k)?.selector ?? `k = ${k}` }))} />
          ) : null}
        </div>
      ) : null}
      {(variantes.length > 1 && ayuda) || corte || textoSinCorte(tarea) ? (
        <div className="space-y-1 text-sm leading-6 text-[var(--portal-muted)]">
          {ES_MODELO_EN_USO(vista.variante) ? <p><Insignia tono="azul">Modelo en uso</Insignia> Es el modelo oficial para las cohortes recientes (desde 2024).</p> : null}
          {variantes.length > 1 && ayuda ? <p>{ayuda}</p> : null}
          {corte ? <p>{corte.frase}</p> : <p>{textoSinCorte(tarea)}</p>}
        </div>
      ) : null}
      <ResultadoEnPalabras tarea={tarea} d={d} vista={vista} />
      {vista.nota ? <Aviso titulo={vista.concluyente ? "Nota de esta vista" : "Resultado no concluyente"}>{limpiarCodigos(vista.nota)}</Aviso> : null}
      <div className={CARD}>
        {vista.variante === "sin_dudosos" ? (
          <>
            <Titulo>Por programa y por facultad</Titulo>
            <p className="text-sm leading-6 text-[var(--portal-muted)]">
              Esta evaluación solo compara el modelo elegido con la tasa histórica en las filas con registro completo; no se calculó por programa ni por facultad. Elige otra evaluación para verlos.
            </p>
          </>
        ) : <SeccionGrupos tarea={tarea} ficha={d.tarea} vista={vista} />}
      </div>
      <Advertencias d={d} />
      <details className="rounded-md border border-[var(--boveda-linea)] p-4" onToggle={(e) => setTecnicoAbierto((e.currentTarget as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer text-base font-semibold text-[var(--portal-fg)]">
          Detalle técnico
          <span className="ml-2 text-xs font-normal text-[var(--portal-muted)]">escalera de modelos, diferencias pareadas, calibración y glosario de métricas</span>
        </summary>
        {tecnicoAbierto ? (
          <div className="mt-4 space-y-5">
            <p className="text-sm leading-6 text-[var(--portal-muted)]">Para el equipo analítico. {d.tarea.poblacion}</p>
            <Poblacion tarea={tarea} d={d} vista={vista} />
            <Resultado tarea={tarea} d={d} vista={vista} />
            <Escalera tarea={tarea} d={d} vista={vista} />
            <Calibracion tarea={tarea} d={d} vista={vista} />
            <Glosario />
          </div>
        ) : null}
      </details>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Encabezado({ tarea, d }: { tarea: TareaId; d: DetalleTarea }) {
  const f = d.tarea;
  const s = FICHA_SIMPLE[tarea];
  return (
    <section className={`${CARD} space-y-3`} aria-label="Qué responde esta tarea">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold text-[var(--portal-fg)]">{f.nombre}</h2>
        <Semaforo tarea={tarea} estado={f.estado} />
      </div>
      <p className="text-base font-medium leading-6 text-[var(--portal-fg)]">{s.pregunta}</p>
      <p className="text-sm leading-6 text-[var(--portal-fg)]">{s.significado}</p>
      <p className="text-sm leading-6 text-[var(--portal-muted)]">Se mira a: {s.quienes}</p>
    </section>
  );
}

function ResultadoEnPalabras({ tarea, d, vista }: { tarea: TareaId; d: DetalleTarea; vista: VistaTarea }) {
  const f = useMemo(() => frasesResultado(tarea, vista, d.modelos, d.particiones), [tarea, vista, d.modelos, d.particiones]);
  if (!f.base && !f.titular) return null;
  return (
    <section className={`${CARD} space-y-2`} aria-label="El resultado en palabras">
      <Titulo sub="Medido con casos recientes que el modelo nunca vio al aprender. Describe al conjunto, no a una persona.">El resultado en palabras</Titulo>
      {f.titular ? <p className="text-base font-semibold leading-7 text-[var(--portal-fg)]">{f.titular}</p> : null}
      {f.complemento ? <p className="text-sm leading-6 text-[var(--portal-fg)]">{f.complemento}</p> : null}
      {f.base ? <p className="text-sm leading-6 text-[var(--portal-muted)]">{f.base}</p> : null}
      {f.nota ? <p className="text-xs leading-5 text-[var(--portal-muted)]">{f.nota}</p> : null}
    </section>
  );
}

function Glosario() {
  return (
    <section aria-label="Glosario de métricas" className="space-y-2">
      <Titulo sub="Qué quiere decir cada término técnico de esta sección.">Glosario</Titulo>
      <dl className="grid gap-x-6 gap-y-2 md:grid-cols-2">
        {GLOSARIO.map((g) => (
          <div key={g.termino}>
            <dt className="text-sm font-semibold text-[var(--portal-fg)]">{g.termino}</dt>
            <dd className="text-sm leading-6 text-[var(--portal-muted)]">{g.definicion}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Poblacion({ tarea, d, vista }: { tarea: TareaId; d: DetalleTarea; vista: VistaTarea }) {
  const filas = d.particiones.filter((p) => p.variante === vista.variante && p.corte_k === vista.corte_k);
  if (filas.length === 0) return null;
  const corte = textoCorte(tarea, vista.corte_k)?.selector ?? "";
  return (
    <section className={CARD} aria-label="Tamaño de cada partición">
      <Titulo sub={`Evento: ${d.tarea.evento}.${corte ? ` Momento: ${corte}.` : ""}${tarea === "t3" ? " Los eventos son egresos observados; hay además salidas y casos aún en seguimiento." : ""}`}>
        Cuántos casos hay en cada partición
      </Titulo>
      <TablaScroll etiqueta="Tamaño de las particiones y tasa del evento">
        <table className="w-full">
          <caption className="sr-only">Casos, eventos y tasa del evento por partición</caption>
          <thead><tr><th className={TH}>Partición</th><th className={`${TH} text-right`}>Casos</th><th className={`${TH} text-right`}>Eventos</th><th className={`${TH} text-right`}>{tarea === "t6" ? "Incidencia" : "Tasa"}</th></tr></thead>
          <tbody>
            {filas.map((p) => (
              <tr key={p.particion} className={FILA}>
                <td className={TD}>{ETIQUETA_PARTICION[p.particion] ?? p.particion}</td>
                <td className={`${TD} text-right tabular-nums`}>{entero(p.n)}</td>
                <td className={`${TD} text-right tabular-nums`}>{entero(p.eventos)}</td>
                <td className={`${TD} whitespace-nowrap text-right tabular-nums`}>
                  {pct(p.tasa)}
                  {p.tasa_inf != null && p.tasa_sup != null ? <span className="block text-xs text-[var(--portal-subtle)]">[{pct(p.tasa_inf)}; {pct(p.tasa_sup)}]</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaScroll>
    </section>
  );
}

function Resultado({ tarea, d, vista }: { tarea: TareaId; d: DetalleTarea; vista: VistaTarea }) {
  const modelos = useMemo(() => modelosDeVista(d.modelos, tarea, vista.variante, vista.corte_k), [d.modelos, tarea, vista]);
  const defs = METRICAS_PAGINA[tarea];
  const prin = defs.find((m) => m.id === vista.metrica_titular) ?? defs[0];
  const sec = defs.find((m) => m.id === vista.metrica_secundaria);
  const conservado = modelos.find((m) => m.modelo === vista.conservado_modelo);
  const referencia = modelos.find((m) => m.modelo === vista.referencia_modelo);
  const comp = d.comparaciones.find((c) => c.variante === vista.variante && c.corte_k === vista.corte_k && c.modelo_a === vista.conservado_modelo
    && c.modelo_b === vista.referencia_modelo && c.metrica === prin.id);
  const texto = (m: typeof conservado, id: string, dec: number) => {
    const x = m?.metricas[id];
    return x ? textoIntervalo(x.valor, x.ic_inf, x.ic_sup, dec) : "—";
  };
  return (
    <section className={`${CARD} space-y-4`} aria-label="Resultado principal">
      <Titulo sub="Conjunto de prueba (los casos más recientes, nunca usados para entrenar ni elegir). Entre corchetes, el intervalo del 95 %.">
        Resultado: modelo conservado frente a la referencia
      </Titulo>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Metrica etiqueta={`${prin.etiqueta} · modelo conservado`} valor={<span className="tabular-nums">{texto(conservado, prin.id, prin.decimales)}</span>}
          detalle={conservado?.nombre ?? "—"} />
        <Metrica etiqueta={`${prin.etiqueta} · referencia`} valor={<span className="tabular-nums">{texto(referencia, prin.id, prin.decimales)}</span>}
          detalle={referencia?.nombre ?? "—"} />
        {sec ? (
          <Metrica etiqueta={`${sec.etiqueta} · modelo conservado`} valor={<span className="tabular-nums">{texto(conservado, sec.id, sec.decimales)}</span>}
            detalle={`Referencia: ${texto(referencia, sec.id, sec.decimales)}`} />
        ) : null}
      </div>
      {comp ? (
        <p className="text-sm leading-6 text-[var(--portal-muted)]">
          Diferencia pareada ({prin.etiqueta}, conservado − referencia): <span className="tabular-nums text-[var(--portal-fg)]">{textoIntervalo(comp.delta, comp.ic_inf, comp.ic_sup, prin.decimales)}</span>.
        </p>
      ) : null}
      <div className="rounded-md border border-[var(--ucn-azul-borde)] bg-[var(--ucn-azul-suave)] px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">¿Las redes neuronales agregan señal?</p>
        <p className="mt-1 text-sm leading-6 text-[var(--portal-fg)]">{d.tarea.veredicto_redes}</p>
      </div>
    </section>
  );
}

function Escalera({ tarea, d, vista }: { tarea: TareaId; d: DetalleTarea; vista: VistaTarea }) {
  const defs = METRICAS_PAGINA[tarea];
  const [metricaId, setMetrica] = useState(vista.metrica_titular);
  const def = defs.find((m) => m.id === metricaId) ?? defs[0];
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const modelos = useMemo(() => modelosDeVista(d.modelos, tarea, vista.variante, vista.corte_k), [d.modelos, tarea, vista]);
  const resaltar = [vista.conservado_modelo, vista.referencia_modelo].filter((x): x is string => !!x);
  const grafico = useMemo(() => (modelos.length ? opcionEscalera(modelos, def, resaltar, ancho) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [modelos, def, ancho, vista.conservado_modelo, vista.referencia_modelo]);
  const nombres = new Map(modelos.map((m) => [m.modelo, m.nombre]));
  const comparaciones = d.comparaciones.filter((c) => c.variante === vista.variante && c.corte_k === vista.corte_k && c.metrica === def.id
    && nombres.has(c.modelo_a) && nombres.has(c.modelo_b));
  const familias = [...new Set(modelos.map((m) => m.familia))];
  if (!grafico) return null;
  return (
    <section className={`${CARD} space-y-3`} aria-label="Escalera de modelos">
      <Titulo sub="Cada escalón agrega información al anterior. El modelo conservado y la referencia van resaltados; los demás, atenuados.">Escalera de modelos (ablación)</Titulo>
      {defs.length > 1 ? <Segmentado etiqueta="Métrica" valor={def.id} onCambio={setMetrica} opciones={defs.map((m) => ({ id: m.id, label: m.etiqueta }))} /> : null}
      <p className="text-xs leading-5 text-[var(--portal-muted)]"><strong className="text-[var(--portal-fg)]">{def.etiqueta}</strong>: {def.descripcion} Cada punto trae su intervalo del 95 %.</p>
      <div ref={ref}>
        <MarcoGrafico descripcion={`Escalera de ablación: ${def.etiqueta} de cada modelo con su intervalo de confianza.`}>
          <EChartsChart option={grafico.option} height={grafico.alto} ariaLabel={`${def.etiqueta} de cada modelo con su intervalo del 95 %, por escalón de información.`} />
        </MarcoGrafico>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--portal-muted)]" aria-label="Leyenda de familias">
        {familias.map((f) => (
          <span key={f}><span aria-hidden="true" className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full align-baseline" style={{ background: COLOR_FAMILIA[f] }} />{ETIQUETA_FAMILIA[f] ?? f}</span>
        ))}
      </div>
      {comparaciones.length > 0 ? (
        <details className="rounded-md border border-[var(--boveda-linea)] px-3 py-2">
          <summary className="cursor-pointer text-sm font-semibold text-[var(--portal-fg)]">Diferencias pareadas ({def.etiqueta}, A − B): {comparaciones.length}</summary>
          <div className="mt-2">
            <TablaScroll etiqueta="Diferencias pareadas entre modelos">
              <table className="w-full">
                <caption className="sr-only">Diferencia de {def.etiqueta} entre pares de modelos, con su intervalo del 95 %</caption>
                <thead><tr><th className={TH}>A</th><th className={TH}>B</th><th className={TH}>Diferencia [IC 95 %]</th><th className={TH}>Lectura</th></tr></thead>
                <tbody>
                  {comparaciones.slice(0, 60).map((c) => (
                    <FilaComparacion key={`${c.modelo_a}-${c.modelo_b}`} c={c} a={nombres.get(c.modelo_a) ?? c.modelo_a} b={nombres.get(c.modelo_b) ?? c.modelo_b} dec={def.decimales} />
                  ))}
                </tbody>
              </table>
            </TablaScroll>
            <p className="mt-2 text-xs text-[var(--portal-muted)]">Una diferencia es real solo si su intervalo no incluye el cero. Para el error (Brier, ECE, IBS), menor es mejor.</p>
          </div>
        </details>
      ) : null}
    </section>
  );
}

function Calibracion({ tarea, d, vista }: { tarea: TareaId; d: DetalleTarea; vista: VistaTarea }) {
  const puntos = (m: string | null) => d.calibracion.filter((c) => c.variante === vista.variante && c.corte_k === vista.corte_k && c.modelo === m);
  const nombres = new Map(d.modelos.filter((m) => m.variante === vista.variante && m.corte_k === vista.corte_k).map((m) => [m.modelo, m.nombre]));
  const cons = puntos(vista.conservado_modelo);
  const ref = puntos(vista.referencia_modelo);
  const grafico = useMemo(() => (cons.length === 0 ? null : opcionCalibracion([
    { nombre: nombres.get(vista.conservado_modelo ?? "") ?? "Modelo conservado", color: PALETA.azul, puntos: cons },
    ...(ref.length ? [{ nombre: nombres.get(vista.referencia_modelo ?? "") ?? "Referencia", color: PALETA.neutro, puntos: ref }] : []),
  ], tarea === "t6" ? "Grupo de riesgo" : "Decil")),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [d.calibracion, vista.variante, vista.corte_k]);
  if (!grafico) {
    return (
      <section className={CARD} aria-label="Calibración">
        <Titulo>Calibración: predicho frente a observado</Titulo>
        <p className="text-sm text-[var(--portal-muted)]">Esta vista no tiene la calibración exportada.</p>
      </section>
    );
  }
  return (
    <section className={`${CARD} space-y-3`} aria-label="Calibración">
      <Titulo sub={`Los casos de prueba se ordenan por riesgo predicho y se agrupan; cada punto compara el riesgo medio predicho con la tasa que realmente ocurrió.${tarea === "t3" ? " Para T3 (Tiempo hasta egreso), a 12 semestres desde la admisión." : ""}`}>
        Calibración: predicho frente a observado
      </Titulo>
      {[...cons, ...ref].some((p) => p.pocos_casos) ? <LeyendaPocosCasos grafico unidad={tarea === "t2" ? "inscripciones" : "personas"} /> : null}
      <MarcoGrafico descripcion="Riesgo medio predicho frente a tasa observada por grupo de riesgo, con la diagonal de calibración perfecta.">
        <EChartsChart option={grafico.option} height={grafico.alto} ariaLabel="Riesgo medio predicho frente a tasa observada por grupo de riesgo." />
      </MarcoGrafico>
      <p className="text-xs leading-5 text-[var(--portal-muted)]">Sobre la diagonal el modelo subestima el riesgo; bajo ella lo sobreestima. Al pasar el cursor por un punto se ve de cuántos casos sale.</p>
    </section>
  );
}

const TITULO_TIPO: Record<string, string> = { dato: "Datos a tener en cuenta", pendiente: "Asuntos por resolver", limite: "Límites de la lectura" };

function Advertencias({ d }: { d: DetalleTarea }) {
  const tipos = ["dato", "pendiente", "limite"] as const;
  const bloques: ReactNode[] = [];
  for (const tipo of tipos) {
    const notas = d.notas.filter((n) => n.tipo === tipo);
    if (notas.length === 0) continue;
    bloques.push(
      <div key={tipo}>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">{TITULO_TIPO[tipo]}</p>
        <ul className="space-y-1.5">
          {notas.map((n) => (
            <li key={`${tipo}-${n.orden}`} className="flex gap-2 text-sm leading-6 text-[var(--portal-fg)]">
              <span aria-hidden="true" className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${tipo === "pendiente" ? "bg-[var(--portal-copper)]" : "bg-[var(--ucn-azul)]"}`} />
              <span>{limpiarCodigos(n.texto)}</span>
            </li>
          ))}
        </ul>
      </div>,
    );
  }
  if (bloques.length === 0) return null;
  return (
    <section className={`${CARD} space-y-4`} aria-label="Advertencias sobre los datos">
      <Titulo sub="Límites de los datos y asuntos aún por resolver.">Qué conviene saber antes de citar estos resultados</Titulo>
      {bloques}
      <Notas notas={["Estos resultados describen al conjunto, no a una persona. Las predicciones individuales no están habilitadas."]} titulo="Alcance" />
    </section>
  );
}
