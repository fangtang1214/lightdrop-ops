import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("antd") || id.includes("@ant-design") || id.includes("rc-")) {
            return "antd-vendor";
          }
          if (id.includes("lucide-react")) return "icons-vendor";
          return "vendor";
        },
      },
    },
  },
});
