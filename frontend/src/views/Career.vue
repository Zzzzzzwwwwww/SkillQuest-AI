<script setup lang="ts">
/*
 * 职业探索
 * 框架占位：AI 应用开发工程师职业路径浏览。
 * 后续将接入：职业路线图、岗位需求分析、技能差距评估。
 */
import PlaceholderCard from "@/components/PlaceholderCard.vue";
</script>

<template>
  <div class="page-container">
    <PlaceholderCard
      title="职业探索"
      description="探索 AI 应用开发工程师的完整职业路径，查看岗位画像、技能要求与成长空间。"
      tag="框架占位"
    >
      <el-row :gutter="12" class="mt-8">
        <el-col :xs="24" :sm="8">
          <el-card shadow="never" class="mini-card">
            <h4>初级</h4>
            <p>掌握 Python 与基础 AI 能力</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="never" class="mini-card">
            <h4>中级</h4>
            <p>独立完成 AI 应用落地</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="never" class="mini-card">
            <h4>高级</h4>
            <p>架构设计与技术引领</p>
          </el-card>
        </el-col>
      </el-row>
    </PlaceholderCard>
  </div>
</template>

<style scoped lang="scss">
.mt-8 {
  margin-top: 8px;
}

.mini-card {
  border-radius: 10px;
  text-align: center;
  h4 {
    margin: 0 0 8px;
  }
  p {
    margin: 0;
    font-size: 12px;
    color: #6b7280;
  }
}
</style>