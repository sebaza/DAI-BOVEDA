"use client";

import { LoginScreen } from "../components/LoginScreen";
import { PaginaPages } from "../components/PaginaPages";
import { Recibidor } from "../components/Recibidor";
import { useSession } from "../lib/SessionProvider";

function PaginaLocal() {
  const { estado, alAutenticar, cerrarSesion } = useSession();
  if (estado.fase === "verificando") {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-[var(--portal-muted)]">
        Verificando sesión…
      </main>
    );
  }
  if (estado.fase === "sin_sesion") {
    return <LoginScreen aviso={estado.aviso} onAuthenticated={alAutenticar} />;
  }
  return <Recibidor usuario={estado.usuario} onCerrarSesion={cerrarSesion} />;
}

export default function Page() {
  // Build-time switch: the other branch (and its imports) is dropped from the bundle.
  // Literal env expression on purpose: webpack prunes the dead branch BEFORE tracking imports.
  return process.env.NEXT_PUBLIC_MODO === "pages" ? <PaginaPages /> : <PaginaLocal />;
}
