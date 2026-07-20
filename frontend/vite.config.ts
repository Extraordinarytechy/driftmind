import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  publicDir: mode === "production" ? false : "public",
  build: {
    outDir: "frontend-dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const moduleId = id.replaceAll("\\", "/");

          if (/\/node_modules\/(react|react-dom|scheduler)\//.test(moduleId)) return "react";
          if (moduleId.includes("/node_modules/lucide-react/")) return "icons";
          if (
            /\/node_modules\/(@radix-ui\/react-slot|class-variance-authority|clsx|tailwind-merge)\//.test(
              moduleId,
            )
          ) {
            return "ui";
          }
        },
      },
    },
  },
}));