/*
 * SkillQuest AI 岗位技能图谱类型定义（模块4，与后端 Schema 保持一致）
 * 层级：岗位 job(L0) → 能力域 capability(L1) → 技能 skill(L2) → 知识点 knowledge(L3)
 */

/** 岗位（含关联技能数） */
export interface JobItem {
  id: number;
  job_name: string;
  job_family: string;
  description: string | null;
  industry: string | null;
  status: string;
  skill_count: number;
}

/** 技能树节点（递归） */
export interface SkillNodeItem {
  id: number;
  name: string;
  level: number;
  node_type: "job" | "capability" | "skill" | "knowledge";
  node_type_label: string;
  description: string;
  importance: number;
  required_level: number | null;
  status: "mastered" | "learning" | "not_started";
  mastery_score: number;
  prerequisites: string[];
  children: SkillNodeItem[];
}

/** Skill Gap 单项 */
export interface SkillGapItem {
  skill_id: number;
  name: string;
  importance: number;
  required: number;
  mastery: number;
  gap: number;
}

/** Skill Gap 汇总 */
export interface SkillGapSummary {
  overall_mastery: number;
  fit_rate: number;
  skill_count: number;
  mastered_count: number;
  gaps: SkillGapItem[];
}

/** 岗位分层技能树出参 */
export interface JobSkillTreeResult {
  job: JobItem;
  tree: SkillNodeItem;
  summary: SkillGapSummary;
}

/** 技能详情：前置知识 */
export interface PrerequisiteItem {
  id: number | null;
  name: string;
  node_type: string;
  mastery: number;
  status: string;
}

/** 技能详情：推荐资源 */
export interface ResourceItem {
  type: string;
  title: string;
  desc: string;
}

/** 技能详情：关联岗位 */
export interface RelatedJobItem {
  job_id: number;
  job_name: string;
  job_family: string;
  importance: number;
  required_level: number;
}

/** 技能详情出参 */
export interface SkillDetailResult {
  id: number;
  name: string;
  node_type: string;
  node_type_label: string;
  level: number;
  description: string;
  importance: number;
  mastery_score: number;
  status: string;
  prerequisites: PrerequisiteItem[];
  resources: ResourceItem[];
  related_jobs: RelatedJobItem[];
}

/** 用户技能掌握状态单条 */
export interface UserSkillStatusItem {
  skill_node_id: number;
  status: string;
  mastery_score: number;
  updated_at: string | null;
}

/** 用户技能掌握状态列表出参 */
export interface UserSkillStatusResult {
  total: number;
  items: UserSkillStatusItem[];
}

/** 批量同步技能状态请求体 */
export interface SkillStatusSyncPayload {
  items: Array<{
    skill_node_id: number;
    status?: string;
    mastery_score: number;
  }>;
}