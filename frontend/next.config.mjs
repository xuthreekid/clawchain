/** @type {import('next').NextConfig} */
const nextConfig = {
  // Tauri 桌面 App 需要静态导出: TAURI_BUILD=1 next build
  ...(process.env.TAURI_BUILD === "1" ? { output: "export", distDir: "out" } : {}),
};

export default nextConfig;
