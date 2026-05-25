import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker 프로덕션 빌드: standalone 모드로 node_modules 최소화
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,
};

export default nextConfig;
