"""
统一 AgentService 单元验证（模块8 收尾）

覆盖：
  - Agent 注册表完整（8 个 Agent 提示词配置齐全）
  - user_prompt 拼装含 user_context/retrieved_docs/history 与裁剪逻辑
  - 未配置大模型 → 规则 fallback 降级 / 无 fallback 错误结构
  - 未知 agent_type → 错误结构
  - 模型成功返回 → 统一 AgentResult.ok=True 且 data 为解析后的 dict
  - 模型解析失败/异常 → fallback 降级
"""

import asyncio
import sys
from typing import Any, Dict, List, Optional

from app.agents.prompts import AGENT_REGISTRY, AGENT_TASKS, AgentSpec
from app.services.agent_service import (
    AgentInput,
    AgentResult,
    AgentService,
    build_user_prompt,
)
from app.services.llm import LLMResponseError

EXPECTED_AGENTS = {
    "orchestrator",
    "career",
    "skill",
    "learning",
    "tutor",
    "assessment",
    "coach",
    "reflection",
}

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -> {detail}")


class _FakeLLM:
    """替身：模拟 LLMService 的调用面（is_configured / chat_json）。"""

    def __init__(
        self,
        configured: bool = True,
        result: Optional[Dict[str, Any]] = None,
        exc: Optional[Exception] = None,
    ) -> None:
        self._configured = configured
        self.result = result if result is not None else {}
        self.exc = exc
        self.calls: List[Dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_hint: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema_hint": schema_hint,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.exc is not None:
            raise self.exc
        return self.result


def _run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------- #
print("== 1. Agent 注册表 ==")
check("注册表含 8 个 Agent", set(AGENT_REGISTRY) == EXPECTED_AGENTS, str(set(AGENT_REGISTRY)))
for name, spec in AGENT_REGISTRY.items():
    ok = (
        isinstance(spec, AgentSpec)
        and bool(spec.system_prompt)
        and bool(spec.json_schema)
        and bool(spec.description)
        and 0 < spec.default_temperature <= 1.0
        and spec.default_max_tokens > 0
    )
    check(f"spec[{name}] 配置齐全", ok, f"system={len(spec.system_prompt)} schema={len(spec.json_schema)} desc={spec.description}")
check("AGENT_TASKS 覆盖全部 Agent", set(AGENT_TASKS) == EXPECTED_AGENTS, str(set(AGENT_TASKS)))

svc = AgentService()
check("available_agents 返回 8 项", len(svc.available_agents()) == 8)
names = {a["name"] for a in svc.available_agents()}
check("available_agents 含全部 agent", names == EXPECTED_AGENTS, str(names))

# ------------------------------------------------------------------- #
print("== 2. user_prompt 拼装与裁剪 ==")
spec = AGENT_REGISTRY["tutor"]
inp = AgentInput(
    agent_type="tutor",
    user_context={"name": "张三", "level": 2, "target_job": "AI 应用开发工程师"},
    retrieved_docs=[
        {"doc_title": "机器学习基础", "chunk_id": 1, "content": "有害" * 400},
        {"doc_title": "排序算法", "chunk_id": 2, "content": "二分查找"},
    ],
    history=[
        {"role": "user", "content": f"问题{i}"} for i in range(8)
    ],
)
prompt = build_user_prompt(spec, inp)
check("user_prompt 含任务指令", AGENT_TASKS["tutor"] in prompt)
check("user_prompt 含用户上下文", "AI 应用开发工程师" in prompt)
check("user_prompt 含检索资料", "机器学习基础" in prompt)
check("user_prompt 含对话历史", "问题7" in prompt)
check("历史裁剪只保留最近6条", "问题0" not in prompt and "问题1" not in prompt, "问题0/1 应被裁掉")
check("文档正文超长已截断", "…(已截断)" in prompt or "...(已截断)" in prompt)

# ------------------------------------------------------------------- #
print("== 3. 未配置大模型：降级行为 ==")
off = AgentService(_FakeLLM(configured=False))
r = _run(off.run({"agent_type": "career", "user_context": {"scores": {"logic": 80}}}))
check("未配置→degraded=True", r.degraded is True, r.model_dump_json())
check("未配置无 fallback→ok=False", r.ok is False)
check("未配置→error 含提示", "未配置" in r.error, r.error)

r2 = _run(off.run({
    "agent_type": "career",
    "user_context": {"scores": {"logic": 80}},
    "fallback": {"persona_summary": "规则画像", "tags": ["逻辑缜密型"]},
}))
check("有 fallback→ok=True", r2.ok is True and r2.data["persona_summary"] == "规则画像")
check("有 fallback→degraded=True", r2.degraded is True)
check("fallback note 说明来源", r2.note != "")

# ------------------------------------------------------------------- #
print("== 4. 未知 agent_type ==")
r3 = _run(svc.run(AgentInput(agent_type="time_machine", user_context={})))
check("未知 agent→ok=False", r3.ok is False and "未注册" in r3.error)
check("未知 agent→degraded=True", r3.degraded is True)

# ------------------------------------------------------------------- #
print("== 5. 模型成功返回：JSON 解析与参数透传 ==")
fake = _FakeLLM(result={"intent": "learning", "confidence": 0.9, "target_agent": "Learning Agent"})
ok_svc = AgentService(fake)
r4 = _run(ok_svc.run(AgentInput(
    agent_type="orchestrator",
    user_context={"question": "我想学机器学习"},
)))
check("成功→ok=True", r4.ok is True)
check("成功→data 为模型 JSON", r4.data["intent"] == "learning")
check("成功→degraded=False", r4.degraded is False and r4.error == "")
call = fake.calls[0]
check("传参：system_prompt=Agent 系统提示词", call["system_prompt"] == AGENT_REGISTRY["orchestrator"].system_prompt)
check("传参：schema_hint=Agent JSON Schema", call["schema_hint"].startswith("{"))
check("传参：默认温度取 spec 默认值", call["temperature"] == AGENT_REGISTRY["orchestrator"].default_temperature)
check("传参：user_prompt 含任务", AGENT_TASKS["orchestrator"] in call["user_prompt"])

# 自定义温度/最大 token 覆盖默认
r4b = _run(ok_svc.run(AgentInput(
    agent_type="learning",
    user_context={"goal": "算法"},
    temperature=0.5,
    max_tokens=512,
)))
call2 = fake.calls[1]
check("自定义温度/maxtokens 生效", call2["temperature"] == 0.5 and call2["max_tokens"] == 512)

# ------------------------------------------------------------------- #
print("== 6. 模型失败：fallback 降级与错误结构 ==")
err_svc = AgentService(_FakeLLM(configured=True, exc=LLMResponseError("模型返回非 JSON")))
r5 = _run(err_svc.run({
    "agent_type": "assessment",
    "user_context": {"score": 80},
    "fallback": {"summary": "规则报告"},
}))
check("模型失败+fallback→ok=True", r5.ok is True and r5.data["summary"] == "规则报告")
check("模型失败→degraded=True", r5.degraded is True)
check("模型失败→error 原因", "非 JSON" in r5.error or "LLMResponseError" in r5.error, r5.error)

err_svc2 = AgentService(_FakeLLM(configured=True, exc=ValueError("连接超时")))
r6 = _run(err_svc2.run({"agent_type": "coach", "user_context": {"streak": 3}}))
check("任意异常→degraded 错误结构", r6.ok is False and r6.degraded is True and "超时" in r6.error, r6.model_dump_json())

# ------------------------------------------------------------------- #
print()
print(f"AgentService 单测: PASS={PASS} FAIL={FAIL}")
raise SystemExit(1 if FAIL else 0)