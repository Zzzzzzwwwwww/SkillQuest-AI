<script setup lang="ts">
/*
 * 学习档案页：目标岗位、等级、XP、学习统计
 * 数据来源 GET /users/learning-archive（统计由后端规则计算）
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Clock, Document, Finished } from "@element-plus/icons-vue";
import { getLearningArchive } from "@/api/user";
import type { ArchiveOverview } from "@/types/user";

const router = useRouter();
const loading = ref(true);
const archive = ref<ArchiveOverview | null>(null);

/** XP 进度（当前等级内进度百分比，规则计算） */
const xpProgress = computed(() => {
  if (!archive.value) return 0;
  const nextNeed = archive.value.xp_to_next_level;
  return nextNeed <= 0 ? 100 : 0;
});

const stats = computed(() => [
  { label: "学习记录", value: archive.value?.total_records ?? 0, icon: Document },
  { label: "累计时长", value: formatDuration(archive.value?.total_duration ?? 0), icon: Clock },
  { label: "完成任务", value: archive.value?.finished_count ?? 0, icon: Finished },
]);

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h${m}m` : `${m}min`;
}

onMounted(async () => {
  try {
    archive.value = await getLearningArchive();
  } catch {
    archive.value = null;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="page-container" v-loading="loading">
    <template v-if="archive">
      <!-- 冒险者状态 -->
      <el-card shadow="never" class="hero-card">
        <div class="hero-inner">
          <div class="hero-left">
            <h3 class="hero-title">{{ archive.archive_name }}</h3>
            <p class="hero-sub">
              目标岗位：
              <el-tag effect="plain" round size="small" type="primary">
                {{ archive.target_job || "待设置" }}
              </el-tag>
            </p>
          </div>
          <div class="hero-level">
            <span class="level-badge">Lv.{{ archive.current_level }}</span>
            <span class="xp-text">{{ archive.total_xp }} XP</span>
          </div>
        </div>
        <el-progress
          :percentage="xpProgress"
          :stroke-width="10"
          :show-text="false"
          class="xp-bar"
        />
        <p class="xp-hint">
          距下一等级还需 {{ archive.xp_to_next_level }} XP
        </p>
      </el-card>

      <!-- 学习统计 -->
      <el-row :gutter="16" class="mt-16">
        <el-col v-for="s in stats" :key="s.label" :xs="24" :sm="8" class="mb-16">
          <el-card shadow="hover" class="stat-card">
            <el-icon :size="26" class="stat-icon" :class="'stat-' + s.label">
              <component :is="s.icon" />
            </el-icon>
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="hover" class="mt-16 action-card">
        <div class="action-inner">
          <span>查看你的完整学习轨迹与测评报告</span>
          <el-button type="primary" plain @click="router.push('/profile/records')">
            学习记录
          </el-button>
          <el-button type="primary" plain @click="router.push('/profile/reports')">
            测评报告
          </el-button>
        </div>
      </el-card>
    </template>

    <el-empty v-else description="学习档案尚未初始化，请重新登录" />
  </div>
</template>

<style scoped lang="scss">
.hero-card {
  border: none;
  border-radius: 16px;
  background: var(--sq-primary-gradient);
  color: #fff;
}

.hero-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.hero-title {
  margin: 0 0 8px;
  font-size: 20px;
}

.hero-sub {
  margin: 0;
  font-size: 13px;
  opacity: 0.9;
}

.hero-level {
  display: flex;
  align-items: center;
  gap: 12px;
}

.level-badge {
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 14px;
  border-radius: 20px;
  font-weight: 700;
  font-size: 16px;
}

.xp-text {
  font-weight: 600;
}

.xp-bar {
  margin-top: 18px;
}

.xp-hint {
  margin: 8px 0 0;
  text-align: right;
  font-size: 12px;
  opacity: 0.85;
}

.mt-16 {
  margin-top: 16px;
}

.mb-16 {
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 12px;
  border: none;
  text-align: center;
}

.stat-icon {
  color: var(--sq-primary);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  margin: 6px 0 2px;
}

.stat-label {
  font-size: 13px;
  color: #9099a8;
}

.action-card {
  border-radius: 12px;
  border: none;
}

.action-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
</style>