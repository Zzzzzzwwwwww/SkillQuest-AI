<script setup lang="ts">
/*
 * 测评结果页（模块3）
 * - 能力雷达图（ECharts）、推荐岗位卡片、画像标签、技能差距列表
 */
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Back, Medal, TrendCharts, Warning } from "@element-plus/icons-vue";
import AbilityRadarChart from "@/components/AbilityRadarChart.vue";
import { getAssessmentResult } from "@/api/assessment";
import type { AssessmentResultDetail } from "@/types/assessment";

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const result = ref<AssessmentResultDetail | null>(null);

const radarPoints = computed(() => result.value?.radar_data.dimensions ?? []);

const rankedDimensions = computed(() => {
  if (!result.value) return [];
  return Object.entries(result.value.dimension_scores)
    .map(([key, score]) => ({
      key,
      label: result.value?.dimension_labels[key] ?? key,
      score,
    }))
    .sort((a, b) => b.score - a.score);
});

const topJob = computed(() => result.value?.recommended_jobs[0] ?? null);

onMounted(async () => {
  const id = Number(route.params.id);
  if (!id) {
    router.replace("/assessment");
    return;
  }
  try {
    result.value = await getAssessmentResult(id);
  } catch {
    router.replace("/assessment");
  } finally {
    loading.value = false;
  }
});

function scoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#4f6ef7";
  return "#f59e0b";
}
</script>

<template>
  <div class="page-container" v-loading="loading">
    <template v-if="result">
      <!-- 总分横幅 -->
      <el-card shadow="never" class="score-card">
        <div class="score-inner">
          <div>
            <p class="score-label">{{ result.paper_title }} · 综合得分</p>
            <div class="score-value">
              {{ result.total_score }}
              <span class="score-unit">/ 100</span>
            </div>
            <p class="score-desc">
              规则引擎依据 10 个维度得分聚合生成，推荐结果与技能差距均可追溯。
            </p>
          </div>
          <el-button round type="primary" :icon="Medal" @click="router.push('/assessment')">
            再做一次测评
          </el-button>
        </div>
      </el-card>

      <el-row :gutter="16" class="mt-16">
        <!-- 左：雷达图 + 维度分 -->
        <el-col :xs="24" :md="10" class="mb-16">
          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">
                <el-icon><TrendCharts /></el-icon> 能力雷达图
              </span>
            </template>
            <AbilityRadarChart :dimensions="radarPoints" :height="300" title="当前能力画像" />
            <div class="dim-grid">
              <div v-for="d in rankedDimensions" :key="d.key" class="dim-item">
                <span class="dim-name">{{ d.label }}</span>
                <div class="dim-bar">
                  <div
                    class="dim-fill"
                    :style="{ width: d.score + '%', background: scoreColor(d.score) }"
                  ></div>
                </div>
                <span class="dim-score">{{ d.score }}</span>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 右：推荐岗位 -->
        <el-col :xs="24" :md="14" class="mb-16">
          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">
                <el-icon><Medal /></el-icon> 推荐职业方向（Top 3）
              </span>
              <el-tag size="small" effect="plain" type="info">
                规则推荐 · 可追溯
              </el-tag>
            </template>

            <div
              v-for="(job, idx) in result.recommended_jobs"
              :key="job.job_id"
              class="job-card"
              :class="{ top: idx === 0 }"
            >
              <div class="job-head">
                <div class="job-name-line">
                  <span class="job-rank">{{ idx + 1 }}</span>
                  <span class="job-name">{{ job.job_name }}</span>
                  <el-tag v-if="idx === 0" size="small" type="danger" effect="dark">
                    最匹配
                  </el-tag>
                </div>
                <span class="job-score" :style="{ color: scoreColor(job.match_score) }">
                  {{ job.match_score }}%
                </span>
              </div>
              <el-progress
                :percentage="Math.round(job.match_score)"
                :show-text="false"
                :stroke-width="6"
                :color="scoreColor(job.match_score)"
              />
              <p class="job-summary">{{ job.summary }}</p>
              <p class="job-reason">
                <el-icon class="reason-icon"><Warning /></el-icon>{{ job.reason }}
              </p>

              <!-- 技能差距 -->
              <div class="gap-box" v-if="job.skill_gaps.length">
                <p class="gap-title">必备技能差距</p>
                <div class="gap-list">
                  <div v-for="g in job.skill_gaps" :key="g.skill" class="gap-item">
                    <span class="gap-skill">{{ g.skill }}</span>
                    <span
                      class="gap-state"
                      :class="g.gap > 0 ? 'miss' : 'ok'"
                    >
                      {{ g.gap > 0 ? `差距 ${g.gap}` : "已达标" }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <p v-if="topJob" class="cta-tip">
              以
              <b>{{ topJob.job_name }}</b>
              为目标岗位，可前往「个人画像」生成你的专属画像，并基于技能差距规划学习路径。
            </p>
            <el-button
              type="primary"
              round
              :icon="Back"
              @click="router.push('/persona')"
            >
              生成个人画像
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped lang="scss">
.score-card {
  border: none;
  border-radius: 16px;
  background: linear-gradient(120deg, #4f6ef7, #7c3aed);
  color: #fff;
}

.score-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.score-label {
  margin: 0 0 4px;
  font-size: 13px;
  opacity: 0.9;
}

.score-value {
  font-size: 40px;
  font-weight: 800;
  line-height: 1.2;
}

.score-unit {
  font-size: 14px;
  font-weight: 400;
  opacity: 0.85;
}

.score-desc {
  margin: 4px 0 0;
  font-size: 12px;
  opacity: 0.9;
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

.block-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.dim-grid {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dim-name {
  width: 64px;
  font-size: 13px;
  color: #5a6276;
  flex-shrink: 0;
}

.dim-bar {
  flex: 1;
  height: 8px;
  background: #eef1f8;
  border-radius: 4px;
  overflow: hidden;
}

.dim-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s;
}

.dim-score {
  width: 34px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
}

.job-card {
  border: 1px solid #e7ebf5;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 14px;
  background: #fafbff;

  &.top {
    border-color: rgba(79, 110, 247, 0.4);
    background: rgba(79, 110, 247, 0.04);
  }
}

.job-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.job-name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.job-rank {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #4f6ef7;
  color: #fff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.job-name {
  font-size: 16px;
  font-weight: 700;
}

.job-score {
  font-size: 18px;
  font-weight: 800;
}

.job-summary,
.job-reason {
  margin: 8px 0 0;
  font-size: 13px;
  color: #5a6276;
  line-height: 1.6;
}

.job-reason {
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.reason-icon {
  margin-top: 2px;
  color: #f59e0b;
  flex-shrink: 0;
}

.gap-box {
  margin-top: 10px;
  background: #fff;
  border-radius: 8px;
  padding: 10px 12px;
}

.gap-title {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #9099a8;
}

.gap-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.gap-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f1f4fb;
  border-radius: 20px;
  padding: 3px 10px;
  font-size: 12px;
}

.gap-skill {
  color: #3a3f50;
}

.gap-state {
  font-weight: 600;

  &.miss {
    color: #f59e0b;
  }

  &.ok {
    color: #22c55e;
  }
}

.cta-tip {
  margin: 4px 0 12px;
  font-size: 13px;
  color: #5a6276;
}
</style>