<script setup lang="ts">
/*
 * 技能图谱占位组件（AntV G6 集成示例）
 * 框架阶段仅演示 G6 图表的初始化 / 渲染 / 销毁流程，
 * 业务数据（AI 应用开发工程师技能图谱）将在后续版本接入。
 */
import G6 from "@antv/g6";
import type { Graph } from "@antv/g6";
import { onBeforeUnmount, onMounted, ref } from "vue";

const containerRef = ref<HTMLDivElement | null>(null);
let graph: Graph | null = null;

/** 占位示例数据：AI 应用开发工程师技能骨架 */
const demoData = {
  nodes: [
    { id: "root", label: "AI 应用开发", x: 300, y: 40, size: 42 },
    { id: "ml", label: "机器学习", x: 120, y: 140 },
    { id: "python", label: "Python", x: 300, y: 160 },
    { id: "backend", label: "后端工程", x: 480, y: 140 },
    { id: "cv", label: "计算机视觉", x: 60, y: 250 },
    { id: "nlp", label: "自然语言处理", x: 180, y: 260 },
    { id: "fastapi", label: "FastAPI", x: 420, y: 260 },
    { id: "deploy", label: "部署运维", x: 540, y: 260 },
  ],
  edges: [
    { source: "root", target: "ml" },
    { source: "root", target: "python" },
    { source: "root", target: "backend" },
    { source: "ml", target: "cv" },
    { source: "ml", target: "nlp" },
    { source: "backend", target: "fastapi" },
    { source: "backend", target: "deploy" },
  ],
};

onMounted(() => {
  if (!containerRef.value) return;
  const width = containerRef.value.clientWidth || 600;
  const height = containerRef.value.clientHeight || 320;

  graph = new G6.Graph({
    container: containerRef.value,
    width,
    height,
    fitView: true,
    modes: { default: ["drag-canvas", "zoom-canvas", "drag-node"] },
    defaultNode: {
      type: "circle",
      size: 30,
      style: { fill: "#4f6ef7", stroke: "#fff", lineWidth: 2 },
      labelCfg: {
        style: { fontSize: 12, fill: "#1f2329" },
        position: "bottom",
        offset: 6,
      },
    },
    defaultEdge: {
      type: "line",
      style: { stroke: "#c9d2ee", lineWidth: 1.5, endArrow: true },
    },
  });
  graph.data(demoData);
  graph.render();
});

onBeforeUnmount(() => {
  // 组件销毁前必须释放图实例，避免内存泄漏
  graph?.destroy();
  graph = null;
});
</script>

<template>
  <div ref="containerRef" class="sq-graph"></div>
</template>

<style scoped lang="scss">
.sq-graph {
  width: 100%;
  height: 320px;
}
</style>