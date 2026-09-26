<script setup lang="ts">
/*
 * 测评报告列表页：卡片 + 查看详情
 */
import { onMounted, reactive, ref } from "vue";
import { getAssessmentReports } from "@/api/user";
import type { AssessmentReport, PageResult } from "@/types/user";

const loading = ref(false);
const detailVisible = ref(false);
const detail = ref<AssessmentReport | null>(null);

const list = ref<PageResult<AssessmentReport>>({
  items: [],
  total: 0,
  page: 1,
  page_size: 12,
});

const query = reactive({
  page: 1,
  page_size: 12,
  report_type: "" as string,
});

const TYPE_LABELS: Record<string, string> = {
  career: "职业画像",
  stage: "阶段测评",
  boss: "Boss 评审",
  periodic: "周期报告",
};

const TYPE_TYPES: Record<string, "primary" | "success" | "warning" | "info"> = {
  career: "primary",
  stage: "success",
  boss: "warning",
  periodic: "info",
};

async function load(): Promise<void> {
  loading.value = true;
  try {
    list.value = await getAssessmentReports({
      page: query.page,
      page_size: query.page_size,
      report_type: query.report_type || undefined,
    });
  } catch {
    // 统一错误提示
  } finally {
    loading.value = false;
  }
}

function onFilter(): void {
  query.page = 1;
  load();
}

/** 摘要：从 report_json 中挑出可展示概要字段 */
function summaryOf(report: AssessmentReport): string {
  const j = report.report_json as Record<string, unknown>;
  const candidates = ["summary", "persona_summary", "goal", "highlights"];
  for (const key of candidates) {
    const v = j?.[key];
    if (typeof v === "string") return v;
  }
  return "点击查看报告详情";
}

function openDetail(report: AssessmentReport): void {
  detail.value = report;
  detailVisible.value = true;
}

onMounted(load);
</script>

<template>
  <div class="page-container">
    <el-card shadow="hover" class="reports-card">
      <template #header>
        <div class="reports-header">
          <b>测评报告</b>
          <el-select
            v-model="query.report_type"
            placeholder="全部类型"
            clearable
            class="report-filter"
            @change="onFilter"
          >
            <el-option
              v-for="(label, key) in TYPE_LABELS"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </div>
      </template>

      <div v-loading="loading" class="report-grid">
        <el-card
          v-for="report in list.items"
          :key="report.id"
          shadow="hover"
          class="report-item"
          @click="openDetail(report)"
        >
          <div class="report-type">
            <el-tag :type="TYPE_TYPES[report.report_type] || 'info'" effect="light" round>
              {{ TYPE_LABELS[report.report_type] || report.report_type }}
            </el-tag>
          </div>
          <p class="report-summary">{{ summaryOf(report) }}</p>
          <p class="report-date">
            {{ report.created_at?.replace("T", " ").slice(0, 19) ?? "" }}
          </p>
        </el-card>

        <el-empty
          v-if="!loading && list.items.length === 0"
          description="暂无测评报告，完成职业测评或阶段考试后这里会生成报告"
        />
      </div>

      <div v-if="list.total > list.page_size" class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="list.total"
          :page-sizes="[12, 24, 48]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="load"
          @size-change="onFilter"
        />
      </div>
    </el-card>

    <!-- 报告详情 -->
    <el-dialog
      v-model="detailVisible"
      :title="detail ? `${TYPE_LABELS[detail.report_type] || '报告'}详情` : '报告详情'"
      width="min(90vw, 680px)"
      top="6vh"
    >
      <pre v-if="detail" class="report-json">{{ JSON.stringify(detail.report_json, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.reports-card {
  border-radius: 12px;
  border: none;
}

.reports-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.report-filter {
  width: 140px;
}

.report-grid {
  min-height: 120px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.report-item {
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-3px);
  }

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}

.report-summary {
  margin: 0;
  font-size: 13px;
  color: #3d4353;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.report-date {
  margin: 0;
  font-size: 12px;
  color: #b0b7c5;
}

.report-json {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  background: #0f1428;
  color: #b3f0ff;
  border-radius: 8px;
  padding: 14px;
  font-size: 12px;
  line-height: 1.7;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>