"use client";

import { LoginScreen } from "../components/LoginScreen";
import { Recibidor } from "../components/Recibidor";
import { useSession } from "../lib/SessionProvider";

export default function Page() {
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
