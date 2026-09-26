<script setup lang="ts">
/*
 * 个人画像页（模块3）
 * - 展示兴趣、价值观、学习目标、职业意向（+容忍度/雷达图）
 * - 未生成时引导基于测评一键生成
 */
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { Aim, MagicStick, RefreshRight, Star } from "@element-plus/icons-vue";
import AbilityRadarChart from "@/components/AbilityRadarChart.vue";
import { generatePersona, getCurrentPersona } from "@/api/persona";
import type { Persona } from "@/types/assessment";

const loading = ref(true);
const generating = ref(false);
const persona = ref<Persona | null>(null);

const radarPoints = computed(() => persona.value?.ability_radar.dimensions ?? []);

interface PreferenceItem {
  question: string;
  labels: string[];
}

function parsePreference(data: Record<string, unknown> | undefined): PreferenceItem[] {
  if (!data) return [];
  const items: PreferenceItem[] = [];
  for (const list of Object.values(data)) {
    if (!Array.isArray(list)) continue;
    (list as Array<Record<string, unknown>>).forEach((entry) => {
      const raw = entry as { question?: string; answer?: Array<{ label?: string }> };
      const labels = (raw.answer ?? [])
        .map((a) => a.label)
        .filter(Boolean) as string[];
      if (raw.question && labels.length) {
        items.push({ question: raw.question, labels });
      }
    });
  }
  return items;
}

const interests = computed(() => parsePreference(persona.value?.interest as Record<string, unknown>));
const values = computed(() => parsePreference(persona.value?.values as Record<string, unknown>));

async function load(): Promise<void> {
  loading.value = true;
  try {
    persona.value = await getCurrentPersona();
  } finally {
    loading.value = false;
  }
}

async function handleGenerate(): Promise<void> {
  generating.value = true;
  try {
    const res = await generatePersona();
    persona.value = res.persona;
    ElMessage.success("画像生成完成");
  } finally {
    generating.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 未生成：引导 -->
    <el-card v-if="!persona && !loading" shadow="never" class="empty-card">
      <el-empty description="还没有你的专属画像">
        <template #description>
          <p class="empty-desc">
            完成一次职业测评后，SkillQuest 会基于测评结果生成你的能力画像、兴趣与价值观标签。
          </p>
        </template>
        <el-button type="primary" :icon="MagicStick" round @click="handleGenerate()">
          基于最近测评生成画像
        </el-button>
      </el-empty>
    </el-card>

    <template v-else-if="persona">
      <!-- 头像卡 -->
      <el-card shadow="never" class="persona-card">
        <div class="persona-head">
          <el-avatar :size="56" :icon="Star" class="persona-avatar" />
          <div>
            <h3 class="persona-name">
              {{ persona.target_job || "目标岗位待定" }}
              <el-tag v-if="persona.ai_enriched" size="small" effect="dark" type="primary" class="ai-tag">
                AI 增强
              </el-tag>
            </h3>
            <p class="persona-sub">{{ persona.persona_summary }}</p>
          </div>
          <el-button :icon="RefreshRight" round @click="handleGenerate()" :loading="generating">
            重新生成
          </el-button>
        </div>

        <!-- 标签 -->
        <div class="tag-line">
          <el-tag
            v-for="tag in persona.persona_tags"
            :key="tag"
            effect="plain"
            round
            class="ptag"
          >
            {{ tag }}
          </el-tag>
        </div>
      </el-card>

      <el-row :gutter="16" class="mt-16">
        <!-- 雷达 + 优势短板 -->
        <el-col :xs="24" :md="12" class="mb-16">
          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">
                <el-icon><Aim /></el-icon> 能力雷达
              </span>
            </template>
            <AbilityRadarChart :dimensions="radarPoints" :height="280" title="能力画像" />
          </el-card>
        </el-col>

        <el-col :xs="24" :md="12" class="mb-16">
          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">
                <el-icon><Star /></el-icon> 优势与短板
              </span>
            </template>
            <p class="sec-label">突出优势</p>
            <ul class="sw-list good">
              <li v-for="(s, i) in persona.strengths" :key="i">{{ s }}</li>
            </ul>
            <p class="sec-label">薄弱项</p>
            <ul class="sw-list warn">
              <li v-for="(w, i) in persona.weaknesses" :key="i">{{ w }}</li>
            </ul>
            <p class="advice">{{ persona.advice }}</p>
          </el-card>

          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">学习目标与职业意向</span>
            </template>
            <p class="goal-line">
              目标岗位：
              <b>{{ persona.target_job || "未设置" }}</b>
            </p>
            <p class="goal-text">{{ persona.learning_goal || "尚未设置学习目标" }}</p>
          </el-card>
        </el-col>
      </el-row>

      <!-- 兴趣 / 价值观 -->
      <el-row :gutter="16">
        <el-col :xs="24" :md="12" class="mb-16">
          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">兴趣</span>
            </template>
            <el-empty v-if="!interests.length" description="暂无兴趣数据" :image-size="60" />
            <div v-for="it in interests" :key="it.question" class="pref-item">
              <p class="pref-q">{{ it.question }}</p>
              <el-tag v-for="label in it.labels" :key="label" effect="plain" round class="ptag small">
                {{ label }}
              </el-tag>
            </div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="12" class="mb-16">
          <el-card shadow="never" class="block-card">
            <template #header>
              <span class="block-title">职业价值观</span>
            </template>
            <el-empty v-if="!values.length" description="暂无价值观数据" :image-size="60" />
            <div v-for="it in values" :key="it.question" class="pref-item">
              <p class="pref-q">{{ it.question }}</p>
              <el-tag v-for="label in it.labels" :key="label" effect="plain" round class="ptag small">
                {{ label }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped lang="scss">
.empty-card {
  border-radius: 14px;
  border: none;
}

.empty-desc {
  margin: 8px 0 4px;
  font-size: 13px;
  color: #9099a8;
}

.persona-card {
  border: none;
  border-radius: 16px;
  background: linear-gradient(120deg, #4f6ef7, #7c3aed);
  color: #fff;
}

.persona-head {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.persona-avatar {
  background: rgba(255, 255, 255, 0.2);
}

.persona-name {
  margin: 0;
  font-size: 19px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-tag {
  margin-left: 4px;
}

.persona-sub {
  margin: 4px 0 0;
  font-size: 13px;
  opacity: 0.9;
  max-width: 720px;
  line-height: 1.6;
}

.tag-line {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ptag {
  border-color: rgba(255, 255, 255, 0.6);
  color: #fff;
  background: rgba(255, 255, 255, 0.12);

  &.small {
    border-color: #d8deeb;
    color: #4f6ef7;
    background: #f1f4fb;
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
  min-height: 100%;
}

.block-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.sec-label {
  margin: 8px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: #9099a8;
}

.sw-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.8;

  &.good {
    color: #15803d;
  }

  &.warn {
    color: #b45309;
  }
}

.advice {
  margin: 12px 0 0;
  padding: 10px 12px;
  background: #f5f7ff;
  border-radius: 8px;
  font-size: 13px;
  color: #4f6ef7;
  line-height: 1.6;
}

.goal-line {
  margin: 4px 0;
  font-size: 14px;
}

.goal-text {
  margin: 6px 0 0;
  font-size: 13px;
  color: #5a6276;
  line-height: 1.7;
}

.pref-item {
  margin-bottom: 12px;
}

.pref-q {
  margin: 0 0 6px;
  font-size: 13px;
  color: #5a6276;
}
</style>