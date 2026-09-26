<script setup lang="ts">
/*
 * 成长档案（模块2 入口页）
 * 提供四个入口：个人中心 / 学习档案 / 学习记录 / 测评报告
 */
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { User, Trophy, List, Document } from "@element-plus/icons-vue";
import { useUserStore } from "@/store/user";

const router = useRouter();
const userStore = useUserStore();
const loaded = ref(false);

const entries = [
  { path: "/profile/center", title: "个人中心", desc: "编辑个人信息与学习偏好", icon: User },
  { path: "/profile/archive", title: "学习档案", desc: "目标岗位 / 等级 / XP / 学习统计", icon: Trophy },
  { path: "/profile/records", title: "学习记录", desc: "历史学习轨迹流水", icon: List },
  { path: "/profile/reports", title: "测评报告", desc: "职业画像 / 阶段复盘报告", icon: Document },
];

onMounted(async () => {
  // 刷新后保持登录：校验并恢复会话
  await userStore.restoreSession();
  loaded.value = true;
});
</script>

<template>
  <div class="page-container">
    <el-card shadow="never" class="banner-card">
      <div class="banner-inner">
        <div>
          <h3 class="banner-title">
            {{ userStore.user?.username || "冒险者" }} 的成长档案
          </h3>
          <p class="banner-sub">
            {{ userStore.profile?.job_intention || "目标岗位待设置" }} ·
            每日计划学习 {{ userStore.profile?.daily_study_time ?? 30 }} 分钟
          </p>
        </div>
        <el-tag round effect="dark" size="large">
          {{
            userStore.isLoggedIn
              ? userStore.user?.email || "已登录"
              : "加载中…"
          }}
        </el-tag>
      </div>
    </el-card>

    <el-row :gutter="16" class="mt-16" v-loading="!loaded">
      <el-col
        v-for="item in entries"
        :key="item.path"
        :xs="24"
        :sm="12"
        :md="6"
        class="mb-16"
      >
        <el-card
          shadow="hover"
          class="entry-card"
          @click="router.push(item.path)"
        >
          <el-icon :size="34" class="entry-icon">
            <component :is="item.icon" />
          </el-icon>
          <h4 class="entry-title">{{ item.title }}</h4>
          <p class="entry-desc">{{ item.desc }}</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.banner-card {
  border: none;
  border-radius: 16px;
  background: var(--sq-primary-gradient);
  color: #fff;
}

.banner-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.banner-title {
  margin: 0 0 6px;
  font-size: 20px;
}

.banner-sub {
  margin: 0;
  opacity: 0.85;
  font-size: 13px;
}

.mt-16 {
  margin-top: 16px;
}

.mb-16 {
  margin-bottom: 16px;
}

.entry-card {
  border-radius: 12px;
  border: none;
  cursor: pointer;
  text-align: center;
  padding: 8px 0;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-4px);
  }
}

.entry-icon {
  color: var(--sq-primary);
}

.entry-title {
  margin: 10px 0 6px;
}

.entry-desc {
  margin: 0;
  font-size: 12px;
  color: #9099a8;
}
</style>