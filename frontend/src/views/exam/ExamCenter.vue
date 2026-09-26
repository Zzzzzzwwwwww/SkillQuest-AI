<script setup lang="ts">
/*
 * 学习评估 · 阶段测评中心
 * 试卷列表 → 开始测评(弹窗答题) → 提交 → 跳转结果页
 */
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getExamPapers, startExam, submitExam } from "@/api/assessment_review";
import type {
  AnswerItem,
  ExamPaper,
  ExamQuestion,
  ExamStartResult,
} from "@/types/assessment_review";
import { EXAM_STAGE_META } from "@/types/assessment_review";

const router = useRouter();
const loading = ref(false);
const papers = ref<ExamPaper[]>([]);

const answering = ref(false);
const submitting = ref(false);
const current = ref<ExamStartResult | null>(null);
const answers = reactive<Record<number, AnswerItem["user_answer"]>>({});

async function load(): Promise<void> {
  loading.value = true;
  try {
    papers.value = await getExamPapers();
  } finally {
    loading.value = false;
  }
}

async function onStart(paper: ExamPaper): Promise<void> {
  try {
    const result = await startExam(paper.id);
    current.value = result;
    Object.keys(answers).forEach((k) => delete answers[Number(k)]);
    answering.value = true;
  } catch {
    // 统一错误提示
  }
}

function multiset(q: ExamQuestion, keys: string | string[]): void {
  if (typeof keys === "string") {
    answers[q.id] = [keys];
    return;
  }
  answers[q.id] = keys;
}

async function onSubmit(): Promise<void> {
  if (!current.value) return;
  const qs = current.value.questions;
  const missing = qs.filter((q) => answers[q.id] === undefined);
  if (missing.length) {
    ElMessage.warning(`还有 ${missing.length} 题未作答`);
    return;
  }
  submitting.value = true;
  try {
    const payload: AnswerItem[] = qs.map((q) => ({
      question_id: q.id,
      user_answer: answers[q.id],
    }));
    const res = await submitExam(current.value.record_id, payload);
    ElMessage.success(`提交成功，得分 ${res.score} 分`);
    answering.value = false;
    router.push(`/exam/result/${res.record_id}`);
  } catch {
    // 统一错误提示
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-container">
    <el-card shadow="hover" class="exam-card">
      <template #header>
        <div class="exam-header">
          <b>阶段测评</b>
          <span class="exam-hint">答题后将按知识点滚动测算掌握度并生成学习报告</span>
        </div>
      </template>

      <div v-loading="loading" class="paper-grid">
        <el-card
          v-for="paper in papers"
          :key="paper.id"
          shadow="hover"
          class="paper-item"
        >
          <div class="paper-stage">
            <el-tag
              round
              effect="light"
              :style="{ color: EXAM_STAGE_META[paper.stage]?.color }"
            >
              {{ EXAM_STAGE_META[paper.stage]?.icon }}
              {{ EXAM_STAGE_META[paper.stage]?.label ?? paper.stage }}
            </el-tag>
          </div>
          <h3 class="paper-title">{{ paper.title }}</h3>
          <p class="paper-desc">{{ paper.description }}</p>
          <div class="paper-meta">
            <span>满分 {{ paper.total_score }}</span>
            <span>建议 {{ paper.duration }} 分钟</span>
          </div>
          <el-button
            type="primary"
            class="paper-btn"
            @click="onStart(paper)"
          >
            开始测评
          </el-button>
        </el-card>

        <el-empty
          v-if="!loading && papers.length === 0"
          description="暂无可用的阶段测评试卷"
        />
      </div>
    </el-card>

    <!-- 答题弹窗 -->
    <el-dialog
      v-model="answering"
      :title="current ? `${current.title} · 开始作答` : '阶段测评'"
      width="min(92vw, 760px)"
      top="4vh"
      destroy-on-close
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <div v-if="current" class="answer-area">
        <div class="answer-head">
          <el-tag type="warning" effect="plain">
            共 {{ current.questions.length }} 题 · 满分 {{ current.total_score }}
          </el-tag>
          <span class="answer-tip">选择题直接勾选即可，结束后统一提交</span>
        </div>

        <div
          v-for="(q, idx) in current.questions"
          :key="q.id"
          class="question-item"
        >
          <p class="question-text">
            <b>{{ idx + 1 }}.</b>
            {{ q.content }}
            <el-tag size="small" type="info" effect="plain" class="q-type">
              {{ q.question_type === "single" ? "单选" : q.question_type === "multiple" ? "多选" : "判断" }}
            </el-tag>
            <el-tag size="small" effect="plain" class="q-score">
              {{ q.score }} 分
            </el-tag>
          </p>

          <el-radio-group
            v-if="q.question_type === 'single'"
            v-model="answers[q.id]"
            class="q-options"
          >
            <el-radio
              v-for="opt in q.options"
              :key="opt.key"
              :value="opt.key"
              class="q-option"
            >
              {{ opt.key }}. {{ opt.label }}
            </el-radio>
          </el-radio-group>

          <el-checkbox-group
            v-else-if="q.question_type === 'multiple'"
            :model-value="answers[q.id] as string[]"
            class="q-options"
            @update:model-value="(v: string[]) => multiset(q, v)"
          >
            <el-checkbox
              v-for="opt in q.options"
              :key="opt.key"
              :value="opt.key"
              class="q-option"
            >
              {{ opt.key }}. {{ opt.label }}
            </el-checkbox>
          </el-checkbox-group>

          <el-radio-group
            v-else
            v-model="answers[q.id]"
            class="q-options"
          >
            <el-radio :value="true" class="q-option">对</el-radio>
            <el-radio :value="false" class="q-option">错</el-radio>
          </el-radio-group>
        </div>
      </div>

      <template #footer>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!current"
          @click="onSubmit"
        >
          提交答卷
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.exam-card {
  border-radius: 12px;
  border: none;
}

.exam-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.exam-hint {
  font-size: 12px;
  color: #a0a8bb;
}

.paper-grid {
  min-height: 120px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.paper-item {
  border-radius: 12px;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-3px);
  }

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}

.paper-title {
  margin: 0;
  font-size: 16px;
}

.paper-desc {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
  min-height: 42px;
}

.paper-meta {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #a0a8bb;
}

.paper-btn {
  align-self: stretch;
}

.answer-area {
  max-height: 62vh;
  overflow-y: auto;
  padding-right: 6px;
}

.answer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.answer-tip {
  font-size: 12px;
  color: #a0a8bb;
}

.question-item {
  border: 1px solid #eef1f7;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}

.question-text {
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.7;
}

.q-type,
.q-score {
  margin-left: 6px;
}

.q-options {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.q-option {
  height: auto;
  padding: 4px 6px;
}
</style>