<script setup lang="ts">
/*
 * 历史学习记录页：表格 + 分页 + 筛选（模块/动作）
 */
import { onMounted, reactive, ref } from "vue";
import { getLearningRecords } from "@/api/user";
import type { LearningRecord, PageResult } from "@/types/user";

const loading = ref(false);
const records = ref<PageResult<LearningRecord>>({ items: [], total: 0, page: 1, page_size: 20 });
const query = reactive({
  page: 1,
  page_size: 10,
  module_type: "" as string,
  action_type: "" as string,
});

/** 标签映射（后端常量的中文展示） */
const MODULE_LABELS: Record<string, string> = {
  assessment: "测评",
  course: "课程",
  exercise: "练习",
  reading: "阅读",
  tutor: "AI 导师",
  boss: "Boss 挑战",
};

const ACTION_LABELS: Record<string, string> = {
  start: "开始",
  finish: "完成",
  submit: "提交",
  progress: "进度更新",
};

async function load(): Promise<void> {
  loading.value = true;
  try {
    records.value = await getLearningRecords({
      page: query.page,
      page_size: query.page_size,
      module_type: query.module_type || undefined,
      action_type: query.action_type || undefined,
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

function formatResult(result: Record<string, unknown> | null): string {
  if (!result) return "—";
  // 只展示少量关键字段，避免超宽
  try {
    const entries = Object.entries(result)
      .slice(0, 3)
      .map(([k, v]) => `${k}:${typeof v === "object" ? JSON.stringify(v) : v}`);
    return entries.join(" · ") || "—";
  } catch {
    return "—";
  }
}

onMounted(load);
</script>

<template>
  <div class="page-container">
    <el-card shadow="hover" class="records-card">
      <template #header>
        <div class="records-header">
          <b>历史学习记录</b>
          <div class="filters">
            <el-select
              v-model="query.module_type"
              placeholder="全部模块"
              clearable
              class="filter-select"
              @change="onFilter"
            >
              <el-option
                v-for="(label, key) in MODULE_LABELS"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
            <el-select
              v-model="query.action_type"
              placeholder="全部动作"
              clearable
              class="filter-select"
              @change="onFilter"
            >
              <el-option
                v-for="(label, key) in ACTION_LABELS"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="records.items" v-loading="loading" stripe class="records-table">
        <el-table-column label="模块" width="110">
          <template #default="{ row }">
            <el-tag size="small" type="primary" effect="light">
              {{ MODULE_LABELS[row.module_type] || row.module_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="动作" width="100">
          <template #default="{ row }">
            {{ ACTION_LABELS[row.action_type] || row.action_type }}
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="对象 ID" width="90">
          <template #default="{ row }">{{ row.target_id ?? "—" }}</template>
        </el-table-column>
        <el-table-column label="时长" width="100">
          <template #default="{ row }">
            {{ row.duration > 0 ? `${Math.floor(row.duration / 60)}min ${row.duration % 60}s` : "—" }}
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="220">
          <template #default="{ row }">
            <span class="result-cell">{{ formatResult(row.result) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            {{ row.created_at?.replace("T", " ").slice(0, 19) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="records.total"
          :page-sizes="[5, 10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="load"
          @size-change="onFilter"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.records-card {
  border-radius: 12px;
  border: none;
}

.records-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-select {
  width: 140px;
}

.records-table {
  width: 100%;
}

.result-cell {
  font-size: 12px;
  color: #5a607f;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>