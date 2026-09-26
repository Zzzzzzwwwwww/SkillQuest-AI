/*
 * SkillQuest AI 游戏化类型定义（模块9）
 * 覆盖：成长首页 / 成就中心 / XP 流水 / 番茄钟 / 每日督导
 */

/** 今日任务条目 */
export interface DailyTaskItem {
  task_id: string;
  type: string;
  title: string;
  detail: string;
  xp: number;
}

/** 成就条目 */
export interface AchievementItem {
  achievement_id: number;
  name: string;
  title: string;
  description: string;
  icon: string;
  hidden: boolean;
  unlocked: boolean;
  unlocked_at: string | null;
  xp_reward: number;
}

/** 成就中心 */
export interface AchievementCenter {
  total: number;
  unlocked_count: number;
  items: AchievementItem[];
}

/** XP 流水条目 */
export interface XpLogItem {
  id: number;
  action_type: string;
  xp_amount: number;
  note: string;
  created_at: string | null;
}

/** 成长首页聚合数据 */
export interface GamificationOverview {
  level: number;
  tier_key: string;
  tier_label: string;
  tier_index: number;
  tier_percent: number;
  total_xp: number;
  xp_to_next_level: number;
  today_xp: number;
  streak: number;
  checked_in_today: boolean;
  pomodoro: {
    session_count: number;
    focus_total_minutes: number;
  };
  daily_tasks: DailyTaskItem[];
  achievements: AchievementCenter;
  recent_xp_logs: XpLogItem[];
}

/** 每日打卡出参 */
export interface CheckinResult {
  already_checked: boolean;
  xp_amount: number;
  streak: number;
  message: string;
}

/** 番茄钟模式 */
export type PomodoroMode = "focus" | "deep";

/** 番茄钟完成入参 */
export interface PomodoroPayload {
  mode: PomodoroMode;
  note?: string;
}

/** 番茄钟完成出参 */
export interface PomodoroResult {
  session_id: number;
  mode: PomodoroMode;
  focus_minutes: number;
  break_minutes: number;
  xp_amount: number;
  message: string;
}

/** 每日督导出参 */
export interface DailySupervision {
  tasks: DailyTaskItem[];
  coach_plan: Array<Record<string, unknown>>;
  pomodoro_suggestion: Record<string, unknown>;
  encouragement: string;
  degraded: boolean;
}