/*
 * 用户画像模块 API（模块3）
 */
import { get, post } from "@/api/request";
import type { Persona, PersonaGenerateResult } from "@/types/assessment";

/** 查询当前用户画像（未生成返回 null） */
export function getCurrentPersona(): Promise<Persona | null> {
  return get<Persona | null>("/persona/current");
}

/** 基于最近一次测评生成/刷新画像 */
export function generatePersona(): Promise<PersonaGenerateResult> {
  return post<PersonaGenerateResult>("/persona/generate");
}