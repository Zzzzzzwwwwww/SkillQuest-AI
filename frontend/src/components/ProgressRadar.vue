<script setup lang="ts">
/*
 * 技能雷达图占位组件（ECharts 集成示例）
 * 框架阶段仅演示 ECharts 初始化 / 配置 / 自适应 resize / 销毁流程。
 */
import * as echarts from "echarts";
import { onBeforeUnmount, onMounted, ref } from "vue";

const containerRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function render(): void {
  if (!containerRef.value) return;
  if (!chart) chart = echarts.init(containerRef.value);

  chart.setOption({
    tooltip: {},
    radar: {
      indicator: [
        { name: "编程基础", max: 100 },
        { name: "AI 理论", max: 100 },
        { name: "工程实践", max: 100 },
        { name: "模型调优", max: 100 },
        { name: "产品思维", max: 100 },
        { name: "沟通协作", max: 100 },
      ],
      radius: "65%",
      splitArea: { show: true },
    },
    series: [
      {
        type: "radar",
        data: [{ value: [82, 60, 70, 45, 55, 75], name: "你的技能画像" }],
        areaStyle: { opacity: 0.25 },
        lineStyle: { color: "#4f6ef7", width: 2 },
        itemStyle: { color: "#7c3aed" },
      },
    ],
  });
}

function handleResize(): void {
  chart?.resize();
}

onMounted(() => {
  render();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="containerRef" class="sq-radar"></div>
</template>

<style scoped lang="scss">
.sq-radar {
  width: 100%;
  height: 300px;
}
</style>