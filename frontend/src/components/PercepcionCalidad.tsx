"use client";

// CALIDAD DEL MODELO (A1) — la primera métrica de "¿esto está bien?" del módulo.
//
// Hasta acá, Percepción mostraba un índice sin ninguna medida de cuánto le erra el
// modelo que lo alimenta. Y el trabajo de revisión que sí existía no lo veía nadie:
// `correcciones_recientes()` estaba escrita en el backend y no la llamaba ningún
// endpoint.
//
// REGLA DE ESTE BLOQUE: ningún número se muestra sin su límite al lado. Los `avisos`
// los emite el SERVICIO, no este componente — así una métrica nueva no puede
// publicarse por olvido sin su advertencia. Cuando el acuerdo no se puede calcular
// se dice "desconocido" y por qué; nunca un 0% que se leería como "el modelo nunca
// acierta" cuando lo que pasa es que los aciertos no se anotaron.
import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import { esCancelacion } from "../lib/percepcion";

import {
  percepcionApi,
  type CalidadAviso,
  type CalidadCampo,
  type CalidadResponse,
  type CalidadResumen,
} from "../lib/percepcion";
import { CARD, TituloBloque, nro } from "./PercepcionUI";

const ETIQUETA_CAMPO: Record<string, string> = {
  sentimiento: "Sentimiento",
  emocion: "Emoción",
  tema: "Tema",
};

const ETIQUETA_MUESTRA: Record<string, string> = {
  duda: "Cola por duda (dirigida)",
  reciente: "Por fecha",
  aleatorio: "Muestra aleatoria",
  "(sin registrar)": "Sin registrar",
};

const ETIQUETA_AUTOR: Record<string, string> = {
  humano: "Persona",
  agente: "Agente LLM",
  "(sin registrar)": "Sin registrar",
};

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function Aviso({ aviso }: { aviso: CalidadAviso }) {
  const critico = aviso.nivel === "critico";
  return (
    <div
      className={`rounded-md border px-4 py-2.5 text-sm leading-5 ${
        critico
          ? "border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] text-ucn-tierra-clara"
          : "border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] text-ucn-tierra-clara"
      }`}
    >
      <strong className="font-semibold">{aviso.titulo}.</strong> {aviso.detalle}
    </div>
  );
}

/** Número grande con su unidad. `null` se muestra como "desconocido", no como 0. */
function Metrica({
  etiqueta, valor, sufijo = "", motivo, tono = "normal",
}: {
  etiqueta: string;
  valor: string | null;
  sufijo?: string;
  motivo?: string | null;
  tono?: "normal" | "alerta";
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-white/10 bg-white/[0.02] px-3 py-2">
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        {etiqueta}
      </span>
      {valor === null ? (
        <>
          <span className="text-sm font-semibold text-slate-500">desconocido</span>
          {motivo ? <span className="text-sm leading-4 text-slate-500">{motivo}</span> : null}
        </>
      ) : (
        <span
          className={`text-lg font-bold ${
            tono === "alerta" ? "text-ucn-tierra-clara" : "text-slate-100"
          }`}
        >
          {valor}
          {sufijo ? <span className="ml-0.5 text-sm font-normal text-slate-500">{sufijo}</span> : null}
        </span>
      )}
    </div>
  );
}

/** Matriz de confusión como lista ordenada: con 3 clases una grilla es más ruido
 *  que señal, y lo que importa es CUÁL desacuerdo domina. */
function Matriz({ resumen }: { resumen: CalidadResumen }) {
  if (!resumen.matriz.length) {
    return <p className="text-sm text-slate-500">Todavía no hay revisiones registradas.</p>;
  }
  const max = Math.max(...resumen.matriz.map((c) => c.n));
  return (
    <ul className="space-y-1">
      {resumen.matriz.map((c) => (
        <li key={`${c.modelo}->${c.revisor}`} className="flex items-center gap-2 text-sm">
          <span className="w-40 shrink-0 truncate text-slate-400">
            {c.modelo_label}
            <span className="mx-1 text-slate-500">→</span>
            <span className={c.acuerdo ? "text-ucn-azul-claro" : "text-ucn-tierra-clara"}>
              {c.revisor_label}
            </span>
          </span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
            <span
              className={`block h-full rounded-full ${
                c.acuerdo ? "bg-[var(--dato-favorable)]" : "bg-[color-mix(in_srgb,var(--portal-copper)_70%,transparent)]"
              }`}
              style={{ width: `${(c.n / max) * 100}%` }}
            />
          </span>
          <span className="w-10 shrink-0 text-right font-semibold text-slate-400">{nro(c.n)}</span>
          {c.acuerdo ? <span className="w-14 shrink-0 text-sm text-dato-favorable">acierto</span> : (
            <span className="w-14 shrink-0 text-sm text-slate-500">corregido</span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Cuánto se corrige según lo SEGURO que estaba el modelo. Corregir mucho donde el
 *  modelo tenía margen alto es la señal fuerte: o está mal calibrado, o el revisor
 *  se está pasando de largo. */
function PorMargen({ resumen }: { resumen: CalidadResumen }) {
  if (!resumen.por_margen.length) return null;
  return (
    <div>
      <p className="mb-1.5 text-sm font-semibold text-slate-400">
        Según qué tan seguro estaba el modelo
      </p>
      <div className="flex flex-wrap gap-2">
        {resumen.por_margen.map((b) => (
          <div key={b.bucket} className="rounded-xl border border-white/10 bg-white/[0.02] px-2.5 py-1.5">
            <div className="text-sm text-slate-500">margen {b.bucket}</div>
            <div className="text-sm font-semibold text-slate-100">
              {nro(b.cambios)}
              <span className="text-sm font-normal text-slate-500"> de {nro(b.n)} corregidos</span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-1 text-sm leading-4 text-slate-500">
        Margen alto = el modelo estaba seguro. Corregir mucho ahí es la señal fuerte: o
        está mal calibrado, o quien revisa se está pasando de largo. En <em>Tema</em> no
        es margen sino la confianza cruda del clasificador, que no devuelve una
        distribución: no hay segunda clase de la cual restar.
      </p>
    </div>
  );
}

function Grupos({ titulo, grupos, etiquetas, nota }: {
  titulo: string;
  grupos: { clave: string; n: number; confirmaciones: number; cambios: number }[];
  etiquetas: Record<string, string>;
  nota?: string;
}) {
  if (!grupos.length) return null;
  return (
    <div>
      <p className="mb-1.5 text-sm font-semibold text-slate-400">{titulo}</p>
      <ul className="space-y-1">
        {grupos.map((g) => (
          <li key={g.clave} className="flex items-center gap-2 text-sm text-slate-400">
            <span className="w-44 shrink-0 truncate">{etiquetas[g.clave] ?? g.clave}</span>
            <span className="text-slate-400">{nro(g.n)}</span>
            <span className="text-slate-500">revisiones ·</span>
            <span className="text-ucn-azul-claro">{nro(g.confirmaciones)} ok</span>
            <span className="text-ucn-tierra-clara">{nro(g.cambios)} corregidas</span>
          </li>
        ))}
      </ul>
      {nota ? <p className="mt-1 text-sm leading-4 text-slate-500">{nota}</p> : null}
    </div>
  );
}

function Campo({ nombre, campo }: { nombre: string; campo: CalidadCampo }) {
  return (
    <div className="rounded-md border border-white/5 bg-white/[0.02] p-3">
      <p className="mb-2 text-sm font-semibold text-slate-100">
        {ETIQUETA_CAMPO[nombre] ?? nombre}
      </p>

      {/* LA ESTIMACIÓN VÁLIDA va primero y sola. El resumen general del campo mezcla
          agente con humano y colas dirigidas con aleatorias: en la base real eso da
          29,2% cuando la lectura correcta es 78%. Mostrar el número mezclado como
          titular sería alarmar por un artefacto del registro, no por el modelo. */}
      {campo.estimacion ? (
        <div className="mb-3 rounded-md border border-[color-mix(in_srgb,var(--portal-cyan)_25%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_5%,transparent)] p-3">
          <p className="mb-2 text-sm font-semibold text-ucn-azul-claro">
            Estimación válida · solo revisión humana sobre muestra aleatoria
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Metrica etiqueta="Comentarios" valor={nro(campo.estimacion.n)} />
            <Metrica
              etiqueta="Acuerdo real"
              valor={campo.estimacion.acuerdo === null ? null : pct(campo.estimacion.acuerdo)}
              motivo={campo.estimacion.acuerdo_motivo}
            />
            <Metrica
              etiqueta="Kappa de Cohen"
              valor={campo.estimacion.kappa === null ? null : campo.estimacion.kappa.toFixed(3)}
              motivo={campo.estimacion.kappa === null ? "Necesita confirmaciones." : null}
            />
          </div>
          {campo.estimacion.suficiente ? null : (
            <p className="mt-1.5 text-sm leading-4 text-ucn-tierra-clara">
              Muestra insuficiente para que estos números signifiquen algo. Anota con el
              orden «aleatorio» de la cola de revisión.
            </p>
          )}
        </div>
      ) : null}

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Metrica etiqueta="Revisiones (todas las fuentes)" valor={nro(campo.n)} />
        <Metrica
          etiqueta="Acuerdo mezclado"
          valor={campo.acuerdo === null ? null : pct(campo.acuerdo)}
          motivo={campo.acuerdo_motivo ?? "Mezcla agente y humano: sirve para auditar el registro, no para estimar."}
        />
        <Metrica
          etiqueta="Con salida del modelo"
          valor={`${nro(campo.con_snapshot)}/${nro(campo.n)}`}
          tono={campo.con_snapshot < campo.n ? "alerta" : "normal"}
        />
      </div>

      {campo.sesgo_direccional?.alerta ? (
        <div className="mb-3 rounded-xl border border-[color-mix(in_srgb,var(--portal-copper)_30%,transparent)] bg-[color-mix(in_srgb,var(--portal-copper)_8%,transparent)] px-3 py-2 text-sm leading-5 text-ucn-tierra-clara">
          <strong>Sesgo direccional:</strong> el{" "}
          {pct(campo.sesgo_direccional.proporcion)} de los cambios (
          {nro(campo.sesgo_direccional.n)} de {nro(campo.sesgo_direccional.de)}) apunta a{" "}
          «{campo.sesgo_direccional.clase_label}». Puede ser un error real del modelo en
          esa dirección o un sesgo de quien revisa —con lo registrado no se pueden separar.
        </div>
      ) : null}

      <div className="space-y-3">
        <div>
          <p className="mb-1.5 text-sm font-semibold text-slate-400">
            Qué dijo el modelo y qué dijo quien revisó
          </p>
          <Matriz resumen={campo} />
        </div>
        <PorMargen resumen={campo} />
        <Grupos
          titulo="Por tipo de revisor"
          grupos={campo.por_autor}
          etiquetas={ETIQUETA_AUTOR}
          nota="Un agente LLM y una persona no valen lo mismo como referencia: un agente sesgado produce el mismo patrón que un modelo que falla en esa dirección."
        />
        <Grupos
          titulo="Por tipo de muestra"
          grupos={campo.por_muestra}
          etiquetas={ETIQUETA_MUESTRA}
          nota="Solo la muestra aleatoria permite estimar la calidad real. La cola por duda apunta a donde el modelo es peor, así que lo medido ahí es un piso pesimista."
        />
      </div>
    </div>
  );
}

export function PercepcionCalidad() {
  const [abierto, setAbierto] = useState(false);
  const [data, setData] = useState<CalidadResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nueva = useSolicitudVigente();
  const recargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      setData(await percepcionApi.calidad(opts));
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "No se pudo cargar la calidad del modelo");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => { if (abierto) void recargar(); }, [abierto, recargar]);

  const criticos = (data?.avisos ?? []).filter((a) => a.nivel === "critico").length;

  return (
    <div className={CARD}>
      <button onClick={() => setAbierto((a) => !a)} className="flex w-full items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-100">
          Calidad del modelo · qué acierta y qué no
        </div>
        <span className="text-sm text-slate-500">
          {abierto ? "▲ ocultar" : criticos ? `▼ ${criticos} advertencia(s)` : "▼ ver"}
        </span>
      </button>

      {abierto ? (
        <div className="mt-3 space-y-3">
          <TituloBloque titulo="Cuánto le erra el scoring">
            Se mide contra el historial de revisiones. Cada número viene con su límite:
            si algo no se puede calcular honestamente, dice «desconocido» y por qué.
          </TituloBloque>

          {error ? (
            <div className="rounded-md border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-4 py-2 text-sm text-ucn-tierra-clara">
              {error}
            </div>
          ) : null}

          {cargando && !data ? (
            <p className="py-6 text-center text-sm text-slate-500">Cargando…</p>
          ) : data ? (
            <>
              {data.avisos.map((a) => <Aviso key={a.titulo} aviso={a} />)}

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Metrica etiqueta="Comentarios" valor={nro(data.total_comentarios)} />
                <Metrica etiqueta="Revisados" valor={nro(data.comentarios_revisados)} />
                <Metrica etiqueta="Cobertura" valor={pct(data.cobertura)} />
              </div>

              {Object.entries(data.campos).map(([nombre, campo]) => (
                <Campo key={nombre} nombre={nombre} campo={campo} />
              ))}
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default PercepcionCalidad;
