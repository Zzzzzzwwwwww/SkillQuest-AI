/*
 * 学习评估复盘业务 API（模块7）
 */
import { get, post } from "@/api/request";
import request from "@/api/request";
import type {
  AnswerItem,
  ExamPaper,
  ExamResultDetail,
  ExamStartResult,
  ExamSubmitResult,
  LearningReport,
  MasteryOverview,
  ReportListItem,
} from "@/types/assessment_review";

/** 一段答辩：阶段测评试卷列表 */
export function getExamPapers(): Promise<ExamPaper[]> {
  return get<ExamPaper[]>("/exam/list");
}

/** 开始测评（下发题目，不含答案） */
export function startExam(examId: number): Promise<ExamStartResult> {
  return post<ExamStartResult, { exam_id: number }>("/exam/start", {
    exam_id: examId,
  });
}

/** 提交答卷（规则评分） */
export function submitExam(
  recordId: number,
  answers: AnswerItem[]
): Promise<ExamSubmitResult> {
  return post<ExamSubmitResult, { record_id: number; answers: AnswerItem[] }>(
    "/exam/submit",
    { record_id: recordId, answers }
  );
}

/** 测评结果详情 */
export function getExamResult(recordId: number): Promise<ExamResultDetail> {
  return get<ExamResultDetail>(`/exam/result/${recordId}`);
}

/** 知识点掌握度总览（热力图） */
export function getMasteryOverview(): Promise<MasteryOverview> {
  return get<MasteryOverview>("/mastery");
}

/** 生成学习报告 */
export function generateReport(payload?: {
  record_id?: number;
  report_type?: string;
}): Promise<LearningReport> {
  return post<LearningReport, { record_id?: number; report_type?: string }>(
    "/report/generate",
    payload ?? {}
  );
}

/** 历史报告列表 */
export function getReportList(): Promise<ReportListItem[]> {
  return get<ReportListItem[]>("/report/list");
}

/** 报告详情 */
export function getReportDetail(reportId: number): Promise<LearningReport> {
  return get<LearningReport>(`/report/${reportId}`);
}

/** 导出报告 PDF（blob 下载） */
export async function downloadReportPdf(reportId?: number): Promise<void> {
  const res = await request.get("/report/export/pdf", {
    params: reportId ? { report_id: reportId } : {},
    responseType: "blob",
  });
  const blob: Blob = res.data;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `skillquest-report-${reportId ?? "latest"}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}