<script setup lang="ts">
/*
 * 测评中心（模块3）
 * - 展示 active 试卷卡片，选择后开始测评
 */
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Document, EditPen, Timer } from "@element-plus/icons-vue";
import { getPapers } from "@/api/assessment";
import type { Paper } from "@/types/assessment";

const router = useRouter();
const loading = ref(true);
const papers = ref<Paper[]>([]);

const typeLabel: Record<string, string> = {
  career: "职业测评",
  stage: "阶段测评",
  boss: "Boss 评审",
};

onMounted(async () => {
  try {
    papers.value = await getPapers();
  } catch {
    papers.value = [];
  } finally {
    loading.value = false;
  }
});

function start(paper: Paper): void {
  router.push({ path: "/assessment/answering", query: { paperId: paper.id } });
}
</script>

<template>
  <div class="page-container">
    <el-card shadow="never" class="hero-card">
      <div class="hero-inner">
        <div>
          <h3 class="hero-title">职业测评中心</h3>
          <p class="hero-sub">
            通过 10 个维度（逻辑 / 编程 / 数据 / 空间 / 语言 / 动手 / 兴趣 /
            职业价值观 / 学习目标 / 职业意向）生成能力雷达图、
            Top3 职业方向与技能差距建议。
          </p>
        </div>
        <el-icon :size="42" color="#fff"><EditPen /></el-icon>
      </div>
    </el-card>

    <el-row :gutter="16" class="mt-16" v-loading="loading">
      <el-col
        v-for="paper in papers"
        :key="paper.id"
        :xs="24"
        :sm="12"
        :md="8"
        class="mb-16"
      >
        <el-card shadow="hover" class="paper-card">
          <div class="paper-head">
            <el-tag effect="dark" :type="paper.type === 'career' ? 'primary' : 'success'">
              {{ typeLabel[paper.type] || paper.type }}
            </el-tag>
            <span class="paper-count">
              <el-icon><Document /></el-icon> {{ paper.question_count }} 题
            </span>
          </div>
          <h4 class="paper-title">{{ paper.title }}</h4>
          <p class="paper-desc">{{ paper.description }}</p>
          <div class="paper-foot">
            <span class="paper-tip">
              <el-icon><Timer /></el-icon> 约 5-10 分钟
            </span>
            <el-button type="primary" round @click="start(paper)">
              开始测评
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col v-if="!loading && papers.length === 0" :span="24">
        <el-empty description="暂无可用测评试卷，请管理员先运行种子脚本" />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.hero-card {
  border: none;
  border-radius: 16px;
  background: var(--sq-primary-gradient);
  color: #fff;
}

.hero-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hero-title {
  margin: 0 0 6px;
  font-size: 20px;
}

.hero-sub {
  margin: 0;
  opacity: 0.9;
  font-size: 13px;
  max-width: 720px;
}

.mt-16 {
  margin-top: 16px;
}

.mb-16 {
  margin-bottom: 16px;
}

.paper-card {
  border-radius: 12px;
  border: none;
  display: flex;
  flex-direction: column;
  min-height: 210px;

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    flex: 1;
  }
}

.paper-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.paper-count {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #9099a8;
}

.paper-title {
  margin: 14px 0 8px;
  font-size: 17px;
}

.paper-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: #5a6276;
  line-height: 1.6;
  flex: 1;
}

.paper-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.paper-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #9099a8;
}
</style>