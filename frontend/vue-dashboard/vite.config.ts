import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/echarts")) return "echarts";
          if (id.includes("node_modules")) return "vendor";
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 9000,
  },
});
