import type { NextConfig } from "next";

// Server-side proxy target for /api/* and /ws/*. In docker-compose this is
// the api service (NEXT_INTERNAL_API_URL=http://api:8420); in local dev it
// defaults to 127.0.0.1:8420. The browser always calls localhost:3000 and the
// Next server proxies — no CORS and no NEXT_PUBLIC_* leakage to the client.
const API_URL = process.env.NEXT_INTERNAL_API_URL || "http://127.0.0.1:8420";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/ws/:path*", destination: `${API_URL}/ws/:path*` },
    ];
  },
};

export default nextConfig;
