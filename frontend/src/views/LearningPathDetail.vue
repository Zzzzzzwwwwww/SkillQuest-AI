<script setup lang="ts">
/*
 * 学习路径详情页（模块5 前端）
 * - 路径信息：目标岗位 / 总进度 / 掌握节点 / 总时长 / 累计预计
 * - 分阶段展示全部技能节点：状态、预估时长、岗位重要度、掌握度
 * - 点击节点：抽屉查看前置知识 + 推荐资源卡片 + 更新进度/断点
 * - 断点续学按钮：一键回到上次学习位置
 */
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Aim,
  ArrowLeft,
  CircleCheck,
  Clock,
  Flag,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import {
  getCurrentLearningPath,
  getLearningPathMap,
  recommendResources,
  resumeLearning,
  updateLearningProgress,
} from "@/api/learning_path";
import { STAGE_META } from "@/types/learning_path";
import type {
  LearningPathMap,
  LearningResource,
  LearningStageNode,
} from "@/types/learning_path";

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const pathData = ref<LearningPathMap | null>(null);

const stageOrder = computed(
  () => pathData.value?.stage_order ?? Object.keys(STAGE_META)
);
const allNodes = computed<LearningStageNode[]>(() =>
  stageOrder.value.flatMap((s) => pathData.value?.stages[s] ?? [])
);
const totalHours = computed(() =>
  allNodes.value.reduce((sum, n) => sum + (n.estimated_hours ?? 0), 0)
);

const STATUS_CLASS: Record<string, string> = {
  completed: "completed",
  learning: "learning",
  unlocked: "unlocked",
  locked: "locked",
};

const STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  learning: "学习中",
  unlocked: "可学习",
  locked: "未解锁",
};

const drawerOpen = ref(false);
const drawerLoading = ref(false);
const activeNode = ref<LearningStageNode | null>(null);
const resources = ref<LearningResource[]>([]);
const progressInput = ref(0);
const saving = ref(false);

async function loadPath() {
  loading.value = true;
  try {
    const pathId = Number(route.params.pathId);
    pathData.value =
      Number.isInteger(pathId) && pathId > 0
        ? await getLearningPathMap(pathId)
        : await getCurrentLearningPath();
  } catch {
    pathData.value = null;
  } finally {
    loading.value = false;
  }
}

async function doResume() {
  if (!pathData.value) return;
  const r = await resumeLearning({ path_id: pathData.value.path_id });
  if (r.resume_node) {
    ElMessage.success(r.hint);
    openNode(r.resume_node);
  } else {
    ElMessage.info(r.hint || "路径尚未开始");
  }
}

async function openNode(node: LearningStageNode) {
  activeNode.value = node;
  progressInput.value = node.progress_percent ?? 0;
  drawerOpen.value = true;
  drawerLoading.value = true;
  resources.value = [];
  try {
    resources.value = await recommendResources({
      skill_node_id: node.skill_node_id,
      limit: 6,
    });
  } catch {
    resources.value = [];
  } finally {
    drawerLoading.value = false;
  }
}

async function saveProgress() {
  if (!activeNode.value || !pathData.value) return;
  saving.value = true;
  try {
    const r = await updateLearningProgress({
      path_id: pathData.value.path_id,
      skill_node_id: activeNode.value.skill_node_id,
      progress_percent: progressInput.value,
    });
    pathData.value = r.path;
    if (r.updated_node) activeNode.value = r.updated_node;
    ElMessage.success(r.to_next ? "进度已保存，解锁下一节点！" : "进度已保存");
  } catch {
    /* 统一提示 */
  } finally {
    saving.value = false;
  }
}

function back() {
  router.push({ name: "LearningPath" });
}

onMounted(loadPath);
</script>

<template>
  <div class="page-container">
    <el-button text :icon="ArrowLeft" @click="back" class="back-btn">返回冒险地图</el-button>

    <template v-if="pathData">
      <!-- 路径信息头 -->
      <el-card shadow="hover" class="head-card" v-loading="loading">
        <div class="head-wrap">
          <div class="head-info">
            <h2>{{ pathData.path_name }}</h2>
            <p>{{ pathData.target_job }}</p>
          </div>
          <div class="head-stats">
            <div class="stat">
              <div class="num">{{ pathData.overall_progress }}<small>%</small></div>
              <div class="lbl"><el-icon><Flag /></el-icon> 整体进度</div>
            </div>
            <div class="stat">
              <div class="num">{{ pathData.mastered_nodes }}<small>/{{ pathData.total_nodes }}</small></div>
              <div class="lbl"><el-icon><CircleCheck /></el-icon> 掌握节点</div>
            </div>
            <div class="stat">
              <div class="num">{{ totalHours }}<small>h</small></div>
              <div class="lbl"><el-icon><Clock /></el-icon> 预计总时长</div>
            </div>
          </div>
        </div>

        <el-progress
          :percentage="pathData.overall_progress"
          :stroke-width="16"
          :show-text="false"
          :color="[
            { color: '#f59e0b', percentage: 40 },
            { color: '#6366f1', percentage: 80 },
            { color: '#22c55e', percentage: 100 },
          ]"
          class="main-progress"
        />

        <div class="head-actions" v-if="pathData.status !== 'completed'">
          <el-button type="primary" :icon="Aim" @click="doResume">断点续学</el-button>
        </div>
        <el-tag v-else type="success" effect="dark" class="done-tag">🎉 路线已通关</el-tag>
      </el-card>

      <!-- 分阶段节点详情 -->
      <div
        v-for="stage in stageOrder"
        :key="stage"
        class="stage-section"
      >
        <div class="stage-head">
          <span class="stage-icon">{{ STAGE_META[stage]?.icon }}</span>
          <b>{{ STAGE_META[stage]?.label }}段位</b>
          <span class="stage-desc">{{ STAGE_META[stage]?.desc }}</span>
          <span class="stage-count">
            {{ (pathData.stages[stage] ?? []).filter((n) => n.status === "completed").length }}
            / {{ (pathData.stages[stage] ?? []).length }} 完成
          </span>
        </div>

        <el-card
          v-for="node in pathData.stages[stage]"
          :key="node.id"
          shadow="hover"
          class="node-card"
          :class="STATUS_CLASS[node.status]"
          @click="openNode(node)"
        >
          <div class="node-left">
            <div class="node-status" :class="STATUS_CLASS[node.status]">
              {{ STATUS_LABEL[node.status] }}
            </div>
            <div class="node-main">
              <div class="node-name">
                {{ node.name }}
                <span class="type-tag">{{ node.node_type }}</span>
              </div>
              <div class="node-sub">
                <span class="cap">
                  {{ node.capability ? node.capability + " · " : "" }}{{ node.importance }}%重要度
                </span>
                <span class="hours"><el-icon><Clock /></el-icon>{{ node.estimated_hours }}h</span>
              </div>
              <el-progress
                :percentage="node.progress_percent"
                :stroke-width="8"
                :show-text="false"
                class="node-progress"
              />
            </div>
          </div>
          <div class="node-right">
            <span class="gap" v-if="node.gap > 0">缺口 {{ node.gap }}</span>
            <span class="arrow">›</span>
          </div>
        </el-card>

        <div v-if="!(pathData.stages[stage] ?? []).length" class="stage-empty">
          该段位暂无节点
        </div>
      </div>
    </template>

    <el-card shadow="hover" v-else-if="!loading">
      <el-empty description="找不到该学习路径" />
    </el-card>

    <!-- 节点详情抽屉 -->
    <el-drawer
      v-model="drawerOpen"
      size="420px"
      :title="activeNode ? `${activeNode.name} · 节点详情` : ''"
    >
      <template v-if="activeNode">
        <el-descriptions :column="2" border size="small" class="node-meta">
          <el-descriptions-item label="段位">
            {{ STAGE_META[activeNode.stage]?.label ?? activeNode.stage }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <span class="status-chip" :class="STATUS_CLASS[activeNode.status]">
              {{ STATUS_LABEL[activeNode.status] }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="预估时长">{{ activeNode.estimated_hours }}h</el-descriptions-item>
          <el-descriptions-item label="岗位重要度">{{ activeNode.importance }}%</el-descriptions-item>
          <el-descriptions-item label="掌握度">{{ activeNode.mastery }} / {{ activeNode.required_level }}</el-descriptions-item>
          <el-descriptions-item label="缺口">{{ activeNode.gap }}</el-descriptions-item>
        </el-descriptions>

        <div class="node-block">
          <b>前置知识</b>
          <div class="tag-list">
            <el-tag v-for="p in activeNode.prerequisites" :key="p" size="small" effect="plain">
              {{ p }}
            </el-tag>
            <span v-if="!activeNode.prerequisites.length" class="muted">无前置要求</span>
          </div>
        </div>

        <div class="node-block" v-if="pathData?.status !== 'completed'">
          <b>学习进度</b>
          <el-slider v-model="progressInput" :step="1" show-input class="progress-slider" />
          <el-button type="primary" size="small" :loading="saving" @click="saveProgress" style="width: 100%">
            保存进度与断点位置
          </el-button>
        </div>

        <div class="node-block">
          <b>推荐资源</b>
          <div v-loading="drawerLoading" class="resource-list">
            <el-card v-for="r in resources" :key="r.resource_id" shadow="never" class="resource-card">
              <div class="res-head">
                <el-tag size="small" effect="dark" type="info">{{ r.type_label }}</el-tag>
                <span class="score">★ {{ r.score }}</span>
              </div>
              <div class="res-title">{{ r.title }}</div>
              <div class="res-reason">{{ r.reason }}</div>
              <div class="res-meta">
                <span>难度 {{ r.difficulty }}</span>
                <span>{{ r.duration }} 分钟</span>
              </div>
            </el-card>
            <el-empty v-if="!drawerLoading && !resources.length" description="暂无推荐资源" :image-size="60" />
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.back-btn {
  margin-bottom: 6px;
  padding-left: 0;
}

.head-card {
  border-radius: 14px;
  border: none;
  margin-bottom: 20px;
  background: linear-gradient(135deg, #ffffff 0%, #f4f6ff 100%);

  .head-wrap {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;

    .head-info h2 {
      margin: 0 0 4px;
      font-size: 22px;
    }

    .head-info p {
      margin: 0;
      color: #6b7280;
      font-size: 13px;
    }

    .head-stats {
      display: flex;
      gap: 24px;

      .stat {
        text-align: center;

        .num {
          font-size: 24px;
          font-weight: 700;
          color: #4f6ef7;

          small {
            font-size: 13px;
            font-weight: 400;
          }
        }

        .lbl {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          font-size: 12px;
          color: #9ca3af;
        }
      }
    }
  }

  .main-progress {
    margin: 18px 0 12px;
  }

  .head-actions {
    margin-top: 8px;
  }

  .done-tag {
    margin-top: 6px;
  }
}

.stage-section {
  margin-bottom: 22px;

  .stage-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .stage-icon {
      font-size: 22px;
    }

    b {
      font-size: 15px;
    }

    .stage-desc {
      font-size: 12px;
      color: #9ca3af;
      flex: 1;
    }

    .stage-count {
      font-size: 12px;
      color: #6b7280;
    }
  }

  .node-card {
    border-radius: 12px;
    margin-bottom: 10px;
    cursor: pointer;
    border: 1px solid #eef1f8;
    transition: transform 0.15s, box-shadow 0.15s;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(79, 110, 247, 0.1);
    }

    .node-left {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
    }

    .node-status {
      width: 56px;
      text-align: center;
      font-size: 12px;
      padding: 4px 0;
      border-radius: 8px;
      flex-shrink: 0;

      &.completed {
        background: #ecfdf5;
        color: #059669;
      }
      &.learning {
        background: #fffbeb;
        color: #d97706;
      }
      &.unlocked {
        background: #eef2ff;
        color: #4f6ef7;
      }
      &.locked {
        background: #f3f4f6;
        color: #9ca3af;
      }
    }

    .node-main {
      flex: 1;

      .node-name {
        font-weight: 600;
        font-size: 14px;

        .type-tag {
          font-weight: 400;
          font-size: 11px;
          color: #9ca3af;
          border: 1px solid #e5e7eb;
          border-radius: 4px;
          padding: 0 6px;
          margin-left: 6px;
        }
      }

      .node-sub {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 12px;
        color: #9ca3af;
        margin-top: 2px;

        .hours {
          display: inline-flex;
          align-items: center;
          gap: 2px;
        }
      }

      .node-progress {
        margin-top: 8px;
      }
    }

    .node-right {
      display: flex;
      align-items: center;
      gap: 8px;

      .gap {
        font-size: 12px;
        color: #ef4444;
        background: #fef2f2;
        padding: 2px 8px;
        border-radius: 999px;
      }

      .arrow {
        font-size: 22px;
        color: #d1d5db;
      }
    }
  }

  .stage-empty {
    color: #d1d5db;
    font-size: 13px;
    padding: 8px 4px;
  }
}

.node-drawer {
  .node-meta {
    margin-bottom: 16px;
  }

  .node-block {
    margin-top: 18px;

    > b {
      display: block;
      margin-bottom: 10px;
      font-size: 14px;
    }

    .tag-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .progress-slider {
      margin: 4px 0 14px;
    }

    .resource-list {
      display: flex;
      flex-direction: column;
      gap: 10px;

      .resource-card {
        border-radius: 10px;
        border: 1px solid #eef1f8;

        .res-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;

          .score {
            color: #d97706;
            font-weight: 600;
          }
        }

        .res-title {
          font-weight: 600;
          font-size: 13px;
          margin-bottom: 4px;
        }

        .res-reason {
          font-size: 12px;
          color: #6b7280;
          line-height: 1.5;
        }

        .res-meta {
          margin-top: 6px;
          font-size: 11px;
          color: #9ca3af;
          display: flex;
          gap: 12px;
        }
      }
    }
  }
}

.status-chip {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;

  &.completed {
    background: #ecfdf5;
    color: #059669;
  }
  &.learning {
    background: #fffbeb;
    color: #d97706;
  }
  &.unlocked {
    background: #eef2ff;
    color: #4f6ef7;
  }
  &.locked {
    background: #f3f4f6;
    color: #9ca3af;
  }
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

@media (max-width: 768px) {
  .head-stats {
    gap: 12px;
  }
}
</style>