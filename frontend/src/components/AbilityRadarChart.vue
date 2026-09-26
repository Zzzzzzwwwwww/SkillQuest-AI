<script setup lang="ts">
/*
 * 能力雷达图（ECharts）
 * - props.dimensions: [{ name, score }]（score 0-100）
 * - 主题色随 score 渐变，支持 resize 自适应与销毁
 */
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { RadarPoint } from "@/types/assessment";

const props = withDefaults(
  defineProps<{
    dimensions: RadarPoint[];
    height?: number;
    title?: string;
  }>(),
  { height: 320, title: "" }
);

const containerRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function render(): void {
  if (!containerRef.value || !props.dimensions.length) return;
  if (!chart) chart = echarts.init(containerRef.value);

  const points = props.dimensions;
  const indicator = points.map((p) => ({ name: p.name, max: 100 }));
  const values = points.map((p) => p.score);

  chart.setOption(
    {
      tooltip: { trigger: "item" },
      legend: props.title
        ? { bottom: 0, data: [props.title] }
        : undefined,
      radar: {
        indicator,
        radius: "62%",
        splitNumber: 4,
        splitArea: { areaStyle: { color: ["#f5f7ff", "#eceffd"] } },
        axisName: { color: "#5a6276", fontSize: 12 },
      },
      series: [
        {
          name: props.title || "能力画像",
          type: "radar",
          data: [
            {
              value: values,
              name: props.title || "能力画像",
              areaStyle: { opacity: 0.3, color: "#4f6ef7" },
              lineStyle: { color: "#4f6ef7", width: 2 },
              itemStyle: { color: "#7c3aed" },
            },
          ],
        },
      ],
    },
    true
  );
}

function handleResize(): void {
  chart?.resize();
}

onMounted(() => {
  render();
  window.addEventListener("resize", handleResize);
});

watch(
  () => props.dimensions,
  async () => {
    await nextTick();
    render();
  },
  { deep: true }
);

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="containerRef" :style="{ width: '100%', height: height + 'px' }"></div>
</template>