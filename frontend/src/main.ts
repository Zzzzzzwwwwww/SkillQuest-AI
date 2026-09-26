/*
 * SkillQuest AI 前端入口
 * 挂载：Element Plus、Pinia、Vue Router 与全局样式。
 */
import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import zhCn from "element-plus/es/locale/lang/zh-cn";

import App from "./App.vue";
import router from "./router";
import "./styles/index.scss";

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(ElementPlus, { locale: zhCn });

app.mount("#app");