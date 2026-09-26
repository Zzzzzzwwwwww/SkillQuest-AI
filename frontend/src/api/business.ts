/*
 * SkillQuest AI 六大业务闭环 API（模块8）
 * - 选定岗位落库（闭环3 触发入口）
 * - 弱点诊断推送（闭环5）
 * - Boss 挑战（闭环6）
 */
import { get, post } from "@/api/request";
import type {
  BossAnswerItem,
  BossFinishResult,
  BossStartResult,
  JobSelectPayload,
  JobSelectResult,
  WeaknessItem,
} from "@/types/business";

/** 选定目标岗位并自动生成学习路径 */
export function selectTargetJob(payload: JobSelectPayload): Promise<JobSelectResult> {
  return post<JobSelectResult, JobSelectPayload>("/jobs/select", payload);
}

/** 待攻克弱点诊断列表（AI 导师推送） */
export function getWeaknesses(): Promise<WeaknessItem[]> {
  return get<WeaknessItem[]>("/chat/weaknesses");
}

/** 开始 Boss 挑战（按技能抽题，不下发答案） */
export function startBossChallenge(skillNodeId: number): Promise<BossStartResult> {
  return post<BossStartResult, { skill_node_id: number }>("/boss/start", {
    skill_node_id: skillNodeId,
  });
}

/** 完成 Boss 挑战（规则评分 → XP/等级/技能等级自动更新） */
export function finishBossChallenge(
  skillNodeId: number,
  answers: BossAnswerItem[]
): Promise<BossFinishResult> {
  return post<BossFinishResult, { skill_node_id: number; answers: BossAnswerItem[] }>(
    "/boss/finish",
    { skill_node_id: skillNodeId, answers }
  );
}