"use client";

// Curación de SUBTEMAS: nombre manual sobre la etiqueta automática que calcula el modelo local.
// Solo se ven etiquetas y términos anonimizados (nunca texto). El nombre manual se guarda con
// quién y cuándo, y sobrevive a la reconstrucción de subtemas si el grupo sigue siendo parecido.
import { useCallback, useEffect, useState } from "react";
import { useSolicitudVigente } from "../lib/solicitud";
import {
  esCancelacion,
  percepcionApi,
  type SubtemaItem,
  type SubtemasTema,
} from "../lib/percepcion";
import { CARD, TituloBloque } from "./PercepcionUI";

const LARGO_MAX = 80;

/** El backend responde `{"detail": "..."}`; se muestra solo el mensaje. */
function mensajeDe(e: unknown, defecto: string): string {
  if (!(e instanceof Error) || !e.message) return defecto;
  try {
    const d = (JSON.parse(e.message) as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  } catch {
    /* no era JSON */
  }
  return e.message;
}

const BOTON =
  "rounded border px-3 py-1 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40";
const BOTON_PRINCIPAL =
  `${BOTON} border-ucn-azul bg-[var(--ucn-azul-suave)] text-ucn-azul-claro hover:brightness-110`;
const BOTON_SECUNDARIO = `${BOTON} border-white/10 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]`;

function Fila({ s, onGuardado }: { s: SubtemaItem; onGuardado: () => Promise<void> }) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(s.etiqueta);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enviar = async (valor: string | null) => {
    setGuardando(true);
    setError(null);
    try {
      await percepcionApi.renombrarSubtema(s.id, valor, s.etiqueta_auto);
      setEditando(false);
      await onGuardado();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo guardar el nombre"));
      // A rebuild may have replaced the list (409/404): refresh it so the next try uses current ids.
      void onGuardado();
    } finally {
      setGuardando(false);
    }
  };

  return (
    <li className="rounded-md border border-white/5 bg-white/[0.02] p-3">
      {editando ? (
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={texto}
            maxLength={LARGO_MAX}
            autoFocus
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && texto.trim()) void enviar(texto); }}
            aria-label="Nombre del subtema"
            className="h-9 min-w-[220px] flex-1 rounded border border-[var(--boveda-linea-fuerte)] bg-[var(--boveda-madera)] px-3 text-sm text-slate-100 outline-none focus:border-[var(--portal-cyan)]"
          />
          <button className={BOTON_PRINCIPAL} disabled={guardando || !texto.trim()} onClick={() => void enviar(texto)}>
            Guardar
          </button>
          <button className={BOTON_SECUNDARIO} disabled={guardando}
                  onClick={() => { setEditando(false); setError(null); setTexto(s.etiqueta); }}>
            Cancelar
          </button>
          {s.manual ? (
            <button className={BOTON_SECUNDARIO} disabled={guardando} onClick={() => void enviar(null)}>
              Volver a automático
            </button>
          ) : null}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-100">{s.etiqueta}</span>
          {s.manual ? (
            <span className="rounded bg-[var(--ucn-tierra-suave)] px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-ucn-tierra-clara">
              manual
            </span>
          ) : null}
          <span className="text-sm text-slate-500">· {s.n_comentarios} comentarios</span>
          <div className="ml-auto flex gap-2">
            <button className={BOTON_SECUNDARIO} onClick={() => { setTexto(s.etiqueta); setEditando(true); }}>
              Renombrar
            </button>
            {s.manual ? (
              <button className={BOTON_SECUNDARIO} disabled={guardando} onClick={() => void enviar(null)}>
                Volver a automático
              </button>
            ) : null}
          </div>
        </div>
      )}
      <p className="mt-1 text-sm text-slate-500">
        {s.manual ? <>Automático: {s.etiqueta_auto}</> : null}
        {s.manual && s.terminos.length ? " · " : null}
        {s.terminos.length ? <>Términos: {s.terminos.join(", ")}</> : null}
      </p>
      {error ? (
        <div className="mt-2 rounded-lg bg-[var(--ucn-tierra-suave)] px-3 py-1.5 text-sm text-ucn-tierra-clara">{error}</div>
      ) : null}
    </li>
  );
}

export function PercepcionSubtemas() {
  const [temas, setTemas] = useState<SubtemasTema[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nueva = useSolicitudVigente();

  const cargar = useCallback(async () => {
    const ctrl = nueva();
    setError(null);
    try {
      const r = await percepcionApi.subtemas({ signal: ctrl.signal });
      setTemas(r.temas);
    } catch (e) {
      if (esCancelacion(e)) return;
      setError(mensajeDe(e, "Error al cargar los subtemas"));
    }
  }, [nueva]);

  useEffect(() => { void cargar(); }, [cargar]);

  return (
    <div className={CARD}>
      <TituloBloque titulo="Subtemas">
        El modelo local agrupa los comentarios de cada tema y le pone un nombre con sus palabras más
        características. Aquí puedes reemplazarlo por uno propio (hasta {LARGO_MAX} caracteres, sin @ ni enlaces).
      </TituloBloque>
      {error ? (
        <div className="mb-2 rounded-lg bg-[var(--ucn-tierra-suave)] px-3 py-1.5 text-sm text-ucn-tierra-clara">{error}</div>
      ) : null}
      {temas === null && !error ? (
        <p className="py-6 text-center text-sm text-slate-500">Cargando…</p>
      ) : temas && temas.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          Todavía no se agruparon subtemas: corre scripts/agrupar_subtemas_percepcion.py
        </p>
      ) : (
        <div className="space-y-5">
          {(temas ?? []).map((t) => (
            <section key={t.tema}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                {t.tema_label || t.tema}
              </h3>
              <ul className="space-y-2">
                {t.subtemas.map((s) => <Fila key={s.id} s={s} onGuardado={cargar} />)}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

export default PercepcionSubtemas;
