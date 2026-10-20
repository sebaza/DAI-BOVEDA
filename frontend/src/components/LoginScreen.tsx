"use client";

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
    <main className="flex min-h-screen items-center justify-center px-6 py-10">
      <div className="portal-panel-strong w-full max-w-md p-6 md:p-8">
        <p className="portal-pill">Acceso restringido</p>
        <h1 className="portal-title mt-4 text-3xl font-bold text-white">Bóveda DAI</h1>
        <p className="mt-3 text-sm leading-7 text-slate-400">
          Termómetro Institucional de la Dirección de Análisis Institucional. Contiene comentarios
          reales de la comunidad, por lo que solo pueden entrar las cuentas autorizadas por la DAI.
        </p>

        <div className="mt-6 flex flex-col gap-4">
          {errorConfig ? (
            <div className="flex flex-col gap-3 rounded-3xl border border-dashed border-white/10 p-4 text-sm text-slate-400">
              <span>No se pudo leer la configuración de acceso. Revisa que el servidor esté en marcha.</span>
              <button
                type="button"
                onClick={() => setReintento((n) => n + 1)}
                className="self-start rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/[0.12]"
              >
                Reintentar conexión
              </button>
            </div>
          ) : !config ? (
            <p className="text-sm text-slate-400">Cargando…</p>
          ) : (
            <>
              {googleActivo ? (
                <>
                  <div ref={botonRef} />
                  {!gsiListo && !gsiFallo ? (
                    <p className="text-sm text-slate-400">Cargando el botón de Google…</p>
                  ) : null}
                  {gsiFallo ? (
                    <div className="flex flex-col gap-2">
                      <p className="text-sm text-rose-200">No se pudo cargar el inicio de sesión de Google.</p>
                      <button
                        type="button"
                        onClick={() => setReintento((n) => n + 1)}
                        className="self-start rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/[0.12]"
                      >
                        Reintentar
                      </button>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="rounded-3xl border border-dashed border-white/10 p-4 text-sm text-slate-400">
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
                  className="flex flex-col items-start rounded-2xl border border-cyan-400/25 bg-cyan-400/10 px-4 py-2 text-left font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:opacity-50"
                >
                  <span>Entrar en modo desarrollo</span>
                  <span className="text-xs font-normal text-cyan-200/70">Solo disponible con APP_ENV=dev</span>
                </button>
              ) : null}
            </>
          )}

          {mensaje ? (
            <p
              role="alert"
              className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100"
            >
              {mensaje}
            </p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
