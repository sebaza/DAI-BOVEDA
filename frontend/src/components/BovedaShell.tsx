"use client";

import Link from "next/link";

import { BovedaCabecera } from "./BovedaCabecera";
import { PercepcionPanel } from "./PercepcionPanel";
import type { AuthUser } from "../lib/session";

interface BovedaShellProps {
  usuario: AuthUser;
  onCerrarSesion: () => void;
}

export function BovedaShell({ usuario, onCerrarSesion }: BovedaShellProps) {
  return (
    <div className="min-h-screen">
      <BovedaCabecera usuario={usuario} onCerrarSesion={onCerrarSesion} modulo="Termómetro Institucional" />
      <main className="mx-auto max-w-[1500px] px-4 py-6 md:px-6">
        {/* Breadcrumb back to the lobby; truncates instead of overflowing at 375px. */}
        <nav aria-label="Ruta de navegación" className="mb-4 min-w-0">
          <ol className="flex min-w-0 items-center gap-2 text-sm">
            <li className="shrink-0">
              <Link
                href="/"
                className="rounded text-[var(--ucn-azul-claro)] underline-offset-4 hover:underline"
              >
                Recibidor
              </Link>
            </li>
            <li aria-hidden="true" className="shrink-0 text-[var(--portal-subtle)]">›</li>
            <li className="min-w-0 truncate font-semibold text-[var(--portal-fg)]" aria-current="page">
              Termómetro Institucional
            </li>
          </ol>
        </nav>
        {/* Sin onIrAFormulario: la Bóveda no tiene módulo de Formularios. El botón de
            retroalimentación solo aparece si NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL está definida. */}
        <PercepcionPanel />
      </main>
    </div>
  );
}
