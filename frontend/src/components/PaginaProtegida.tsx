"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useSession } from "../lib/SessionProvider";
import type { AuthUser } from "../lib/session";

/** Guard de rutas: sin sesión redirige a "/"; mientras verifica muestra un aviso. */
export function PaginaProtegida({
  children,
}: {
  children: (usuario: AuthUser, cerrarSesion: () => void) => ReactNode;
}) {
  const { estado, cerrarSesion } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (estado.fase === "sin_sesion") router.replace("/");
  }, [estado.fase, router]);

  if (estado.fase !== "activa") {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-[var(--portal-muted)]">
        Verificando sesión…
      </main>
    );
  }
  return <>{children(estado.usuario, cerrarSesion)}</>;
}
