import type { NextConfig } from "next";

// Security headers. No strict CSP on purpose: the app loads Google Identity Services
// (accounts.google.com), ECharts from jsDelivr (with SRI) and Google Fonts. If a CSP is
// added later, allow exactly those origins plus NEXT_PUBLIC_API_BASE_URL in connect-src.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
];

// NEXT_PUBLIC_MODO=pages -> static export for GitHub Pages (read-only, PIN access, no local
// backend). Any other value keeps the local mode exactly as before. See docs/github-pages.md.
const modoPages = process.env.NEXT_PUBLIC_MODO === "pages";
const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").trim().replace(/\/+$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not let `next dev` generate an AGENTS.md at the repo.
  agentRules: false,
  // Pin the workspace root: Next infers it from lockfiles found upwards, and a stray
  // package-lock.json in the home folder would make it pick the wrong one.
  turbopack: { root: __dirname },
  ...(modoPages
    ? {
        // `headers()` is not supported with a static export: the host (Pages) sets headers.
        output: "export" as const,
        trailingSlash: true,
        images: { unoptimized: true },
        ...(basePath ? { basePath, assetPrefix: basePath } : {}),
      }
    : {
        async headers() {
          return [{ source: "/:path*", headers: securityHeaders }];
        },
      }),
};

export default nextConfig;
