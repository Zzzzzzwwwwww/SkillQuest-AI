<script setup lang="ts">
/*
 * 学习评估 · 学习报告中心
 * 报告列表 / 生成最新报告 / 详情展示 / PDF 导出
 */
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  downloadReportPdf,
  generateReport,
  getReportDetail,
  getReportList,
} from "@/api/assessment_review";
import type { LearningReport, ReportListItem } from "@/types/assessment_review";
import { EXAM_STAGE_META } from "@/types/assessment_review";

const loading = ref(false);
const generating = ref(false);
const exporting = ref(false);
const list = ref<ReportListItem[]>([]);

const detailVisible = ref(false);
const detail = ref<LearningReport | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  try {
    list.value = await getReportList();
  } finally {
    loading.value = false;
  }
}

async function onGenerate(): Promise<void> {
  generating.value = true;
  try {
    const rep = await generateReport();
    ElMessage.success("学习报告生成成功");
    await load();
    openDetail(rep.id);
  } catch {
    // 统一错误提示
  } finally {
    generating.value = false;
  }
}

async function openDetail(id: number): Promise<void> {
  try {
    detail.value = await getReportDetail(id);
    detailVisible.value = true;
  } catch {
    // 统一错误提示
  }
}

async function onExport(): Promise<void> {
  exporting.value = true;
  try {
    await downloadReportPdf(detail.value?.id);
    ElMessage.success("PDF 已开始下载");
  } catch {
    // 统一错误提示
  } finally {
    exporting.value = false;
  }
}

function fmtTime(t?: string | null): string {
  return t ? t.replace("T", " ").slice(0, 19) : "";
}

onMounted(load);
</script>

<template>
  <div class="page-container">
    <el-card shadow="hover" class="report-card">
      <template #header>
        <div class="report-header">
          <b>学习报告</b>
          <el-button
            type="primary"
            :loading="generating"
            @click="onGenerate"
          >
            生成最新报告
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="report-grid">
        <el-card
          v-for="rep in list"
          :key="rep.id"
          shadow="hover"
          class="report-item"
          @click="openDetail(rep.id)"
        >
          <div class="report-top">
            <el-tag size="small" effect="plain" type="primary" round>
              学习评估报告
            </el-tag>
            <el-tag
              v-if="rep.score !== null"
              size="small"
              :type="rep.score >= 60 ? 'success' : 'danger'"
              effect="light"
              round
            >
              {{ rep.score }} 分
            </el-tag>
          </div>
          <h3 class="report-title">{{ rep.exam_title ?? "综合学习报告" }}</h3>
          <p class="report-date">{{ fmtTime(rep.created_at) }}</p>
        </el-card>

        <el-empty
          v-if="!loading && list.length === 0"
          description="暂无学习报告，先去完成一场阶段测评吧"
        />
      </div>
    </el-card>

    <!-- 报告详情 -->
    <el-dialog
      v-model="detailVisible"
      :title="detail ? `${detail.report_json?.exam_title ?? '学习报告'} 详情` : '学习报告'"
      width="min(92vw, 760px)"
      top="4vh"
      destroy-on-close
    >
      <div v-if="detail" class="report-detail">
        <div class="detail-head">
          <div>
            <el-tag round effect="dark">
              {{ EXAM_STAGE_META[detail.report_json.stage]?.icon }}
              {{ EXAM_STAGE_META[detail.report_json.stage]?.label ?? detail.report_json.stage }}
            </el-tag>
            <h3 class="detail-title">
              {{ detail.report_json.exam_title }}
              <el-tag
                v-if="detail.ai_enriched"
                size="small"
                type="success"
                effect="plain"
                class="ai-tag"
              >
                AI 解读增强
              </el-tag>
            </h3>
            <p class="detail-date">生成于 {{ fmtTime(detail.created_at) }}</p>
          </div>
          <div class="detail-score" :class="{ pass: (detail.report_json.score ?? 0) >= 60 }">
            {{ detail.report_json.score ?? "-" }}
            <span class="detail-unit">分</span>
          </div>
        </div>

        <el-alert
          :title="detail.report_json.overall || detail.report_json.summary"
          type="info"
          :closable="false"
          show-icon
          class="overall"
        />

        <div class="grid-2">
          <div class="detail-block">
            <h4>优势知识点</h4>
            <ul v-if="detail.report_json.strengths?.length" class="tag-list">
              <li
                v-for="s in detail.report_json.strengths"
                :key="s.name"
                class="tag-item strong"
              >
                {{ s.name }}（{{ s.score }}）
              </li>
            </ul>
            <p v-else class="muted">暂无优势项</p>
          </div>
          <div class="detail-block">
            <h4>薄弱知识点</h4>
            <ul v-if="detail.report_json.weaknesses?.length" class="tag-list">
              <li
                v-for="(w, wi) in detail.report_json.weaknesses"
                :key="wi"
                class="tag-item weak"
              >
                {{ w.name }}（{{ w.mastery_score }}）
              </li>
            </ul>
            <p v-else class="muted">暂无薄弱项</p>
          </div>
        </div>

        <div class="detail-block">
          <h4>学习建议</h4>
          <p class="suggestion">
            {{ detail.report_json.improvement_plan || detail.report_json.suggestion }}
          </p>
        </div>

        <div class="detail-block">
          <h4>下一步任务</h4>
          <ul class="next-list">
            <li v-for="(n, i) in detail.report_json.next_steps ?? []" :key="i">
              {{ i + 1 }}. {{ n }}
            </li>
          </ul>
        </div>
      </div>

      <template #footer>
        <el-button
          type="primary"
          :loading="exporting"
          @click="onExport"
        >
          导出 PDF
        </el-button>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.report-card {
  border-radius: 12px;
  border: none;
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.report-grid {
  min-height: 120px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.report-item {
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-3px);
  }
}

.report-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-title {
  margin: 10px 0 4px;
  font-size: 15px;
}

.report-date {
  margin: 0;
  font-size: 12px;
  color: #a0a8bb;
}

.report-detail {
  max-height: 62vh;
  overflow-y: auto;
  padding-right: 6px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.detail-title {
  margin: 8px 0 2px;
  font-size: 18px;
}

.ai-tag {
  margin-left: 6px;
}

.detail-date {
  margin: 0;
  font-size: 12px;
  color: #a0a8bb;
}

.detail-score {
  font-size: 40px;
  font-weight: 800;
  color: #dc2626;

  &.pass {
    color: #16a34a;
  }
}

.detail-unit {
  font-size: 13px;
  color: #a0a8bb;
}

.overall {
  border-radius: 8px;
  margin-bottom: 14px;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.detail-block {
  margin-bottom: 12px;

  h4 {
    margin: 0 0 8px;
    font-size: 13px;
    color: #3d4353;
  }
}

.tag-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-item {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;

  &.strong {
    background: #ecfdf5;
    color: #16a34a;
  }

  &.weak {
    background: #fef2f2;
    color: #dc2626;
  }
}

.muted {
  font-size: 12px;
  color: #a0a8bb;
  margin: 0;
}

.suggestion {
  margin: 0;
  font-size: 13px;
  color: #5a6276;
  line-height: 1.7;
}

.next-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #5a6276;
  line-height: 1.9;
}

@media (max-width: 768px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>