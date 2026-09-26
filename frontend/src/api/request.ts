/*
 * axios 统一封装
 * - 基础地址、超时、请求头
 * - 请求拦截：自动携带 JWT
 * - 响应拦截：统一解包 { code, message, data }，统一错误提示
 */
import axios from "axios";
import type { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import { ElMessage } from "element-plus";

/** 后端统一响应结构 */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

/** 业务成功码 */
export const SUCCESS_CODE = 0;

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// ---------- 请求拦截 ----------
request.interceptors.request.use((config) => {
  const token = localStorage.getItem("sq_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------- 响应拦截 ----------
request.interceptors.response.use(
  (response) => {
    // 二进制流等场景直接透传
    if (response.request.responseType === "blob") {
      return response;
    }
    const body = response.data as ApiResponse;
    if (body && typeof body.code === "number" && body.code !== SUCCESS_CODE) {
      ElMessage.error(body.message || "请求失败");
      return Promise.reject(new Error(body.message || "请求失败"));
    }
    return response;
  },
  (error: AxiosError<ApiResponse>) => {
    const status = error.response?.status;
    const message =
      error.response?.data?.message || error.message || "网络请求异常";

    if (status === 401) {
      // 会话失效：清理本地凭证并回到登录页
      ElMessage.error("登录状态失效，请重新登录");
      localStorage.removeItem("sq_token");
      localStorage.removeItem("sq_user");
      if (!window.location.pathname.startsWith("/login")) {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login?redirect=${redirect}`;
      }
    } else if (status === 403) {
      ElMessage.error("没有权限执行该操作");
    } else if (typeof status === "number" && status >= 500) {
      ElMessage.error("服务器开小差了，请稍后重试");
    } else {
      ElMessage.error(message);
    }
    return Promise.reject(error);
  }
);

/**
 * 发起请求并解包出 data 字段。
 * 简化业务侧取值逻辑：`const data = await get<X>(url)` 即可拿到后端 data。
 */
export async function get<T = unknown>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const { data } = await request.get<ApiResponse<T>>(url, config);
  return data.data;
}

export async function post<T = unknown, B = unknown>(
  url: string,
  body?: B,
  config?: AxiosRequestConfig
): Promise<T> {
  const { data } = await request.post<ApiResponse<T>>(url, body, config);
  return data.data;
}

export async function put<T = unknown, B = unknown>(
  url: string,
  body?: B,
  config?: AxiosRequestConfig
): Promise<T> {
  const { data } = await request.put<ApiResponse<T>>(url, body, config);
  return data.data;
}

export async function del<T = unknown>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const { data } = await request.delete<ApiResponse<T>>(url, config);
  return data.data;
}

export default request;