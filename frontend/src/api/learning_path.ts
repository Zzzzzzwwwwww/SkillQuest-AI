/*
 * 个性化导学业务 API（模块5）
 */
import { get, post, put } from "@/api/request";
import type {
  GeneratePathResult,
  LearningPathMap,
  LearningResource,
  ResumePathResult,
  UpdateProgressPayload,
  UpdateProgressResult,
} from "@/types/learning_path";

/** 生成个性化学习路径（rule 规划 + Learning Agent 增强） */
export function generateLearningPath(payload?: {
  job_id?: number;
  job_name?: string;
  force?: boolean;
}): Promise<GeneratePathResult> {
  return post<GeneratePathResult>("/learning-path/generate", payload ?? {});
}

/** 当前进行中的学习路径（无结果时返回 null） */
export function getCurrentLearningPath(): Promise<LearningPathMap | null> {
  return get<LearningPathMap | null>("/learning-path/current");
}

/** 学习路径分段地图 */
export function getLearningPathMap(pathId: number): Promise<LearningPathMap> {
  return get<LearningPathMap>(`/learning-path/${pathId}/map`);
}

/** 更新节点进度（含断点位置） */
export function updateLearningProgress(
  payload: UpdateProgressPayload
): Promise<UpdateProgressResult> {
  return put<UpdateProgressResult, UpdateProgressPayload>(
    "/learning-progress",
    payload
  );
}

/** 断点续学（返回上次学习位置） */
export function resumeLearning(payload?: {
  path_id?: number;
}): Promise<ResumePathResult> {
  return post<ResumePathResult>("/learning-progress/resume", payload ?? {});
}

/** 学习资源推荐（规则评分排序，可按类型过滤） */
export function recommendResources(params?: {
  skill_node_id?: number;
  resource_type?: string;
  limit?: number;
}): Promise<LearningResource[]> {
  return get<LearningResource[]>("/learning-resources/recommend", { params });
}