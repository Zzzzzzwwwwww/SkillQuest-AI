/*
 * 用户中心业务 API（模块2）
 */
import { get, put } from "@/api/request";
import type {
  ArchiveOverview,
  AssessmentReport,
  LearningRecord,
  PageResult,
  ProfileUpdatePayload,
  RecordQuery,
  ReportQuery,
  UserProfile,
  UserWithProfile,
} from "@/types/user";

/** 获取当前用户信息（含画像） */
export function getUserMe(): Promise<UserWithProfile> {
  return get<UserWithProfile>("/users/me");
}

/** 更新个人信息 */
export function updateUserProfile(
  payload: ProfileUpdatePayload
): Promise<UserProfile> {
  return put<UserProfile, ProfileUpdatePayload>("/users/profile", payload);
}

/** 学习档案概览（目标岗位 / 等级 / XP / 统计） */
export function getLearningArchive(): Promise<ArchiveOverview> {
  return get<ArchiveOverview>("/users/learning-archive");
}

/** 分页查询历史学习记录 */
export function getLearningRecords(
  query: RecordQuery = {}
): Promise<PageResult<LearningRecord>> {
  return get<PageResult<LearningRecord>>("/users/learning-records", {
    params: query,
  });
}

/** 分页查询测评报告 */
export function getAssessmentReports(
  query: ReportQuery = {}
): Promise<PageResult<AssessmentReport>> {
  return get<PageResult<AssessmentReport>>("/users/assessment-reports", {
    params: query,
  });
}