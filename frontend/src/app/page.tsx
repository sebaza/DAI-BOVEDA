"use client";

import { useCallback, useEffect, useState } from "react";

import { BovedaShell } from "../components/BovedaShell";
import { LoginScreen } from "../components/LoginScreen";
import {
  clearSession,
  fetchSessionUser,
  getSessionToken,
  persistSession,
  type AuthUser,
  type LoginResponse,
} from "../lib/session";

type Estado =
  | { fase: "verificando" }
  | { fase: "sin_sesion"; aviso?: string }
  | { fase: "activa"; usuario: AuthUser };

export default function Page() {
  const [estado, setEstado] = useState<Estado>({ fase: "verificando" });

  // On load: if there is a stored token, re-validate it against the backend. The backend
  // re-resolves the role from the allowlists, so a revoked account is kicked out here.
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
        // refresh the cached copy (the role may have changed since the last login)
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

  if (estado.fase === "verificando") {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-slate-400">
        Verificando sesión…
      </main>
    );
  }
  if (estado.fase === "sin_sesion") {
    return <LoginScreen aviso={estado.aviso} onAuthenticated={alAutenticar} />;
  }
  return <BovedaShell usuario={estado.usuario} onCerrarSesion={cerrarSesion} />;
}
