<script setup lang="ts">
/*
 * 登录页
 * 账号（用户名或邮箱）+ 密码 → 登录 → 回跳 redirect 或首页
 */
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { User, Lock } from "@element-plus/icons-vue";
import { useUserStore } from "@/store/user";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const formRef = ref<FormInstance>();
const loading = ref(false);

const form = reactive({
  account: "",
  password: "",
});

const rules: FormRules = {
  account: [{ required: true, message: "请输入用户名或邮箱", trigger: "blur" }],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, message: "密码至少 6 位", trigger: "blur" },
  ],
};

async function handleLogin(): Promise<void> {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  loading.value = true;
  try {
    await userStore.login({ account: form.account, password: form.password });
    ElMessage.success("登录成功，欢迎回来！");
    const redirect = (route.query.redirect as string) || "/";
    router.push(redirect);
  } catch {
    // 错误提示已由 axios 统一处理
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">
        <span class="auth-logo">S</span>
        <h1 class="auth-title">SkillQuest AI</h1>
        <p class="auth-sub">AI 职业成长智能体 · 开启你的成长冒险</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="用户名 / 邮箱" prop="account">
          <el-input v-model="form.account" placeholder="请输入用户名或邮箱" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="auth-submit"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <div class="auth-footer">
        还没有账号？
        <router-link to="/register" class="auth-link">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background:
    radial-gradient(1200px 600px at 10% 10%, rgba(79, 110, 247, 0.25), transparent 60%),
    radial-gradient(900px 500px at 90% 90%, rgba(124, 58, 237, 0.22), transparent 60%),
    #f5f7fb;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 36px 32px 28px;
  box-shadow: 0 12px 40px rgba(31, 35, 41, 0.1);
}

.auth-brand {
  text-align: center;
  margin-bottom: 24px;
}

.auth-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: var(--sq-primary-gradient);
  color: #fff;
  font-size: 28px;
  font-weight: 700;
}

.auth-title {
  margin: 14px 0 4px;
  font-size: 22px;
}

.auth-sub {
  margin: 0;
  color: #9099a8;
  font-size: 13px;
}

.auth-submit {
  width: 100%;
  margin-top: 4px;
}

.auth-footer {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: #9099a8;
}

.auth-link {
  color: var(--sq-primary);
  font-weight: 600;
}
</style>