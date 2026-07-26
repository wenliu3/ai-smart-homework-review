import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

// Vitest 配置：复用 vite 别名，并对 CSS/SCSS 导入返回空模块，
// 避免 element-plus 等库的样式导入阻断测试。
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    // jsdom：组件挂载与 DOMPurify 都依赖 DOM
    environment: "jsdom",
    include: ["src/**/__tests__/**/*.spec.ts"],
    setupFiles: ["./src/__tests__/setup.ts"],
    // 静默处理 CSS/SCSS 导入
    server: {
      deps: {
        inline: [/element-plus/, /@element-plus/],
      },
    },
  },
  css: {
    // 让 vite 把 css 当作空模块处理
    preprocessorOptions: {},
  },
  // 兜底：所有 css/scss 导入返回空字符串
  plugins: [
    vue(),
    {
      name: "stub-css",
      enforce: "pre",
      resolveId(id) {
        if (/\.(css|scss|sass|less|styl)$/.test(id)) {
          return { id: "\0stub.css", external: false };
        }
        return null;
      },
      load(id) {
        if (id === "\0stub.css") return "";
        return null;
      },
    },
  ],
});
