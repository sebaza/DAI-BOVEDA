"use client";

import { useCallback, useEffect, useState } from "react";

import { BovedaCabecera } from "./BovedaCabecera";
import { PercepcionPanel } from "./PercepcionPanel";
import { PinScreen } from "./PinScreen";
import { Recibidor } from "./Recibidor";
import { ACCESO_CAMBIO_EVENT, limpiarToken, obtenerToken, vencimientoToken } from "../lib/accesoPages";
import type { ModuloAcceso } from "../lib/session";

type Estado = { fase: "verificando" } | { fase: "sin_acceso"; aviso?: string } | { fase: "activo" };

const MAX_TIMEOUT_MS = 2_000_000_000; // setTimeout overflows past ~24.8 days

// The PIN opens every module listed here (no per-person roles in Pages mode); `rol` is not shown.
const MODULOS_PAGES: ModuloAcceso[] = [{ id: "percepcion", nombre: "Termómetro Institucional", rol: "lector" }];

/** Modo Pages: PIN -> token en sessionStorage -> recibidor (`/`) o un módulo de solo lectura. */
export function PaginaPages({ modulo }: { modulo?: "percepcion" }) {
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
  const salir = () => {
    limpiarToken({ silencioso: true });
    setEstado({ fase: "sin_acceso" }); // voluntary exit: no "expired" notice
  };
  if (!modulo) return <Recibidor modulos={MODULOS_PAGES} onCerrarSesion={salir} />;
  return (
    <div className="min-h-screen">
      <BovedaCabecera onCerrarSesion={salir} modulo="Termómetro Institucional" />
      <main className="mx-auto max-w-[1500px] px-4 py-6 md:px-6">
        <PercepcionPanel />
      </main>
    </div>
  );
}
