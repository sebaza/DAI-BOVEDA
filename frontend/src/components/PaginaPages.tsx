"use client";

import { useCallback, useEffect, useState } from "react";

import { BovedaEmblema } from "./BovedaEmblema";
import { PercepcionPanel } from "./PercepcionPanel";
import { PinScreen } from "./PinScreen";
import { ACCESO_CAMBIO_EVENT, limpiarToken, obtenerToken, vencimientoToken } from "../lib/accesoPages";

type Estado = { fase: "verificando" } | { fase: "sin_acceso"; aviso?: string } | { fase: "activo" };

const MAX_TIMEOUT_MS = 2_000_000_000; // setTimeout overflows past ~24.8 days

/** Modo Pages: PIN -> token en sessionStorage -> tablero de solo lectura. */
export function PaginaPages() {
  const [estado, setEstado] = useState<Estado>({ fase: "verificando" });
  const [huboAcceso, setHuboAcceso] = useState(false);

  const revisar = useCallback(() => {
    const hay = obtenerToken() !== null;
    setEstado((previo) => {
      if (hay) return { fase: "activo" };
      // Had a session and lost it (expiry, 401/403): tell the person why.
      return previo.fase === "activo"
        ? { fase: "sin_acceso", aviso: "Tu acceso venció. Ingresa la clave nuevamente." }
        : { fase: "sin_acceso" };
    });
    if (hay) setHuboAcceso(true);
  }, []);

  useEffect(() => {
    revisar();
    window.addEventListener(ACCESO_CAMBIO_EVENT, revisar);
    return () => window.removeEventListener(ACCESO_CAMBIO_EVENT, revisar);
  }, [revisar]);

  // Drop the token (and show the PIN screen) exactly when it expires.
  useEffect(() => {
    if (estado.fase !== "activo") return;
    const exp = vencimientoToken();
    if (exp === null) return;
    const t = window.setTimeout(() => limpiarToken(), Math.min(Math.max(exp - Date.now(), 0), MAX_TIMEOUT_MS));
    return () => window.clearTimeout(t);
  }, [estado.fase]);

  if (estado.fase === "verificando") {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-[var(--portal-muted)]">Cargando…</main>
    );
  }
  if (estado.fase === "sin_acceso") {
    return <PinScreen aviso={huboAcceso ? estado.aviso : undefined} />;
  }
  return (
    <div className="min-h-screen">
      <header className="boveda-banda sticky top-0 z-30 h-16">
        <div className="mx-auto flex h-full max-w-[1500px] items-center justify-between gap-3 px-4 pb-2 md:px-6">
          <div className="portal-title flex items-center gap-2 text-lg font-bold tracking-tight text-[var(--portal-fg)]">
            <BovedaEmblema size={28} />
            <span className="whitespace-nowrap">Termómetro Institucional</span>
          </div>
          <button
            type="button"
            onClick={() => {
              limpiarToken({ silencioso: true });
              setEstado({ fase: "sin_acceso" }); // voluntary exit: no "expired" notice
            }}
            className="rounded border border-[color-mix(in_srgb,var(--boveda-laton)_40%,transparent)] whitespace-nowrap px-3 py-2 text-sm font-semibold text-[var(--portal-muted)] transition hover:bg-white/[0.06] hover:text-[var(--portal-fg)]"
          >
            Salir
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-6 md:px-6">
        <PercepcionPanel />
      </main>
    </div>
  );
}
