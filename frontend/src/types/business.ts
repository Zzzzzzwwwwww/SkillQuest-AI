/*
 * SkillQuest AI 六大业务闭环类型定义（模块8）
 * 覆盖：选定岗位落库 / 弱点诊断推送 / Boss 挑战奖励
 */

/** 选定目标岗位入参 */
export interface JobSelectPayload {
  job_id: number;
  auto_generate_path?: boolean;
}

/** 选定目标岗位出参（含自动生成的学习路径） */
export interface JobSelectResult {
  job_id: number;
  job_name: string;
  job_family: string;
  target_job: string;
  auto_generated_path: boolean;
  path: LearningPathBrief | null;
  meta?: Record<string, unknown> | null;
}

/** 学习路径简要结构（与后端 plan_path 入参派生，仅取展示字段） */
export interface LearningPathBrief {
  stage_order: string[];
  stages?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

/** 弱点诊断条目（AI 导师待攻克） */
export interface WeaknessItem {
  id: number;
  knowledge_point_id: number | null;
  kp_name: string;
  domain: string;
  mastery_score: number;
  diagnosis: string;
  created_at: string;
}

/** Boss 挑战题目（不下发答案） */
export interface BossQuestion {
  id: number;
  question_type: string;
  content: string;
  options: Array<{ key: string; label: string }>;
  score: number;
  knowledge_point_id: number | null;
}

/** Boss 挑战开始出参 */
export interface BossStartResult {
  challenge_id: number;
  skill_node_id: number;
  skill_name: string;
  stage: string;
  description: string;
  total_points: number;
  questions: BossQuestion[];
  source?: string;
}

/** Boss 挑战单题作答 */
export interface BossAnswerItem {
  question_id: number;
  user_answer: string | string[] | boolean;
}

/** Boss 挑战完成出参（含奖励与等级变化） */
export interface BossFinishResult {
  challenge_id: number;
  skill_node_id: number;
  skill_name: string;
  score: number;
  pass_flag: boolean;
  reward_xp: number;
  archive_xp: number;
  level: number;
  xp_to_next_level: number;
  skill_mastery: number;
  skill_status: string;
  message: string;
}