<script setup lang="ts">
/*
 * Boss 挑战答题对话框（模块8 业务闭环6）
 * - 打开时调用 /boss/start 按技能抽题（不下发答案）
 * - 单选/多选/判断三种题型作答，提交后规则评分
 * - 通过(≥60 分)升级技能等级并发放 XP，结果内联展示，支持再战
 */
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { finishBossChallenge, startBossChallenge } from "@/api/business";
import type {
  BossAnswerItem,
  BossFinishResult,
  BossQuestion,
} from "@/types/business";

const emit = defineEmits<{ (e: "finished"): void }>();

const visible = ref(false);
const loading = ref(false);
const submitting = ref(false);
const skillNodeId = ref(0);
const skillName = ref("");
const stage = ref("");
const description = ref("");
const questions = ref<BossQuestion[]>([]);
const answers = ref<Record<number, string | string[] | boolean>>({});
const result = ref<BossFinishResult | null>(null);

const typeLabel = computed<Record<string, string>>(() => ({
  single: "单选",
  multiple: "多选",
  judge: "判断",
}));

const answered = computed(() =>
  questions.value.every((q) => answers.value[q.id] !== undefined)
);

async function open(nodeId: number, name: string): Promise<void> {
  skillNodeId.value = nodeId;
  skillName.value = name;
  result.value = null;
  answers.value = {};
  visible.value = true;
  loading.value = true;
  try {
    const bz = await startBossChallenge(nodeId);
    stage.value = bz.stage;
    description.value = bz.description;
    questions.value = bz.questions;
  } catch {
    questions.value = [];
    /* 错误已统一提示 */
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  if (submitting.value) return;
  const payload = questions.value.map((q) => ({
    question_id: q.id,
    user_answer: answers.value[q.id],
  }));
  submitting.value = true;
  try {
    result.value = await finishBossChallenge(skillNodeId.value, payload as BossAnswerItem[]);
    if (result.value.pass_flag) {
      ElMessage.success(result.value.message);
    } else {
      ElMessage.warning(result.value.message);
    }
    emit("finished");
  } catch {
    /* 错误已统一提示 */
  } finally {
    submitting.value = false;
  }
}

defineExpose({ open });
</script>

<template>
  <el-dialog
    v-model="visible"
    width="680px"
    :title="`Boss 挑战 · ${skillName}（${stage}）`"
    destroy-on-close
    class="boss-dialog"
  >
    <div v-loading="loading" class="boss-body">
      <el-alert
        v-if="description"
        :title="description"
        type="warning"
        :closable="false"
        class="boss-desc"
      />

      <!-- 结果展示 -->
      <template v-if="result">
        <div class="boss-result" :class="{ win: result.pass_flag }">
          <div class="result-score">
            <span class="result-num">{{ result.score }}</span>
            <span class="result-unit">分</span>
          </div>
          <div class="result-rows">
            <div class="result-row">
              <span class="row-label">结果</span>
              <el-tag :type="result.pass_flag ? 'success' : 'danger'" effect="dark" round>
                {{ result.pass_flag ? "通过" : "未通过" }}
              </el-tag>
            </div>
            <div class="result-row">
              <span class="row-label">奖励 XP</span>
              <b class="row-xp">+{{ result.reward_xp }}</b>
            </div>
            <div class="result-row">
              <span class="row-label">当前等级</span>
              <b>Lv.{{ result.level }}</b>
            </div>
            <div class="result-row">
              <span class="row-label">技能状态</span>
              <b>{{ result.skill_mastery }} 分 · {{ result.skill_status }}</b>
            </div>
            <div class="result-row">
              <span class="row-label">距下一级</span>
              <span>{{ result.xp_to_next_level }} XP</span>
            </div>
          </div>
        </div>
        <div class="boss-message">{{ result.message }}</div>
        <div class="boss-actions">
          <el-button @click="visible = false">关闭</el-button>
          <el-button
            type="primary"
            :loading="loading"
            @click="open(skillNodeId, skillName)"
          >
            再战一次
          </el-button>
        </div>
      </template>

      <!-- 答题区 -->
      <template v-else>
        <div v-for="(q, qi) in questions" :key="q.id" class="boss-question">
          <div class="q-head">
            <span class="q-index">{{ qi + 1 }}</span>
            <span class="q-type">
              {{ typeLabel[q.question_type] ?? q.question_type }}
            </span>
            <span class="q-score">{{ q.score }} 分</span>
          </div>
          <div class="q-content">{{ q.content }}</div>

          <el-radio-group
            v-if="q.question_type === 'single'"
            v-model="answers[q.id]"
            class="q-opts"
          >
            <el-radio
              v-for="o in q.options"
              :key="o.key"
              :value="o.key"
              class="q-opt"
            >
              {{ o.key }}. {{ o.label }}
            </el-radio>
          </el-radio-group>

          <el-checkbox-group
            v-else-if="q.question_type === 'multiple'"
            :model-value="(answers[q.id] as string[] | undefined) ?? []"
            class="q-opts"
            @update:model-value="
              (val: string[]) => {
                answers[q.id] = val;
              }
            "
          >
            <el-checkbox
              v-for="o in q.options"
              :key="o.key"
              :label="o.key"
              class="q-opt"
            >
              {{ o.key }}. {{ o.label }}
            </el-checkbox>
          </el-checkbox-group>

          <el-radio-group
            v-else-if="q.question_type === 'judge'"
            v-model="answers[q.id]"
            class="q-opts"
          >
            <el-radio :value="true" class="q-opt">正确</el-radio>
            <el-radio :value="false" class="q-opt">错误</el-radio>
          </el-radio-group>
        </div>

        <div class="boss-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="!answered"
            :loading="submitting"
            @click="submit"
          >
            提交挑战（{{ questions.filter((q) => answers[q.id] !== undefined).length }}/{{ questions.length }}）
          </el-button>
        </div>
      </template>
    </div>
  </el-dialog>
</template>

<style scoped lang="scss">
.boss-body {
  min-height: 120px;
}

.boss-desc {
  margin-bottom: 14px;
}

.boss-question {
  border: 1px solid #eef1f8;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fafbff;

  .q-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;

    .q-index {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--sq-primary);
      color: #fff;
      font-size: 12px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .q-type {
      font-size: 12px;
      color: #6b7280;
    }

    .q-score {
      margin-left: auto;
      font-size: 12px;
      color: #d97706;
      font-weight: 600;
    }
  }

  .q-content {
    font-size: 14px;
    font-weight: 500;
    color: #1f2329;
    margin-bottom: 8px;
  }

  .q-opts {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .q-opt {
    margin-right: 0;
    width: 100%;
  }
}

.boss-result {
  display: flex;
  align-items: center;
  gap: 20px;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 12px;
  background: #eef2ff;

  &.win {
    background: #ecfdf5;
  }

  .result-score {
    text-align: center;
    flex-shrink: 0;

    .result-num {
      font-size: 42px;
      font-weight: 800;
      color: #4f6ef7;
      line-height: 1;
    }

    .result-unit {
      font-size: 13px;
      color: #6b7280;
    }
  }

  .result-rows {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 6px;

    .result-row {
      display: flex;
      justify-content: space-between;
      font-size: 13px;

      .row-label {
        color: #6b7280;
      }

      .row-xp {
        color: #d97706;
      }
    }
  }
}

.boss-message {
  font-size: 13px;
  color: #5a607f;
  line-height: 1.7;
  margin-bottom: 12px;
}

.boss-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>