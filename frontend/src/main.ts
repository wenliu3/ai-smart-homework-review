import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import * as ElementPlusIconsVue from "@element-plus/icons-vue";
import App from "./App.vue";
import router from "./router";
import store from "@/store";
import "./router/permission"; // 引入路由权限控制
// 引入wangEditor的css
import "@wangeditor/editor/dist/css/style.css";
// 引入 wangeditor 的补充样式
// wangeditor获取的是html标签没有内联样式-回显要和编辑器一样，需要引入自定义样式文件
import "@/assets/wangEidtAdd.css";
// 引入自适应表格样式
import "@/assets/styles/adaptive-table.css";
// 配置moment中文语言包
import moment from "moment";
import "moment/locale/zh-cn";
import zhCn from 'element-plus/es/locale/lang/zh-cn'  // 引入中文语言包
moment.locale("zh-cn");

// 创建Vue应用实例
const app = createApp(App);

// 全局错误处理 - 防止白屏
app.config.errorHandler = (err, vm, info) => {
  console.error("Vue全局错误:", err, info);
  // 在开发环境显示错误
  if (import.meta.env.DEV) {
    console.error("错误堆栈:", err);
  }
};

// 处理未捕获的Promise错误
window.addEventListener("unhandledrejection", (event) => {
  console.error("未处理的Promise拒绝:", event.reason);
  // 阻止浏览器的默认行为（在控制台显示错误）
  // event.preventDefault()
});

// 注册Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

// 挂载Vuex
app.use(store);

// 挂载路由
app.use(router);

// 挂载Element Plus
app.use(ElementPlus, {
  locale: zhCn,   // 告诉 Element Plus：用中文
})

// 挂载应用
app.mount("#app");
