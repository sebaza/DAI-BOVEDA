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

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not let `next dev` generate an AGENTS.md at the repo.
  agentRules: false,
  // Pin the workspace root: Next infers it from lockfiles found upwards, and a stray
  // package-lock.json in the home folder would make it pick the wrong one.
  turbopack: { root: __dirname },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
