"use client";

import Link from "next/link";

import { BovedaCabecera } from "../../components/BovedaCabecera";
import { NeuralPanel } from "../../components/NeuralPanel";
import { PaginaPages } from "../../components/PaginaPages";
import { PaginaProtegida } from "../../components/PaginaProtegida";

export default function Page() {
  // Literal env expression on purpose: webpack prunes the dead branch BEFORE tracking imports.
  return process.env.NEXT_PUBLIC_MODO === "pages" ? <PaginaPages modulo="neural" /> : <PaginaNeural />;
}

function TarjetaCentrada({ kicker, titulo, texto }: { kicker: string; titulo: string; texto: string }) {
  return (
    <div className="boveda-placa-card w-full max-w-md p-8 text-center">
      <p className="boveda-kicker">{kicker}</p>
      <h1 className="portal-title mt-2 text-2xl font-bold text-[var(--portal-fg)]">{titulo}</h1>
      <p className="mt-3 text-sm leading-7 text-[var(--portal-muted)]">{texto}</p>
      <Link href="/" className="boveda-cta mt-6">
        Volver al recibidor
      </Link>
    </div>
  );
}

function PaginaNeural() {
  return (
    <PaginaProtegida>
      {(usuario, cerrarSesion) =>
        usuario.modulos.some((m) => m.id === "neural") ? (
          <div className="min-h-screen">
            <BovedaCabecera usuario={usuario} onCerrarSesion={cerrarSesion} modulo="DAI Neural" />
            <main className="mx-auto max-w-[1500px] px-4 py-6 md:px-6">
              <nav aria-label="Ruta de navegación" className="mb-4 min-w-0">
                <ol className="flex min-w-0 items-center gap-2 text-sm">
                  <li className="shrink-0">
                    <Link href="/" className="rounded text-[var(--ucn-azul-claro)] underline-offset-4 hover:underline">
                      Recibidor
                    </Link>
                  </li>
                  <li aria-hidden="true" className="shrink-0 text-[var(--portal-subtle)]">›</li>
                  <li className="min-w-0 truncate font-semibold text-[var(--portal-fg)]" aria-current="page">
                    DAI Neural
                  </li>
                </ol>
              </nav>
              <NeuralPanel />
            </main>
          </div>
        ) : (
          // Keeps the header so a user without access can still sign out.
          <div className="flex min-h-screen flex-col">
            <BovedaCabecera usuario={usuario} onCerrarSesion={cerrarSesion} />
            <main className="flex flex-1 items-center justify-center px-4 py-10">
              <TarjetaCentrada
                kicker="Sin acceso"
                titulo="No tienes acceso a este módulo"
                texto="Tu cuenta no tiene asignado DAI Neural. Pide acceso a la DAI."
              />
            </main>
          </div>
        )
      }
    </PaginaProtegida>
  );
}
