"use client";

import { BovedaEmblema } from "./BovedaEmblema";
import { useEffect, useRef, useState } from "react";

import {
  devLogin,
  fetchAuthConfig,
  verifyGoogleCredential,
  type AuthConfig,
  type LoginResponse,
} from "../lib/session";

interface LoginScreenProps {
  aviso?: string;
  onAuthenticated: (respuesta: LoginResponse) => void;
}

interface GoogleIdentity {
  accounts: {
    id: {
      initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
}
declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

// Google Identity Services. Versionless endpoint that Google updates continuously, so it
// cannot carry an SRI hash (same documented exception as in the Torre).
const GSI_SRC = "https://accounts.google.com/gsi/client";
const GSI_POLL_MS = 250;
const GSI_POLL_MAX = 40; // ~10 s

function ensureGsiScript() {
  if (typeof document === "undefined" || window.google?.accounts?.id) return;
  if (document.querySelector(`script[src="${GSI_SRC}"]`)) return;
  const script = document.createElement("script");
  script.src = GSI_SRC;
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);
}

export function LoginScreen({ aviso, onAuthenticated }: LoginScreenProps) {
  const botonRef = useRef<HTMLDivElement | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [errorConfig, setErrorConfig] = useState(false);
  const [gsiListo, setGsiListo] = useState(false);
  const [gsiFallo, setGsiFallo] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(aviso ?? null);
  const [trabajando, setTrabajando] = useState(false);
  const [reintento, setReintento] = useState(0);

  // Backend auth config (client id, dev-login availability).
  useEffect(() => {
    let vivo = true;
    setErrorConfig(false);
    fetchAuthConfig()
      .then((c) => {
        if (vivo) setConfig(c);
      })
      .catch(() => {
        if (vivo) setErrorConfig(true);
      });
    return () => {
      vivo = false;
    };
  }, [reintento]);

  // Wait for the Google Identity Services script.
  useEffect(() => {
    if (!config?.google_oauth_enabled) return;
    setGsiFallo(false);
    if (window.google?.accounts?.id) {
      setGsiListo(true);
      return;
    }
    ensureGsiScript();
    let intentos = 0;
    const timer = window.setInterval(() => {
      intentos += 1;
      if (window.google?.accounts?.id) {
        window.clearInterval(timer);
        setGsiListo(true);
      } else if (intentos >= GSI_POLL_MAX) {
        window.clearInterval(timer);
        setGsiFallo(true);
      }
    }, GSI_POLL_MS);
    return () => window.clearInterval(timer);
  }, [config, reintento]);

  // Render the Google button once everything is ready.
  useEffect(() => {
    if (!gsiListo || !config?.google_oauth_enabled || !config.google_client_id) return;
    if (!botonRef.current || !window.google?.accounts?.id) return;
    botonRef.current.innerHTML = "";
    window.google.accounts.id.initialize({
      client_id: config.google_client_id,
      callback: async (respuesta) => {
        setTrabajando(true);
        setMensaje(null);
        try {
          onAuthenticated(await verifyGoogleCredential(respuesta.credential));
        } catch (error) {
          setMensaje(error instanceof Error ? error.message : "No se pudo validar la cuenta de Google.");
        } finally {
          setTrabajando(false);
        }
      },
    });
    window.google.accounts.id.renderButton(botonRef.current, {
      theme: "outline",
      size: "large",
      shape: "pill",
      text: "signin_with",
      logo_alignment: "left",
      width: 320,
      locale: "es",
    });
  }, [gsiListo, config, onAuthenticated]);

  async function entrarDev() {
    setTrabajando(true);
    setMensaje(null);
    try {
      onAuthenticated(await devLogin());
    } catch (error) {
      setMensaje(error instanceof Error ? error.message : "No se pudo iniciar sesión en modo desarrollo.");
    } finally {
      setTrabajando(false);
    }
  }

  const googleActivo = Boolean(config?.google_oauth_enabled);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <div className="boveda-madera w-full max-w-md overflow-hidden">
        <div className="boveda-banda h-7" aria-hidden="true" />
        <div className="p-6 md:p-8">
        <BovedaEmblema size={56} />
        <p className="boveda-kicker mt-4">Acceso restringido</p>
        <h1 className="portal-title mt-2 text-3xl font-bold text-[var(--portal-fg)]">Bóveda DAI</h1>
        <p className="mt-3 text-sm text-[var(--portal-muted)]">
          Bóveda de la Dirección de Análisis Institucional, reservada a la dirección universitaria. Contiene comentarios
          reales de la comunidad, por lo que solo pueden entrar las cuentas autorizadas por la DAI.
        </p>

        <div className="mt-6 flex flex-col gap-4">
          {errorConfig ? (
            <div className="flex flex-col gap-3 rounded-md border border-dashed border-[color-mix(in_srgb,var(--boveda-laton)_25%,transparent)] p-4 text-sm text-[var(--portal-muted)]">
              <span>No se pudo leer la configuración de acceso. Revisa que el servidor esté en marcha.</span>
              <button
                type="button"
                onClick={() => setReintento((n) => n + 1)}
                className="self-start rounded border border-[color-mix(in_srgb,var(--boveda-laton)_25%,transparent)] bg-white/[0.06] px-4 py-2 text-sm font-semibold text-[var(--portal-fg)] transition hover:bg-white/[0.12]"
              >
                Reintentar conexión
              </button>
            </div>
          ) : !config ? (
            <p className="text-sm text-[var(--portal-muted)]">Cargando…</p>
          ) : (
            <>
              {googleActivo ? (
                <>
                  <div ref={botonRef} />
                  {!gsiListo && !gsiFallo ? (
                    <p className="text-sm text-[var(--portal-muted)]">Cargando el botón de Google…</p>
                  ) : null}
                  {gsiFallo ? (
                    <div className="flex flex-col gap-2">
                      <p className="text-sm text-ucn-tierra-clara">No se pudo cargar el inicio de sesión de Google.</p>
                      <button
                        type="button"
                        onClick={() => setReintento((n) => n + 1)}
                        className="self-start rounded border border-[color-mix(in_srgb,var(--boveda-laton)_25%,transparent)] bg-white/[0.06] px-4 py-2 text-sm font-semibold text-[var(--portal-fg)] transition hover:bg-white/[0.12]"
                      >
                        Reintentar
                      </button>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="rounded-md border border-dashed border-[color-mix(in_srgb,var(--boveda-laton)_25%,transparent)] p-4 text-sm text-[var(--portal-muted)]">
                  {config.dev_login_enabled
                    ? "Google no está configurado (falta GOOGLE_CLIENT_ID). Puedes entrar en modo desarrollo."
                    : "El inicio de sesión con Google no está configurado en el servidor."}
                </p>
              )}

              {config.dev_login_enabled ? (
                <button
                  type="button"
                  onClick={() => void entrarDev()}
                  disabled={trabajando}
                  className="flex flex-col items-start rounded-md border border-[color-mix(in_srgb,var(--ucn-azul)_40%,transparent)] bg-[color-mix(in_srgb,var(--ucn-azul)_10%,transparent)] px-4 py-2 text-left font-semibold text-[var(--portal-fg)] transition hover:bg-[color-mix(in_srgb,var(--ucn-azul)_20%,transparent)] disabled:opacity-50"
                >
                  <span>Entrar en modo desarrollo</span>
                  <span className="text-sm font-normal text-[var(--ucn-azul-claro)]">Solo disponible con APP_ENV=dev</span>
                </button>
              ) : null}
            </>
          )}

          {mensaje ? (
            <p
              role="alert"
              className="rounded-md border border-[var(--alerta-media)] bg-[var(--ucn-tierra-suave)] px-4 py-3 text-sm text-ucn-tierra-clara"
            >
              {mensaje}
            </p>
          ) : null}
        </div>
        </div>
      </div>
    </main>
  );
}
