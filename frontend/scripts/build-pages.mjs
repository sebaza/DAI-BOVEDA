// Builds the static export for GitHub Pages (NEXT_PUBLIC_MODO=pages) in a cross-platform way
// (no cross-env needed). Output goes to ./out. See docs/github-pages.md.
//
// Env hygiene: Next also loads frontend/.env.local and never overrides variables that are
// already defined, so this script pins everything that must not leak into a PUBLIC bundle.
//   - NEXT_PUBLIC_API_BASE_URL: required, https, not loopback (unless PAGES_PERMITIR_LOCAL=1).
//   - NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL: forced to PAGES_FEEDBACK_URL, or empty.
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

function fallar(msg) {
  console.error(`build:pages: ${msg}`);
  process.exit(1);
}

const permitirLocal = process.env.PAGES_PERMITIR_LOCAL === "1";
const bruta = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim();
if (!bruta) fallar("define NEXT_PUBLIC_API_BASE_URL (URL de wh-api, https).");
let url;
try {
  url = new URL(bruta);
} catch {
  fallar("NEXT_PUBLIC_API_BASE_URL no es una URL válida.");
}
const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
const esLoopback = host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".localhost");
if (esLoopback && !permitirLocal) {
  fallar("NEXT_PUBLIC_API_BASE_URL apunta a localhost; usa la URL pública o PAGES_PERMITIR_LOCAL=1 para pruebas.");
}
if (url.protocol !== "https:" && !(permitirLocal && esLoopback && url.protocol === "http:")) {
  fallar("NEXT_PUBLIC_API_BASE_URL debe ser https.");
}
console.log(`build:pages: API origin = ${url.origin}`);

const require = createRequire(import.meta.url);
const nextBin = require.resolve("next/dist/bin/next");
const r = spawnSync(process.execPath, [nextBin, "build", "--webpack"], {
  stdio: "inherit",
  env: {
    ...process.env,
    NEXT_PUBLIC_MODO: "pages",
    NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL: process.env.PAGES_FEEDBACK_URL ?? "",
  },
});
process.exit(r.status ?? 1);
