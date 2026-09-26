<script setup lang="ts">
/*
 * AI 导师聊天页（模块6 RAG）
 * - 左侧：历史会话列表 + 新建会话 + 知识库管理入口
 * - 中部：SSE 流式对话（增量打字机）、引用来源卡片、关联知识点、推荐练习
 * - 顶部：当前问答模式提示（规则/模型 Embedding 与 LLM 状态）
 */
import { computed, onMounted, ref } from "vue";
import {
  ChatDotRound,
  Collection,
  MagicStick,
  Plus,
  Refresh,
  Upload,
  WarningFilled,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import {
  createChatSession,
  getChatHistory,
  searchKnowledge,
  sendChatMessageStream,
  uploadKnowledge,
} from "@/api/tutor";
import { getWeaknesses } from "@/api/business";
import type {
  ChatMessageItem,
  ChatReference,
  ChatSessionItem,
  PracticeItem,
  RelatedSkillItem,
} from "@/types/tutor";
import type { WeaknessItem } from "@/types/business";

interface DisplayMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  references?: ChatReference[];
  related_skills?: RelatedSkillItem[];
  practice?: PracticeItem[];
  streaming?: boolean;
}

const loading = ref(false);
const sending = ref(false);
const sessions = ref<ChatSessionItem[]>([]);
const activeSessionId = ref<number | null>(null);
const messages = ref<DisplayMessage[]>([]);
const input = ref("");
const bodyRef = ref<HTMLDivElement | null>(null);

// ---- 业务闭环5：待攻克弱点诊断（AI 导师推送） ----
const weaknesses = ref<WeaknessItem[]>([]);
const weakLoading = ref(false);

const streamingMsg = ref<DisplayMessage | null>(null);
let abortStream: (() => void) | null = null;

// ---- 知识库上传对话框 ----
const kbVisible = ref(false);
const kbTitle = ref("");
const kbSource = ref("");
const kbContent = ref("");
const kbUploading = ref(false);
const kbHits = ref<Array<{ doc_title: string; score: number; content: string }>>([]);

const currentMode = computed(() => {
  return {
    em: "规则向量",
    llm: "规则降级",
    note: "未配置华为云模型，走规则检索/降级问答；配置 HUAWEI_EMBEDDING_*/HUAWEI_LLM_* 后自动切换。",
  };
});

function scrollBottom(): void {
  requestAnimationFrame(() => {
    if (bodyRef.value) {
      bodyRef.value.scrollTop = bodyRef.value.scrollHeight;
    }
  });
}

async function refreshSessions(): Promise<void> {
  const r = await getChatHistory();
  sessions.value = r.sessions ?? [];
}

/** 加载待攻克弱点诊断（闭环5：测评 → 弱点 → 导师推送） */
async function loadWeaknesses(): Promise<void> {
  weakLoading.value = true;
  try {
    weaknesses.value = await getWeaknesses();
  } catch {
    weaknesses.value = [];
  } finally {
    weakLoading.value = false;
  }
}

/** 把弱点诊断转为提问并自动发送 */
function askWeakness(item: WeaknessItem): void {
  input.value = `如何攻克「${item.kp_name}」这个学习弱点？掌握度仅 ${item.mastery_score} 分，请结合我的学习进度给出建议。`;
  if (!activeSessionId.value) {
    void newSession().then(() => void send());
  } else {
    void send();
  }
}

async function loadSession(id: number): Promise<void> {
  abortStream?.();
  activeSessionId.value = id;
  const r = await getChatHistory(id);
  messages.value = (r.messages ?? []).map((m: ChatMessageItem) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    references: m.references ?? [],
  }));
  scrollBottom();
}

async function newSession(): Promise<void> {
  abortStream?.();
  activeSessionId.value = null;
  messages.value = [];
  try {
    const s = await createChatSession();
    activeSessionId.value = s.id;
    await refreshSessions();
    ElMessage.success("已创建新会话");
  } catch {
    /* 统一提示 */
  }
}

async function init(): Promise<void> {
  loading.value = true;
  try {
    await loadWeaknesses();
    await refreshSessions();
    const first = sessions.value.find((s) => s.message_count > 0) ?? sessions.value[0];
    if (first) {
      await loadSession(first.id);
    } else {
      await newSession();
    }
  } finally {
    loading.value = false;
  }
}

async function send(): Promise<void> {
  const text = input.value.trim();
  if (!text || sending.value || !activeSessionId.value) return;
  input.value = "";

  messages.value.push({ id: Date.now(), role: "user", content: text });

  const holder: DisplayMessage = {
    id: Date.now() + 1,
    role: "assistant",
    content: "",
    streaming: true,
  };
  streamingMsg.value = holder;
  messages.value.push(holder);
  sending.value = true;
  scrollBottom();

  const sid = activeSessionId.value;
  let done = false;
  abortStream = () => {
    done = true;
  };

  try {
    await sendChatMessageStream(sid, text, {
      onDelta: (token) => {
        if (done) return;
        holder.content += token;
        scrollBottom();
      },
      onReferences: (refs) => {
        holder.references = refs;
      },
      onKnowledge: (skills) => {
        holder.related_skills = skills;
      },
      onPractice: (practice) => {
        holder.practice = practice;
      },
      onError: (err) => {
        if (done) return;
        ElMessage.error(err);
      },
      onDone: async () => {
        done = true;
        holder.streaming = false;
        await refreshSessions();
      },
    });
  } finally {
    if (!done) {
      holder.streaming = false;
      if (!holder.content) {
        holder.content = "（连接中断，请重试）";
      }
    }
    abortStream = null;
    sending.value = false;
    scrollBottom();
  }
}

// ---- 知识库 ----
async function doSearch(): Promise<void> {
  kbHits.value = [];
  const q = kbTitle.value.trim() || kbContent.value.trim().slice(0, 20);
  if (!q) return;
  try {
    const r = await searchKnowledge({ q, top_k: 3 });
    kbHits.value = r.hits.map((h) => ({
      doc_title: h.doc_title,
      score: h.score,
      content: h.content,
    }));
  } catch {
    /* 统一提示 */
  }
}

async function doUpload(): Promise<void> {
  if (!kbTitle.value.trim() || !kbContent.value.trim()) {
    ElMessage.warning("请填写标题与文档内容");
    return;
  }
  kbUploading.value = true;
  try {
    const r = await uploadKnowledge({
      title: kbTitle.value.trim(),
      content: kbContent.value.trim(),
      source: kbSource.value.trim(),
    });
    ElMessage.success(`上传成功：${r.chunk_count} 个分块（${r.embedding_mode}向量模式）`);
    kbVisible.value = false;
    kbTitle.value = "";
    kbSource.value = "";
    kbContent.value = "";
    kbHits.value = [];
  } finally {
    kbUploading.value = false;
  }
}

function clearKb(): void {
  kbHits.value = [];
  kbTitle.value = "";
  kbSource.value = "";
  kbContent.value = "";
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    void send();
  }
}

onMounted(init);
</script>

<template>
  <div class="page-container tutor-layout">
    <!-- 左侧：会话历史 + 待攻克弱点 -->
    <el-card shadow="never" class="side-card">
      <template #header>
        <div class="side-header">
          <b>会话历史</b>
          <el-button type="primary" size="small" :icon="Plus" @click="newSession">
            新建
          </el-button>
        </div>
      </template>

      <!-- 业务闭环5：弱点诊断推送 -->
      <div class="weak-block" v-loading="weakLoading">
        <div class="weak-title">
          <el-icon class="weak-icon"><WarningFilled /></el-icon>
          <span>待攻克弱点</span>
          <el-tag size="small" type="danger" effect="light" round v-if="weaknesses.length">
            {{ weaknesses.length }}
          </el-tag>
        </div>
        <div v-if="weaknesses.length" class="weak-list">
          <div
            v-for="w in weaknesses"
            :key="w.id"
            class="weak-item"
            title="点击向 AI 导师提问"
            @click="askWeakness(w)"
          >
            <div class="weak-name">{{ w.kp_name }}</div>
            <div class="weak-sub">
              <el-tag size="small" effect="plain">{{ w.domain || "综合" }}</el-tag>
              <span class="weak-score">{{ w.mastery_score }} 分</span>
            </div>
            <div class="weak-diagnosis">{{ w.diagnosis }}</div>
          </div>
        </div>
        <el-empty
          v-else-if="!weakLoading"
          description="暂无待攻克弱点"
          :image-size="44"
        />
      </div>

      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
          @click="loadSession(s.id)"
        >
          <div class="session-title">{{ s.title }}</div>
          <div class="session-sub">
            {{ s.message_count }} 条 · {{ s.last_message || "暂无消息" }}
          </div>
        </div>
        <el-empty v-if="!sessions.length" description="暂无会话" :image-size="60" />
      </div>
    </el-card>

    <!-- 中部：聊天区 -->
    <el-card shadow="hover" class="chat-card" v-loading="loading">
      <template #header>
        <div class="chat-header">
          <div class="title-area">
            <b>AI 导师</b>
            <el-tag size="small" effect="light" type="info" class="mode-tag">
              <el-icon><MagicStick /></el-icon>
              Embedding:{{ currentMode.em }} · LLM:{{ currentMode.llm }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button size="small" :icon="Upload" @click="kbVisible = true">
              知识库
            </el-button>
            <el-button size="small" :icon="Refresh" @click="refreshSessions">
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div ref="bodyRef" class="chat-body">
        <div v-for="(m, idx) in messages" :key="idx" class="msg-row" :class="m.role">
          <div class="avatar" :class="m.role">
            {{ m.role === "user" ? "我" : "AI" }}
          </div>
          <div class="bubble">
            <div class="bubble-text" v-if="m.content">{{ m.content }}</div>
            <div v-if="m.streaming" class="cursor">▍</div>

            <!-- 引用来源 -->
            <div v-if="m.references?.length" class="meta-block">
              <div class="meta-title">
                <el-icon><Collection /></el-icon> 引用来源（{{ m.references.length }}）
              </div>
              <el-card
                v-for="(r, ri) in m.references"
                :key="ri"
                shadow="never"
                class="ref-card"
              >
                <div class="ref-head">
                  <b>{{ r.doc_title }}</b>
                  <span class="score">{{ (r.score * 100).toFixed(1) }}%</span>
                </div>
                <div class="ref-src">{{ r.source || "未知来源" }} · 分块#{{ r.chunk_id }}</div>
                <div class="ref-evi">{{ r.evidence }}</div>
              </el-card>
            </div>

            <!-- 关联知识点 -->
            <div v-if="m.related_skills?.length" class="meta-block">
              <div class="meta-title">
                <el-icon><ChatDotRound /></el-icon> 关联知识点
              </div>
              <div class="tag-line">
                <el-tag
                  v-for="(s, si) in m.related_skills"
                  :key="si"
                  size="small"
                  effect="plain"
                >{{ s.name }}</el-tag>
              </div>
            </div>

            <!-- 推荐练习 -->
            <div v-if="m.practice?.length" class="meta-block">
              <div class="meta-title">
                <el-icon><Collection /></el-icon> 推荐练习
              </div>
              <el-card
                v-for="(p, pi) in m.practice"
                :key="pi"
                shadow="never"
                class="practice-card"
              >
                <div class="practice-head">
                  <b>{{ p.title }}</b>
                  <el-tag size="small" effect="dark" type="warning">练习</el-tag>
                </div>
                <div class="practice-desc">{{ p.reason }} · {{ p.duration }} 分钟 · 难度{{ p.difficulty }}</div>
              </el-card>
            </div>
          </div>
        </div>

        <div v-if="!messages.length" class="empty-tip">
          <div class="tip-hero">🎓</div>
          <p>向 AI 导师提问，例如「什么是机器学习？」</p>
          <p class="tip-sub">回答基于知识库检索，带引用来源并推荐练习</p>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          :disabled="sending"
          placeholder="输入问题，Enter 发送 / Shift+Enter 换行…"
          @keydown="onKeydown"
        />
        <el-button
          type="primary"
          class="send-btn"
          :loading="sending"
          :disabled="!input.trim()"
          @click="send"
        >发送</el-button>
      </div>
    </el-card>

    <!-- 知识库上传对话框 -->
    <el-dialog v-model="kbVisible" title="知识库管理（RAG）" width="560px">
      <el-form label-width="72px">
        <el-form-item label="标题">
          <el-input v-model="kbTitle" placeholder="如：机器学习基础文档" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="kbSource" placeholder="选填，如：技能图谱课程" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input
            v-model="kbContent"
            type="textarea"
            :rows="6"
            placeholder="粘贴知识文档正文，上传后自动切分并向量化入库…"
          />
        </el-form-item>
      </el-form>

      <div class="kb-actions">
        <el-button @click="clearKb">清空</el-button>
        <el-button @click="doSearch">检索预览</el-button>
        <el-button type="primary" :loading="kbUploading" @click="doUpload">
          <el-icon><Upload /></el-icon> 上传入库
        </el-button>
      </div>

      <div v-if="kbHits.length" class="kb-preview">
        <div class="kb-preview-title">检索预览：</div>
        <div v-for="(h, i) in kbHits" :key="i" class="kb-hit">
          <b>《{{ h.doc_title }}》</b> <span>{{ (h.score * 100).toFixed(1) }}%</span>
          <div class="kb-hit-text">{{ h.content }}</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.tutor-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 140px);
  min-height: 440px;
}

.side-card {
  width: 260px;
  border-radius: 14px;
  border: none;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;

  :deep(.el-card__body) {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .side-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .weak-block {
    border: 1px solid #fee2e2;
    background: #fff7f7;
    border-radius: 10px;
    padding: 10px;
    margin-bottom: 10px;

    .weak-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
      color: #b91c1c;
      margin-bottom: 8px;

      .weak-icon {
        color: #ef4444;
      }
    }

    .weak-list {
      max-height: 220px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .weak-item {
      background: #fff;
      border: 1px solid #fee2e2;
      border-radius: 8px;
      padding: 8px 10px;
      cursor: pointer;
      transition: border-color 0.15s, box-shadow 0.15s;

      &:hover {
        border-color: #f87171;
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.12);
      }

      .weak-name {
        font-size: 13px;
        font-weight: 600;
        color: #1f2329;
        margin-bottom: 4px;
      }

      .weak-sub {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        margin-bottom: 4px;

        .weak-score {
          font-size: 11px;
          color: #dc2626;
          font-weight: 600;
        }
      }

      .weak-diagnosis {
        font-size: 11px;
        color: #9ca3af;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
    }
  }

  .session-item {
    padding: 10px 12px;
    border-radius: 10px;
    cursor: pointer;
    margin-bottom: 6px;
    transition: background 0.15s;

    &:hover {
      background: #f1f4ff;
    }

    &.active {
      background: #eef2ff;
    }

    .session-title {
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 2px;
    }

    .session-sub {
      font-size: 11px;
      color: #9ca3af;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
}

.chat-card {
  flex: 1;
  border-radius: 14px;
  border: none;
  display: flex;
  flex-direction: column;
  min-width: 0;

  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .title-area {
      display: flex;
      align-items: center;
      gap: 8px;

      .mode-tag {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        font-size: 11px;
      }
    }

    .header-actions {
      display: flex;
      gap: 4px;
    }
  }

  .chat-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 4px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .msg-row {
    display: flex;
    gap: 10px;
    max-width: 100%;

    &.user {
      flex-direction: row-reverse;
    }

    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      flex-shrink: 0;
      margin-top: 2px;

      &.user {
        background: var(--sq-primary-gradient);
        color: #fff;
      }

      &.assistant {
        background: #eef2ff;
        color: #4f6ef7;
      }
    }

    .bubble {
      max-width: 78%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.7;
      word-break: break-word;

      &.user {
        background: var(--sq-primary-gradient);
        color: #fff;
        border-top-right-radius: 4px;
      }

      &.assistant {
        background: #f1f4ff;
        color: #1f2329;
        border-top-left-radius: 4px;
      }

      .cursor {
        display: inline-block;
        animation: blink 0.8s infinite;
        color: #4f6ef7;
      }

      .meta-block {
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px dashed #d9defa;

        .meta-title {
          font-size: 12px;
          color: #6b7280;
          display: flex;
          align-items: center;
          gap: 4px;
          margin-bottom: 8px;
        }

        .tag-line {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .ref-card,
        .practice-card {
          border-radius: 8px;
          border: 1px solid #eef1f8;
          margin-bottom: 8px;
          background: #fff;

          .ref-head,
          .practice-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 4px;

            .score {
              color: #d97706;
              font-size: 12px;
              font-weight: 600;
            }
          }

          .ref-src,
          .practice-desc {
            font-size: 11px;
            color: #9ca3af;
            margin-bottom: 4px;
          }

          .ref-evi {
            font-size: 12px;
            color: #4b5563;
            line-height: 1.5;
            background: #f9fafb;
            border-radius: 6px;
            padding: 6px 8px;
          }
        }
      }
    }
  }

  .empty-tip {
    margin: auto;
    text-align: center;
    color: #9ca3af;

    .tip-hero {
      font-size: 52px;
    }

    p {
      font-size: 14px;
      margin: 8px 0 0;
    }

    .tip-sub {
      font-size: 12px;
      opacity: 0.7;
    }
  }

  .chat-input {
    display: flex;
    gap: 10px;
    margin-top: 12px;

    .send-btn {
      flex-shrink: 0;
      min-width: 72px;
    }
  }
}

.kb-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.kb-preview {
  margin-top: 12px;

  .kb-preview-title {
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 6px;
  }

  .kb-hit {
    font-size: 12px;
    border: 1px solid #eef1f8;
    border-radius: 8px;
    padding: 8px 10px;
    margin-bottom: 6px;

    .kb-hit-text {
      color: #6b7280;
      margin-top: 4px;
      line-height: 1.5;
    }
  }
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.2;
  }
}

@media (max-width: 768px) {
  .tutor-layout {
    flex-direction: column;
    height: auto;
  }

  .side-card {
    width: 100%;
    max-height: 180px;
  }

  .bubble {
    max-width: 88% !important;
  }
}
</style>