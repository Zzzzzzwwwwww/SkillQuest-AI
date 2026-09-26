/*
 * 测评模块 API（模块3）
 */
import { get, post } from "@/api/request";
import type {
  AssessmentResultDetail,
  AssessmentSubmitPayload,
  AssessmentSubmitResult,
  Paper,
  Question,
} from "@/types/assessment";

/** 可用试卷列表 */
export function getPapers(): Promise<Paper[]> {
  return get<Paper[]>("/assessment/papers");
}

/** 获取试卷题目（不含评分规则） */
export function getPaperQuestions(paperId: number): Promise<Question[]> {
  return get<Question[]>("/assessment/questions", { params: { paper_id: paperId } });
}

/** 提交测评答卷 */
export function submitAssessment(
  payload: AssessmentSubmitPayload
): Promise<AssessmentSubmitResult> {
  return post<AssessmentSubmitResult, AssessmentSubmitPayload>(
    "/assessment/submit",
    payload
  );
}

/** 查询测评结果详情 */
export function getAssessmentResult(resultId: number): Promise<AssessmentResultDetail> {
  return get<AssessmentResultDetail>(`/assessment/result/${resultId}`);
}