/*
 * SkillQuest AI 前端路由
 * - 一级：/login /register 独立页；其余进入 BasicLayout
 * - 成长档案下设：个人中心 / 学习档案 / 学习记录 / 测评报告
 * - 全局守卫：未登录重定向登录页（redirect 回跳），已登录访问登录页跳首页
 */
import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import { useUserStore } from "@/store/user";

const routes: RouteRecordRaw[] = [
  // ---------- 独立页：登录 / 注册 ----------
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/auth/Login.vue"),
    meta: { title: "登录", public: true },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("@/views/auth/Register.vue"),
    meta: { title: "注册", public: true },
  },

  // ---------- 主布局 ----------
  {
    path: "/",
    component: () => import("@/layouts/BasicLayout.vue"),
    children: [
      {
        path: "",
        name: "Home",
        component: () => import("@/views/Home.vue"),
        meta: { title: "成长首页" },
      },
      {
        path: "career",
        name: "Career",
        component: () => import("@/views/Career.vue"),
        meta: { title: "职业探索" },
      },
      {
        path: "skill-tree",
        name: "SkillTree",
        component: () => import("@/views/SkillTree.vue"),
        meta: { title: "技能图谱" },
      },
      {
        path: "skill-tree/jobs",
        name: "JobSelect",
        component: () => import("@/views/skill/JobSelect.vue"),
        meta: { title: "岗位选择" },
      },
      {
        path: "adventure",
        name: "LearningPath",
        component: () => import("@/views/LearningPath.vue"),
        meta: { title: "冒险地图" },
      },
      {
        path: "adventure/:pathId",
        name: "LearningPathDetail",
        component: () => import("@/views/LearningPathDetail.vue"),
        meta: { title: "学习路径详情" },
      },
      {
        path: "tutor",
        name: "Tutor",
        component: () => import("@/views/Tutor.vue"),
        meta: { title: "AI 导师" },
      },
      // ---------- 游戏化（模块9） ----------
      {
        path: "achievements",
        name: "AchievementCenter",
        component: () => import("@/views/gamification/AchievementCenter.vue"),
        meta: { title: "成就中心" },
      },
      // ---------- 学习评估复盘（模块7） ----------
      {
        path: "exam",
        name: "ExamCenter",
        component: () => import("@/views/exam/ExamCenter.vue"),
        meta: { title: "阶段测评" },
      },
      {
        path: "exam/result/:id",
        name: "ExamResult",
        component: () => import("@/views/exam/ExamResult.vue"),
        meta: { title: "测评结果" },
      },
      {
        path: "mastery",
        name: "MasteryView",
        component: () => import("@/views/exam/MasteryView.vue"),
        meta: { title: "掌握度分析" },
      },
      {
        path: "report",
        name: "ReportCenter",
        component: () => import("@/views/exam/ReportCenter.vue"),
        meta: { title: "学习报告" },
      },
      // ---------- 职业测评与画像（模块3） ----------
      {
        path: "assessment",
        name: "Assessment",
        component: () => import("@/views/assessment/AssessmentCenter.vue"),
        meta: { title: "测评中心" },
      },
      {
        path: "assessment/answering",
        name: "AssessmentAnswering",
        component: () => import("@/views/assessment/Answering.vue"),
        meta: { title: "正在测评" },
      },
      {
        path: "assessment/result/:id",
        name: "AssessmentResult",
        component: () => import("@/views/assessment/ResultView.vue"),
        meta: { title: "测评结果" },
      },
      {
        path: "persona",
        name: "Persona",
        component: () => import("@/views/persona/Persona.vue"),
        meta: { title: "个人画像" },
      },
      // ---------- 成长档案（模块2 用户中心） ----------
      {
        path: "profile",
        name: "Profile",
        component: () => import("@/views/Profile.vue"),
        meta: { title: "成长档案" },
      },
      {
        path: "profile/center",
        name: "ProfileCenter",
        component: () => import("@/views/ProfileCenter.vue"),
        meta: { title: "个人中心" },
      },
      {
        path: "profile/archive",
        name: "ProfileArchive",
        component: () => import("@/views/Archive.vue"),
        meta: { title: "学习档案" },
      },
      {
        path: "profile/records",
        name: "ProfileRecords",
        component: () => import("@/views/Records.vue"),
        meta: { title: "学习记录" },
      },
      {
        path: "profile/reports",
        name: "ProfileReports",
        component: () => import("@/views/Reports.vue"),
        meta: { title: "测评报告" },
      },
    ],
  },
  // 兜底
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 全局前置守卫：登录态校验 + 标题
router.beforeEach((to, _from, next) => {
  const base = import.meta.env.VITE_APP_TITLE || "SkillQuest AI";
  document.title = `${(to.meta.title as string) ?? ""} · ${base}`;

  const userStore = useUserStore();
  const isPublic = Boolean(to.meta.public);

  if (!isPublic && !userStore.isLoggedIn) {
    // 未登录访问受限页：跳登录并携带回跳地址
    next({ path: "/login", query: to.fullPath === "/" ? {} : { redirect: to.fullPath } });
    return;
  }
  if (isPublic && userStore.isLoggedIn) {
    next({ path: "/" });
    return;
  }
  next();
});

export default router;