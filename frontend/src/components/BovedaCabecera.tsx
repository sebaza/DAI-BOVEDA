"use client";

import Link from "next/link";

import { BovedaEmblema } from "./BovedaEmblema";
import { rolDelUsuario } from "../lib/roles";
import type { AuthUser } from "../lib/session";

interface BovedaCabeceraProps {
  usuario: AuthUser;
  onCerrarSesion: () => void;
  /** Nombre del módulo abierto; en el recibidor se omite. */
  modulo?: string;
}

export function BovedaCabecera({ usuario, onCerrarSesion, modulo }: BovedaCabeceraProps) {
  const rol = rolDelUsuario(usuario);
  return (
    <header className="boveda-banda sticky top-0 z-30 h-16">
      <div className="mx-auto flex h-full max-w-[1500px] items-center justify-between gap-3 px-4 pb-2 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/"
            className="portal-title flex items-center gap-2 rounded-lg text-lg font-bold tracking-tight text-[var(--portal-fg)]"
            aria-label="Bóveda DAI, volver al recibidor"
          >
            <BovedaEmblema size={28} />
            <span className="whitespace-nowrap">Bóveda DAI</span>
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden text-right leading-tight sm:block">
            <p className="text-sm font-semibold text-[var(--portal-fg)]">{usuario.name || usuario.email}</p>
            <p className="text-xs text-[var(--portal-subtle)]">
              {usuario.email}
              {rol ? ` · ${rol}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onCerrarSesion}
            className="rounded border border-[color-mix(in_srgb,var(--boveda-laton)_40%,transparent)] whitespace-nowrap px-3 py-2 text-sm font-semibold text-[var(--portal-muted)] transition hover:bg-white/[0.06] hover:text-[var(--portal-fg)]"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    </header>
  );
}
