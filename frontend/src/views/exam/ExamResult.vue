<script setup lang="ts">
/*
 * 学习评估 · 测评结果复盘
 * 分数总览 / 能力雷达 / 知识点掌握度 / 学习趋势 / 薄弱点与建议 / 题目对错明细
 */
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { CircleCheck, CircleClose } from "@element-plus/icons-vue";
import AbilityRadarChart from "@/components/AbilityRadarChart.vue";
import { getExamResult } from "@/api/assessment_review";
import type { ExamResultDetail } from "@/types/assessment_review";
import { EXAM_STAGE_META } from "@/types/assessment_review";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const result = ref<ExamResultDetail | null>(null);

function toRadarPoints(): { name: string; key: string; score: number }[] {
  return (result.value?.radar ?? []).map((p) => ({
    name: p.domain,
    key: p.domain,
    score: p.value,
  }));
}

function masteryColor(score: number): string {
  if (score >= 70) return "#16a34a";
  if (score >= 60) return "#d97706";
  return "#dc2626";
}

function answerText(
  a: unknown
): string {
  if (a === null || a === undefined) return "未作答";
  if (typeof a === "boolean") return a ? "对" : "错";
  if (Array.isArray(a)) return (a as string[]).join("、");
  return String(a);
}

function goReport(): void {
  router.push("/report");
}

onMounted(() => {
  const recordId = Number(route.params.id);
  if (Number.isNaN(recordId) || recordId <= 0) {
    router.replace("/exam");
    return;
  }
  getExamResult(recordId)
    .then((data) => (result.value = data))
    .catch(() => router.replace("/exam"))
    .finally(() => (loading.value = false));
});
</script>

<template>
  <div class="page-container">
    <div v-loading="loading">
      <template v-if="result">
        <div class="stage-hero">
          <div>
            <div class="hero-top">
              <el-tag round effect="dark" class="stage-tag">
                {{ EXAM_STAGE_META[result.stage]?.icon }}
                {{ EXAM_STAGE_META[result.stage]?.label ?? result.stage }} · 阶段测评
              </el-tag>
              <h2 class="hero-title">{{ result.exam_title }}</h2>
            </div>
            <p class="hero-sub">
              提交于 {{ result.submitted_at.replace("T", " ").slice(0, 19) }}
            </p>
          </div>
          <div class="score-badge">
            <span class="score-num" :class="{ pass: result.score >= 60 }">
              {{ result.score }}
            </span>
            <span class="score-unit">分</span>
            <el-tag
              :type="result.score >= 60 ? 'success' : 'danger'"
              effect="dark"
              round
              class="score-tag"
            >
              {{ result.score >= 60 ? "已通过" : "未通过" }}
            </el-tag>
          </div>
        </div>

        <div class="stat-row">
          <el-card shadow="never" class="stat-card">
            <p class="stat-num">{{ result.correct_count }} / {{ result.total_count }}</p>
            <p class="stat-label">答对题数</p>
          </el-card>
          <el-card shadow="never" class="stat-card">
            <p class="stat-num">{{ result.mastery.length }}</p>
            <p class="stat-label">掌握知识点</p>
          </el-card>
          <el-card shadow="never" class="stat-card">
            <p class="stat-num">{{ result.weak_points.length }}</p>
            <p class="stat-label">薄弱知识点</p>
          </el-card>
        </div>

        <div class="grid-2">
          <!-- 能力雷达 -->
          <el-card shadow="hover" class="block-card">
            <template #header><b>能力雷达</b></template>
            <AbilityRadarChart
              v-if="result.radar.length"
              :dimensions="toRadarPoints()"
              :height="300"
              title="能力域掌握度"
            />
            <el-empty v-else description="暂无雷达数据（先完成一次测评）" :image-size="70" />
          </el-card>

          <!-- 学习趋势 -->
          <el-card shadow="hover" class="block-card">
            <template #header><b>学习趋势</b></template>
            <el-empty
              v-if="!result.trend.length"
              description="暂无历史测评记录"
              :image-size="70"
            />
            <div v-else class="trend-list">
              <div v-for="t in result.trend" :key="t.record_id" class="trend-item">
                <div class="trend-head">
                  <span class="trend-title">{{ t.exam_title }}</span>
                  <span class="trend-score" :class="{ pass: t.score >= 60 }">
                    {{ t.score }} 分
                  </span>
                </div>
                <el-progress
                  :percentage="t.score"
                  :color="masteryColor(t.score)"
                  :stroke-width="8"
                  :show-text="false"
                  class="trend-bar"
                />
                <span class="trend-date">
                  {{ t.submitted_at.replace("T", " ").slice(0, 19) }}
                </span>
              </div>
            </div>
          </el-card>
        </div>

        <!-- 知识点掌握度 -->
        <el-card shadow="hover" class="block-card">
          <template #header><b>知识点掌握度</b></template>
          <el-empty
            v-if="!result.mastery.length"
            description="本次测评未覆盖知识点，先完成一场阶段测评吧"
            :image-size="70"
          />
          <div v-else class="mastery-grid">
            <div v-for="(m, mi) in result.mastery" :key="mi" class="mastery-item">
              <div class="mastery-head">
                <span class="mastery-name">{{ m.name }}</span>
                <el-tag size="small" effect="plain" type="info">{{ m.domain }}</el-tag>
              </div>
              <el-progress
                :percentage="m.mastery_score"
                :color="masteryColor(m.mastery_score)"
                :stroke-width="10"
              />
              <span class="mastery-meta">
                测评 {{ m.review_count }} 次 · 掌握度 {{ m.mastery_score }}
              </span>
            </div>
          </div>
        </el-card>

        <div class="grid-2">
          <!-- 薄弱点 -->
          <el-card shadow="hover" class="block-card">
            <template #header><b>薄弱知识点</b></template>
            <el-empty
              v-if="!result.weak_points.length"
              description="当前无薄弱知识点，保持节奏继续冒险"
              :image-size="70"
            />
            <el-alert
              v-for="(w, wi) in result.weak_points"
              :key="wi"
              :title="`${w.name} · 掌握度 ${w.mastery_score} 分`"
              :description="w.suggestion"
              type="warning"
              :closable="false"
              show-icon
              class="weak-item"
            />
          </el-card>

          <!-- 下一步建议 -->
          <el-card shadow="hover" class="block-card">
            <template #header><b>下一步行动</b></template>
            <el-empty
              v-if="!result.next_steps.length"
              description="暂无行动建议"
              :image-size="70"
            />
            <ul v-else class="next-list">
              <li v-for="(n, i) in result.next_steps" :key="i" class="next-item">
                <span class="next-index">{{ i + 1 }}</span>
                {{ n }}
              </li>
            </ul>
            <el-button type="primary" class="report-btn" @click="goReport">
              生成学习报告
            </el-button>
          </el-card>
        </div>

        <!-- 题目对错明细 -->
        <el-card shadow="hover" class="block-card">
          <template #header><b>答题明细</b></template>
          <el-collapse>
            <el-collapse-item
              v-for="(q, idx) in result.questions"
              :key="q.question_id"
              :name="q.question_id"
            >
              <template #title>
                <span class="q-title">
                  <el-icon
                    :color="q.is_correct ? '#16a34a' : '#dc2626'"
                    class="q-icon"
                  >
                    <CircleCheck v-if="q.is_correct" />
                    <CircleClose v-else />
                  </el-icon>
                  {{ idx + 1 }}. {{ q.content }}
                </span>
                <span class="q-points">
                  得 {{ q.points_earned }} / {{ q.points_total }} 分
                </span>
              </template>
              <div class="q-detail">
                <p>你的答案：{{ answerText(q.user_answer) }}</p>
                <p>正确答案：{{ answerText(q.correct_answer) }}</p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stage-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 14px;
  background: linear-gradient(120deg, #1e2447 0%, #313c8f 100%);
  color: #fff;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-title {
  margin: 6px 0 0;
  font-size: 20px;
}

.hero-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: #b9c0e8;
}

.score-badge {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.score-num {
  font-size: 46px;
  font-weight: 800;
  color: #f87171;

  &.pass {
    color: #4ade80;
  }
}

.score-unit {
  font-size: 14px;
  color: #c7cdee;
}

.score-tag {
  margin-left: 4px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

.stat-card {
  border-radius: 12px;
  text-align: center;
}

.stat-num {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1e2447;
}

.stat-label {
  margin: 4px 0 0;
  font-size: 12px;
  color: #a0a8bb;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.block-card {
  border-radius: 12px;
  border: none;
}

.trend-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.trend-title {
  font-size: 13px;
}

.trend-score {
  font-weight: 600;
  color: #dc2626;

  &.pass {
    color: #16a34a;
  }
}

.trend-date {
  font-size: 11px;
  color: #a0a8bb;
}

.mastery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.mastery-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.mastery-name {
  font-size: 13px;
  font-weight: 600;
}

.mastery-meta {
  font-size: 11px;
  color: #a0a8bb;
}

.weak-item {
  margin-bottom: 10px;
  border-radius: 8px;
}

.next-list {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.next-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
}

.next-index {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--sq-primary-gradient);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.report-btn {
  margin-top: 6px;
}

.q-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  flex: 1;
}

.q-points {
  font-size: 12px;
  color: #a0a8bb;
}

.q-detail {
  padding-left: 26px;
  font-size: 13px;
  color: #5a6276;

  p {
    margin: 4px 0;
  }
}

@media (max-width: 768px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>