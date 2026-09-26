/*
 * SkillQuest AI 智能答疑（RAG）类型定义（模块6，与后端 Schema 保持一致）
 */

/** 消息角色 */
export type ChatRole = "user" | "assistant";

/** 引用来源 */
export interface ChatReference {
  chunk_id: number;
  doc_title: string;
  source: string;
  score: number;
  evidence: string;
  url: string;
}

/** 历史消息 */
export interface ChatMessageItem {
  id: number;
  role: ChatRole;
  content: string;
  references?: ChatReference[];
  created_at?: string | null;
}

/** 会话（历史列表项） */
export interface ChatSessionItem {
  id: number;
  title: string;
  message_count: number;
  last_message?: string | null;
  created_at?: string | null;
}

/** 历史查询结果 */
export interface ChatHistoryResult {
  sessions: ChatSessionItem[];
  messages: ChatMessageItem[];
}

/** 关联知识点 */
export interface RelatedSkillItem {
  skill_node_id: number;
  name: string;
}

/** 推荐练习 */
export interface PracticeItem {
  resource_id: number;
  title: string;
  type: string;
  duration: number;
  difficulty: number;
  reason: string;
}

/** SSE 事件类型 */
export type SseEventType =
  | "delta"
  | "answer"
  | "references"
  | "knowledge"
  | "practice"
  | "done";

/** 知识库检索命中 */
export interface KnowledgeHit {
  chunk_id: number;
  document_id: number;
  doc_title: string;
  source: string;
  score: number;
  content: string;
  skill_node_id?: number | null;
}

/** 知识库检索结果 */
export interface KnowledgeSearchResult {
  query: string;
  hits: KnowledgeHit[];
  embedding_mode: string;
  total_documents: number;
}

/** 上传文档结果 */
export interface KnowledgeUploadResult {
  document_id: number;
  title: string;
  status: string;
  chunk_count: number;
  embedding_mode: string;
}