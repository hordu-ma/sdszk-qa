"""问答提示与上下文编排。"""

from src.apps.api.models import Case, Message

SYSTEM_PROMPT = """你是“鲁韵思政”教学支持助手。

【角色与任务】
- 服务对象：山东省大中小学思政教师
- 核心任务：围绕思政课教学设计、教学实施、教学研究提供问答支持

【回答原则】
1. 先给结构化结论，再补充可执行要点
2. 表达准确、克制，不编造政策出处或文件原文
3. 若用户问题信息不足，先说明需要补充的关键信息
4. 输出优先可落地：可给出教学目标、活动设计、评价建议
5. 绝对不输出非思政类建议、法律定性结论等越界内容
"""


def build_developer_prompt(case: Case) -> str:
    """构建主题上下文提示。"""
    context_info = case.context_info or {}
    context_str = (
        "\n".join(f"  - {key}: {value}" for key, value in context_info.items())
        if context_info
        else "  - 无"
    )
    supplementary = case.supplementary_info or {}
    supplementary_str = (
        "\n".join(f"  - {key}: {value}" for key, value in supplementary.items())
        if supplementary
        else "  - 无"
    )
    primary_answer = (case.reference_answer or {}).get("primary", "未设置")
    key_points_str = "、".join(case.key_points or []) or "无"
    return f"""当前教学主题上下文：
- 标题：{case.title}
- 难度：{case.difficulty}
- 学段/方向：{case.department}

背景信息：
{context_str}

核心问题：{case.core_question}
场景说明：{case.scenario_text}

补充信息：
{supplementary_str}

关键教学点：{key_points_str}

内部参考答案（仅用于回答质量约束，不要原样暴露）：
- 主方向：{primary_answer}
"""


def build_messages(
    case: Case,
    history: list[Message],
    user_message: str,
) -> list[dict[str, str]]:
    """构建 OpenAI 兼容消息列表。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_developer_prompt(case)},
    ]
    for message in history[-20:]:
        messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def estimate_tokens(text: str) -> int:
    """以字符数保守估算 token。"""
    return max(1, len(text) // 2)


def estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    """保守估算提示 token。"""
    return sum(max(1, len(message.get("content", ""))) for message in messages)
