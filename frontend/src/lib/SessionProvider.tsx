"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  clearSession,
  fetchSessionUser,
  getSessionToken,
  persistSession,
  type AuthUser,
  type LoginResponse,
} from "./session";

type Estado =
  | { fase: "verificando" }
  | { fase: "sin_sesion"; aviso?: string }
  | { fase: "activa"; usuario: AuthUser };

interface SessionContextValue {
  estado: Estado;
  alAutenticar: (respuesta: LoginResponse) => void;
  cerrarSesion: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/** Pages mode has no Google session: it renders the children untouched. */
export function SessionProvider({ children }: { children: ReactNode }) {
  // Literal env expression on purpose: the bundler folds it before analyzing imports, so the
  // Google session client (and its /auth endpoints) never reaches the Pages bundle.
  return process.env.NEXT_PUBLIC_MODO === "pages" ? <>{children}</> : <SessionProviderLocal>{children}</SessionProviderLocal>;
}

function SessionProviderLocal({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ fase: "verificando" });

  // On load: if there is a stored token, re-validate it against the backend. The backend
  // re-resolves the role from the database, so a revoked account is kicked out here.
  useEffect(() => {
    let vivo = true;
    (async () => {
      const token = getSessionToken();
      if (!token) {
        if (vivo) setEstado({ fase: "sin_sesion" });
        return;
      }
      try {
        const usuario = await fetchSessionUser();
        if (!vivo) return;
        persistSession(token, usuario);
        setEstado({ fase: "activa", usuario });
      } catch (error) {
        if (!vivo) return;
        clearSession();
        const detalle = error instanceof Error ? error.message : "";
        setEstado({
          fase: "sin_sesion",
          aviso: detalle ? `La sesión ya no es válida: ${detalle}` : "La sesión ya no es válida.",
        });
      }
    })();
    return () => {
      vivo = false;
    };
  }, []);

  const alAutenticar = useCallback((respuesta: LoginResponse) => {
    persistSession(respuesta.session_token, respuesta.user);
    setEstado({ fase: "activa", usuario: respuesta.user });
  }, []);

  const cerrarSesion = useCallback(() => {
    clearSession();
    setEstado({ fase: "sin_sesion" });
  }, []);

  const valor = useMemo(() => ({ estado, alAutenticar, cerrarSesion }), [estado, alAutenticar, cerrarSesion]);
  return <SessionContext.Provider value={valor}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession debe usarse dentro de SessionProvider");
  return ctx;
}
