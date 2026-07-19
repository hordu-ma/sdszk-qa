"""诊断规则字典 v2 的行为与非评分防护测试（自助开发优先级 §0.5-4）。

覆盖：默认三维规则的达标/需关注判定、blocking 汇总、可扩展注册，
以及评分/排名标识符和重复注册的防护拦截（对齐开发计划 §16.1）。
"""

from __future__ import annotations

import pytest

from src.apps.api.services.diagnostic_rules import (
    RULE_STATUS_ALIGNED,
    RULE_STATUS_ATTENTION,
    DiagnosticRule,
    diagnostic_rules,
    evaluate_diagnostic_rules,
    register_diagnostic_rule,
)

_ALIGNED_SECTIONS = {
    "alignment_card": {"citations": [{"filename": "课程标准.md"}]},
    "design_blueprint": {"objectives": ["目标"], "evidence": ["观察证据"]},
    "lesson_design": {"activities": [{"title": "讨论"}]},
}


def test_default_dictionary_covers_three_engineering_dimensions() -> None:
    dimensions = [rule.dimension for rule in diagnostic_rules()]
    assert dimensions == ["依据可追溯", "目标—证据一致", "任务可实施"]


def test_all_aligned_produces_no_blocking() -> None:
    items, blocking = evaluate_diagnostic_rules(_ALIGNED_SECTIONS)

    assert blocking == []
    assert [item.status for item in items] == [RULE_STATUS_ALIGNED] * 3
    assert items[0].evidence == "引用片段 1 条"
    assert items[1].evidence == "目标 1 项 / 证据 1 项"
    assert items[2].evidence == "课时活动 1 个"


def test_missing_evidence_flags_needs_attention_and_blocks() -> None:
    sections = {
        "alignment_card": {"citations": []},
        "design_blueprint": {"objectives": ["目标"], "evidence": []},
        "lesson_design": {},
    }
    items, blocking = evaluate_diagnostic_rules(sections)

    assert [item.status for item in items] == [RULE_STATUS_ATTENTION] * 3
    assert blocking == ["依据可追溯", "目标—证据一致", "任务可实施"]
    assert items[0].suggestion == "补充并审核权威资料后重新运行对齐卡"


def test_status_domain_is_binary_never_a_score() -> None:
    items, _ = evaluate_diagnostic_rules(_ALIGNED_SECTIONS)
    for item in items:
        assert item.status in {RULE_STATUS_ALIGNED, RULE_STATUS_ATTENTION}


def test_registry_rejects_scoring_rule_identifiers() -> None:
    with pytest.raises(ValueError, match="评分/排名"):
        register_diagnostic_rule(
            DiagnosticRule(
                rule_id="teacher_scoring",
                dimension="非法评分维度",
                section="alignment_card",
                source_path="alignment_card",
                rule_basis="非法",
                impact="非法",
                example_revision="非法",
                revision_target_path="lesson_design.teacher_notes",
                predicate=lambda section: True,
                evidence=lambda section: "",
                aligned_suggestion="",
                attention_suggestion="",
            )
        )
    assert "teacher_scoring" not in {rule.rule_id for rule in diagnostic_rules()}


def test_registry_rejects_duplicate_rule() -> None:
    with pytest.raises(ValueError, match="重复注册"):
        register_diagnostic_rule(
            DiagnosticRule(
                rule_id="basis_traceability",
                dimension="依据可追溯",
                section="alignment_card",
                source_path="alignment_card",
                rule_basis="重复",
                impact="重复",
                example_revision="重复",
                revision_target_path="lesson_design.teacher_notes",
                predicate=lambda section: True,
                evidence=lambda section: "",
                aligned_suggestion="",
                attention_suggestion="",
            )
        )


def test_non_blocking_rule_reports_without_blocking() -> None:
    rule = DiagnosticRule(
        rule_id="optional_reflection_note",
        dimension="课后反思提示",
        section="lesson_design",
        source_path="lesson_design.teacher_notes",
        rule_basis="教学反思应记录可观察调整",
        impact="缺少记录会影响后续复盘",
        example_revision="记录本课调整及原因。",
        revision_target_path="lesson_design.teacher_notes",
        predicate=lambda section: bool(section.get("teacher_notes")),
        evidence=lambda section: "反思提示待补充",
        aligned_suggestion="保持课后反思记录",
        attention_suggestion="补充课后反思要点",
        blocking=False,
    )
    item = rule.evaluate({"lesson_design": {}})

    assert item.status == RULE_STATUS_ATTENTION
    assert item.dimension == "课后反思提示"
