/*
 * 认证相关 API
 */
import { post } from "@/api/request";
import type { LoginPayload, RegisterPayload, TokenResult } from "@/types/user";

/** 注册：自动完成画像/档案初始化并返回令牌 */
export function registerApi(payload: RegisterPayload): Promise<TokenResult> {
  return post<TokenResult, RegisterPayload>("/auth/register", payload);
}

/** 登录：用户名或邮箱 + 密码，返回令牌 */
export function loginApi(payload: LoginPayload): Promise<TokenResult> {
  return post<TokenResult, LoginPayload>("/auth/login", payload);
}