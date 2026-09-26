<script setup lang="ts">
/*
 * 岗位选择页（模块4）
 * - 岗位列表按岗位族分组展示，点击进入技能图谱
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Aim, Connection } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { getJobs } from "@/api/skill";
import { selectTargetJob } from "@/api/business";
import type { JobItem } from "@/types/skill";

const router = useRouter();
const loading = ref(false);
const selecting = ref(false);
const jobs = ref<JobItem[]>([]);

const familyGroups = computed(() => {
  const map = new Map<string, JobItem[]>();
  for (const job of jobs.value) {
    const list = map.get(job.job_family) ?? [];
    list.push(job);
    map.set(job.job_family, list);
  }
  return Array.from(map.entries());
});

async function loadJobs(): Promise<void> {
  loading.value = true;
  try {
    jobs.value = await getJobs();
  } finally {
    loading.value = false;
  }
}

async function goGraph(jobId: number): Promise<void> {
  selecting.value = true;
  try {
    const r = await selectTargetJob({ job_id: jobId, auto_generate_path: true });
    if (r.auto_generated_path && r.path) {
      ElMessage.success(`已选定「${r.job_name}」，学习路径已自动生成`);
    } else {
      ElMessage.success(`已选定「${r.job_name}」为目标岗位`);
    }
    await router.push({ path: "/skill-tree", query: { job_id: String(jobId) } });
  } catch {
    /* 错误已被拦截器提示；仍允许进入图谱查看 */
    await router.push({ path: "/skill-tree", query: { job_id: String(jobId) } });
  } finally {
    selecting.value = false;
  }
}

async function quickEnter(): Promise<void> {
  const first = jobs.value[0];
  if (first) await goGraph(first.id);
}

onMounted(loadJobs);
</script>

<template>
  <div class="page-container" v-loading="loading">
    <el-card shadow="never" class="head-card">
      <div class="head">
        <div>
          <h2 class="page-title">选择目标岗位</h2>
          <p class="page-desc">
            选择你期望的岗位，将自动生成本人画像与学习路径，并查看完整技能图谱。
          </p>
        </div>
        <el-button type="primary" :icon="Connection" round :loading="selecting" @click="quickEnter">
          快速进入技能图谱
        </el-button>
      </div>
    </el-card>

    <el-empty v-if="!loading && jobs.length === 0" description="暂无岗位数据" />

    <section v-for="[family, list] in familyGroups" :key="family" class="family-block">
      <div class="family-title">
        <el-icon class="family-icon"><Aim /></el-icon>
        <span>{{ family }}</span>
        <span class="family-count">{{ list.length }} 个岗位</span>
      </div>
      <el-row :gutter="16">
        <el-col v-for="job in list" :key="job.id" :xs="24" :sm="12" :lg="8" class="mb-16">
          <el-card
            shadow="hover"
            class="job-card"
            @click="goGraph(job.id)"
          >
            <div class="job-card-top">
              <h3 class="job-name">{{ job.job_name }}</h3>
              <el-tag size="small" effect="plain" round class="job-tag">
                {{ job.industry || "通用行业" }}
              </el-tag>
            </div>
            <p class="job-desc">{{ job.description || "暂无描述" }}</p>
            <div class="job-foot">
              <span class="job-count">
                <el-icon><Connection /></el-icon>
                技能要求 {{ job.skill_count }} 项
              </span>
              <el-button type="primary" link>
                选定并查看图谱 →
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<style scoped lang="scss">
.head-card {
  border: none;
  border-radius: 12px;
  margin-bottom: 20px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
}

.page-desc {
  margin: 0;
  color: #98a1b3;
  font-size: 13px;
}

.family-block {
  margin-bottom: 24px;

  .family-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 600;

    .family-icon {
      color: var(--sq-primary);
    }

    .family-count {
      color: #98a1b3;
      font-weight: 400;
      font-size: 12px;
    }
  }
}

.job-card {
  border-radius: 12px;
  cursor: pointer;
  height: 100%;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }
}

.job-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.job-name {
  margin: 0;
  font-size: 16px;
}

.job-tag {
  flex-shrink: 0;
}

.job-desc {
  color: #5a607f;
  font-size: 13px;
  line-height: 1.6;
  min-height: 40px;
  margin: 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.job-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px dashed #eceff5;
  padding-top: 10px;

  .job-count {
    color: #98a1b3;
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
}

.mb-16 {
  margin-bottom: 16px;
}
</style>