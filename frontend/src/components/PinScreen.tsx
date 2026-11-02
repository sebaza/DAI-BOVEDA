"use client";

import { useState, type FormEvent } from "react";

import { BovedaEmblema } from "./BovedaEmblema";
import { ingresarConPin } from "../lib/accesoPages";

/** Pantalla de acceso por PIN (modo Pages). El PIN nunca se guarda ni se registra. */
export function PinScreen({ aviso }: { aviso?: string }) {
  const [pin, setPin] = useState("");
  const [mensaje, setMensaje] = useState<string | null>(aviso ?? null);
  const [trabajando, setTrabajando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!pin || trabajando) return;
    setTrabajando(true);
    setMensaje(null);
    const r = await ingresarConPin(pin);
    setTrabajando(false);
    if (r.ok) {
      setPin(""); // the parent swaps to the dashboard on the access-change event
    } else {
      setMensaje(r.mensaje);
      if (r.motivo === "pin") setPin("");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <div className="boveda-madera w-full max-w-md overflow-hidden">
        <div className="boveda-banda h-7" aria-hidden="true" />
        <div className="p-6 md:p-8">
          <BovedaEmblema size={48} />
          <p className="boveda-kicker mt-4">Acceso restringido</p>
          <h1 className="portal-title mt-2 text-3xl font-bold text-[var(--portal-fg)]">Termómetro Institucional</h1>
          <p className="mt-3 text-sm text-[var(--portal-muted)]">
            Ingresa la clave de acceso que te entregó la Dirección de Análisis Institucional.
          </p>
          <form onSubmit={enviar} className="mt-6 flex flex-col gap-4" noValidate>
            <div className="flex flex-col gap-2">
              <label htmlFor="acceso-pin" className="text-sm font-semibold text-[var(--portal-fg)]">
                Clave de acceso
              </label>
              <input
                id="acceso-pin"
                name="pin"
                type="password"
                autoComplete="off"
                autoFocus
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                disabled={trabajando}
                aria-invalid={mensaje ? true : undefined}
                aria-describedby={mensaje ? "acceso-pin-mensaje" : undefined}
                className="rounded-md border border-white/15 bg-white/[0.05] px-3 py-2 text-base text-[var(--portal-fg)] outline-none focus:border-[var(--ucn-azul-claro)]"
              />
            </div>
            <button type="submit" disabled={trabajando || !pin} className="boveda-cta justify-center disabled:opacity-50">
              {trabajando ? "Verificando…" : "Entrar"}
            </button>
            <div id="acceso-pin-mensaje" role="alert" aria-live="assertive">
              {mensaje ? (
                <p className="rounded-md border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-4 py-3 text-sm text-ucn-tierra-clara">
                  {mensaje}
                </p>
              ) : null}
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}
