"""检查意图解析与格式化。

本模块支持“方案 2”的交互体验：
- 医生可以在聊天中通过自然语言下检查单
- 系统会自动创建 TestRequest 记录并返回检查报告

我们有意保持实现轻量（正则/关键词），以确保确定性与可审计性。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TestIntent:
    kind: str  # "order"（下检查）| "result"（要结果）
    test_types: list[str]


_ORDER_VERBS = (
    "做",
    "查",
    "开",
    "申请",
    "安排",
    "先做",
    "去做",
    "做个",
    "做一下",
    "查一下",
)

_RESULT_WORDS = ("结果", "报告", "片子")


def extract_test_intent(message: str, available_test_types: set[str]) -> TestIntent | None:
    """从医生消息中提取检查相关意图。

    Args:
        message: 原始用户消息
        available_test_types: 当前病例允许的 test_type 集合

    Returns:
        TestIntent 或 None
    """
    text = (message or "").strip()
    if not text:
        return None

    normalized = text.lower()

    # 关键词映射（中英文变体） -> 标准 test_type。
    keyword_to_type: list[tuple[str, str]] = [
        ("血常规", "blood_routine"),
        ("血常", "blood_routine"),
        ("尿常规", "urine_routine"),
        ("尿常", "urine_routine"),
        ("心电", "ecg"),
        ("ecg", "ecg"),
        ("超声", "ultrasound"),
        ("b超", "ultrasound"),
        ("b 超", "ultrasound"),
        ("x光", "x_ray"),
        ("x-ray", "x_ray"),
        ("x ray", "x_ray"),
        ("胸片", "x_ray"),
        ("ct", "ct"),
    ]

    matched: list[str] = []
    for kw, test_type in keyword_to_type:
        if kw in normalized and test_type in available_test_types and test_type not in matched:
            matched.append(test_type)

    if not matched:
        return None

    # 启发式判断：要结果 vs 下检查。
    wants_result = any(w in text for w in _RESULT_WORDS)

    if wants_result:
        return TestIntent(kind="result", test_types=matched)

    # 下检查：需要有“动词”信号，避免误触发。
    if any(v in text for v in _ORDER_VERBS) or re.search(
        r"(做|查).{0,6}(ct|血常规|尿常规|心电|超声|胸片|x光)", text, re.IGNORECASE
    ):
        return TestIntent(kind="order", test_types=matched)

    return None


def format_test_result_text(test_name: str, result: dict) -> str:
    """将检查结果字典格式化为可读文本块。"""
    if not result:
        return f"[检查结果] {test_name}: 无异常"

    # 嵌套结构优先以可读形式输出。
    lines: list[str] = []
    for key, value in result.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")

    joined = "\n".join(lines)
    return f"[检查结果] {test_name}:\n{joined}"
