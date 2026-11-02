import "./globals.css";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { SessionProvider } from "../lib/SessionProvider";

export const metadata: Metadata = {
  title: "Bóveda DAI",
  description: "Bóveda de la Dirección de Análisis Institucional UCN. Acceso restringido.",
  // The vault is private: keep it out of search engines.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

/**
 * Pages mode only: CSP delivered via <meta> (GitHub Pages cannot set headers). Notes:
 *  - script-src needs 'unsafe-inline': the static export inlines the Next bootstrap / flight
 *    data scripts (their content changes per build, so hashes would need a post-build step).
 *  - style-src needs 'unsafe-inline': React `style={{}}` attributes and Next's inline styles.
 *  - Google Fonts (CSS import in globals.css) and ECharts from jsDelivr are the only third parties.
 *  - `frame-ancestors` is ignored in <meta>; it cannot be enforced from here.
 */
function cspPages(): string {
  let api = "";
  try {
    api = new URL(process.env.NEXT_PUBLIC_API_BASE_URL ?? "").origin;
  } catch {
    /* build-pages.mjs refuses to build without a valid API URL */
  }
  return [
    "default-src 'self'",
    `connect-src 'self' ${api}`.trim(),
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      {/* Literal env expression so the local build drops this block. */}
      {process.env.NEXT_PUBLIC_MODO === "pages" ? (
        <head>
          <meta name="referrer" content="strict-origin-when-cross-origin" />
          <meta httpEquiv="Content-Security-Policy" content={cspPages()} />
        </head>
      ) : null}
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
