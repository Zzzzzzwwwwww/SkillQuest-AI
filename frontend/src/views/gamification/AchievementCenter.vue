<script setup lang="ts">
/*
 * 成就中心：已解锁 / 未解锁成就卡片墙
 */
import { computed, onMounted, ref } from "vue";
import { getAchievements } from "@/api/gamification";
import type { AchievementItem } from "@/types/gamification";

const loading = ref(false);
const view = ref<{ total: number; unlocked_count: number; items: AchievementItem[] }>({
  total: 0,
  unlocked_count: 0,
  items: [],
});

/** 成就图标映射（后端 icon 为语义 key） */
const ACHI_ICONS: Record<string, string> = {
  trophy: "🏆",
  calendar: "📅",
  chat: "💬",
  sword: "⚔️",
  star: "⭐",
  medal: "🎖️",
};

function iconText(icon: string): string {
  return ACHI_ICONS[icon] ?? icon.slice(0, 1).toUpperCase() ?? "★";
}

/** 成就展示顺序：已解锁在前，其余按 sort 顺序 */
const ordered = computed(() => {
  const items = [...view.value.items];
  items.sort((a, b) =>
    Number(b.unlocked) - Number(a.unlocked) || a.achievement_id - b.achievement_id
  );
  return items;
});

async function load(): Promise<void> {
  loading.value = true;
  try {
    view.value = await getAchievements();
  } catch {
    // 统一错误提示
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-container">
    <!-- 顶部统计 -->
    <el-card shadow="never" class="stat-card">
      <div class="stat-inner">
        <div>
          <h3 class="stat-title">成就中心</h3>
          <p class="stat-sub">每解锁一项成就都能收获专属 XP 奖励</p>
        </div>
        <div class="stat-right">
          <span class="stat-level">{{ view.unlocked_count }} / {{ view.total }}</span>
          <el-progress
            :percentage="view.total ? Math.round((view.unlocked_count / view.total) * 100) : 0"
            :stroke-width="8"
            :show-text="false"
            class="stat-bar"
          />
        </div>
      </div>
    </el-card>

    <div v-loading="loading" class="body">
      <template v-if="!ordered.length">
        <el-empty description="暂无成就数据" />
      </template>
      <el-row :gutter="16" v-else>
        <el-col
          v-for="a in ordered"
          :key="a.achievement_id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
          class="mb-16"
        >
          <el-card
            shadow="hover"
            class="achi-card"
            :class="{ unlocked: a.unlocked }"
          >
            <div class="achi-head">
              <div class="achi-icon">
                <span class="achi-icon-text">{{ iconText(a.icon) }}</span>
              </div>
              <el-tag v-if="a.unlocked" type="success" effect="dark" size="small">
                已解锁
              </el-tag>
              <el-tag v-else type="info" effect="plain" size="small">未解锁</el-tag>
            </div>
            <h4 class="achi-title">{{ a.title }}</h4>
            <p class="achi-desc">{{ a.description }}</p>
            <div class="achi-foot">
              <span class="achi-xp">+{{ a.xp_reward }} XP</span>
              <span v-if="a.unlocked && a.unlocked_at" class="achi-time">
                {{ a.unlocked_at.slice(0, 10) }}
              </span>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stat-card {
  border: none;
  border-radius: 16px;
  background: var(--sq-primary-gradient);
  color: #fff;
  margin-bottom: 16px;
}

.stat-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.stat-title {
  margin: 0 0 6px;
  font-size: 20px;
}

.stat-sub {
  margin: 0;
  opacity: 0.85;
  font-size: 13px;
}

.stat-right {
  min-width: 220px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-level {
  font-weight: 700;
  font-size: 16px;
  white-space: nowrap;
}

.stat-bar {
  flex: 1;
}

.body {
  min-height: 200px;
}

.mb-16 {
  margin-bottom: 16px;
}

.achi-card {
  border-radius: 14px;
  border: 1px solid #eceff5;
  transition: all 0.2s;

  &.unlocked {
    border-color: #67c23a55;
    background: linear-gradient(180deg, #f6ffed 0%, #ffffff 100%);
  }

  .achi-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }

  .achi-icon {
    width: 52px;
    height: 52px;
    border-radius: 12px;
    background: linear-gradient(135deg, #eef1ff 0%, #f8f9ff 100%);
    color: var(--sq-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 700;
  }

  .achi-title {
    margin: 10px 0 6px;
    font-size: 15px;
  }

  .achi-desc {
    margin: 0 0 12px;
    color: #6b7280;
    font-size: 12.5px;
    line-height: 1.6;
    min-height: 40px;
  }

  .achi-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-top: 1px dashed #eceff5;
    padding-top: 8px;
  }

  .achi-xp {
    color: #f59e0b;
    font-weight: 600;
    font-size: 13px;
  }

  .achi-time {
    color: #9ca3af;
    font-size: 12px;
  }
}
</style>