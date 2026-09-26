<script setup lang="ts">
/*
 * 冒险地图页（模块5 前端）
 * - 路径总览：目标岗位 / 总进度条 / 掌握节点 / 总时长
 * - 冒险地图：青铜→王者 6 段位路线，节点按状态着色（完成绿/学习中黄/解锁蓝/锁定灰）
 * - 断点续学：返回上次学习位置并定位到当前节点
 * - 点击节点：抽屉展示节点详情（前置/时长）+ 规则推荐资源卡片
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  Aim,
  CircleCheck,
  Clock,
  Flag,
  MapLocation,
  Upload,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import {
  generateLearningPath,
  getCurrentLearningPath,
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

const router = useRouter();

const loading = ref(false);
const generating = ref(false);
const pathData = ref<LearningPathMap | null>(null);

const drawerOpen = ref(false);
const drawerLoading = ref(false);
const activeNode = ref<LearningStageNode | null>(null);
const resources = ref<LearningResource[]>([]);
const resType = ref("");
const RES_TYPE_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "全部" },
  { key: "video", label: "视频" },
  { key: "course", label: "课程" },
  { key: "article", label: "文章" },
  { key: "exercise", label: "练习" },
];
const progressInput = ref(0);

/** 段位顺序 */
const stageOrder = computed(
  () => pathData.value?.stage_order ?? Object.keys(STAGE_META)
);

/** 节点状态 → 样式类（与后端规则一致） */
const STATUS_CLASS: Record<string, string> = {
  completed: "completed",
  learning: "learning",
  unlocked: "unlocked",
  locked: "locked",
};

/** 状态文案 */
const STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  learning: "学习中",
  unlocked: "可学习",
  locked: "未解锁",
};

/** 当前进行中的节点（未完成为准，无则取第一个） */
const currentNodes = computed(() => {
  if (!pathData.value) return [];
  return stageOrder.value.flatMap(
    (s) => pathData.value?.stages[s] ?? []
  );
});

const currentNode = computed(() => {
  const list = currentNodes.value;
  if (!list.length) return null;
  const curId = pathData.value?.current_node_id;
  const target =
    list.find((n) => n.id === curId) ??
    list.find((n) => n.status === "learning") ??
    list.find((n) => n.status === "unlocked");
  return target ?? null;
});

async function loadPath() {
  loading.value = true;
  try {
    pathData.value = await getCurrentLearningPath();
    if (pathData.value) {
      progressInput.value = currentNode.value?.progress_percent ?? 0;
    }
  } catch {
    pathData.value = null;
  } finally {
    loading.value = false;
  }
}

async function doGenerate(force = false) {
  generating.value = true;
  try {
    const r = await generateLearningPath({ force });
    pathData.value = r.path;
    ElMessage.success(force ? "已重新生成学习路径" : "学习路径已生成，开始冒险吧！");
  } catch {
    /* 错误提示已由拦截器统一处理 */
  } finally {
    generating.value = false;
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
    await loadPath();
  }
}

async function loadResources() {
  if (!activeNode.value) return;
  drawerLoading.value = true;
  resources.value = [];
  try {
    resources.value = await recommendResources({
      skill_node_id: activeNode.value.skill_node_id,
      resource_type: resType.value || undefined,
      limit: 6,
    });
  } catch {
    resources.value = [];
  } finally {
    drawerLoading.value = false;
  }
}

async function openNode(node: LearningStageNode) {
  activeNode.value = node;
  progressInput.value = node.progress_percent ?? 0;
  drawerOpen.value = true;
  await loadResources();
}

async function saveProgress() {
  if (!activeNode.value || !pathData.value) return;
  try {
    await updateLearningProgress({
      path_id: pathData.value.path_id,
      skill_node_id: activeNode.value.skill_node_id,
      progress_percent: progressInput.value,
    });
    ElMessage.success("进度已保存");
    drawerOpen.value = false;
    await loadPath();
  } catch {
    /* 统一错误提示 */
  }
}

function viewDetail() {
  if (!pathData.value) return;
  drawerOpen.value = false;
  router.push({ name: "LearningPathDetail", params: { pathId: pathData.value.path_id } });
}

function nodeIcon(node: LearningStageNode): string {
  switch (node.node_type) {
    case "knowledge":
      return "📘";
    case "capability":
      return "🗂️";
    case "skill":
      return node.status === "completed" ? "✅" : "⚔️";
    default:
      return "📍";
  }
}

onMounted(loadPath);
</script>

<template>
  <div class="page-container">
    <!-- 空状态：无路径 -->
    <el-card shadow="hover" v-if="!loading && !pathData" class="empty-card">
      <el-empty description="还没有学习路径，先规划一条属于你的成长路线吧！">
        <template #image>
          <div class="empty-hero">🗺️</div>
        </template>
        <el-button type="primary" :loading="generating" @click="doGenerate()">
          生成我的学习路径
        </el-button>
      </el-empty>
    </el-card>

    <template v-else-if="pathData">
      <!-- 路径总览 -->
      <el-card shadow="hover" class="overview-card" v-loading="loading">
        <div class="overview-head">
          <div class="overview-title">
            <div class="badge-route">
              <el-icon><MapLocation /></el-icon>
              冒险地图
            </div>
            <h2>{{ pathData.path_name }}</h2>
            <div class="sub">
              <span class="job-tag">{{ pathData.target_job }}</span>
              <span v-if="pathData.status === 'completed'"
                class="state-tag completed">已通关</span>
              <span v-else class="state-tag">进行中</span>
            </div>
          </div>
          <div class="overview-stats">
            <div class="stat">
              <div class="num">{{ pathData.overall_progress }}<small>%</small></div>
              <div class="lbl"><el-icon><Flag /></el-icon> 整体进度</div>
            </div>
            <div class="stat">
              <div class="num">{{ pathData.mastered_nodes }}/{{ pathData.total_nodes }}</div>
              <div class="lbl"><el-icon><CircleCheck /></el-icon> 掌握节点</div>
            </div>
          </div>
        </div>

        <el-progress
          :percentage="pathData.overall_progress"
          :stroke-width="14"
          :show-text="false"
          :color="[
            { color: '#f59e0b', percentage: 40 },
            { color: '#6366f1', percentage: 80 },
            { color: '#22c55e', percentage: 100 },
          ]"
        />

        <div class="overview-actions">
          <el-button type="primary" :icon="Aim" @click="doResume" :disabled="!currentNode">
            {{ currentNode ? `继续学习：${currentNode.name}` : "断点续学" }}
          </el-button>
          <el-button
            :icon="Upload"
            @click="viewDetail"
            :disabled="pathData.status === 'completed'"
          >查看完整路线</el-button>
          <el-button
            text
            @click="doGenerate(true)"
            :loading="generating"
            class="regen-btn"
          >重新安排路线</el-button>
        </div>
      </el-card>

      <!-- 冒险地图：6 段位路线 -->
      <el-card shadow="never" class="map-card" v-loading="loading">
        <template #header>
          <div class="map-header">
            <b>🌍 成长冒险路线</b>
            <div class="legend">
              <span class="dot completed"></span>已完成
              <span class="dot learning"></span>学习中
              <span class="dot unlocked"></span>可学习
              <span class="dot locked"></span>未解锁
            </div>
          </div>
        </template>

        <div class="adventure-map">
          <div
            v-for="(stage, idx) in stageOrder"
            :key="stage"
            class="stage-row"
          >
            <div class="stage-badge" :style="{ color: STAGE_META[stage]?.color }"
                 :title="STAGE_META[stage]?.desc">
              <span class="stage-icon">{{ STAGE_META[stage]?.icon }}</span>
              <span class="stage-name">{{ STAGE_META[stage]?.label }}</span>
            </div>

            <div class="stage-track">
              <div class="rail" v-if="idx > 0"></div>
              <template v-if="(pathData.stages[stage] ?? []).length">
                <div
                  v-for="node in pathData.stages[stage]"
                  :key="node.id"
                  class="node-slot"
                  @click="openNode(node)"
                >
                  <div class="node-pin" :class="[STATUS_CLASS[node.status], { current: node.id === pathData.current_node_id }]">
                    <span class="node-emoji">{{ nodeIcon(node) }}</span>
                    <span v-if="node.status === 'completed'" class="check">✔</span>
                  </div>
                  <div class="node-name">{{ node.name }}</div>
                  <div class="node-hours">
                    <el-icon><Clock /></el-icon>{{ node.estimated_hours }}h
                  </div>
                </div>
              </template>
              <div v-else class="stage-empty">—</div>
            </div>
          </div>
        </div>
      </el-card>
    </template>

    <!-- 节点详情抽屉 -->
    <el-drawer
      v-model="drawerOpen"
      size="420px"
      :title="activeNode ? `${activeNode.name} · 节点详情` : ''"
      class="node-drawer"
    >
      <template v-if="activeNode">
        <el-descriptions :column="2" border size="small" class="node-meta">
          <el-descriptions-item label="段位">
            {{ STAGE_META[activeNode.stage]?.label ?? activeNode.stage }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <span class="status-chip"
                  :class="STATUS_CLASS[activeNode.status]">{{ STATUS_LABEL[activeNode.status] }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ activeNode.node_type }}
          </el-descriptions-item>
          <el-descriptions-item label="预估时长">
            {{ activeNode.estimated_hours }} 小时
          </el-descriptions-item>
          <el-descriptions-item label="岗位重要度">
            {{ activeNode.importance }}
          </el-descriptions-item>
          <el-descriptions-item label="掌握度">
            {{ activeNode.mastery }} / {{ activeNode.required_level }}
          </el-descriptions-item>
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

        <!-- 进度更新 -->
        <div class="node-block" v-if="pathData?.status !== 'completed'">
          <b>更新学习进度</b>
          <el-slider v-model="progressInput" :step="1" show-input class="progress-slider" />
          <el-button
            type="primary"
            size="small"
            :loading="generating"
            @click="saveProgress"
            style="width: 100%"
          >保存进度与断点</el-button>
        </div>

        <!-- 资源推荐卡片 -->
        <div class="node-block">
          <b>推荐资源</b>
          <el-radio-group
            v-model="resType"
            size="small"
            class="res-type-filter"
            @change="loadResources"
          >
            <el-radio-button v-for="f in RES_TYPE_FILTERS" :key="f.key" :value="f.key">
              {{ f.label }}
            </el-radio-button>
          </el-radio-group>
          <div v-loading="drawerLoading" class="resource-list">
            <el-card
              v-for="r in resources"
              :key="r.resource_id"
              shadow="never"
              class="resource-card"
            >
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
            <el-empty v-if="!drawerLoading && !resources.length"
                      description="暂无推荐资源" :image-size="60" />
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.overview-card {
  border-radius: 14px;
  border: none;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #ffffff 0%, #f4f6ff 100%);

  .overview-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
  }

  .overview-title {
    .badge-route {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #6b7280;
      letter-spacing: 1px;
    }

    h2 {
      margin: 6px 0 4px;
      font-size: 20px;
      color: #1f2329;
    }

    .sub {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #6b7280;
    }

    .job-tag {
      background: rgba(79, 110, 247, 0.1);
      color: #4f6ef7;
      padding: 2px 10px;
      border-radius: 999px;
    }

    .state-tag {
      padding: 2px 10px;
      border-radius: 999px;
      background: #fffbeb;
      color: #d97706;

      &.completed {
        background: #ecfdf5;
        color: #059669;
      }
    }
  }

  .overview-stats {
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

  .overview-actions {
    margin-top: 14px;
    display: flex;
    align-items: center;
    gap: 4px;

    .regen-btn {
      margin-left: auto;
      color: #9ca3af;
    }
  }
}

.map-card {
  border-radius: 14px;
  border: none;

  .map-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;

    .legend {
      font-size: 12px;
      color: #6b7280;
      display: flex;
      align-items: center;
      gap: 10px;

      .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;

        &.completed {
          background: #22c55e;
        }
        &.learning {
          background: #f59e0b;
        }
        &.unlocked {
          background: #4f6ef7;
        }
        &.locked {
          background: #d1d5db;
        }
      }
    }
  }
}

.adventure-map {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.stage-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 12px;
  align-items: start;

  .stage-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 18px;
    font-weight: 700;

    .stage-icon {
      font-size: 26px;
      line-height: 1;
    }

    .stage-name {
      font-size: 13px;
      margin-top: 4px;
      letter-spacing: 1px;
    }
  }

  .stage-track {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    padding: 18px 12px 8px;

    .rail {
      position: absolute;
      left: 20px;
      top: -10px;
      height: 18px;
      border-left: 2px dashed #e5e7eb;
    }
  }

  .stage-empty {
    color: #d1d5db;
    font-size: 22px;
    padding: 18px;
  }

  .node-slot {
    width: 96px;
    text-align: center;
    cursor: pointer;
    padding: 6px 2px;
    border-radius: 10px;
    transition: transform 0.15s, box-shadow 0.15s;

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 16px rgba(79, 110, 247, 0.12);
      background: #f8faff;
    }

    .node-pin {
      width: 52px;
      height: 52px;
      margin: 0 auto;
      border-radius: 50% 50% 50% 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      border: 3px solid #fff;
      box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12);
      transition: border-color 0.15s;

      .node-emoji {
        font-size: 22px;
      }

      .check {
        position: absolute;
        right: -4px;
        top: -4px;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #22c55e;
        color: #fff;
        font-size: 11px;
        line-height: 18px;
        text-align: center;
      }

      &.completed {
        background: #22c55e;
      }
      &.learning {
        background: #f59e0b;
      }
      &.unlocked {
        background: #4f6ef7;
      }
      &.locked {
        background: #d1d5db;
      }

      &.current {
        border: 3px solid #fff;
        box-shadow: 0 0 0 3px #6366f1, 0 4px 14px rgba(99, 102, 241, 0.35);
      }
    }

    .node-name {
      font-size: 12px;
      margin-top: 8px;
      line-height: 1.3;
      color: #1f2329;
      min-height: 30px;
    }

    .node-hours {
      font-size: 11px;
      color: #9ca3af;
      display: inline-flex;
      align-items: center;
      gap: 2px;
    }
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

.empty-card {
  border-radius: 14px;
  border: none;

  .empty-hero {
    font-size: 64px;
    text-align: center;
  }
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

@media (max-width: 768px) {
  .stage-row {
    grid-template-columns: 56px 1fr;
  }
  .overview-stats {
    gap: 12px;
  }
}
</style>