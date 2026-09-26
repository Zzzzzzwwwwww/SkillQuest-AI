<script setup lang="ts">
/*
 * 测评答题页（模块3）
 * - 进度条 / 上一题 / 下一题 / 作答态校验 / 提交
 * - 题型渲染：单选 radio、多选 checkbox、量表档位、简答 textarea
 */
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, ArrowRight, Promotion } from "@element-plus/icons-vue";
import { getPaperQuestions, submitAssessment } from "@/api/assessment";
import type { Question } from "@/types/assessment";

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const submitting = ref(false);
const paperId = Number(route.query.paperId || 0);
const questions = ref<Question[]>([]);
const answers = reactive<Record<number, string | number | string[]>>({});
const current = ref(0);

const total = computed(() => questions.value.length);
const progress = computed(() =>
  total.value ? Math.round(((current.value + 1) / total.value) * 100) : 0
);
const currentQuestion = computed<Question | null>(
  () => questions.value[current.value] ?? null
);

const qid = computed(() => currentQuestion.value?.id ?? 0);

const typeLabel: Record<string, string> = {
  single: "单选",
  multiple: "多选",
  scale: "量表",
  text: "简答",
};

onMounted(async () => {
  if (!paperId) {
    ElMessage.error("缺少试卷参数");
    router.replace("/assessment");
    return;
  }
  try {
    questions.value = await getPaperQuestions(paperId);
  } catch {
    router.replace("/assessment");
    return;
  } finally {
    loading.value = false;
  }
});

function isAnswered(q: Question | null): boolean {
  if (!q) return false;
  const v = answers[q.id];
  if (v === undefined) return false;
  if (Array.isArray(v)) return v.length > 0;
  return String(v).trim() !== "";
}

// ---- 各题型计算属性（规避模板泛类型绑定问题） ----
const singleValue = computed<string | number | undefined>({
  get() {
    const v = answers[qid.value];
    return typeof v === "string" || typeof v === "number" ? v : undefined;
  },
  set(v) {
    if (v === undefined || v === "") delete answers[qid.value];
    else answers[qid.value] = v;
  },
});

const multipleValue = computed<string[]>({
  get() {
    const v = answers[qid.value];
    return Array.isArray(v) ? v.map(String) : [];
  },
  set(v) {
    const arr = Array.isArray(v) ? v : [];
    if (arr.length) answers[qid.value] = arr;
    else delete answers[qid.value];
  },
});

const textValue = computed<string>({
  get() {
    const v = answers[qid.value];
    return typeof v === "string" ? v : "";
  },
  set(v) {
    if (v && v.trim()) answers[qid.value] = v;
    else delete answers[qid.value];
  },
});

function selectScale(key: string): void {
  if (qid.value) answers[qid.value] = key;
}

function prev(): void {
  if (current.value > 0) current.value -= 1;
}

function next(): void {
  const q = currentQuestion.value;
  if (q && !isAnswered(q)) {
    ElMessage.warning("请先完成当前题目");
    return;
  }
  if (current.value < total.value - 1) current.value += 1;
  else void handleSubmit();
}

async function handleSubmit(): Promise<void> {
  const unanswered = questions.value.filter((q) => !isAnswered(q));
  if (unanswered.length > 0) {
    ElMessage.warning(`还有 ${unanswered.length} 道题未作答，请完成后再提交`);
    const idx = questions.value.findIndex((q) => unanswered.includes(q));
    if (idx >= 0) current.value = idx;
    return;
  }

  try {
    await ElMessageBox.confirm(
      "提交后将生成你的职业画像与推荐岗位，确认提交？",
      "提交测评",
      {
        confirmButtonText: "提交",
        cancelButtonText: "再检查一遍",
        type: "info",
      }
    );
  } catch {
    return;
  }

  submitting.value = true;
  try {
    const res = await submitAssessment({
      paper_id: paperId,
      answers: questions.value.map((q) => ({
        question_id: q.id,
        answer: (answers[q.id] ?? null) as string | number | string[] | null,
      })),
    });
    ElMessage.success(`测评完成，总分 ${res.total_score} 分`);
    router.replace(`/assessment/result/${res.result_id}`);
  } catch {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="page-container" v-loading="loading">
    <el-card shadow="never" class="answer-card" v-if="currentQuestion">
      <!-- 顶部：进度 -->
      <div class="answer-head">
        <div class="head-left">
          <span class="q-index">第 {{ current + 1 }} / {{ total }} 题</span>
          <span class="grow"></span>
          <el-tag size="small" effect="plain" type="primary">
            {{ currentQuestion.dimension_label }} ·
            {{ typeLabel[currentQuestion.question_type] }}
          </el-tag>
        </div>
        <el-progress
          :percentage="progress"
          :stroke-width="8"
          :show-text="false"
          class="q-progress"
        />
      </div>

      <!-- 题干 -->
      <h3 class="q-content">{{ currentQuestion.content }}</h3>

      <!-- 单选 -->
      <el-radio-group
        v-if="currentQuestion.question_type === 'single' && currentQuestion.options"
        v-model="singleValue"
        class="q-options"
      >
        <el-radio
          v-for="opt in currentQuestion.options"
          :key="opt.key"
          :value="opt.key"
          border
          class="q-option"
        >
          {{ opt.key }}. {{ opt.label }}
        </el-radio>
      </el-radio-group>

      <!-- 多选 -->
      <el-checkbox-group
        v-else-if="currentQuestion.question_type === 'multiple' && currentQuestion.options"
        v-model="multipleValue"
        class="q-options"
      >
        <el-checkbox
          v-for="opt in currentQuestion.options"
          :key="opt.key"
          :value="opt.key"
          border
          class="q-option"
        >
          {{ opt.key }}. {{ opt.label }}
        </el-checkbox>
      </el-checkbox-group>

      <!-- 量表：档位按钮 + 档位文本 -->
      <div
        v-else-if="currentQuestion.question_type === 'scale' && currentQuestion.options"
        class="q-scale"
      >
        <button
          v-for="opt in currentQuestion.options"
          :key="opt.key"
          class="scale-btn"
          :class="{ active: String(answers[currentQuestion.id]) === opt.key }"
          @click="selectScale(opt.key)"
        >
          <span class="scale-num">{{ opt.key }}</span>
          <span class="scale-label">{{ opt.label }}</span>
        </button>
      </div>

      <!-- 简答 -->
      <el-input
        v-else-if="currentQuestion.question_type === 'text'"
        v-model="textValue"
        type="textarea"
        :rows="5"
        :placeholder="currentQuestion.placeholder || '请输入你的想法…'"
        class="q-text"
        maxlength="300"
        show-word-limit
      />

      <!-- 操作 -->
      <div class="answer-foot">
        <el-button :disabled="current === 0" :icon="ArrowLeft" @click="prev()">
          上一题
        </el-button>
        <span class="grow"></span>
        <el-button
          v-if="current < total - 1"
          type="primary"
          :icon="ArrowRight"
          @click="next()"
        >
          下一题
        </el-button>
        <el-button
          v-else
          type="primary"
          :icon="Promotion"
          :loading="submitting"
          @click="handleSubmit()"
        >
          提交测评
        </el-button>
      </div>
    </el-card>

    <el-empty v-else-if="!loading" description="该试卷暂无题目" />
  </div>
</template>

<style scoped lang="scss">
.answer-card {
  max-width: 760px;
  margin: 0 auto;
  border-radius: 14px;
  border: none;
}

.answer-head {
  margin-bottom: 20px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.q-index {
  font-size: 14px;
  font-weight: 600;
  color: #5a6276;
}

.grow {
  flex: 1;
}

.q-progress {
  :deep(.el-progress-bar__inner) {
    background: linear-gradient(90deg, #4f6ef7, #7c3aed);
  }
}

.q-content {
  margin: 0 0 20px;
  font-size: 18px;
  line-height: 1.6;
}

.q-options {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.q-option {
  width: 100%;
  margin: 0;
  height: auto;
  padding: 10px 14px;
  white-space: normal;
  border-radius: 8px;
}

.q-scale {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin: 8px 0;
}

.scale-btn {
  border: 1px solid #d8deeb;
  border-radius: 10px;
  background: #fff;
  padding: 12px 8px;
  cursor: pointer;
  text-align: center;
  transition: all 0.15s;

  &:hover {
    border-color: #4f6ef7;
  }

  &.active {
    border-color: #4f6ef7;
    background: rgba(79, 110, 247, 0.08);
  }
}

.scale-num {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #3a3f50;
}

.scale-label {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #9099a8;
  line-height: 1.4;
}

.q-text {
  margin-top: 8px;
}

.answer-foot {
  display: flex;
  align-items: center;
  margin-top: 24px;
}
</style>