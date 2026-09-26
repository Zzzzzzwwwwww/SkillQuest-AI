<script setup lang="ts">
/*
 * 通用占位卡片组件
 * 用于框架阶段的页面占位展示：标题 + 描述 + 可选插槽内容。
 */
withDefaults(
  defineProps<{
    /** 卡片标题 */
    title: string;
    /** 占位说明文案 */
    description: string;
    /** 右上角标签文案 */
    tag?: string;
  }>(),
  { tag: "即将上线" }
);
</script>

<template>
  <el-card class="sq-placeholder-card" shadow="hover">
    <template #header>
      <div class="sq-placeholder-header">
        <span class="sq-placeholder-title">{{ title }}</span>
        <el-tag size="small" effect="light" round>{{ tag }}</el-tag>
      </div>
    </template>

    <el-empty :description="description">
      <template #image>
        <div class="sq-placeholder-image">S</div>
      </template>
      <slot />
    </el-empty>
  </el-card>
</template>

<style scoped lang="scss">
.sq-placeholder-card {
  border-radius: 12px;
  border: none;
}

.sq-placeholder-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sq-placeholder-title {
  font-weight: 600;
  font-size: 15px;
}

.sq-placeholder-image {
  width: 88px;
  height: 88px;
  margin: 0 auto 8px;
  border-radius: 22px;
  background: var(--sq-primary-gradient);
  color: #fff;
  font-size: 40px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.75;
}
</style>