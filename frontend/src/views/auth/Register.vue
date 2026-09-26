<script setup lang="ts">
/*
 * 注册页
 * 用户名 + 邮箱 + 密码 → 注册（自动登录）→ 跳首页
 */
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { User, Lock, Message } from "@element-plus/icons-vue";
import { useUserStore } from "@/store/user";

const router = useRouter();
const userStore = useUserStore();

const formRef = ref<FormInstance>();
const loading = ref(false);

const form = reactive({
  username: "",
  email: "",
  password: "",
  confirm: "",
});

const validateConfirm = (
  _rule: unknown,
  value: string,
  callback: (error?: Error) => void
): void => {
  if (value !== form.password) callback(new Error("两次输入的密码不一致"));
  else callback();
};

const rules: FormRules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 3, max: 64, message: "用户名 3-64 个字符", trigger: "blur" },
  ],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "邮箱格式不正确", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, max: 128, message: "密码至少 6 位", trigger: "blur" },
  ],
  confirm: [
    { required: true, message: "请再次输入密码", trigger: "blur" },
    { validator: validateConfirm, trigger: "blur" },
  ],
};

async function handleRegister(): Promise<void> {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  loading.value = true;
  try {
    await userStore.register({
      username: form.username,
      email: form.email,
      password: form.password,
    });
    ElMessage.success("注册成功，欢迎加入 SkillQuest AI！");
    router.push("/");
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
        <h1 class="auth-title">创建账号</h1>
        <p class="auth-sub">注册即开始你的职业成长冒险</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="3-64 个字符" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="example@mail.com" :prefix-icon="Message" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="至少 6 位"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="再次输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="auth-submit"
          :loading="loading"
          @click="handleRegister"
        >
          注 册
        </el-button>
      </el-form>

      <div class="auth-footer">
        已有账号？
        <router-link to="/login" class="auth-link">去登录</router-link>
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
  max-width: 420px;
  background: #fff;
  border-radius: 16px;
  padding: 36px 32px 28px;
  box-shadow: 0 12px 40px rgba(31, 35, 41, 0.1);
}

.auth-brand {
  text-align: center;
  margin-bottom: 22px;
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