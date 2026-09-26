/*
 * 岗位技能图谱业务 API（模块4）
 */
import { get, put } from "@/api/request";
import type {
  JobItem,
  JobSkillTreeResult,
  SkillDetailResult,
  SkillStatusSyncPayload,
  UserSkillStatusResult,
} from "@/types/skill";

/** 岗位列表（岗位族/行业筛选） */
export function getJobs(params?: {
  family?: string;
  industry?: string;
}): Promise<JobItem[]> {
  return get<JobItem[]>("/jobs", { params });
}

/** 岗位分层技能树（含当前用户掌握状态 + Gap 汇总） */
export function getJobSkillTree(jobId: number): Promise<JobSkillTreeResult> {
  return get<JobSkillTreeResult>(`/jobs/${jobId}/skill-tree`);
}

/** 技能节点详情（前置知识 / 推荐资源 / 关联岗位） */
export function getSkillDetail(nodeId: number): Promise<SkillDetailResult> {
  return get<SkillDetailResult>(`/skills/${nodeId}/detail`);
}

/** 查询指定用户技能掌握状态 */
export function getUserSkillStatus(userId: number): Promise<UserSkillStatusResult> {
  return get<UserSkillStatusResult>(`/users/${userId}/skill-status`);
}

/** 批量同步更新本人技能掌握状态 */
export function updateUserSkillStatus(
  payload: SkillStatusSyncPayload
): Promise<UserSkillStatusResult> {
  return put<UserSkillStatusResult, SkillStatusSyncPayload>(
    "/users/skill-status",
    payload
  );
}