<script setup lang="ts">
/*
 * 成长首页（模块9 游戏化）
 * 展示：等级/段位/XP 进度 / 每日打卡 / 今日任务 / 番茄钟 / 成就简览 / XP 流水
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  checkinToday,
  completeDailyTask,
  completePomodoro,
  getGamificationOverview,
} from "@/api/gamification";
import type {
  AchievementItem,
  DailyTaskItem,
  GamificationOverview,
} from "@/types/gamification";

const router = useRouter();
const loading = ref(false);
const checking = ref(false);
const pomodoroVisible = ref(false);
const pomodoroSubmitting = ref(false);
const finishedTaskIds = ref<string[]>([]);

const blank = (): GamificationOverview => ({
  level: 1,
  tier_key: "bronze",
  tier_label: "青铜",
  tier_index: 0,
  tier_percent: 0,
  total_xp: 0,
  xp_to_next_level: 50,
  today_xp: 0,
  streak: 0,
  checked_in_today: false,
  pomodoro: { session_count: 0, focus_total_minutes: 0 },
  daily_tasks: [],
  achievements: { total: 0, unlocked_count: 0, items: [] },
  recent_xp_logs: [],
});

const overview = ref<GamificationOverview>(blank());

/** 等级/段位展示 */
const levelText = computed(() => `Lv.${overview.value.level}`);
const tierLabel = computed(() => overview.value.tier_label);

/** 升级进度条百分比（当前等级起点→下一等级起点的累计 XP 区间） */
const xpPercent = computed(() => {
  const level = overview.value.level;
  const total = overview.value.total_xp;
  const curCum = 50 * level * (level - 1);
  const nextCum = 50 * (level + 1) * level;
  const span = nextCum - curCum;
  if (span <= 0) return 100;
  const pct = ((total - curCum) / span) * 100;
  return Math.min(100, Math.max(2, Math.round(pct)));
});

/** 成就简览（展示前 4 个，点击进成就中心） */
const previewAchievements = computed<AchievementItem[]>(() => {
  const items = [...overview.value.achievements.items];
  items.sort(
    (a, b) =>
      Number(b.unlocked) - Number(a.unlocked) || a.achievement_id - b.achievement_id
  );
  return items.slice(0, 4);
});

/** 任务完成态：本地已完成的优先标记 */
function taskDone(task: DailyTaskItem): boolean {
  return finishedTaskIds.value.includes(task.task_id);
}

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

async function load(): Promise<void> {
  loading.value = true;
  try {
    overview.value = await getGamificationOverview();
  } catch {
    // 统一错误提示
  } finally {
    loading.value = false;
  }
}

async function onCheckin(): Promise<void> {
  checking.value = true;
  try {
    const res = await checkinToday();
    ElMessage.success(res.message || "打卡成功");
    await load();
  } catch {
    // 统一错误提示
  } finally {
    checking.value = false;
  }
}

async function onCompleteTask(task: DailyTaskItem): Promise<void> {
  try {
    const res = await completeDailyTask(task.task_id);
    if (res.already_done) {
      ElMessage.info(res.message || "该任务已完成");
    } else {
      ElMessage.success(res.message || `任务完成 +${res.xp_amount} XP`);
    }
    if (!res.already_done) {
      finishedTaskIds.value.push(task.task_id);
    }
    await load();
  } catch {
    // 统一错误提示
  }
}

async function onPomodoro(mode: "focus" | "deep"): Promise<void> {
  pomodoroSubmitting.value = true;
  try {
    const res = await completePomodoro({ mode });
    ElMessage.success(`${res.message} +${res.xp_amount} XP`);
    pomodoroVisible.value = false;
    await load();
  } catch {
    // 统一错误提示
  } finally {
    pomodoroSubmitting.value = false;
  }
}

function fmtLogTime(t: string): string {
  return t ? t.replace("T", " ").slice(5, 16) : "";
}

onMounted(load);
</script>

<template>
  <div class="page-container">
    <!-- 冒险者状态栏 -->
    <el-card shadow="never" class="hero-card">
      <div v-loading="loading" class="hero-inner">
        <div class="hero-left">
          <h3 class="hero-title">
            欢迎回来，AI 应用开发新手
            <el-tag class="tier-tag" effect="dark" round>{{ tierLabel }}</el-tag>
          </h3>
          <p class="hero-sub">
            今日冒险即将开始
            <template v-if="overview.streak > 0">
              · 已连续学习 {{ overview.streak }} 天
            </template>
          </p>
          <div class="hero-lv-line">
            <span class="hero-level">{{ levelText }}</span>
            <el-progress
              :percentage="xpPercent"
              :stroke-width="8"
              :show-text="false"
              class="hero-xp"
            />
            <span class="hero-xp-text">{{ overview.total_xp }} XP</span>
          </div>
        </div>
        <div class="hero-right">
          <div class="hero-stat">
            <span class="hero-stat-num">{{ overview.today_xp }}</span>
            <span class="hero-stat-label">今日 XP</span>
          </div>
          <el-button
            type="primary"
            size="large"
            round
            :disabled="overview.checked_in_today"
            :loading="checking"
            class="checkin-btn"
            @click="onCheckin"
          >
            {{ overview.checked_in_today ? "今日已打卡" : "每日打卡 +10 XP" }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16" class="mt-16">
      <!-- 今日任务 -->
      <el-col :xs="24" :sm="24" :md="12" class="mb-16">
        <el-card shadow="hover" class="block-card" body-class="task-body">
          <template #header>
            <div class="card-header">
              <b>今日任务</b>
              <el-tag size="small" effect="plain" round>
                {{ overview.daily_tasks.length }} 项
              </el-tag>
            </div>
          </template>
          <div v-loading="loading" class="task-list">
            <template v-if="overview.daily_tasks.length">
              <div
                v-for="task in overview.daily_tasks"
                :key="task.task_id"
                class="task-item"
              >
                <div class="task-info">
                  <p class="task-title">{{ task.title }}</p>
                  <p class="task-detail">{{ task.detail }}</p>
                </div>
                <div class="task-right">
                  <span class="task-xp">+{{ task.xp }} XP</span>
                  <el-button
                    size="small"
                    :type="taskDone(task) ? 'success' : 'primary'"
                    plain
                    @click="onCompleteTask(task)"
                  >
                    {{ taskDone(task) ? "已完成" : "完成" }}
                  </el-button>
                </div>
              </div>
            </template>
            <el-empty
              v-else-if="!loading"
              description="今日没有待办任务，先去冒险吧"
              :image-size="60"
            />
          </div>
        </el-card>

        <!-- 近期 XP 流水 -->
        <el-card shadow="hover" class="block-card mt-16">
          <template #header>
            <div class="card-header">
              <b>最近成长记录</b>
            </div>
          </template>
          <el-table
            v-loading="loading"
            :data="overview.recent_xp_logs"
            size="small"
            class="xp-table"
          >
            <el-table-column prop="note" label="事件" min-width="150" />
            <el-table-column label="时间" width="110" align="right">
              <template #default="{ row }">{{ fmtLogTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="XP" width="80" align="right">
              <template #default="{ row }">
                <span class="xp-amount">+{{ row.xp_amount }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 成就简览 + 番茄钟 -->
      <el-col :xs="24" :sm="24" :md="12" class="mb-16">
        <el-card shadow="hover" class="block-card">
          <template #header>
            <div class="card-header">
              <b>成就</b>
              <el-button
                link
                type="primary"
                @click="router.push('/achievements')"
              >
                成就中心 →
              </el-button>
            </div>
          </template>
          <div v-loading="loading" class="achi-strip">
            <div
              v-for="a in previewAchievements"
              :key="a.achievement_id"
              class="achi-mini"
              :class="{ locked: !a.unlocked }"
              :title="a.unlocked ? a.description : '尚未解锁'"
            >
              <span class="achi-mini-icon">{{ iconText(a.icon) }}</span>
              <span class="achi-mini-name">{{ a.title }}</span>
            </div>
            <el-empty
              v-if="!loading && !previewAchievements.length"
              description="暂无成就"
              :image-size="60"
            />
          </div>
          <div class="achi-progress">
            <span>{{ overview.achievements.unlocked_count }} / {{ overview.achievements.total }} 已解锁</span>
            <el-progress
              :percentage="overview.achievements.total
                ? Math.round((overview.achievements.unlocked_count / overview.achievements.total) * 100)
                : 0"
              :stroke-width="6"
            />
          </div>
        </el-card>

        <!-- 番茄钟 -->
        <el-card shadow="hover" class="block-card mt-16">
          <template #header>
            <div class="card-header">
              <b>番茄钟</b>
              <el-tag size="small" effect="plain" type="warning" round>
                累计专注 {{ overview.pomodoro.focus_total_minutes }} 分钟
              </el-tag>
            </div>
          </template>
          <div class="pomo-row">
            <div class="pomo-info">
              <p class="pomo-title">开启一段专注学习</p>
              <p class="pomo-sub">已完成 {{ overview.pomodoro.session_count }} 回番茄钟</p>
            </div>
            <el-button type="warning" plain round @click="pomodoroVisible = true">
              开始番茄钟
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 番茄钟完成弹窗 -->
    <el-dialog
      v-model="pomodoroVisible"
      title="完成番茄钟专注"
      width="min(92vw, 420px)"
    >
      <p class="pomo-tip">选择你刚刚完成的专注模式，完成后将自动获得 XP。</p>
      <div class="pomo-options">
        <el-button
          type="primary"
          plain
          :loading="pomodoroSubmitting"
          class="pomo-option"
          @click="onPomodoro('focus')"
        >
          标准专注 25 分钟 +8 XP
        </el-button>
        <el-button
          type="danger"
          plain
          :loading="pomodoroSubmitting"
          class="pomo-option"
          @click="onPomodoro('deep')"
        >
          深度专注 40 分钟 +12 XP
        </el-button>
      </div>
    </el-dialog>
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
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.hero-left {
  flex: 1;
  min-width: 260px;
}

.hero-title {
  margin: 0 0 6px;
  font-size: 20px;
}

.tier-tag {
  margin-left: 8px;
  background: rgba(255, 255, 255, 0.25);
  border: none;
  color: #fff;
}

.hero-sub {
  margin: 0 0 12px;
  opacity: 0.85;
  font-size: 13px;
}

.hero-lv-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-level {
  font-weight: 700;
  font-size: 16px;
  white-space: nowrap;
}

.hero-xp {
  flex: 1;
  :deep(.el-progress-bar__outer) {
    background: rgba(255, 255, 255, 0.3);
  }
}

.hero-xp-text {
  font-size: 12px;
  white-space: nowrap;
  opacity: 0.9;
}

.hero-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.hero-stat {
  text-align: center;
}

.hero-stat-num {
  display: block;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
}

.hero-stat-label {
  font-size: 12px;
  opacity: 0.85;
}

.checkin-btn {
  border: none;
  background: rgba(255, 255, 255, 0.92);
  color: var(--sq-primary);
  font-weight: 600;

  &:disabled {
    background: rgba(255, 255, 255, 0.35);
    color: #fff;
  }
}

.mt-16 {
  margin-top: 16px;
}

.mb-16 {
  margin-bottom: 16px;
}

.block-card {
  border-radius: 12px;
  border: none;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-list {
  min-height: 120px;
}

.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed #eff1f7;

  &:last-child {
    border-bottom: none;
  }
}

.task-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: #2e3443;
}

.task-detail {
  margin: 0;
  font-size: 12px;
  color: #8a93a8;
}

.task-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.task-xp {
  color: #f59e0b;
  font-weight: 700;
  font-size: 13px;
  white-space: nowrap;
}

.xp-table {
  width: 100%;
}

.xp-amount {
  color: #f59e0b;
  font-weight: 700;
}

.achi-strip {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 70px;
}

.achi-mini {
  width: 90px;
  padding: 10px 8px;
  border-radius: 12px;
  background: linear-gradient(180deg, #eef1ff 0%, #f8f9ff 100%);
  text-align: center;
  cursor: default;

  &.locked {
    opacity: 0.45;
    filter: grayscale(0.6);
  }
}

.achi-mini-icon {
  display: block;
  font-size: 20px;
  font-weight: 800;
  color: var(--sq-primary);
  margin-bottom: 4px;
}

.achi-mini-name {
  font-size: 11.5px;
  color: #4b5267;
}

.achi-progress {
  margin-top: 14px;
  font-size: 12px;
  color: #7a8399;
}

.pomo-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.pomo-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: #2e3443;
}

.pomo-sub {
  margin: 0;
  font-size: 12px;
  color: #8a93a8;
}

.pomo-tip {
  margin: 0 0 14px;
  font-size: 13px;
  color: #5a6276;
}

.pomo-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pomo-option {
  margin-left: 0 !important;
  width: 100%;
}
</style>