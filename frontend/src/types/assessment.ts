/*
 * SkillQuest AI 测评与画像模块类型定义（与后端 Schema 保持一致）
 */

/** 试卷（测评中心列表） */
export interface Paper {
  id: number;
  title: string;
  description: string | null;
  type: string;
  status: string;
  question_count: number;
  created_at: string;
}

/** 量表展示参数 */
export interface ScaleSpec {
  min: number;
  max: number;
  step: number;
  labels?: string[];
}

/** 题目选项 */
export interface QuestionOption {
  key: string;
  label: string;
}

/** 题目（不含评分规则） */
export interface Question {
  id: number;
  paper_id: number;
  question_type: "single" | "multiple" | "scale" | "text";
  content: string;
  dimension: string;
  dimension_label: string;
  order_no: number;
  options?: QuestionOption[] | null;
  scale?: ScaleSpec | null;
  placeholder?: string | null;
}

/** 提交单题答案 */
export interface AnswerItem {
  question_id: number;
  answer: string | number | string[] | null;
}

/** 提交测评请求体 */
export interface AssessmentSubmitPayload {
  paper_id: number;
  answers: AnswerItem[];
  duration?: number;
}

/** 提交响应摘要 */
export interface AssessmentSubmitResult {
  result_id: number;
  total_score: number;
  top_job: string | null;
}

/** 技能差距 */
export interface SkillGap {
  skill: string;
  dimension: string;
  current: number;
  threshold: number;
  gap: number;
}

/** 推荐岗位 */
export interface RecommendedJob {
  job_id: string;
  job_name: string;
  summary: string;
  match_score: number;
  reason: string;
  skill_gaps: SkillGap[];
}

/** 能力雷达图数据点 */
export interface RadarPoint {
  name: string;
  key: string;
  score: number;
}

/** 测评结果详情 */
export interface AssessmentResultDetail {
  id: number;
  paper_id: number;
  paper_title: string;
  total_score: number;
  dimension_scores: Record<string, number>;
  dimension_labels: Record<string, string>;
  radar_data: { dimensions: RadarPoint[] };
  recommended_jobs: RecommendedJob[];
  recommendation_source: string;
  created_at: string;
}

/** 能力雷达出参 */
export interface AbilityRadar {
  dimensions: RadarPoint[];
}

/** 用户画像 */
export interface Persona {
  id: number;
  user_id: number;
  persona_tags: string[];
  persona_summary: string;
  strengths: string[];
  weaknesses: string[];
  advice: string;
  ai_enriched: boolean;
  ability_radar: AbilityRadar;
  interest: Record<string, unknown>;
  values: Record<string, unknown>;
  learning_goal: string | null;
  target_job: string | null;
  created_at: string;
  updated_at: string;
}

/** 画像生成响应 */
export interface PersonaGenerateResult {
  persona: Persona;
  source_result_id: number | null;
}