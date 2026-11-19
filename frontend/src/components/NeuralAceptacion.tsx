"use client";

// DAI Neural — puerta de aceptación: la declaración de confidencialidad (texto del servidor, tal cual) debe confirmarse antes de
// que se monte o consulte cualquier pestaña. Si el servidor ya la tiene aceptada, avisa y no muestra nada (salvo que las pestañas
// acaben de ser rechazadas: entonces el servidor es inconsistente y se muestra un error en vez de entrar en bucle).
import { useCallback, useEffect, useId, useState } from "react";

import { AceptacionRequerida, NeuralError, neuralApi } from "../lib/neural";
import { ACEPTACION_TEXTOS } from "../lib/neuralLenguaSimple";
import { BOTON, CARD, Carga, ErrorCarga, Titulo, useCarga } from "./NeuralUI";

// Build-time switch (see docs/github-pages.md); literal on purpose so the bundler folds it.
const MODO_PAGES = process.env.NEXT_PUBLIC_MODO === "pages";
/** Pages: la aceptación vive solo en esta pestaña (sessionStorage); el servidor no la registra. */
const CLAVE_ACEPTACION_PAGES = "neural-aceptacion";

function aceptadaEnEstaPestana(version: string): boolean {
  try {
    return window.sessionStorage.getItem(CLAVE_ACEPTACION_PAGES) === version;
  } catch {
    return false;
  }
}

export function NeuralAceptacion({
  onAceptada, trasRechazo, onReintentar,
}: {
  onAceptada: () => void;
  /** Las pestañas respondieron «aceptación requerida» estando la puerta abierta. */
  trasRechazo: boolean;
  onReintentar: () => void;
}) {
  const [ronda, setRonda] = useState(0);
  const [aviso, setAviso] = useState<string | null>(null);
  const estado = useCarga(
    async (signal) => {
      try {
        return await neuralApi.aceptacion(signal);
      } catch (e) {
        // El endpoint de la puerta no debería exigir aceptación; si lo hiciera, se muestra como error con reintento.
        if (e instanceof AceptacionRequerida) throw new NeuralError(503, ACEPTACION_TEXTOS.errorCargar);
        throw e;
      }
    },
    [ronda],
  );
  const yaAceptada = estado.fase === "ok" && (estado.datos.aceptada || (MODO_PAGES && aceptadaEnEstaPestana(estado.datos.version)));
  useEffect(() => {
    if (yaAceptada && !trasRechazo) onAceptada();
  }, [yaAceptada, trasRechazo, onAceptada]);
  const versionCambio = useCallback(() => {
    setAviso(ACEPTACION_TEXTOS.versionCambio);
    setRonda((n) => n + 1);
  }, []);

  if (yaAceptada) {
    return trasRechazo ? (
      <ErrorCarga mensaje={ACEPTACION_TEXTOS.errorInconsistente} status={503} onReintentar={onReintentar} />
    ) : null;
  }
  return (
    <div className="space-y-3">
      {aviso ? <p role="alert" className="max-w-3xl text-sm text-ucn-tierra-clara">{aviso}</p> : null}
      <Carga estado={estado} filas={3}>
        {(d) => (
          <Declaracion key={`${ronda}-${d.version}`} version={d.version} texto={d.texto} onAceptada={onAceptada} onVersionCambio={versionCambio} />
        )}
      </Carga>
    </div>
  );
}

function Declaracion({
  version, texto, onAceptada, onVersionCambio,
}: { version: string; texto: string; onAceptada: () => void; onVersionCambio: () => void }) {
  const idCheck = useId();
  const [marcada, setMarcada] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const aceptar = async () => {
    setEnviando(true);
    setError(null);
    if (MODO_PAGES) {
      // Sitio publicado: solo lectura. Se recuerda en esta pestaña y no se envía nada al servidor.
      try { window.sessionStorage.setItem(CLAVE_ACEPTACION_PAGES, version); } catch { /* sin sessionStorage: se pedirá de nuevo al recargar */ }
      onAceptada();
      return;
    }
    try {
      await neuralApi.aceptar(version);
      onAceptada();
    } catch (e) {
      if (e instanceof AceptacionRequerida || (e instanceof NeuralError && e.status === 409)) {
        onVersionCambio(); // vuelve a pedir texto y versión vigentes; esta tarjeta se reemplaza (checkbox desmarcado)
        return;
      }
      setEnviando(false);
      setError(e instanceof NeuralError ? e.message : ACEPTACION_TEXTOS.errorGuardar);
    }
  };

  return (
    <section className={`${CARD} max-w-3xl space-y-4 p-4`} aria-label={ACEPTACION_TEXTOS.titulo}>
      <Titulo>{ACEPTACION_TEXTOS.titulo}</Titulo>
      <p className="whitespace-pre-line break-words text-base leading-7 text-[var(--portal-fg)]">{texto}</p>
      <div className="flex items-start gap-3">
        <input
          id={idCheck}
          type="checkbox"
          checked={marcada}
          onChange={(e) => setMarcada(e.target.checked)}
          className="mt-1 h-5 w-5 shrink-0 accent-[var(--ucn-azul-claro)]"
        />
        <label htmlFor={idCheck} className="cursor-pointer text-sm leading-6 text-[var(--portal-fg)]">
          {ACEPTACION_TEXTOS.confirmacion}
        </label>
      </div>
      {MODO_PAGES ? <p className="text-xs leading-5 text-[var(--portal-muted)]">En el sitio publicado esta aceptación no queda registrada.</p> : null}
      {error ? <p role="alert" className="text-sm text-ucn-tierra-clara">{error}</p> : null}
      <button type="button" disabled={!marcada || enviando} onClick={aceptar} className={`${BOTON} w-full sm:w-auto`}>
        {enviando ? ACEPTACION_TEXTOS.enviando : ACEPTACION_TEXTOS.boton}
      </button>
    </section>
  );
}
