/*
 * 智能答疑（RAG）业务 API（模块6）
 * - 常规接口走统一响应解包
 * - 发送消息使用 fetch + SSE 流式解析（支持增量渲染/引用/知识点/练习）
 */
import { get, post } from "@/api/request";
import type {
  ChatHistoryResult,
  ChatReference,
  ChatSessionItem,
  KnowledgeSearchResult,
  KnowledgeUploadResult,
  PracticeItem,
  RelatedSkillItem,
  SseEventType,
} from "@/types/tutor";

/** 创建答疑会话 */
export function createChatSession(payload?: {
  title?: string;
}): Promise<{ id: number; title: string; created_at?: string }> {
  return post<{ id: number; title: string }>("/chat/session", payload ?? {});
}

/** 查询会话历史（无 sessionId 返回会话列表，有则返回消息） */
export function getChatHistory(sessionId?: number): Promise<ChatHistoryResult> {
  return get<ChatHistoryResult>("/chat/history", {
    params: sessionId ? { session_id: sessionId } : {},
  });
}

/** 上传知识文档（正文文本） */
export function uploadKnowledge(payload: {
  title: string;
  content: string;
  source?: string;
  file_url?: string;
  skill_node_id?: number;
}): Promise<KnowledgeUploadResult> {
  return post<KnowledgeUploadResult>("/knowledge/upload", payload);
}

/** 知识库相似检索 */
export function searchKnowledge(params: {
  q: string;
  top_k?: number;
  document_id?: number;
}): Promise<KnowledgeSearchResult> {
  return get<KnowledgeSearchResult>("/knowledge/search", { params });
}

/** SSE 事件回调载荷 */
export interface SseHandlers {
  onDelta: (token: string) => void;
  onAnswer?: (answer: string) => void;
  onReferences?: (references: ChatReference[], sufficient: boolean) => void;
  onKnowledge?: (skills: RelatedSkillItem[]) => void;
  onPractice?: (practice: PracticeItem[]) => void;
  onDone?: (messageId: number, sessionId: number) => void;
  onError?: (message: string) => void;
}

/**
 * 发送消息（SSE 流式）。
 * 使用 fetch 手动解析 text/event-stream，支持进度/引用/知识点/练习四类事件。
 */
export async function sendChatMessageStream(
  sessionId: number,
  content: string,
  handlers: SseHandlers
): Promise<void> {
  const base = (import.meta.env.VITE_API_BASE as string) || "/api/v1";
  const token = localStorage.getItem("sq_token") ?? "";
  const resp = await fetch(`${base}/chat/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ session_id: sessionId, content }),
  });

  if (!resp.ok) {
    let detail = `请求失败(${resp.status})`;
    try {
      const body = await resp.json();
      detail = body?.message || detail;
    } catch {
      /* ignore */
    }
    handlers.onError?.(detail);
    return;
  }

  const reader = resp.body?.getReader();
  if (!reader) {
    handlers.onError?.("当前环境不支持流式读取");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let eventType: SseEventType | "" = "";

  const dispatch = (line: string) => {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim() as SseEventType;
      return;
    }
    if (line.startsWith("data:")) {
      const raw = line.slice(5).trim();
      if (!raw) return;
      let data: Record<string, any>;
      try {
        data = JSON.parse(raw);
      } catch {
        return;
      }
      switch (eventType) {
        case "delta":
          handlers.onDelta(String(data.token ?? ""));
          break;
        case "answer":
          handlers.onAnswer?.(String(data.answer ?? ""));
          break;
        case "references":
          handlers.onReferences?.(
            (data.references ?? []) as ChatReference[],
            Boolean(data.sufficient)
          );
          break;
        case "knowledge":
          handlers.onKnowledge?.((data.related_skills ?? []) as RelatedSkillItem[]);
          break;
        case "practice":
          handlers.onPractice?.((data.practice ?? []) as PracticeItem[]);
          break;
        case "done":
          handlers.onDone?.(Number(data.message_id), Number(data.session_id));
          break;
      }
      return;
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const ln of lines) dispatch(ln);
  }
  if (buffer.trim()) {
    dispatch(buffer);
  }
}

/** 便捷方法：兜底非流式（当 fetch 不可用时） */
export async function sendChatMessage(payload: {
  session_id: number;
  content: string;
}): Promise<string> {
  return post<string>("/chat/message", payload);
}

export type { ChatSessionItem };