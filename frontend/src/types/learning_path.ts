/*
 * SkillQuest AI 个性化导学类型定义（模块5，与后端 Schema 保持一致）
 * 路径映射：青铜 → 白银 → 黄金 → 铂金 → 钻石 → 王者
 */

/** 路径节点状态（规则推导：completed/learning/unlocked/locked） */
export type LearningNodeStatus = "completed" | "learning" | "unlocked" | "locked";

/** 路径节点（地图/详情复用） */
export interface LearningStageNode {
  id: number;
  skill_node_id: number;
  name: string;
  node_type: string;
  capability: string;
  stage: string;
  order_no: number;
  status: LearningNodeStatus;
  estimated_hours: number;
  importance: number;
  required_level: number;
  mastery: number;
  gap: number;
  progress_percent: number;
  last_position: string | null;
  prerequisites: string[];
}

/** 学习路径地图（6 段位） */
export interface LearningPathMap {
  path_id: number;
  target_job: string;
  path_name: string;
  status: string;
  current_node_id: number | null;
  total_nodes: number;
  mastered_nodes: number;
  overall_progress: number;
  stages: Record<string, LearningStageNode[]>;
  stage_order: string[];
}

/** 生成结果（路径 + meta） */
export interface GeneratePathResult {
  path: LearningPathMap;
  meta: Record<string, any>;
  agent_note?: string;
}

/** 更新进度入参 */
export interface UpdateProgressPayload {
  path_id: number;
  skill_node_id: number;
  progress_percent: number;
  last_position?: string;
}

/** 更新进度出参 */
export interface UpdateProgressResult {
  path: LearningPathMap;
  updated_node: LearningStageNode | null;
  to_next: boolean;
}

/** 断点续学出参 */
export interface ResumePathResult {
  path: LearningPathMap;
  resume_node: LearningStageNode | null;
  resume_position: string | null;
  hint: string;
}

/** 学习资源（规则推荐，含理由/评分） */
export interface LearningResource {
  resource_id: number;
  title: string;
  type: "video" | "course" | "article" | "exercise";
  type_label: string;
  url: string;
  skill_node_id: number;
  difficulty: number;
  duration: number;
  description: string;
  reason: string;
  score: number;
}

/** 段位展示元数据 */
export const STAGE_META: Record<
  string,
  { label: string; color: string; icon: string; desc: string }
> = {
  bronze: {
    label: "青铜",
    color: "#b45309",
    icon: "🥉",
    desc: "夯实基础：入门技能与前置知识",
  },
  silver: {
    label: "白银",
    color: "#64748b",
    icon: "🥈",
    desc: "巩固技能：核心工具与语言训练",
  },
  gold: {
    label: "黄金",
    color: "#d97706",
    icon: "🥇",
    desc: "进阶实战：关键技能与项目实践",
  },
  platinum: {
    label: "铂金",
    color: "#06b6d4",
    icon: "💎",
    desc: "能力提升：突破难点技能",
  },
  diamond: {
    label: "钻石",
    color: "#6366f1",
    icon: "🔷",
    desc: "精进打磨：补齐遗留短板",
  },
  king: {
    label: "王者",
    color: "#dc2626",
    icon: "👑",
    desc: "巅峰冲刺：达成岗位胜任",
  },
};