"use client";

import { PercepcionPanel } from "./PercepcionPanel";
import type { AuthUser } from "../lib/session";

interface BovedaShellProps {
  usuario: AuthUser;
  onCerrarSesion: () => void;
}

const ETIQUETA_ROL: Record<string, string> = {
  admin: "Administración",
  equipo: "Equipo DAI",
  lector: "Solo lectura",
};

export function BovedaShell({ usuario, onCerrarSesion }: BovedaShellProps) {
  // El administrador es global: se rotula como tal, sea cual sea su rol en cada módulo.
  const claveRol = usuario.is_admin ? "admin" : usuario.role;
  const rol = claveRol ? ETIQUETA_ROL[claveRol] ?? claveRol : "";
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#081120]/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-4 py-3 md:px-6">
          <div className="flex items-center gap-3">
            <span className="portal-title text-lg font-bold tracking-tight text-white">Bóveda DAI</span>
            <span className="portal-pill hidden sm:inline-flex">Termómetro Institucional</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right leading-tight sm:block">
              <p className="text-sm font-semibold text-slate-100">{usuario.name || usuario.email}</p>
              <p className="text-xs text-slate-400">
                {usuario.email}
                {rol ? ` · ${rol}` : ""}
              </p>
            </div>
            <button
              type="button"
              onClick={onCerrarSesion}
              className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-6 md:px-6">
        {/* Sin onIrAFormulario: la Bóveda no tiene módulo de Formularios. El botón de
            retroalimentación solo aparece si NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL está definida. */}
        <PercepcionPanel />
      </main>
    </div>
  );
}
