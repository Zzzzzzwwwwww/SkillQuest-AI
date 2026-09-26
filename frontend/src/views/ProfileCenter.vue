<script setup lang="ts">
/*
 * 个人中心：个人信息编辑
 * - 展示基础账号信息
 * - 编辑画像字段（姓名/学历/专业/学校/公司/意向岗位/学习目标/每日时长/手机号）
 */
import { onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { useUserStore } from "@/store/user";
import type { ProfileUpdatePayload } from "@/types/user";

const userStore = useUserStore();
const formRef = ref<FormInstance>();
const loading = ref(true);
const saving = ref(false);

const form = reactive<ProfileUpdatePayload>({
  real_name: "",
  education: "",
  major: "",
  school: "",
  company: "",
  job_intention: "",
  learning_goal: "",
  daily_study_time: 30,
  phone: "",
  avatar: "",
});

const rules: FormRules = {
  daily_study_time: [
    { type: "number", min: 5, max: 480, message: "每日学习时长 5-480 分钟", trigger: "blur" },
  ],
};

onMounted(async () => {
  try {
    const me = await userStore.fetchMe();
    const p = me.profile;
    form.real_name = p?.real_name ?? "";
    form.education = p?.education ?? "";
    form.major = p?.major ?? "";
    form.school = p?.school ?? "";
    form.company = p?.company ?? "";
    form.job_intention = p?.job_intention ?? "";
    form.learning_goal = p?.learning_goal ?? "";
    form.daily_study_time = p?.daily_study_time ?? 30;
    form.phone = me.phone ?? "";
    form.avatar = me.avatar ?? "";
  } catch {
    // 统一错误提示
  } finally {
    loading.value = false;
  }
});

async function handleSave(): Promise<void> {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  saving.value = true;
  try {
    // 空字符串转 null，避免后端收到无意义空串
    const payload = Object.fromEntries(
      Object.entries(form).map(([k, v]) => [k, v === "" ? null : v])
    ) as ProfileUpdatePayload;
    await userStore.updateProfile(payload);
    ElMessage.success("个人信息已更新");
  } catch {
    // 统一错误提示
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="page-container">
    <el-card shadow="hover" class="center-card" v-loading="loading">
      <template #header><b>个人信息编辑</b></template>

      <el-descriptions :column="1" border class="account-info">
        <el-descriptions-item label="用户名">
          {{ userStore.user?.username ?? "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">
          {{ userStore.user?.email ?? "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="注册时间">
          {{ userStore.user?.created_at?.slice(0, 10) ?? "—" }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="110px"
        class="profile-form"
      >
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="真实姓名">
              <el-input v-model="form.real_name" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="学历">
              <el-select v-model="form.education" placeholder="选择学历" clearable class="w-full">
                <el-option v-for="e in ['高中','专科','本科','硕士','博士']" :key="e" :label="e" :value="e" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="专业">
              <el-input v-model="form.major" placeholder="如：计算机科学" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="学校">
              <el-input v-model="form.school" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="公司">
              <el-input v-model="form.company" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="求职意向">
              <el-input v-model="form.job_intention" placeholder="如：AI 应用开发工程师" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" placeholder="选填" maxlength="20" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="每日学习时长">
              <el-input-number
                v-model="form.daily_study_time"
                :min="5"
                :max="480"
                :step="5"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="学习目标">
              <el-input
                v-model="form.learning_goal"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
                placeholder="描述你近期想达成的学习目标…"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="头像 URL">
              <el-input v-model="form.avatar" placeholder="选填，图片链接" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">
            保存修改
          </el-button>
          <el-button @click="userStore.logout()">退出登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.center-card {
  border-radius: 12px;
  border: none;
}

.account-info {
  margin-bottom: 8px;
}

.profile-form {
  margin-top: 16px;
}

.w-full {
  width: 100%;
}
</style>