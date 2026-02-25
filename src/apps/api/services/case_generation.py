"""随机主题生成服务。

通过已配置的 LLM 生成完整的 Case 载荷（沿用历史字段，语义迁移到思政教学场景）。
本模块保持与现有 Case 模型字段对齐，以降低迁移成本。
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any

import httpx

from src.apps.api.config import settings
from src.apps.api.exceptions import BusinessError

CASE_GENERATION_PROMPT_VERSION = "3.0-sizheng"

# 思政教学主题池（序号 1-N）
TOPIC_LIST: dict[int, str] = {
    1: "习近平新时代中国特色社会主义思想进课堂路径设计",
    2: "大中小学思政课一体化目标衔接",
    3: "家国情怀主题单元教学设计",
    4: "中华优秀传统文化融入思政课",
    5: "红色资源校本化开发",
    6: "思政课议题式教学流程设计",
    7: "课程思政与学科思政协同机制",
    8: "思政课课堂讨论的组织与评价",
    9: "思政课项目化学习设计",
    10: "思政课实践教学与社会调查组织",
    11: "法治教育主题课堂活动设计",
    12: "国家安全教育进课堂实施方案",
    13: "劳动教育与思政课融合设计",
    14: "生态文明教育主题课堂设计",
    15: "铸牢中华民族共同体意识教学设计",
    16: "青年价值观引导案例教学",
    17: "网络时代思政课媒介素养教育",
    18: "思政课教学难点突破策略",
    19: "思政课同课异构教研方案",
    20: "思政课课堂观察量表设计",
}


def _extract_json(text: str) -> str:
    """从 LLM 输出中提取 JSON 对象。"""

    s = (text or "").strip()
    if not s:
        return s

    if s.startswith("```"):
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1].strip()
    return s


def _estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    """粗略估算 OpenAI 风格消息的 token 数。"""

    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for m in messages:
            total += len(enc.encode(str(m.get("content", ""))))
            total += 4
        return total
    except Exception:
        total = 0
        for m in messages:
            content = str(m.get("content", ""))
            total += max(1, len(content) // 2)
            total += 4
        return total


def _build_generation_messages(topic_name: str, case_number: int) -> list[dict[str, str]]:
    system = (
        "你是思政课教学主题生成器。请基于指定主题生成一个可用于问答辅助的结构化主题卡片，"
        "并严格输出 JSON（不能包含额外文本、Markdown、注释）。\n\n"
        "输出必须包含以下字段（与历史系统字段兼容）：\n"
        "- title, difficulty, department\n"
        "- patient_info{age,gender,occupation}\n"
        "- chief_complaint, present_illness\n"
        "- past_history{diseases[],allergies[],medications[]}\n"
        "- marriage_childbearing_history (字符串)\n"
        "- family_history (字符串)\n"
        "- physical_exam{visible{},on_request{}}\n"
        "- available_tests[]\n"
        "- standard_diagnosis{primary,differential[]}\n"
        "- key_points[]\n"
        "- recommended_tests[]\n\n"
        "语义要求（思政场景）：\n"
        "1) title 为思政教学主题标题，department 写学段（小学/初中/高中/大学）。\n"
        "2) chief_complaint 写用户核心诉求；present_illness 写应用场景与约束。\n"
        "3) standard_diagnosis.primary 写推荐教学方案主方向；differential 写可选思路。\n"
        "4) key_points 至少 5 项，且均为可执行教学要点。\n"
        "5) available_tests/recommended_tests 可为空数组，不要编造医学内容。\n"
        "6) difficulty 仅可为 easy/medium/hard。\n"
        "7) 输出必须是可解析的严格 JSON。"
    )
    user = (
        f"请围绕主题『{topic_name}』（主题序号 {case_number}）生成一份结构化主题卡片。"
        "重点体现教学设计与教研支持价值。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """对 LLM 返回进行最小归一化，保证下游可落库。"""

    if not isinstance(payload.get("past_history"), dict):
        payload["past_history"] = {"diseases": [], "allergies": [], "medications": []}

    if not isinstance(payload.get("physical_exam"), dict):
        payload["physical_exam"] = {"visible": {}, "on_request": {}}
    else:
        payload["physical_exam"].setdefault("visible", {})
        payload["physical_exam"].setdefault("on_request", {})

    if not isinstance(payload.get("available_tests"), list):
        payload["available_tests"] = []

    if not isinstance(payload.get("recommended_tests"), list):
        payload["recommended_tests"] = []

    if "marriage_childbearing_history" not in payload:
        payload["marriage_childbearing_history"] = "未提供"
    if "family_history" not in payload:
        payload["family_history"] = "未提供"

    return payload


async def generate_random_case_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    """通过 LLM 生成随机主题载荷（沿用函数名以兼容现有调用）。"""

    case_number = random.randint(1, len(TOPIC_LIST))
    topic_name = TOPIC_LIST[case_number]
    messages = _build_generation_messages(topic_name, case_number)
    start = datetime.utcnow()

    prompt_tokens = _estimate_prompt_tokens(messages)
    available_tokens = max(0, settings.LLM_MAX_CONTEXT_LEN - prompt_tokens)
    max_tokens = max(16, min(settings.LLM_CASE_GEN_MAX_TOKENS, available_tokens))

    last_err: Exception | None = None
    payload: dict[str, Any] | None = None

    for _attempt in range(settings.LLM_CASE_GEN_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/v1/chat/completions",
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": messages,
                        "stream": False,
                        "temperature": settings.LLM_CASE_GEN_TEMPERATURE,
                        "max_tokens": max_tokens,
                        "response_format": {"type": "json_object"},
                    },
                )
        except httpx.TimeoutException as e:
            last_err = e
            continue
        except httpx.RequestError as e:
            last_err = e
            continue

        if resp.status_code != 200:
            last_err = BusinessError(
                f"LLM 生成主题失败: HTTP {resp.status_code}",
                status_code=502,
            )
            continue

        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            last_err = BusinessError("LLM 返回为空，无法生成主题", status_code=502)
            continue

        try:
            payload = json.loads(_extract_json(content))
            payload = _normalize_payload(payload)
        except json.JSONDecodeError as e:
            last_err = e
            continue

        break

    if payload is None:
        if isinstance(last_err, BusinessError):
            raise last_err
        if isinstance(last_err, httpx.TimeoutException):
            raise BusinessError("LLM 生成主题超时", status_code=504) from last_err
        if isinstance(last_err, httpx.RequestError):
            raise BusinessError(f"LLM 连接失败: {str(last_err)}", status_code=502) from last_err
        if isinstance(last_err, json.JSONDecodeError):
            raise BusinessError("LLM 返回不是合法 JSON，无法生成主题", status_code=502) from last_err
        raise BusinessError("LLM 生成主题失败", status_code=502) from last_err

    payload["case_number"] = case_number

    generation_meta = {
        "generated_at": start.isoformat() + "Z",
        "prompt_version": CASE_GENERATION_PROMPT_VERSION,
        "model": settings.LLM_MODEL,
        "temperature": settings.LLM_CASE_GEN_TEMPERATURE,
        "max_tokens": settings.LLM_CASE_GEN_MAX_TOKENS,
        "retries": settings.LLM_CASE_GEN_RETRIES,
        "case_number": case_number,
        "topic_name": topic_name,
    }
    return payload, generation_meta
