"use client";

// Sección de CURACIÓN MANUAL de temas: asignar a mano el tema de los comentarios
// que quedaron en "Otros". Dos vistas: por PUBLICACIÓN (los comentarios "otros" del
// post heredan) y por COMENTARIO (uno por uno). Cada asignación escribe en la base
// del worker y reconstruye los hechos → se refleja en todo el tablero (onCambio).
import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import { esCancelacion } from "../lib/percepcion";

import {
  percepcionApi,
  type ComentarioCurar,
  type PublicacionCurar,
  type TemaAsignable,
} from "../lib/percepcion";
import { CARD, SELECT } from "./PercepcionUI";

const INPUT = SELECT;

function TemaSelect({ temas, onPick }: { temas: TemaAsignable[]; onPick: (t: string) => void }) {
  return (
    <select
      className={`${SELECT} shrink-0`}
      value=""
      onChange={(e) => { if (e.target.value) onPick(e.target.value); }}
    >
      <option value="">Asignar tema…</option>
      {temas.map((t) => <option key={t.tema} value={t.tema}>{t.etiqueta}</option>)}
    </select>
  );
}

export function PercepcionCuracion({ onCambio }: { onCambio: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [vista, setVista] = useState<"post" | "comentario">("post");
  const [temas, setTemas] = useState<TemaAsignable[]>([]);
  const [pubs, setPubs] = useState<PublicacionCurar[]>([]);
  const [coms, setComs] = useState<ComentarioCurar[]>([]);
  const [cargando, setCargando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nombreTema, setNombreTema] = useState("");
  const [kwTema, setKwTema] = useState("");

  const nueva = useSolicitudVigente();
  const recargar = useCallback(async () => {
    const ctrl = nueva();
    const opts = { signal: ctrl.signal };
    setCargando(true);
    setError(null);
    try {
      const [t, p, c] = await Promise.all([
        percepcionApi.curacionTemas(opts),
        percepcionApi.curacionPublicaciones(opts),
        percepcionApi.curacionComentarios(opts),
      ]);
      setTemas(t.items);
      setPubs(p.items);
      setComs(c.items);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(e instanceof Error ? e.message : "Error al cargar la curación");
    } finally {
      if (!ctrl.signal.aborted) setCargando(false);
    }
  }, [nueva]);

  useEffect(() => { if (abierto) void recargar(); }, [abierto, recargar]);

  const asignar = async (fn: Promise<{ comentarios_actualizados: number }>, ok: (n: number) => string) => {
    setError(null);
    try {
      const r = await fn;
      setMsg(ok(r.comentarios_actualizados));
      await recargar();
      onCambio(); // refresca los gráficos del tablero
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo asignar el tema");
    }
  };

  const crearTema = async () => {
    const kws = kwTema.split(",").map((k) => k.trim()).filter(Boolean);
    setError(null);
    try {
      const r = await percepcionApi.crearTema(nombreTema.trim(), kws);
      setMsg(`Tema “${r.etiqueta}” creado${kws.length ? " con sus keywords (el clasificador lo usará en próximas ingestas)" : ""}. Ya puedes asignarlo.`);
      setNombreTema("");
      setKwTema("");
      await recargar();
      onCambio();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo crear el tema");
    }
  };

  const pendientes = `${pubs.length} posts · ${coms.length} comentarios`;

  return (
    <div className={CARD}>
      <button onClick={() => setAbierto((a) => !a)} className="flex w-full items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-100">
          Curación de temas · asignar los “Otros” a mano
        </div>
        <span className="text-sm text-slate-500">{abierto ? "▲ ocultar" : `▼ pendientes: ${pendientes}`}</span>
      </button>

      {abierto ? (
        <div className="mt-3">
          {/* Crear tema nuevo (con keywords → el clasificador lo aprende) */}
          <div className="mb-3 rounded-md border border-[color-mix(in_srgb,var(--portal-cyan)_20%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_5%,transparent)] p-3">
            <div className="mb-2 text-sm font-semibold text-slate-400">Crear tema nuevo</div>
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre</span>
                <input value={nombreTema} onChange={(e) => setNombreTema(e.target.value)} placeholder="Ej: Deportes" className={INPUT} />
              </label>
              <label className="flex min-w-[220px] flex-1 flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Palabras clave (separadas por coma)</span>
                <input value={kwTema} onChange={(e) => setKwTema(e.target.value)} placeholder="futbol, deporte, campeonato" className={INPUT} />
              </label>
              <button
                onClick={crearTema}
                disabled={!nombreTema.trim()}
                className="rounded-xl border border-[color-mix(in_srgb,var(--portal-cyan)_40%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_15%,transparent)] px-4 py-1.5 text-sm font-semibold text-slate-100 transition hover:bg-[color-mix(in_srgb,var(--portal-cyan)_25%,transparent)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Crear
              </button>
            </div>
            <p className="mt-1.5 text-sm text-slate-500">
              Sin palabras clave sirve solo para asignar a mano; con palabras clave, el clasificador lo usa solo en las próximas ingestas.
            </p>
          </div>

          <div className="mb-3 flex flex-wrap items-center gap-2">
            {(["post", "comentario"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setVista(v)}
                className={`rounded border px-3 py-1 text-sm font-semibold transition ${
                  vista === v
                    ? "border-[color-mix(in_srgb,var(--portal-cyan)_50%,transparent)] bg-[color-mix(in_srgb,var(--portal-cyan)_15%,transparent)] text-slate-100"
                    : "border-white/10 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]"
                }`}
              >
                {v === "post" ? "Por publicación" : "Por comentario"}
              </button>
            ))}
            <span className="ml-auto text-sm text-slate-500">
              asignar escribe en la base y actualiza los gráficos
            </span>
          </div>

          {msg ? <div className="mb-2 rounded-lg bg-[var(--ucn-azul-suave)] px-3 py-1.5 text-sm text-ucn-azul-claro">{msg}</div> : null}
          {error ? <div className="mb-2 rounded-lg bg-[var(--ucn-tierra-suave)] px-3 py-1.5 text-sm text-ucn-tierra-clara">{error}</div> : null}

          {cargando ? (
            <p className="py-6 text-center text-sm text-slate-500">Cargando…</p>
          ) : vista === "post" ? (
            pubs.length > 0 ? (
              <ul className="space-y-2">
                {pubs.map((p) => (
                  <li key={p.id} className="flex items-start justify-between gap-3 rounded-md border border-white/5 bg-white/[0.02] p-3">
                    <div className="flex-1">
                      <p className="text-sm text-slate-100">{p.caption || "(publicación sin texto)"}</p>
                      <p className="mt-1 text-sm text-slate-500">
                        {p.cuenta ? `@${p.cuenta} · ` : ""}<strong className="text-ucn-tierra-clara">{p.n_otros}</strong> de {p.n_comentarios} comentarios en “Otros” heredarán
                      </p>
                    </div>
                    <TemaSelect temas={temas} onPick={(t) => asignar(
                      percepcionApi.asignarTemaPublicacion(p.id, t),
                      (n) => `Asignado a ${n} comentario(s) del post.`,
                    )} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-6 text-center text-sm text-slate-500">No quedan publicaciones con comentarios en “Otros”. 🎉</p>
            )
          ) : coms.length > 0 ? (
            <ul className="space-y-2">
              {coms.map((c) => (
                <li key={c.id} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="flex-1 text-sm text-slate-100">{c.texto}</p>
                    <TemaSelect temas={temas} onPick={(t) => asignar(
                      percepcionApi.asignarTemaComentario(c.id, t),
                      () => "Comentario reclasificado.",
                    )} />
                  </div>
                  <p className="mt-1 text-sm text-slate-500">
                    {c.fecha} · {c.sentimiento}{c.caption ? ` · post: ${c.caption}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">No quedan comentarios en “Otros”. 🎉</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default PercepcionCuracion;
