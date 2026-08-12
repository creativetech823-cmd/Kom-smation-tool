import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lets the Next.js dev server accept requests coming through an ngrok tunnel
  // (otherwise it blocks cross-origin dev requests by default).
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok-free.dev", "*.ngrok.io", "*.ngrok.app"],
  // Free ngrok accounts only allow one online tunnel at a time, so instead of a
  // second public tunnel for the backend, the Next.js server proxies API calls to
  // it locally — the browser only ever talks to the single tunneled frontend origin.
  async rewrites() {
    return [
      {
        source: "/backend-api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
