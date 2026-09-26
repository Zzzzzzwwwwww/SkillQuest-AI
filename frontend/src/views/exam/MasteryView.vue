<script setup lang="ts">
/*
 * 学习评估 · 掌握度分析
 * ECharts 热力图（能力域 × 知识点）+ 掌握度条目列表
 */
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { getMasteryOverview } from "@/api/assessment_review";
import type { MasteryOverview } from "@/types/assessment_review";

const loading = ref(true);
const data = ref<MasteryOverview>({ items: [], heatmap: { domains: [], points: [] } });
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function render(): void {
  if (!chartRef.value) return;
  if (!chart) chart = echarts.init(chartRef.value);

  const { domains, points } = data.value.heatmap;
  const rows = Array.from(new Set(points.map((p) => p.name)));

  chart.setOption(
    {
      tooltip: {
        position: "top",
        formatter: (p: { data: (string | number)[] }) => {
          const [x, y, v] = p.data;
          return `<b>${y}</b><br/>能力域：${x}<br/>掌握度：${v}`;
        },
      },
      grid: { left: 110, right: 30, top: 40, bottom: 30 },
      xAxis: {
        type: "category",
        data: domains,
        axisLabel: { interval: 0, rotate: domains.length > 3 ? 15 : 0 },
      },
      yAxis: { type: "category", data: rows },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        inRange: { color: ["#f87171", "#fbbf24", "#4ade80"] },
        text: ["高", "低"],
      },
      series: [
        {
          type: "heatmap",
          data: points.map((p) => [p.domain, p.name, p.value]),
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 6, shadowColor: "rgba(0,0,0,.4)" } },
        },
      ],
    },
    true
  );
}

function handleResize(): void {
  chart?.resize();
}

onMounted(async () => {
  try {
    data.value = await getMasteryOverview();
  } catch {
    // 统一错误提示
  } finally {
    loading.value = false;
  }
  await nextTick();
  render();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});

function masteryColor(score: number): string {
  if (score >= 70) return "#16a34a";
  if (score >= 60) return "#d97706";
  return "#dc2626";
}
</script>

<template>
  <div class="page-container">
    <el-card shadow="hover" class="heat-card">
      <template #header>
        <div class="heat-header">
          <b>知识点掌握度热力图</b>
          <span class="heat-hint">颜色越绿代表掌握度越高，点击图例可筛选</span>
        </div>
      </template>
      <div v-loading="loading" class="heat-body">
        <el-empty
          v-if="!loading && data.items.length === 0"
          description="暂无掌握度数据，先完成一场阶段测评吧"
        />
        <div
          v-else-if="data.heatmap.points.length"
          ref="chartRef"
          class="heat-chart"
        ></div>
      </div>
    </el-card>

    <el-card shadow="hover" class="mastery-card">
      <template #header><b>掌握度明细</b></template>
      <div v-loading="loading" class="mastery-list">
        <el-empty
          v-if="!loading && data.items.length === 0"
          description="暂无数据"
        />
        <div v-for="(m, mi) in data.items" :key="mi" class="mastery-item">
          <div class="mastery-head">
            <span class="mastery-name">{{ m.name }}</span>
            <el-tag size="small" effect="plain" type="info">{{ m.domain }}</el-tag>
          </div>
          <el-progress
            :percentage="m.mastery_score"
            :color="masteryColor(m.mastery_score)"
            :stroke-width="10"
          />
          <span class="mastery-meta">
            测评 {{ m.review_count }} 次 · 最近 {{ m.last_test_time?.replace("T", " ").slice(0, 19) }}
          </span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.heat-card,
.mastery-card {
  border-radius: 12px;
  border: none;
  margin-bottom: 14px;
}

.heat-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.heat-hint {
  font-size: 12px;
  color: #a0a8bb;
}

.heat-body {
  min-height: 200px;
}

.heat-chart {
  width: 100%;
  height: 420px;
}

.mastery-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  min-height: 80px;
}

.mastery-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.mastery-name {
  font-size: 13px;
  font-weight: 600;
}

.mastery-meta {
  font-size: 11px;
  color: #a0a8bb;
}
</style>