/*
 * SkillQuest AI 用户模块类型定义（与后端 Schema 保持一致）
 */

/** 用户信息 */
export interface User {
  id: number;
  username: string;
  email: string;
  phone: string | null;
  avatar: string | null;
  status: number;
  created_at: string;
  updated_at: string;
}

/** 用户画像 */
export interface UserProfile {
  id: number;
  user_id: number;
  real_name: string | null;
  education: string | null;
  major: string | null;
  school: string | null;
  company: string | null;
  job_intention: string | null;
  learning_goal: string | null;
  daily_study_time: number;
  created_at: string;
  updated_at: string;
}

/** 用户信息 + 画像（GET /users/me） */
export interface UserWithProfile extends User {
  profile: UserProfile | null;
}

/** 注册请求体 */
export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
}

/** 登录请求体 */
export interface LoginPayload {
  account: string;
  password: string;
}

/** 档案信息更新请求体 */
export interface ProfileUpdatePayload {
  real_name?: string | null;
  education?: string | null;
  major?: string | null;
  school?: string | null;
  company?: string | null;
  job_intention?: string | null;
  learning_goal?: string | null;
  daily_study_time?: number | null;
  phone?: string | null;
  avatar?: string | null;
}

/** 认证令牌 + 用户 */
export interface TokenResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

/** 学习档案 */
export interface LearningArchive {
  id: number;
  user_id: number;
  archive_name: string;
  target_job: string | null;
  current_level: number;
  total_xp: number;
  created_at: string;
  updated_at: string;
}

/** 档案概览（含规则统计） */
export interface ArchiveOverview extends LearningArchive {
  total_records: number;
  total_duration: number;
  finished_count: number;
  xp_to_next_level: number;
}

/** 学习记录 */
export interface LearningRecord {
  id: number;
  user_id: number;
  module_type: string;
  action_type: string;
  target_id: number | null;
  duration: number;
  result: Record<string, unknown> | null;
  created_at: string;
}

/** 测评报告 */
export interface AssessmentReport {
  id: number;
  user_id: number;
  assessment_id: number | null;
  report_type: string;
  report_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** 统一分页结果 */
export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** 学习记录筛选条件 */
export interface RecordQuery {
  page?: number;
  page_size?: number;
  module_type?: string;
  action_type?: string;
}

/** 报告查询条件 */
export interface ReportQuery {
  page?: number;
  page_size?: number;
  report_type?: string;
}

/** 统一响应体（后端约定） */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}