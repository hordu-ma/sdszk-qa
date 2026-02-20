from src.apps.api.models import Case, Message
from src.apps.api.routes.chat import (
    SYSTEM_PROMPT,
    build_developer_prompt,
    build_messages,
    estimate_prompt_tokens,
)


def _build_case() -> Case:
    return Case(
        title="高血压伴头晕",
        difficulty="medium",
        department="心内科",
        patient_info={"age": 56, "gender": "male", "occupation": "司机"},
        chief_complaint="头晕 1 周",
        present_illness="近一周反复头晕，无恶心呕吐",
        past_history={"diseases": ["高血压"], "allergies": [], "medications": []},
        physical_exam={
            "visible": {"blood_pressure": "165/105 mmHg"},
            "on_request": {"fundus": "眼底动脉硬化"},
        },
        available_tests=[{"type": "blood_routine", "name": "血常规"}],
        standard_diagnosis={"primary": "高血压病 2 级（很高危）", "differential": []},
        key_points=["头晕、头痛症状及特点"],
        recommended_tests=["blood_routine"],
        is_active=True,
        source="fixed",
        generation_meta=None,
    )


def test_build_developer_prompt_contains_case_info() -> None:
    case = _build_case()
    prompt = build_developer_prompt(case)

    assert "头晕 1 周" in prompt
    assert "165/105 mmHg" in prompt
    assert "眼底动脉硬化" in prompt


def test_build_messages_includes_system_prompt() -> None:
    case = _build_case()
    history = [
        Message(session_id=1, role="user", content="请问头晕多久了？"),
        Message(session_id=1, role="assistant", content="大约一周左右。"),
    ]
    messages = build_messages(case, history, "还有没有胸闷？")

    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "还有没有胸闷？"


def test_estimate_prompt_tokens_is_positive() -> None:
    case = _build_case()
    messages = build_messages(case, [], "你好")
    tokens = estimate_prompt_tokens(messages)

    assert tokens > 0
