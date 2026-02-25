from src.apps.api.models import Case, Message
from src.apps.api.routes.chat import (
    SYSTEM_PROMPT,
    build_developer_prompt,
    build_messages,
    estimate_prompt_tokens,
)


def _build_case() -> Case:
    return Case(
        title="新时代思政课堂设计",
        difficulty="medium",
        department="高中",
        context_info={"teacher_role": "思政教师", "grade": "高二", "class_size": 50},
        core_question="围绕家国情怀开展课堂活动设计",
        scenario_text="希望形成可落地的45分钟教学流程",
        supplementary_info={
            "existing_issues": [],
            "constraints": ["班额50人"],
            "available_resources": [],
        },
        reference_answer={"primary": "目标明确、活动闭环、评价可执行"},
        key_points=["教学目标", "教学活动", "教学评价"],
        is_active=True,
        source="fixed",
        generation_meta=None,
    )


def test_build_developer_prompt_contains_case_info() -> None:
    case = _build_case()
    prompt = build_developer_prompt(case)

    assert "新时代思政课堂设计" in prompt
    assert "45分钟" in prompt
    assert "班额50人" in prompt


def test_build_messages_includes_system_prompt() -> None:
    case = _build_case()
    history = [
        Message(session_id=1, role="user", content="请给一个教学目标模板"),
        Message(session_id=1, role="assistant", content="可以按三维目标来写。"),
    ]
    messages = build_messages(case, history, "请补一个课堂评价方法")

    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "请补一个课堂评价方法"


def test_system_prompt_matches_sizheng_role() -> None:
    assert "鲁韵思政" in SYSTEM_PROMPT


def test_estimate_prompt_tokens_is_positive() -> None:
    case = _build_case()
    messages = build_messages(case, [], "你好")
    tokens = estimate_prompt_tokens(messages)

    assert tokens > 0
