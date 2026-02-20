"""检查意图解析回归测试。"""

from src.apps.api.services.test_intents import extract_test_intent, format_test_result_text


AVAILABLE_TEST_TYPES = {"blood_routine", "x_ray", "ct"}


def test_extract_test_intent_detects_order_intent() -> None:
    intent = extract_test_intent("先做个血常规，再拍个胸片", AVAILABLE_TEST_TYPES)

    assert intent is not None
    assert intent.kind == "order"
    assert intent.test_types == ["blood_routine", "x_ray"]


def test_extract_test_intent_detects_result_intent() -> None:
    intent = extract_test_intent("把血常规结果给我看下", AVAILABLE_TEST_TYPES)

    assert intent is not None
    assert intent.kind == "result"
    assert intent.test_types == ["blood_routine"]


def test_extract_test_intent_returns_none_when_no_action_verb() -> None:
    intent = extract_test_intent("我担心肺部感染，ct能看出来吗", AVAILABLE_TEST_TYPES)

    assert intent is None


def test_format_test_result_text_handles_empty_result() -> None:
    text = format_test_result_text("血常规", {})

    assert text == "[检查结果] 血常规: 无异常"
