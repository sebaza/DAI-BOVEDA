"use client";

import Link from "next/link";

import { BovedaCabecera } from "./BovedaCabecera";
import { BovedaEmblema } from "./BovedaEmblema";
import { etiquetaRol } from "../lib/roles";
import type { AuthUser, ModuloAcceso } from "../lib/session";

interface ModuloInfo {
  ruta: string;
  descripcion: string;
}

// Catálogo del frontend: qué ruta abre cada módulo y cómo se describe.
const CATALOGO: Record<string, ModuloInfo> = {
  percepcion: {
    ruta: "/percepcion",
    descripcion: "Percepción de la comunidad UCN en redes sociales",
  },
};

function Esquinas() {
  return (
    <>
      <span className="boveda-esquina left-0 top-0 rounded-br-md" aria-hidden="true" />
      <span className="boveda-esquina right-0 top-0 rounded-bl-md" aria-hidden="true" />
      <span className="boveda-esquina bottom-0 left-0 rounded-tr-md" aria-hidden="true" />
      <span className="boveda-esquina bottom-0 right-0 rounded-tl-md" aria-hidden="true" />
    </>
  );
}

/** Frente del baúl: dos fajas de hierro con remaches, esquineros y placa de latón con cerradura. */
function FrenteBaul() {
  return (
    <>
      <span className="boveda-faja left-[11%]" aria-hidden="true" />
      <span className="boveda-faja right-[11%]" aria-hidden="true" />
      <Esquinas />
      <BovedaEmblema size={54} className="boveda-placa" />
    </>
  );
}

function Compartimento({ modulo, mostrarRol }: { modulo: ModuloAcceso; mostrarRol: boolean }) {
  const info = CATALOGO[modulo.id];
  const contenido = (
    <>
      <FrenteBaul />
      <div className="boveda-baul-interno">
        <div className="min-w-0 text-center">
          <p className="boveda-kicker">Compartimento</p>
          <h2 className="portal-title mt-1 text-xl font-bold text-[var(--portal-fg)]">{modulo.nombre}</h2>
        </div>
        <p className="mt-3 text-center text-sm text-[var(--portal-muted)]">
          {info?.descripcion ?? "Módulo de la Bóveda DAI"}
        </p>
        <div className="mt-5 flex min-h-9 flex-wrap items-center justify-center gap-3">
          {mostrarRol ? <span className="portal-pill bg-[var(--boveda-fondo)]">{etiquetaRol(modulo.rol)}</span> : null}
          {info ? <span className="boveda-cta">Entrar →</span> : null}
        </div>
      </div>
    </>
  );
  if (!info) return <div className="boveda-madera boveda-baul w-full opacity-70">{contenido}</div>;
  return (
    <Link
      href={info.ruta}
      className="boveda-madera boveda-baul block w-full"
    >
      {contenido}
    </Link>
  );
}

interface RecibidorProps {
  /** Sesión de Google (modo local). Sin ella (modo Pages) se usan `modulos` y no se muestran roles. */
  usuario?: AuthUser;
  modulos?: ModuloAcceso[];
  onCerrarSesion: () => void;
}

export function Recibidor({ usuario, modulos: modulosSinSesion = [], onCerrarSesion }: RecibidorProps) {
  const modulos = usuario ? usuario.modulos : modulosSinSesion;
  const saludo = usuario ? `Te damos la bienvenida, ${usuario.name || usuario.email}` : "Te damos la bienvenida";
  return (
    <div className="flex min-h-screen flex-col">
      <BovedaCabecera usuario={usuario} onCerrarSesion={onCerrarSesion} />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 md:px-6 md:py-14">
        <div className="flex flex-col items-center text-center">
          <BovedaEmblema size={64} />
          <p className="boveda-kicker mt-5">Recibidor</p>
          <h1 className="portal-title mt-2 max-w-full break-words text-3xl font-bold text-[var(--portal-fg)] md:text-4xl">
            {saludo}
          </h1>
          <p className="mt-3 max-w-xl text-base text-[var(--portal-muted)]">
            Elige un compartimento para entrar. Cada módulo guarda información reservada a la dirección
            universitaria.
          </p>
          {usuario?.is_admin ? <p className="portal-pill mt-4">Acceso de administración</p> : null}
        </div>

        {modulos.length === 0 ? (
          <div className="boveda-madera boveda-baul mx-auto mt-10 max-w-lg text-center">
            <FrenteBaul />
            <div className="boveda-baul-interno">
              <h2 className="portal-title text-lg font-bold text-[var(--portal-fg)]">
                Aún no tienes compartimentos asignados
              </h2>
              <p className="mt-2 text-sm text-[var(--portal-muted)]">
                Tu cuenta ya está activa, pero ningún módulo está habilitado para ti. Pide acceso al equipo de la
                Dirección de Análisis Institucional (DAI) y vuelve a ingresar.
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto mt-10 flex max-w-4xl flex-wrap justify-center gap-5">
            {modulos.map((m) => (
              <div key={m.id} className="w-full max-w-md sm:w-[calc(50%-0.625rem)] lg:w-[calc(33.333%-0.85rem)]">
                <Compartimento modulo={m} mostrarRol={usuario ? !usuario.is_admin : false} />
              </div>
            ))}
          </div>
        )}
      </main>
      <footer className="px-4 py-6 text-center text-xs text-[var(--portal-subtle)]">
        Dirección de Análisis Institucional · Universidad Católica del Norte
      </footer>
    </div>
  );
}
