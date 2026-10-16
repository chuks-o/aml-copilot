import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle for the Docker image (web/Dockerfile).
  output: "standalone",
};

export default config;
