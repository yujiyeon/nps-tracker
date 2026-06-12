import type { NextConfig } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,

  // FastAPI Swagger UI를 웹 서비스 URL에서 접근 가능하도록 프록시
  async rewrites() {
    return [
      { source: "/docs", destination: `${API_BASE}/docs` },
      { source: "/redoc", destination: `${API_BASE}/redoc` },
      { source: "/openapi.json", destination: `${API_BASE}/openapi.json` },
    ];
  },
};

export default nextConfig;
