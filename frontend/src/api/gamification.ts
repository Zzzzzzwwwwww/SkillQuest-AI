/*
 * SkillQuest AI 游戏化 API（模块9）
 * - 成长首页 / 成就中心 / XP 流水
 * - 每日打卡 / 番茄钟 / 每日督导任务
 */
import { get, post } from "@/api/request";
import type {
  AchievementCenter,
  CheckinResult,
  DailySupervision,
  GamificationOverview,
  PomodoroPayload,
  PomodoroResult,
} from "@/types/gamification";

/** 成长首页聚合数据 */
export function getGamificationOverview(): Promise<GamificationOverview> {
  return get<GamificationOverview>("/gamification/overview");
}

/** 成就中心 */
export function getAchievements(): Promise<AchievementCenter> {
  return get<AchievementCenter>("/gamification/achievements");
}

/** XP 流水（分页） */
export function getXpLogs(
  page = 1,
  pageSize = 20
): Promise<{ items: Array<Record<string, unknown>>; total: number; page: number; page_size: number }> {
  return get("/gamification/xp-logs", { params: { page, page_size: pageSize } });
}

/** 每日打卡 */
export function checkinToday(): Promise<CheckinResult> {
  return post<CheckinResult>("/gamification/checkin", {});
}

/** 完成番茄钟（focus 25min / deep 40min） */
export function completePomodoro(payload: PomodoroPayload): Promise<PomodoroResult> {
  return post<PomodoroResult, PomodoroPayload>("/gamification/pomodoro", payload);
}

/** 每日督导（规则任务 + Coach Agent 增强） */
export function getTodaySupervision(): Promise<DailySupervision> {
  return get<DailySupervision>("/gamification/today-tasks");
}

/** 完成每日任务（规则奖励 XP） */
export function completeDailyTask(
  taskId: string
): Promise<{ task_id: string; already_done: boolean; xp_amount: number; message: string }> {
  return post("/gamification/tasks/complete", { task_id: taskId });
}