import type { NextConfig } from "next";

/**
 * Same-origin deployment: the browser only ever talks to this origin. Next proxies the
 * PIIShield API and the health probes to the API service, so there is no CORS to manage.
 * In production a load balancer may route /api/v1 straight to the API before it reaches
 * Next.
 */
const apiInternal = (process.env.API_INTERNAL_URL || "http://localhost:5530").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  // One self-contained server bundle (`node server.js`), the unit a container image ships.
  output: "standalone",
  outputFileTracingRoot: __dirname,
  poweredByHeader: false,
  devIndicators: false,
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${apiInternal}/api/v1/:path*` },
      { source: "/healthz", destination: `${apiInternal}/healthz` },
      { source: "/readyz", destination: `${apiInternal}/readyz` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
