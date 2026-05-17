import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/echarts/core")) return "echarts-core";
          if (id.includes("node_modules/echarts/renderers")) return "echarts-renderers";
          if (id.includes("node_modules/echarts/components")) return "echarts-components";
          if (id.includes("node_modules/echarts/charts")) return "echarts-charts";
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
