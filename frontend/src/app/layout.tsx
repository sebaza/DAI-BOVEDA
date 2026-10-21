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

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
