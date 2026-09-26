/*
 * 用户状态管理（Pinia）
 * - token / user 持久化到 localStorage，刷新后保持登录
 * - fetchMe 静默校验令牌合法性；login/register/logout/updateProfile
 */
import { ref } from "vue";
import { defineStore } from "pinia";
import { loginApi, registerApi } from "@/api/auth";
import { getUserMe, updateUserProfile } from "@/api/user";
import type {
  LoginPayload,
  ProfileUpdatePayload,
  RegisterPayload,
  User,
  UserProfile,
  UserWithProfile,
} from "@/types/user";

/** 本地存储 key */
const TOKEN_KEY = "sq_token";
const USER_KEY = "sq_user";

function loadJSON<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export const useUserStore = defineStore("user", () => {
  // ---------- 状态（从 localStorage 恢复） ----------
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || "");
  const user = ref<User | null>(loadJSON<User>(USER_KEY));
  const profile = ref<UserProfile | null>(null);
  const isLoggedIn = ref<boolean>(Boolean(token.value));

  // ---------- 动作 ----------
  function persistToken(value: string): void {
    token.value = value;
    isLoggedIn.value = Boolean(value);
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  }

  function persistUser(value: User | null): void {
    user.value = value;
    if (value) localStorage.setItem(USER_KEY, JSON.stringify(value));
    else localStorage.removeItem(USER_KEY);
  }

  /** 登录 */
  async function login(payload: LoginPayload): Promise<void> {
    const res = await loginApi(payload);
    persistToken(res.access_token);
    persistUser(res.user);
  }

  /** 注册（成功后自动登录） */
  async function register(payload: RegisterPayload): Promise<void> {
    const res = await registerApi(payload);
    persistToken(res.access_token);
    persistUser(res.user);
  }

  /** 登出：清空本地状态 */
  function logout(): void {
    persistToken("");
    persistUser(null);
    profile.value = null;
  }

  /** 拉取当前用户（含画像）并同步本地状态；用于刷新后保持登录 */
  async function fetchMe(): Promise<UserWithProfile> {
    const data = await getUserMe();
    persistUser({
      id: data.id,
      username: data.username,
      email: data.email,
      phone: data.phone,
      avatar: data.avatar,
      status: data.status,
      created_at: data.created_at,
      updated_at: data.updated_at,
    });
    profile.value = data.profile;
    return data;
  }

  /** 更新个人信息 */
  async function updateProfile(payload: ProfileUpdatePayload): Promise<UserProfile> {
    const data = await updateUserProfile(payload);
    profile.value = data;
    // 同步 user.phone/avatar 展示字段
    if (user.value) {
      if (payload.phone !== undefined) user.value.phone = payload.phone;
      if (payload.avatar !== undefined) user.value.avatar = payload.avatar;
      persistUser(user.value);
    }
    return data;
  }

  /** 初始化：存在 token 时尝试恢复会话（不阻塞路由） */
  async function restoreSession(): Promise<boolean> {
    if (!token.value) return false;
    try {
      await fetchMe();
      return true;
    } catch {
      logout();
      return false;
    }
  }

  return {
    token,
    user,
    profile,
    isLoggedIn,
    login,
    register,
    logout,
    fetchMe,
    updateProfile,
    restoreSession,
  };
});