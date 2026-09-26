<script setup lang="ts">
/*
 * 技能图谱页（模块4）
 * - 岗位技能树（岗位→能力域→技能→知识点），ECharts 树图展示
 * - 节点颜色：绿=已掌握 / 黄=学习中 / 灰=未掌握
 * - 点击节点 → 侧边栏详情（重要度/前置知识/推荐资源/关联岗位）
 * - Skill Gap 分析区：行业/岗位要求 vs 我的能力
 * - 状态筛选 / 展开折叠 / 统计概览
 */
import * as echarts from "echarts";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeft,
  Connection,
  Refresh,
  Sell,
  TrendCharts,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import {
  getJobSkillTree,
  getJobs,
  getSkillDetail,
  updateUserSkillStatus,
} from "@/api/skill";
import BossChallenge from "@/views/skill/BossChallenge.vue";
import type {
  JobItem,
  JobSkillTreeResult,
  SkillDetailResult,
  SkillNodeItem,
} from "@/types/skill";

/** 整体进度颜色 */
function overallColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score > 0) return "#f59e0b";
  return "#9ca3af";
}

/** 节点状态 → 颜色（与后端 NODE_COLORS 保持一致） */
const STATUS_COLOR: Record<string, string> = {
  mastered: "#22c55e",
  learning: "#f59e0b",
  not_started: "#9ca3af",
};

const STATUS_LABEL: Record<string, string> = {
  mastered: "已掌握",
  learning: "学习中",
  not_started: "未掌握",
};

/** 节点类型 → 文案（与后端一致） */
const NODE_TYPE_LABEL: Record<string, string> = {
  job: "岗位",
  capability: "能力域",
  skill: "技能",
  knowledge: "知识点",
};

/** ECharts 树节点 */
interface GraphNode {
  name: string;
  id: number;
  node_type: string;
  level: number;
  status: string;
  mastery_score: number;
  importance: number;
  itemStyle: { color: string };
  children?: GraphNode[];
}

const route = useRoute();
const router = useRouter();

const bossRef = ref<InstanceType<typeof BossChallenge> | null>(null);

const loading = ref(false);
const detailLoading = ref(false);
const jobs = ref<JobItem[]>([]);
const data = ref<JobSkillTreeResult | null>(null);
const detail = ref<SkillDetailResult | null>(null);
const filterStatus = ref<string>("all");
const expandAll = ref(false);
const containerRef = ref<HTMLDivElement | null>(null);
const detailVisible = ref(false);

let chart: echarts.ECharts | null = null;

const currentJobId = computed(() => {
  const raw = route.query.job_id;
  const id = Number(raw);
  return Number.isInteger(id) && id > 0 ? id : (data.value?.job.id ?? 0);
});

/** 树节点状态统计（不含 job 根） */
const statMap = computed(() => {
  const stat = { total: 0, mastered: 0, learning: 0, not_started: 0 };
  const walk = (node: SkillNodeItem): void => {
    if (node.node_type !== "job") {
      stat.total += 1;
      if (node.status === "mastered") stat.mastered += 1;
      else if (node.status === "learning") stat.learning += 1;
      else stat.not_started += 1;
    }
    node.children?.forEach(walk);
  };
  if (data.value) walk(data.value.tree);
  return stat;
});

/** 岗位完整名称 */
const jobCaption = computed(
  () => `${data.value?.job.job_name ?? ""} · ${data.value?.job.job_family ?? ""}`
);

/** 展开/折叠按钮文本 */
const expandAllLabel = computed(() =>
  expandAll.value ? "全部折叠" : "全部展开"
);

/** 状态筛选后的树（仅保留符合状态的节点及其祖先） */
const filteredTree = computed<GraphNode | null>(() => {
  if (!data.value) return null;
  const raw = toGraphNode(data.value.tree);
  if (filterStatus.value === "all") return raw;
  return pruneTree(raw, filterStatus.value);
});

async function loadJobs(): Promise<void> {
  try {
    jobs.value = await getJobs();
  } catch {
    jobs.value = [];
  }
}

async function loadTree(jobId: number): Promise<void> {
  loading.value = true;
  detail.value = null;
  try {
    data.value = await getJobSkillTree(jobId);
    renderChart();
  } finally {
    loading.value = false;
  }
}

/** 把后端树节点转为 ECharts tree 数据 */
function toGraphNode(node: SkillNodeItem): GraphNode {
  return {
    name: node.name,
    id: node.id,
    node_type: node.node_type,
    level: node.level,
    status: node.status,
    mastery_score: node.mastery_score,
    importance: node.importance,
    itemStyle: { color: STATUS_COLOR[node.status] ?? "#9ca3af" },
    children: node.children?.length ? node.children.map(toGraphNode) : undefined,
  };
}

/** 按状态裁剪树：保留符合状态的节点与必要祖先链 */
function pruneTree(node: GraphNode, status: string): GraphNode | null {
  const children = (node.children ?? [])
    .map((c) => pruneTree(c, status))
    .filter((c): c is GraphNode => c !== null);
  if (node.status === status || children.length > 0 || node.node_type === "job") {
    return { ...node, children: children.length ? children : undefined };
  }
  return null;
}

function renderChart(): void {
  if (!containerRef.value) return;
  if (!chart) chart = echarts.init(containerRef.value);
  const root = filteredTree.value;
  if (!root) return;

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "#e4e9f7",
      textStyle: { color: "#1f2329" },
      formatter: (params: unknown): string => {
        const p = params as { data: GraphNode };
        const d = p.data;
        return [
          `<b>${d.name}</b>`,
          `类型：${NODE_TYPE_LABEL[d.node_type] ?? d.node_type}`,
          `状态：<span style="color:${STATUS_COLOR[d.status]}">${STATUS_LABEL[d.status] ?? d.status}</span>`,
          `掌握度：${d.mastery_score} / 100`,
          `重要度：${d.importance}`,
        ].join("<br/>");
      },
    },
    series: [
      {
        type: "tree",
        data: [root],
        left: 30,
        right: 200,
        top: 30,
        bottom: 30,
        orient: "LR",
        symbol: "circle",
        symbolSize: (val: unknown) => {
          const d = val as GraphNode;
          if (d.node_type === "job") return 14;
          if (d.node_type === "capability") return 12;
          if (d.node_type === "skill") return 10;
          return 7;
        },
        expandAndCollapse: true,
        initialTreeDepth: expandAll.value ? 100 : 2,
        itemStyle: {
          borderColor: "#ffffff",
          borderWidth: 2,
          shadowBlur: 6,
          shadowColor: "rgba(80,100,180,0.25)",
        },
        lineStyle: { color: "#c9d2ee", width: 1.5 },
        label: {
          position: "left",
          verticalAlign: "middle",
          align: "right",
          fontSize: 13,
          fontWeight: 500,
          color: "#3a4258",
          formatter: (params: unknown): string => {
            const d = (params as { data: GraphNode }).data;
            return `${d.name}  ${d.mastery_score > 0 ? `${d.mastery_score}` : ""}`;
          },
        },
        leaves: {
          label: { position: "right", align: "left" },
        },
        emphasis: {
          focus: "relative",
          itemStyle: { borderColor: "#4f6ef7", borderWidth: 3 },
        },
        animationDuration: 500,
        animationDurationUpdate: 400,
      },
    ],
  };
  chart.setOption(option, true);
  chart.off("click");
  chart.on("click", (params: unknown) => {
    const p = params as {
      data: GraphNode;
      event?: unknown;
    };
    if (p.data && p.data.id) {
      openDetail(p.data.id, p.data.node_type);
    }
  });
}

/** 展开/折叠全部节点 */
function toggleExpand(): void {
  expandAll.value = !expandAll.value;
  renderChart();
}

/** 打开节点详情（岗位节点显示概览，其余请求详情接口） */
async function openDetail(nodeId: number, nodeType: string): Promise<void> {
  detailVisible.value = true;
  if (nodeType === "job" || !data.value) {
    detail.value = null;
    return;
  }
  detailLoading.value = true;
  try {
    detail.value = await getSkillDetail(nodeId);
  } finally {
    detailLoading.value = false;
  }
}

/** 快捷标记掌握状态（规则触发，同步刷新图谱） */
async function quickMark(status: string): Promise<void> {
  if (!detail.value) return;
  const payload = { items: [{ skill_node_id: detail.value.id, status, mastery_score: detail.value.mastery_score }] };
  try {
    await updateUserSkillStatus(payload);
    ElMessage.success(`已标记为「${STATUS_LABEL[status] ?? status}」`);
    if (data.value) await loadTree(data.value.job.id);
    if (detail.value) await openDetail(detail.value.id, detail.value.node_type);
  } catch {
    /* 错误已被拦截器提示 */
  }
}

/** 打开 Boss 挑战（闭环6：挑战通过 → XP/技能等级自动升级） */
function openBoss(): void {
  if (!detail.value || detail.value.node_type !== "skill") return;
  void bossRef.value?.open(detail.value.id, detail.value.name);
}

/** Boss 挑战完成后刷新图谱掌握状态 */
function onBossFinished(): void {
  if (data.value) void loadTree(data.value.job.id);
}

function changeJob(jobId: number): void {
  router.replace({ path: "/skill-tree", query: { job_id: String(jobId) } });
}

function goJobSelect(): void {
  router.push("/skill-tree/jobs");
}

function handleResize(): void {
  chart?.resize();
}

watch(filteredTree, () => renderChart());
watch(
  () => route.query.job_id,
  (v) => {
    const id = Number(v);
    if (Number.isInteger(id) && id > 0) void loadTree(id);
  }
);

onMounted(async () => {
  await loadJobs();
  handleResize();
  window.addEventListener("resize", handleResize);
  const id = currentJobId.value;
  if (id) {
    await loadTree(id);
  } else if (jobs.value.length) {
    changeJob(jobs.value[0].id);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 顶部：岗位信息 + 操作 -->
    <el-card shadow="never" class="top-card">
      <div class="top-row">
        <div class="job-info">
          <el-button
            :icon="ArrowLeft"
            text
            circle
            title="返回岗位选择"
            @click="goJobSelect"
          />
          <div>
            <h2 class="job-title">
              {{ data?.job.job_name ?? "技能图谱" }}
              <el-tag size="small" effect="plain" round>{{ data?.job.job_family }}</el-tag>
            </h2>
            <p class="job-desc">{{ data?.job.description ?? "选择岗位查看技能图谱" }}</p>
          </div>
        </div>
        <div class="top-actions">
          <el-select
            :model-value="currentJobId"
            placeholder="切换岗位"
            size="default"
            style="width: 220px"
            @update:model-value="changeJob(Number($event))"
          >
            <el-option
              v-for="job in jobs"
              :key="job.id"
              :label="job.job_name"
              :value="job.id"
            />
          </el-select>
          <el-button :icon="Refresh" round @click="currentJobId && loadTree(currentJobId)">
            刷新
          </el-button>
        </div>
      </div>

      <!-- 统计概览 -->
      <div class="stats">
        <div class="stat-item">
          <span class="stat-num" style="color: #4f6ef7">{{ statMap.total }}</span>
          <span class="stat-label">节点总数</span>
        </div>
        <div class="stat-item">
          <span class="stat-num" style="color: #22c55e">{{ statMap.mastered }}</span>
          <span class="stat-label">已掌握</span>
        </div>
        <div class="stat-item">
          <span class="stat-num" style="color: #f59e0b">{{ statMap.learning }}</span>
          <span class="stat-label">学习中</span>
        </div>
        <div class="stat-item">
          <span class="stat-num" style="color: #9ca3af">{{ statMap.not_started }}</span>
          <span class="stat-label">未掌握</span>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16" class="mt-16">
      <!-- 图谱 + 筛选 -->
      <el-col :xs="24" :lg="16" class="mb-16">
        <el-card shadow="never" class="graph-card">
          <template #header>
            <div class="graph-toolbar">
              <div class="graph-title">
                <el-icon class="title-icon"><Connection /></el-icon>
                <span>{{ jobCaption }}</span>
                <el-tag size="small" effect="light" round>可缩放/折叠</el-tag>
              </div>
              <div class="toolbar-actions">
                <el-radio-group v-model="filterStatus" size="small">
                  <el-radio-button value="all">全部</el-radio-button>
                  <el-radio-button value="mastered">已掌握</el-radio-button>
                  <el-radio-button value="learning">学习中</el-radio-button>
                  <el-radio-button value="not_started">未掌握</el-radio-button>
                </el-radio-group>
                <el-button size="small" :icon="Sell" round @click="toggleExpand">
                  {{ expandAllLabel }}
                </el-button>
              </div>
            </div>
          </template>
          <div ref="containerRef" class="graph-canvas"></div>
          <el-alert
            v-if="!data"
            title="请先在顶部选择岗位，或从「岗位选择」页进入。"
            type="info"
            :closable="false"
            class="graph-tip"
          />
        </el-card>
      </el-col>

      <!-- 右侧：详情 + Gap 分析 -->
      <el-col :xs="24" :lg="8">
        <!-- Skill Gap 分析 -->
        <el-card shadow="never" class="gap-card mb-16" v-if="data">
          <template #header>
            <div class="block-title">
              <el-icon class="title-icon"><TrendCharts /></el-icon>
              <span>Skill Gap 分析</span>
              <el-tag size="small" type="warning" effect="light" round>
                行业要求 vs 我的能力
              </el-tag>
            </div>
          </template>
          <div class="gap-metrics">
            <div class="metric">
              <el-progress
                type="dashboard"
                :percentage="Math.round(data.summary.overall_mastery)"
                :color="overallColor(data.summary.overall_mastery)"
                :width="96"
              >
                <template #default>
                  <span class="metric-num">{{ Math.round(data.summary.overall_mastery) }}</span>
                </template>
              </el-progress>
              <span class="metric-label">综合掌握度</span>
            </div>
            <div class="metric">
              <el-progress
                type="dashboard"
                :percentage="Math.round(data.summary.fit_rate)"
                :color="overallColor(data.summary.fit_rate)"
                :width="96"
              >
                <template #default>
                  <span class="metric-num">{{ Math.round(data.summary.fit_rate) }}</span>
                </template>
              </el-progress>
              <span class="metric-label">岗位匹配度</span>
            </div>
          </div>
          <p class="gap-summary">
            共需 {{ data.summary.skill_count }} 项技能，已达标
            {{ data.summary.mastered_count }} 项（掌握度 ≥ 岗位要求等级）。
          </p>
          <el-table
            :data="data.summary.gaps.filter((g) => Number(g.gap) > 0).slice(0, 6)"
            size="small"
            class="gap-table"
          >
            <el-table-column prop="name" label="技能" min-width="90" />
            <el-table-column prop="importance" label="重要" width="52" />
            <el-table-column prop="required" label="要求" width="52" />
            <el-table-column prop="mastery" label="当前" width="52" />
            <el-table-column label="差距" width="60">
              <template #default="{ row }">
                <el-tag size="small" type="danger" effect="light" round>
                  {{ Number(row.gap).toFixed(0) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详情侧边栏 -->
    <el-drawer
      v-model="detailVisible"
      size="38%"
      :with-header="false"
      class="sq-detail-drawer"
    >
      <div v-loading="detailLoading" class="drawer-body">
        <template v-if="detail">
          <div class="drawer-head">
            <div>
              <h2 class="drawer-title">{{ detail.name }}</h2>
              <p class="drawer-sub">
                {{ detail.node_type_label }} · 重要度 {{ detail.importance }}
              </p>
            </div>
            <el-tag
              size="large"
              effect="dark"
              :color="STATUS_COLOR[detail.status]"
              round
            >
              {{ STATUS_LABEL[detail.status] ?? detail.status }}
            </el-tag>
          </div>

          <p class="drawer-desc">{{ detail.description || "暂无描述" }}</p>

          <div class="drawer-panel">
            <h4 class="panel-title">掌握进度</h4>
            <el-progress
              :percentage="detail.mastery_score"
              :color="STATUS_COLOR[detail.status]"
              :stroke-width="10"
            />
          </div>

          <div class="drawer-panel">
            <h4 class="panel-title">快速标记</h4>
            <div class="detail-quick-actions">
              <el-button size="small" type="success" round @click="quickMark('mastered')">
                已掌握
              </el-button>
              <el-button size="small" type="warning" round @click="quickMark('learning')">
                学习中
              </el-button>
              <el-button size="small" round @click="quickMark('not_started')">
                未掌握
              </el-button>
            </div>
          </div>

          <div v-if="detail.node_type === 'skill'" class="drawer-panel">
            <h4 class="panel-title">Boss 挑战</h4>
            <p class="boss-tip">
              通过(≥60 分)当前技能的 Boss 挑战，将自动发放经验并升级技能等级。
            </p>
            <el-button type="danger" round class="boss-btn" @click="openBoss">
              开始 Boss 挑战
            </el-button>
          </div>

          <div class="drawer-panel">
            <h4 class="panel-title">前置知识</h4>
            <template v-if="detail.prerequisites.length">
              <div
                v-for="p in detail.prerequisites"
                :key="p.name"
                class="prereq-line"
              >
                <span :style="{ color: STATUS_COLOR[p.status] }" class="dot"></span>
                <span>{{ p.name }}</span>
                <span class="prereq-status">
                  {{ STATUS_LABEL[p.status] ?? p.status }}
                </span>
              </div>
            </template>
            <el-empty v-else description="无前置知识" :image-size="50" />
          </div>

          <div class="drawer-panel">
            <h4 class="panel-title">推荐资源</h4>
            <div v-for="r in detail.resources" :key="r.title" class="resource-item">
              <el-tag size="small" effect="plain" round>{{ r.type }}</el-tag>
              <div class="resource-body">
                <b>{{ r.title }}</b>
                <p>{{ r.desc }}</p>
              </div>
            </div>
          </div>

          <div class="drawer-panel">
            <h4 class="panel-title">关联岗位</h4>
            <div v-for="job in detail.related_jobs" :key="job.job_id" class="rel-job">
              <span>{{ job.job_name }}</span>
              <el-tag size="small" effect="plain" round>
                重要度 {{ job.importance }} · 要求 L{{ job.required_level }}
              </el-tag>
            </div>
            <el-empty
              v-if="detail.related_jobs.length === 0"
              description="暂无关联岗位"
              :image-size="50"
            />
          </div>
        </template>

        <el-empty
          v-else
          description="请点击图谱中的节点查看详情"
          :image-size="80"
        />
      </div>
    </el-drawer>

    <!-- Boss 挑战对话框（模块8 闭环6） -->
    <BossChallenge ref="bossRef" @finished="onBossFinished" />
  </div>
</template>


<style scoped lang="scss">
.top-card {
  border: none;
  border-radius: 12px;
}

.top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.job-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.job-title {
  margin: 0;
  font-size: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.job-desc {
  margin: 4px 0 0;
  color: #98a1b3;
  font-size: 13px;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stats {
  display: flex;
  gap: 24px;
  margin-top: 16px;
  flex-wrap: wrap;

  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 64px;
  }

  .stat-num {
    font-size: 22px;
    font-weight: 700;
  }

  .stat-label {
    color: #98a1b3;
    font-size: 12px;
  }
}

.mt-16 {
  margin-top: 16px;
}

.mb-16 {
  margin-bottom: 16px;
}

.graph-card {
  border-radius: 12px;
  border: none;

  :deep(.el-card__header) {
    padding: 12px 16px;
  }

  :deep(.el-card__body) {
    padding: 0;
  }
}

.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.graph-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.title-icon {
  color: var(--sq-primary);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.graph-canvas {
  width: 100%;
  height: 560px;
}

.graph-tip {
  margin: 16px;
}

.block-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.gap-card {
  border-radius: 12px;
  border: none;
}

.gap-metrics {
  display: flex;
  justify-content: space-around;
  align-items: center;
  gap: 8px;
  .metric {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .metric-label {
    color: #98a1b3;
    font-size: 12px;
    margin-top: 6px;
  }
  .metric-num {
    font-size: 22px;
    font-weight: 700;
    color: #3a4258;
  }
}

.gap-summary {
  margin: 12px 0;
  color: #5a607f;
  font-size: 13px;
  line-height: 1.6;
}

.gap-table {
  :deep(.el-table__header th) {
    background: #f7f9ff;
    color: #5a607f;
  }
}





.detail-quick-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.boss-tip {
  margin: 0 0 10px;
  color: #98a1b3;
  font-size: 12px;
  line-height: 1.6;
}

.boss-btn {
  width: 100%;
}

.drawer-body {
  padding: 8px 4px;
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.drawer-title {
  margin: 0;
  font-size: 20px;
}

.drawer-sub {
  margin: 4px 0 0;
  color: #98a1b3;
  font-size: 13px;
}

.drawer-desc {
  color: #5a607f;
  font-size: 14px;
  line-height: 1.7;
}

.drawer-panel {
  margin-top: 20px;
  border-top: 1px dashed #eceff5;
  padding-top: 14px;

  .panel-title {
    margin: 0 0 10px;
    font-size: 14px;
    font-weight: 600;
  }
}

.prereq-line {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .prereq-status {
    margin-left: auto;
    color: #98a1b3;
    font-size: 12px;
  }
}

.resource-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;

  .resource-body {
    flex: 1;
    b {
      font-size: 14px;
    }
    p {
      margin: 4px 0 0;
      color: #98a1b3;
      line-height: 1.5;
      font-size: 12px;
    }
  }
}

.rel-job {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

@media (max-width: 768px) {
  .graph-canvas {
    height: 420px;
  }
}

:deep(.sq-detail-drawer) {
  .el-drawer__body {
    padding: 16px;
  }
}
</style>