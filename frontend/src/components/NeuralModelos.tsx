"use client";

// Vista «Modelos»: cómo funcionan las redes y qué tan bien funcionaron. Solo explicaciones de arquitectura y
// métricas agregadas de los benchmarks; las predicciones individuales no están habilitadas (revisión institucional).
import { useMemo, useState, type ReactNode } from "react";

import { neuralApi, type ParametroModelo, type ResumenModelos, type TareaId, type TareaModelo, type TarjetaTarea } from "../lib/neural";
import { textoCodigo, valorCodigo, valorParametro } from "../lib/neuralGraficosModelos";
import { NOMBRE_CORTO, SELECTOR_TAREA, TAREAS } from "../lib/neuralGraficosTareas";
import { FICHA_SIMPLE, PROPOSITO_MODELOS, etiquetaCorte, unaDeCada } from "../lib/neuralLenguaSimple";
import { DiagramaCatBoost, DiagramaGRU, DiagramaGraphSAGE, DiagramaMLP } from "./NeuralModelosDiagramas";
import { PaginaTarea } from "./NeuralModelosTarea";
import { Semaforo } from "./NeuralModelosSemaforo";
import { PanelResultados } from "./NeuralModelosResultados";
import {
  CARD, Carga, ETIQUETA_CAMPO, Pestanas, SELECT, Segmentado, Titulo, Vacio, entero, fechaCorta, useCarga,
  type PestanaDef,
} from "./NeuralUI";

type Sub = "panorama" | "tareas" | "gru" | "graphsage" | "mlp" | "catboost";
const SUBS: readonly PestanaDef<Sub>[] = [
  { id: "panorama", label: "Resumen" },
  { id: "tareas", label: "Resultados por tarea" },
  { id: "gru", label: "Cómo funciona: GRU (T1 Continuidad y T3 Tiempo hasta egreso)" },
  { id: "graphsage", label: "Cómo funciona: GraphSAGE (T2 Aprobación por ramo)" },
  { id: "mlp", label: "Cómo funciona: red de capas (T3 Tiempo hasta egreso)" },
  { id: "catboost", label: "Cómo funciona: CatBoost" },
];
const PREFIJO = "neural-modelos";

const VARIABLES_T1 = [
  "matriculado", "interrupción", "intentos evaluados", "aprobados", "reprobados", "convalidaciones", "créditos aprobados",
  "cursos de verano o invierno", "tasa de aprobación", "¿tiene tasa?", "promedio", "¿tiene promedio?", "créditos acumulados",
];
const VARIABLES_T3 = [
  "matriculado", "interrupción", "créditos aprobados", "créditos acumulados", "convalidaciones", "cursos de verano o invierno",
];

export function NeuralModelos({ onVerFacultades }: { onVerFacultades?: () => void } = {}) {
  const estado = useCarga((s) => neuralApi.modelosResumen(s), []);
  const [sub, setSub] = useState<Sub>("panorama");
  const [tarea, setTarea] = useState<TareaId>("t1");
  return (
    <div className="space-y-5">
      <Carga estado={estado} filas={5} alto="h-8">
        {(datos) =>
          !datos.disponible ? (
            <Vacio titulo="El resumen de resultados aún no se exportó">
              Para ver los resultados, el equipo debe ejecutar <code>python tools/exportar_resumen_modelos.py</code> en Redes. Los diagramas se verán igual cuando esté disponible.
            </Vacio>
          ) : (
            <Contenido datos={datos} sub={sub} onSub={setSub} tarea={tarea} onTarea={setTarea} onVerFacultades={onVerFacultades} />
          )
        }
      </Carga>
    </div>
  );
}

function Contenido({
  datos, sub, onSub, tarea, onTarea, onVerFacultades,
}: { datos: ResumenModelos; sub: Sub; onSub: (s: Sub) => void; tarea: TareaId; onTarea: (t: TareaId) => void; onVerFacultades?: () => void }) {
  return (
    <>
      <Pestanas pestanas={SUBS} activa={sub} onCambio={onSub} etiqueta="Modelos" prefijo={PREFIJO} compacta />
      <p className="text-sm leading-6 text-[var(--portal-muted)]">{PROPOSITO_MODELOS[sub]}</p>
      <div role="tabpanel" id={`${PREFIJO}-panel-${sub}`} aria-labelledby={`${PREFIJO}-tab-${sub}`} className="vista-entrar space-y-5">
        {sub === "panorama" ? <Panorama onSub={onSub} onTarea={onTarea} onVerFacultades={onVerFacultades} />
          : sub === "tareas" ? <PorTarea tarea={tarea} onTarea={onTarea} />
          : sub === "gru" ? <VistaGRU datos={datos} />
          : sub === "graphsage" ? <VistaGraphSAGE datos={datos} />
          : sub === "mlp" ? <VistaMLP datos={datos} />
          : <VistaCatBoost datos={datos} />}
      </div>
      <p className="text-xs text-[var(--portal-subtle)]">
        Resultados actualizados {datos.generado_en ? `el ${fechaCorta(datos.generado_en)}` : ""} a partir de las pruebas técnicas. {datos.notas.join(" ")}
      </p>
    </>
  );
}

// ---------------------------------------------------------------------------
// Piezas comunes
// ---------------------------------------------------------------------------
function Explicacion({ mira, predice, aprende }: { mira: ReactNode; predice: ReactNode; aprende: ReactNode }) {
  return (
    <dl className="grid gap-3 md:grid-cols-3">
      {[["Qué mira", mira], ["Qué predice", predice], ["Cómo aprende", aprende]].map(([titulo, texto]) => (
        <div key={titulo as string} className="rounded-md border border-[var(--boveda-linea)] p-3">
          <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">{titulo as string}</dt>
          <dd className="mt-1 text-sm leading-6 text-[var(--portal-fg)]">{texto as ReactNode}</dd>
        </div>
      ))}
    </dl>
  );
}

function Tamanos({ filas }: { filas: { etiqueta: string; valor: string; detalle?: string }[] }) {
  const validas = filas.filter((f) => f.valor !== "—");
  if (validas.length === 0) return null;
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Tamaños (tomados del código y de la configuración registrada)</p>
      <dl className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {validas.map((f) => (
          <div key={f.etiqueta} className="rounded-md border border-white/10 bg-white/[0.02] px-3 py-2">
            <dt className="text-xs text-[var(--portal-muted)]">{f.etiqueta}</dt>
            <dd className="text-base font-semibold text-[var(--portal-fg)]">{f.valor}</dd>
            {f.detalle ? <dd className="text-xs text-[var(--portal-subtle)]">{f.detalle}</dd> : null}
          </div>
        ))}
      </dl>
    </div>
  );
}

const ent = (v: number | null) => (v == null ? "—" : entero(Math.round(v)));

function Seccion({ children, etiqueta }: { children: ReactNode; etiqueta: string }) {
  return <section className={`${CARD} space-y-4`} aria-label={etiqueta}>{children}</section>;
}

// ---------------------------------------------------------------------------
// Resultados por tarea (T1 a T6)
// ---------------------------------------------------------------------------
function PorTarea({ tarea, onTarea }: { tarea: TareaId; onTarea: (t: TareaId) => void }) {
  return (
    <div className="space-y-4">
      <Segmentado etiqueta="Tarea" valor={tarea} onCambio={onTarea} opciones={TAREAS.map((t) => ({ id: t, label: SELECTOR_TAREA[t] }))} />
      <PaginaTarea key={tarea} tarea={tarea} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panorama: una tarjeta por tarea con su pregunta, el modelo conservado, la métrica principal y el veredicto sobre las redes
// ---------------------------------------------------------------------------
const ARQUITECTURA: Partial<Record<TareaId, { ver: Sub; texto: string }>> = {
  t1: { ver: "gru", texto: "Ver el diagrama de la GRU →" },
  t2: { ver: "graphsage", texto: "Ver el diagrama de GraphSAGE →" },
  t3: { ver: "mlp", texto: "Ver el diagrama de la red de capas →" },
};

function Panorama({ onSub, onTarea, onVerFacultades }: { onSub: (s: Sub) => void; onTarea: (t: TareaId) => void; onVerFacultades?: () => void }) {
  const estado = useCarga((s) => neuralApi.modelosTareas(s), []);
  return (
    <>
      <Seccion etiqueta="Qué se probó">
        <Titulo sub="Seis preguntas sobre la trayectoria de los estudiantes, cada una con su semáforo. Los resultados se miden con casos recientes que el modelo nunca vio al aprender.">
          Qué se probó y qué se encontró
        </Titulo>
        {onVerFacultades ? (
          <p className="-mt-1 mb-3 text-sm text-[var(--portal-muted)]">
            ¿Quieres ver cómo le fue a cada facultad?{" "}
            <button type="button" onClick={onVerFacultades} className="font-semibold text-[var(--ucn-azul-claro)] underline-offset-4 hover:underline">Ir a «Modelo por facultad» →</button>
          </p>
        ) : null}
        <Carga estado={estado} filas={4} alto="h-8">
          {(d) => (!d.disponible || d.tareas.length === 0
            ? <Vacio titulo="El resumen por tarea aún no se exportó">Para ver las seis tareas, el equipo debe ejecutar <code>python tools/exportar_resumen_modelos.py</code> en Redes.</Vacio>
            : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {d.tareas.map((t) => {
                  const arq = ARQUITECTURA[t.tarea];
                  return (
                    <TarjetaDeTarea key={t.tarea} t={t} onVer={() => { onTarea(t.tarea); onSub("tareas"); }}
                      onArquitectura={arq ? () => onSub(arq.ver) : undefined} textoArquitectura={arq?.texto} />
                  );
                })}
              </div>
            ))}
        </Carga>
      </Seccion>
      <Seccion etiqueta="Cómo leer los resultados">
        <Titulo>Cómo leer los resultados</Titulo>
        <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-[var(--portal-muted)]">
          <li>Los modelos se comparan de menos a más información: primero el perfil de ingreso, luego el desempeño académico hasta el momento de la estimación y, por último, la secuencia semestre a semestre o la relación entre cursos.</li>
          <li>Una mejora pequeña no es una mejora demostrada: solo se cuenta como real cuando se mantiene tras descontar la incertidumbre de la medición.</li>
          <li>Las redes neuronales aportan donde hay secuencia que aprender; en el resto, árboles y regresiones rinden igual con menos costo y más claridad.</li>
          <li>En las tareas donde lo que se busca es raro (T4 Cambio de programa, T5 Eliminación y T6 Postgrado UCN) los aciertos parecen bajos: se leen frente a una regla simple de referencia, no frente a la perfección.</li>
          <li>Estos modelos describen el comportamiento del conjunto, no a una persona. Su uso individual aún no está aprobado.</li>
        </ul>
      </Seccion>
    </>
  );
}

function TarjetaDeTarea({
  t, onVer, onArquitectura, textoArquitectura,
}: { t: TarjetaTarea; onVer: () => void; onArquitectura?: () => void; textoArquitectura?: string }) {
  const ficha = FICHA_SIMPLE[t.tarea];
  const tasa = unaDeCada(t.tasa_prueba);
  const corte = etiquetaCorte(t.tarea, t.corte_k);
  return (
    <article className="flex min-w-0 flex-col rounded-md border border-[var(--boveda-linea)] p-4" aria-label={NOMBRE_CORTO[t.tarea]}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-[var(--portal-fg)]">{NOMBRE_CORTO[t.tarea]}</h3>
        <Semaforo tarea={t.tarea} estado={t.estado} />
      </div>
      <p className="mt-2 text-sm font-medium leading-6 text-[var(--portal-fg)]">{ficha.pregunta}</p>
      <p className="mt-2 flex-1 text-sm leading-6 text-[var(--portal-muted)]">{ficha.significado}</p>
      <p className="mt-3 text-xs leading-5 text-[var(--portal-subtle)]">
        {tasa ? `${ficha.base(tasa)}.` : ""}{corte ? ` Vista principal: ${corte}.` : ""}{!t.concluyente ? " Resultado no concluyente." : ""}
      </p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        <button type="button" onClick={onVer} className="text-sm font-semibold text-[var(--ucn-azul-claro)] underline-offset-4 hover:underline">Ver la tarea →</button>
        {onArquitectura ? (
          <button type="button" onClick={onArquitectura} className="text-sm text-[var(--portal-muted)] underline-offset-4 hover:text-[var(--portal-fg)] hover:underline">{textoArquitectura}</button>
        ) : null}
      </div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// GRU
// ---------------------------------------------------------------------------
function VistaGRU({ datos }: { datos: ResumenModelos }) {
  const [tarea, setTarea] = useState<"t1" | "t3">("t1");
  const [k1, setK1] = useState(2);
  const [k3, setK3] = useState(2);
  const k = tarea === "t1" ? k1 : k3;
  const arq = datos.arquitectura;
  const modelo = tarea === "t1" ? "gru_seq" : "nn_gru";
  const p = useMemo(() => {
    if (tarea === "t1") {
      return {
        tarea, k, dSeq: valorParametro(arq, "t1", k, "gru_seq", "d_secuencia") ?? VARIABLES_T1.length,
        hidden: valorCodigo(arq, "gru_t1", "hidden") ?? 48, estatica: valorCodigo(arq, "gru_t1", "static_dim") ?? 32,
        cabeza: valorCodigo(arq, "gru_t1", "cabeza_oculta") ?? 64, variables: VARIABLES_T1,
      } as const;
    }
    const capas = (textoCodigo(arq, "nn_gru", "capas") ?? "128-64").split("-").map(Number);
    return {
      tarea, k, dSeq: VARIABLES_T3.length, hidden: valorCodigo(arq, "nn_gru", "gru_hidden") ?? 48, estatica: capas[0] ?? 128,
      cabeza: valorCodigo(arq, "nn_gru", "cabeza_oculta") ?? capas[capas.length - 1] ?? 64, variables: VARIABLES_T3,
    } as const;
  }, [arq, tarea, k]);
  return (
    <Seccion etiqueta="GRU">
      <Titulo sub="Una red que lee la historia académica semestre a semestre, en orden, y la resume en una memoria.">GRU desenrollada sobre los semestres</Titulo>
      <div className="flex flex-wrap items-center gap-3">
        <Segmentado etiqueta="Tarea" valor={tarea} onCambio={setTarea}
          opciones={[{ id: "t1", label: "T1 · Continuidad" }, { id: "t3", label: "T3 · Tiempo hasta egreso" }]} />
        <Segmentado etiqueta="Semestres antes del corte" valor={String(k)}
          onCambio={(v) => (tarea === "t1" ? setK1(Number(v)) : setK3(Number(v)))}
          opciones={(tarea === "t1" ? [1, 2] : [2, 4]).map((x) => ({ id: String(x), label: `k = ${x}` }))} />
      </div>
      <DiagramaGRU key={`${tarea}-${k}`} p={p} />
      <Explicacion
        mira={tarea === "t1"
          ? "Para cada semestre hasta el corte: si estuvo matriculada, interrupciones, intentos, aprobados y reprobados, convalidaciones, créditos, promedio. Además, el perfil previo al ingreso."
          : "Para cada semestre hasta el corte: matrícula, interrupción, créditos aprobados y acumulados, convalidaciones y cursos de verano. Además, el perfil de ingreso y los agregados al corte."}
        predice={tarea === "t1"
          ? "La probabilidad de que la persona ya no esté matriculada dos períodos regulares después del corte."
          : "Para cada semestre después del corte, el riesgo de egresar y el de salir del programa, que compiten entre sí; de ahí salen las curvas de probabilidad acumulada."}
        aprende="Ajusta sus pesos con casos de cohortes pasadas hasta que el error deja de bajar en una cohorte reservada, y se repite con varias semillas. Se evalúa en cohortes más recientes."
      />
      <Tamanos filas={[
        { etiqueta: "Memoria (h)", valor: ent(p.hidden), detalle: "números por semestre" },
        { etiqueta: "Vector por semestre", valor: ent(p.dSeq), detalle: "variables" },
        { etiqueta: "Rama del perfil", valor: ent(p.estatica) },
        { etiqueta: "Parámetros entrenables", valor: ent(valorParametro(arq, tarea, k, modelo, "n_parametros")) },
      ]} />
      <PanelResultados key={tarea} datos={datos} tarea={tarea} resaltar={[modelo]} corteInicial={tarea === "t1" ? 2 : 2} />
    </Seccion>
  );
}

// ---------------------------------------------------------------------------
// GraphSAGE
// ---------------------------------------------------------------------------
function VistaGraphSAGE({ datos }: { datos: ResumenModelos }) {
  const [cod, setCod] = useState<string | null>(null);
  const programas = useCarga((s) => neuralApi.programas(s), []);
  const malla = useCarga((s) => neuralApi.mallaEjemplo(cod, 4, s), [cod]);
  const arq = datos.arquitectura;
  const p = {
    dHid: valorCodigo(arq, "nn_gnn", "sage_d_hid") ?? 64, dOut: valorCodigo(arq, "nn_gnn", "sage_d_out") ?? 32,
    capas: valorCodigo(arq, "nn_gnn", "capas_sage") ?? 2, relaciones: valorCodigo(arq, "nn_gnn", "relaciones") ?? 3,
    cabeza: textoCodigo(arq, "nn_gnn", "capas") ?? "256-128",
  };
  return (
    <Seccion etiqueta="GraphSAGE">
      <Titulo sub="Una red que da a cada curso una representación que mezcla sus atributos con los de sus prerrequisitos y de los cursos que dependen de él.">
        GraphSAGE sobre el grafo curricular
      </Titulo>
      <div className="max-w-md">
        <label htmlFor="sage-prog" className={ETIQUETA_CAMPO}>Malla de ejemplo</label>
        <select id="sage-prog" className={SELECT} value={cod ?? ""} onChange={(e) => setCod(e.target.value || null)}>
          <option value="">Automática (la de más prerrequisitos)</option>
          {programas.fase === "ok" ? programas.datos.map((q) => (
            <option key={q.cod_programa} value={q.cod_programa}>{q.nombre_programa ?? q.cod_programa} ({q.cod_programa})</option>
          )) : null}
        </select>
        <p className="mt-1 text-xs text-[var(--portal-subtle)]">Solo se usan códigos, nombres y prerrequisitos de la malla oficial; ningún dato de personas.</p>
      </div>
      <Carga estado={malla} filas={1} alto="h-72">
        {(m) => <DiagramaGraphSAGE key={`${m.cod_programa}-${m.catalogo}`} malla={m} p={p} />}
      </Carga>
      <Explicacion
        mira="Los atributos de cada curso (créditos, semestre de la malla, departamento, tasa histórica de aprobación anterior a 2015) y quiénes son sus prerrequisitos y sus cursos posteriores. Después, datos del estudiante y de la carga del período."
        predice="Si el estudiante reprobará el curso en el período que viene (aprobación por intento)."
        aprende="Se entrena de punta a punta: las matrices de cada capa se ajustan junto con la red densa final, usando intentos de 2015 a 2020. También se probó entrenar el grafo solo para reconstruir prerrequisitos y usar esos embeddings en CatBoost."
      />
      <Tamanos filas={[
        { etiqueta: "Capas del grafo", valor: ent(p.capas), detalle: `${p.dHid} → ${p.dHid} → ${p.dOut}` },
        { etiqueta: "Relaciones", valor: ent(p.relaciones), detalle: "previos, posteriores, coinscripción" },
        { etiqueta: "Red densa final", valor: p.cabeza.replace("-", " → ") },
        { etiqueta: "Parámetros entrenables", valor: ent(valorParametro(arq, "t2", 0, "nn_gnn", "n_parametros")), detalle: `sin grafo: ${ent(valorParametro(arq, "t2", 0, "nn_mlp", "n_parametros"))}` },
        { etiqueta: "Cursos (nodos)", valor: ent(valorParametro(arq, "t2", 0, "grafo", "n_nodos")), detalle: "todos los programas" },
        { etiqueta: "Prerrequisitos (aristas)", valor: ent(valorParametro(arq, "t2", 0, "grafo", "n_aristas_prerrequisito")) },
        { etiqueta: "Pares de coinscripción", valor: ent(valorParametro(arq, "t2", 0, "grafo", "n_pares_coinscripcion")) },
      ]} />
      <PanelResultados datos={datos} tarea="t2" resaltar={["nn_gnn", "nn_gnn_prereq", "nn_mlp", "nn_ninguno", "cb_cemb", "cb_c"]} />
    </Seccion>
  );
}

// ---------------------------------------------------------------------------
// Red de capas (MLP) de riesgos discretos
// ---------------------------------------------------------------------------
function VistaMLP({ datos }: { datos: ResumenModelos }) {
  const arq = datos.arquitectura;
  const capas = (textoCodigo(arq, "nn_mlp_agg", "capas") ?? "128-64").split("-").map(Number);
  return (
    <Seccion etiqueta="Red de capas">
      <Titulo sub="La red más simple: capas de neuronas conectadas. Aquí se usa en T3 (Tiempo hasta egreso) sin secuencia, con los agregados al corte.">Red de capas (perceptrón multicapa)</Titulo>
      <DiagramaMLP p={{ entrada: "variables + embeddings", capas, salidaTexto: "U semestres × 3" }} />
      <Explicacion
        mira="El perfil de ingreso (puntajes, vía, colegio, programa) y, desde el segundo semestre, los agregados al corte: créditos, tasas, convalidaciones, interrupciones. Las variables categóricas se convierten en vectores aprendidos (embeddings)."
        predice="Para cada semestre posterior al corte, tres valores (sigue, egresa, sale) que forman los riesgos de un semestre; la verosimilitud considera la censura y que egreso y salida compiten."
        aprende="Minimiza la verosimilitud negativa de tiempo discreto con parada temprana en una cohorte reservada, varias semillas y GPU. No es DeepHit: no hay softmax conjunto sobre tiempo y causa."
      />
      <Tamanos filas={[
        { etiqueta: "Capas ocultas", valor: capas.join(" → ") },
        { etiqueta: "Salida", valor: "U × 3", detalle: "sigue, egresa, sale" },
        { etiqueta: "Parámetros (ingreso)", valor: ent(valorParametro(arq, "t3", 0, "nn_mlp_adm", "n_parametros")) },
        { etiqueta: "Parámetros (con agregados)", valor: ent(valorParametro(arq, "t3", 2, "nn_mlp_agg", "n_parametros")) },
      ]} />
      <PanelResultados datos={datos} tarea="t3" resaltar={["nn_mlp_adm", "nn_mlp_agg", "nn_gru"]} />
    </Seccion>
  );
}

// ---------------------------------------------------------------------------
// CatBoost
// ---------------------------------------------------------------------------
function VistaCatBoost({ datos }: { datos: ResumenModelos }) {
  const [tarea, setTarea] = useState<TareaModelo>("t1");
  const arq: readonly ParametroModelo[] = datos.arquitectura;
  const ref = { t1: ["t1", 1, "cb_acad"], t2: ["t2", 0, "cb_c"], t3: ["t3", 2, "dt_cb_agg"] } as const;
  const [t, k, m] = ref[tarea];
  const p = {
    iteraciones: valorParametro(arq, t, k, m, "iteraciones"), profundidad: valorCodigo(arq, "catboost", "profundidad"),
    tasa: valorCodigo(arq, "catboost", "tasa_aprendizaje"), variables: valorParametro(arq, t, k, m, "n_variables"),
  };
  return (
    <Seccion etiqueta="CatBoost">
      <Titulo sub="Un conjunto de árboles de decisión que se corrigen unos a otros. Es el modelo de comparación fuerte frente a las redes.">CatBoost: árboles en secuencia</Titulo>
      <Segmentado etiqueta="Tarea" valor={tarea} onCambio={setTarea}
        opciones={(["t1", "t2", "t3"] as const).map((id) => ({ id, label: NOMBRE_CORTO[id] }))} />
      <DiagramaCatBoost p={p} />
      <Explicacion
        mira="Las mismas variables que la regresión: perfil de ingreso, agregados al corte, estadística del curso. Maneja directamente las variables categóricas."
        predice="La misma salida que cada tarea: probabilidad de no continuar (T1 Continuidad), de reprobar (T2 Aprobación por ramo) o riesgos por semestre (T3 Tiempo hasta egreso, en forma persona-período)."
        aprende="Agrega árboles de a uno; cada uno reduce el error que dejan los anteriores. Una parada temprana en una cohorte reservada decide cuántos conservar."
      />
      <Tamanos filas={[
        { etiqueta: "Árboles conservados", valor: ent(p.iteraciones), detalle: "mediana entre semillas" },
        { etiqueta: "Profundidad", valor: ent(p.profundidad) },
        { etiqueta: "Variables", valor: ent(p.variables) },
        { etiqueta: "Tasa de aprendizaje", valor: p.tasa == null ? "—" : p.tasa.toLocaleString("es-CL") },
      ]} />
      <PanelResultados key={tarea} datos={datos} tarea={tarea} resaltar={tarea === "t1" ? ["cb_pre", "cb_acad"] : tarea === "t2" ? ["cb_a", "cb_b", "cb_c", "cb_d"] : ["dt_cb_adm", "dt_cb_agg"]} />
    </Seccion>
  );
}
