import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // In development, send /api to the local FastAPI server. On Vercel, the project's service
  // rewrites route /api to the Python backend instead.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    const api = process.env.API_DEV_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default nextConfig;
