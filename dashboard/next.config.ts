import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const apiUrl = process.env.API_URL || "http://127.0.0.1:8420";

const nextConfig: NextConfig = {
  output: process.env.STANDALONE === "true" ? "standalone" : undefined,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${isDev ? "http://127.0.0.1:8420" : apiUrl}/api/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${isDev ? "http://127.0.0.1:8420" : apiUrl}/ws/:path*`,
      },
    ];
  },
  ...(process.env.ROOBEN_PRO_DASHBOARD_DIR
    ? {
        webpack(config: any) {
          config.resolve.alias["@rooben-pro/dashboard"] =
            process.env.ROOBEN_PRO_DASHBOARD_DIR;
          return config;
        },
      }
    : {}),
};

export default nextConfig;
