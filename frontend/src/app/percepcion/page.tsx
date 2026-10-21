"use client";

import Link from "next/link";

import { BovedaShell } from "../../components/BovedaShell";
import { PaginaProtegida } from "../../components/PaginaProtegida";

export default function PaginaPercepcion() {
  return (
    <PaginaProtegida>
      {(usuario, cerrarSesion) =>
        usuario.modulos.some((m) => m.id === "percepcion") ? (
          <BovedaShell usuario={usuario} onCerrarSesion={cerrarSesion} />
        ) : (
          <main className="flex min-h-screen items-center justify-center px-4">
            <div className="boveda-compartimento max-w-md p-8 text-center">
              <p className="boveda-kicker">Sin acceso</p>
              <h1 className="portal-title mt-2 text-2xl font-bold text-[var(--portal-fg)]">
                No tienes acceso a este módulo
              </h1>
              <p className="mt-3 text-sm leading-7 text-[var(--portal-muted)]">
                Tu cuenta no tiene asignado el Termómetro Institucional. Pide acceso a la DAI.
              </p>
              <Link href="/" className="boveda-cta mt-6">
                Volver al recibidor
              </Link>
            </div>
          </main>
        )
      }
    </PaginaProtegida>
  );
}
