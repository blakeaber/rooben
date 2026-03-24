import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: "http://127.0.0.1:8420/api/:path*",
            },
            {
              source: "/ws/:path*",
              destination: "http://127.0.0.1:8420/ws/:path*",
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
