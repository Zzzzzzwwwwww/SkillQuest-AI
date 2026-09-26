<script setup lang="ts">
/*
 * 基础布局：左侧侧边栏 + 顶部栏 + 内容区
 * - 侧边栏菜单与路由联动高亮
 * - 移动端（<768px）自动切换为抽屉模式，配合汉堡按钮展开
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ChatDotRound,
  Compass,
  Connection,
  MapLocation,
  Medal,
  Operation,
  Trophy,
  UserFilled,
} from "@element-plus/icons-vue";
import { useUserStore } from "@/store/user";

interface SubMenuItem {
  path: string;
  title: string;
}

interface MenuItem {
  path: string;
  title: string;
  icon: Component;
  children?: SubMenuItem[];
}

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

/** 侧边栏菜单配置（成长档案为子菜单） */
const menus: MenuItem[] = [
  { path: "/", title: "成长首页", icon: UserFilled },
  { path: "/achievements", title: "成就中心", icon: Medal },
  { path: "/career", title: "职业探索", icon: Compass },
  {
    path: "/skill-tree",
    title: "技能图谱",
    icon: Connection,
    children: [
      { path: "/skill-tree/jobs", title: "岗位选择" },
      { path: "/skill-tree", title: "技能图谱" },
    ],
  },
  { path: "/adventure", title: "冒险地图", icon: MapLocation },
  { path: "/tutor", title: "AI 导师", icon: ChatDotRound },
  {
    path: "/exam",
    title: "学习评估",
    icon: Trophy,
    children: [
      { path: "/exam", title: "阶段测评" },
      { path: "/mastery", title: "掌握度分析" },
      { path: "/report", title: "学习报告" },
    ],
  },
  {
    path: "/assessment",
    title: "职业测评",
    icon: Operation,
    children: [
      { path: "/assessment", title: "测评中心" },
      { path: "/persona", title: "个人画像" },
    ],
  },
  {
    path: "/profile",
    title: "成长档案",
    icon: Trophy,
    children: [
      { path: "/profile/center", title: "个人中心" },
      { path: "/profile/archive", title: "学习档案" },
      { path: "/profile/records", title: "学习记录" },
      { path: "/profile/reports", title: "测评报告" },
    ],
  },
];

/** 当前激活菜单（根据路径精确匹配，父子均由 Element Plus 处理展开） */
const activeMenu = computed(() => route.path);

/** 当前路由标题 */
const currentTitle = computed(
  () => (route.meta.title as string) || "SkillQuest AI"
);

// ---------- 移动端适配 ----------
const isMobile = ref(false);
const drawerVisible = ref(false);

function handleResize(): void {
  isMobile.value = window.innerWidth < 768;
}

function onSelectMenu(path: string): void {
  drawerVisible.value = false;
  router.push(path);
}

onMounted(() => {
  handleResize();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
});
</script>

<template>
  <el-container class="sq-layout">
    <!-- 桌面端侧边栏 -->
    <el-aside v-if="!isMobile" width="220px" class="sq-aside">
      <div class="sq-logo" @click="router.push('/')">
        <span class="sq-logo-mark">S</span>
        <span class="sq-logo-text">SkillQuest AI</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="transparent"
        text-color="#aeb6d4"
        active-text-color="#ffffff"
        class="sq-menu"
      >
        <template v-for="item in menus" :key="item.path">
          <el-menu-item
            v-if="!item.children"
            :index="item.path"
            @click="onSelectMenu(item.path)"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
          <el-sub-menu v-else :index="item.path">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              :key="child.path"
              :index="child.path"
              @click="onSelectMenu(child.path)"
            >
              {{ child.title }}
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <!-- 移动端抽屉 -->
    <el-drawer
      v-if="isMobile"
      v-model="drawerVisible"
      direction="ltr"
      size="220px"
      :with-header="false"
      class="sq-drawer"
    >
      <div class="sq-logo">
        <span class="sq-logo-mark">S</span>
        <span class="sq-logo-text">SkillQuest AI</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="transparent"
        text-color="#aeb6d4"
        active-text-color="#ffffff"
        class="sq-menu"
      >
        <template v-for="item in menus" :key="item.path">
          <el-menu-item
            v-if="!item.children"
            :index="item.path"
            @click="onSelectMenu(item.path)"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
          <el-sub-menu v-else :index="item.path">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              :key="child.path"
              :index="child.path"
              @click="onSelectMenu(child.path)"
            >
              {{ child.title }}
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-drawer>

    <el-container class="sq-main-wrap">
      <!-- 顶部栏 -->
      <el-header class="sq-header">
        <div class="sq-header-left">
          <el-icon
            v-if="isMobile"
            class="sq-burger"
            :size="22"
            @click="drawerVisible = true"
          >
            <Operation />
          </el-icon>
          <h2 class="sq-header-title">{{ currentTitle }}</h2>
        </div>
        <div class="sq-header-right">
          <el-tag effect="plain" round size="small" class="sq-domain-tag">
            AI 应用开发工程师
          </el-tag>
          <el-avatar
            :size="32"
            class="sq-avatar"
            @click="router.push('/profile/center')"
          >
            {{ userStore.user?.username?.slice(0, 1)?.toUpperCase() || "旅" }}
          </el-avatar>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="sq-content">
        <router-view />
      </el-main>

      <el-footer class="sq-footer" height="auto">
        SkillQuest AI v0.1.0 · 基于华为云盘古大模型（预览框架）
      </el-footer>
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
.sq-layout {
  height: 100vh;
  overflow: hidden;
}

/* 侧边栏 */
.sq-aside {
  background: linear-gradient(180deg, #1e2447 0%, #161a33 100%);
  display: flex;
  flex-direction: column;
}

.sq-menu {
  flex: 1;
  border-right: none;
  :deep(.el-menu-item) {
    height: 46px;
    margin: 4px 10px;
    border-radius: 8px;
    &.is-active {
      background: var(--sq-primary-gradient);
      box-shadow: 0 4px 12px rgba(79, 110, 247, 0.4);
    }
    &:hover {
      color: #fff;
    }
  }
}

/* Logo */
.sq-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px;
  cursor: pointer;
}

.sq-logo-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--sq-primary-gradient);
  color: #fff;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sq-logo-text {
  color: #fff;
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
}

/* 主区域 */
.sq-main-wrap {
  min-width: 0;
}

/* 顶部栏 */
.sq-header {
  height: var(--sq-header-height);
  background: #fff;
  border-bottom: 1px solid #eceff5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.sq-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sq-burger {
  cursor: pointer;
  color: #5a607f;
}

.sq-header-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}

.sq-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sq-avatar {
  background: var(--sq-primary-gradient);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

/* 内容区 */
.sq-content {
  overflow-y: auto;
  padding: 0;
  background: transparent;
}

.sq-footer {
  text-align: center;
  color: #98a1b3;
  font-size: 12px;
  padding: 10px 0;
  border-top: 1px solid #eceff5;
  background: #fff;
}

/* 移动端 */
@media (max-width: 768px) {
  .sq-domain-tag {
    display: none;
  }
  .sq-header {
    padding: 0 12px;
  }
}
</style>