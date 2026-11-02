// Acceso por PIN del modo Pages (wh-api). El token vive en sessionStorage (muere con la
// pestaña) junto con su vencimiento. Nunca se registra el PIN ni el token.

const TOKEN_KEY = "boveda-pages-token";
const EXPIRA_KEY = "boveda-pages-expira";
export const ACCESO_CAMBIO_EVENT = "boveda-pages-acceso-cambio";

export const API_PAGES_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/+$/, "");

function emitir() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(ACCESO_CAMBIO_EVENT));
}

export function limpiarToken(opts: { silencioso?: boolean } = {}) {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(EXPIRA_KEY);
  } catch {
    /* nothing to clear */
  }
  if (!opts.silencioso) emitir();
}

/** Vencimiento en ms epoch, o null si no hay token guardado. */
export function vencimientoToken(): number | null {
  if (typeof window === "undefined") return null;
  try {
    if (!window.sessionStorage.getItem(TOKEN_KEY)) return null;
    const v = Number(window.sessionStorage.getItem(EXPIRA_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

/** Token vigente; si venció lo borra y devuelve null. */
export function obtenerToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const token = window.sessionStorage.getItem(TOKEN_KEY);
    if (!token) return null;
    const exp = vencimientoToken();
    if (exp === null || exp <= Date.now()) {
      limpiarToken({ silencioso: true });
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

function aMs(expira: unknown): number | null {
  if (typeof expira === "number" && Number.isFinite(expira)) {
    // Heuristic: small numbers are seconds from now, big ones are epoch (s or ms).
    if (expira < 1e9) return Date.now() + expira * 1000;
    return expira < 1e12 ? expira * 1000 : expira;
  }
  if (typeof expira === "string") {
    const t = Date.parse(expira);
    return Number.isNaN(t) ? null : t;
  }
  return null;
}

export type ResultadoAcceso =
  | { ok: true }
  | { ok: false; motivo: "pin" | "limite" | "no_disponible" | "red" | "otro"; mensaje: string };

/** POST /percepcion/acceso. Mensajes amigables; jamás incluye el PIN. */
export async function ingresarConPin(pin: string): Promise<ResultadoAcceso> {
  let res: Response;
  try {
    res = await fetch(`${API_PAGES_URL}/percepcion/acceso`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
      cache: "no-store",
      credentials: "omit",
    });
  } catch {
    return { ok: false, motivo: "red", mensaje: "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo." };
  }
  if (res.status === 401) return { ok: false, motivo: "pin", mensaje: "PIN incorrecto." };
  if (res.status === 429) {
    const seg = Number(res.headers.get("Retry-After"));
    const min = Number.isFinite(seg) && seg > 0 ? Math.max(1, Math.ceil(seg / 60)) : null;
    return {
      ok: false,
      motivo: "limite",
      mensaje: min
        ? `Demasiados intentos. Espera ${min} ${min === 1 ? "minuto" : "minutos"} antes de volver a intentar.`
        : "Demasiados intentos. Espera unos minutos antes de volver a intentar.",
    };
  }
  if (res.status === 503) return { ok: false, motivo: "no_disponible", mensaje: "Acceso no disponible por ahora." };
  if (!res.ok) return { ok: false, motivo: "otro", mensaje: `No se pudo validar el acceso (error ${res.status}).` };
  try {
    const body = (await res.json()) as { token?: unknown; expira_en?: unknown };
    const exp = aMs(body.expira_en);
    if (typeof body.token !== "string" || !body.token || exp === null) throw new Error("respuesta inválida");
    window.sessionStorage.setItem(TOKEN_KEY, body.token);
    window.sessionStorage.setItem(EXPIRA_KEY, String(exp));
  } catch {
    return { ok: false, motivo: "otro", mensaje: "Respuesta inesperada del servidor." };
  }
  emitir();
  return { ok: true };
}
