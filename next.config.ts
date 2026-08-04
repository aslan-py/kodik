import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: process.env.NODE_ENV === "production",
};



export default nextConfig;
