// Session + auth client of the Boveda DAI frontend.
// Modeled on the Torre's lib/api.ts (fetchAuthConfig / verifyGoogleCredential / devLogin /
// fetchSessionUser) but trimmed to what this app needs.

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8012").replace(/\/+$/, "");

export const SESSION_TOKEN_STORAGE_KEY = "boveda-dai-session-token";
export const USER_STORAGE_KEY = "boveda-dai-user";
export const SESSION_CHANGED_EVENT = "boveda-session-changed";

/** `equipo` = DAI team (read + write); `lector` = read only. Resolved by the backend. */
export type BovedaRole = "equipo" | "lector";

export interface AuthUser {
  email: string;
  name: string;
  allowed: boolean;
  auth_mode: string;
  role: BovedaRole | null;
  picture?: string | null;
  hosted_domain?: string | null;
}

export interface AuthConfig {
  google_oauth_enabled: boolean;
  google_client_id: string | null;
  dev_login_enabled: boolean;
}

export interface LoginResponse {
  message: string;
  user: AuthUser;
  next_step: string;
  session_token: string;
  expires_at: string;
}

function emitSessionChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
}

export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function persistSession(token: string, user: AuthUser) {
  try {
    window.localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, token);
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  } catch {
    /* storage blocked: the session just will not survive a reload */
  }
  emitSessionChanged();
}

export function clearSession() {
  try {
    window.localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
    window.localStorage.removeItem(USER_STORAGE_KEY);
  } catch {
    /* nothing to clear */
  }
  emitSessionChanged();
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      /* body was not JSON */
    }
    throw new Error(detail || `Error ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  return parseJson<AuthConfig>(await fetch(`${API_BASE_URL}/auth/config`, { cache: "no-store" }));
}

export async function verifyGoogleCredential(credential: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/google/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  return parseJson<LoginResponse>(response);
}

/** Only exists while the backend runs with APP_ENV=dev (404 otherwise). */
export async function devLogin(email?: string, name?: string): Promise<LoginResponse> {
  const params = new URLSearchParams();
  if (email) params.set("email", email);
  if (name) params.set("name", name);
  const qs = params.toString();
  return parseJson<LoginResponse>(await fetch(`${API_BASE_URL}/auth/dev-login${qs ? `?${qs}` : ""}`, { cache: "no-store" }));
}

/** Re-validates the stored token against the backend (it re-resolves the role from the allowlists). */
export async function fetchSessionUser(): Promise<AuthUser> {
  const token = getSessionToken();
  const response = await fetch(`${API_BASE_URL}/auth/session-user`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  return parseJson<AuthUser>(response);
}
