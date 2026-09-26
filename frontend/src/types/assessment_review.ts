/*
 * SkillQuest AI 学习评估复盘类型定义（模块7，与后端 Schema 保持一致）
 * 流程：开始测评 → 提交答卷 → 结果复盘 → 掌握度热力图 → 学习报告/PDF
 */

/** 试卷状态 */
export type ExamStatus = "active" | "disabled";

/** 题型 */
export type QuestionType = "single" | "multiple" | "judge";

/** 测评题目（下发不含答案） */
export interface ExamQuestion {
  id: number;
  question_type: QuestionType;
  content: string;
  options: { key: string; label: string }[];
  score: number;
  knowledge_point_id: number | null;
}

/** 阶段测评试卷列表项 */
export interface ExamPaper {
  id: number;
  title: string;
  stage: string;
  description: string;
  total_score: number;
  duration: number;
  status: ExamStatus;
}

/** 开始测评返回 */
export interface ExamStartResult {
  record_id: number;
  exam_id: number;
  title: string;
  stage: string;
  description: string;
  duration: number;
  total_score: number;
  end_time: string;
  questions: ExamQuestion[];
}

/** 单题作答 */
export interface AnswerItem {
  question_id: number;
  user_answer: string | string[] | boolean;
}

/** 提交结果摘要 */
export interface ExamSubmitResult {
  record_id: number;
  score: number;
  correct_count: number;
  total_count: number;
  pass_flag: boolean;
}

/** 单题结果 */
export interface QuestionResultItem {
  question_id: number;
  content: string;
  is_correct: boolean;
  points_earned: number;
  points_total: number;
  correct_answer: string | string[] | boolean;
  user_answer: string | string[] | boolean | null;
}

/** 知识点掌握度条目 */
export interface MasteryItem {
  knowledge_point_id: number | null;
  name: string;
  domain: string;
  mastery_score: number;
  last_test_time: string | null;
  review_count: number;
}

/** 能力雷达点（按能力域聚合） */
export interface RadarPointItem {
  domain: string;
  value: number;
}

/** 学习趋势点 */
export interface TrendPointItem {
  record_id: number;
  exam_title: string;
  score: number;
  submitted_at: string;
}

/** 薄弱知识点 */
export interface WeakPointItem {
  knowledge_point_id: number | null;
  name: string;
  mastery_score: number;
  suggestion: string;
}

/** 测评结果详情 */
export interface ExamResultDetail {
  record_id: number;
  exam_id: number;
  exam_title: string;
  stage: string;
  score: number;
  correct_count: number;
  total_count: number;
  submitted_at: string;
  questions: QuestionResultItem[];
  mastery: MasteryItem[];
  radar: RadarPointItem[];
  trend: TrendPointItem[];
  weak_points: WeakPointItem[];
  next_steps: string[];
}

/** 掌握度总览（含热力图） */
export interface MasteryOverview {
  items: MasteryItem[];
  heatmap: {
    domains: string[];
    points: { domain: string; name: string; value: number }[];
  };
}

/** 学习报告生成/详情 */
export interface LearningReport {
  id: number;
  report_type: string;
  report_json: {
    score: number;
    exam_title: string;
    stage: string;
    overall: string;
    summary?: string;
    strengths: { name: string; score: number }[];
    weaknesses: WeakPointItem[];
    suggestion: string;
    improvement_plan?: string;
    next_steps: string[];
    radar: RadarPointItem[];
    trend: TrendPointItem[];
    mastery: MasteryItem[];
    mastered_count: number;
    weak_count: number;
    domain_analysis?: unknown[];
    mistake_patterns?: unknown[];
    next_focus?: unknown[];
  };
  ai_enriched: boolean;
  pdf_url: string | null;
  created_at: string;
}

/** 报告列表项 */
export interface ReportListItem {
  id: number;
  report_type: string;
  score: number | null;
  exam_title: string | null;
  created_at: string;
}

/** 段位元信息 */
export const EXAM_STAGE_META: Record<
  string,
  { label: string; color: string; icon: string }
> = {
  bronze: { label: "青铜", color: "#b45309", icon: "🥉" },
  silver: { label: "白银", color: "#64748b", icon: "🥈" },
  gold: { label: "黄金", color: "#d97706", icon: "🥇" },
  platinum: { label: "铂金", color: "#06b6d4", icon: "💎" },
  diamond: { label: "钻石", color: "#6366f1", icon: "🔷" },
  king: { label: "王者", color: "#dc2626", icon: "👑" },
};