"""WP2.4 第二增量纯函数测试：抽检状态机与 L4 信号汇总。"""

from src.apps.api.services.signal_summary_service import (
    L4_SUMMARY_DISCLAIMER,
    summarize_l4_signals,
)
from src.apps.api.services.spot_check_service import (
    SPOT_CHECK_DISCLAIMER,
    next_item_status,
    review_signature,
)


def test_review_signature_normalizes_tag_order_and_duplicates() -> None:
    left = review_signature("needs_adjustment", ["evidence_gap", "citation_missing"])
    right = review_signature(
        "needs_adjustment", ["citation_missing", "evidence_gap", "citation_missing"]
    )
    assert left == right
    assert left != review_signature("confirmed", ["citation_missing", "evidence_gap"])


def test_next_item_status_follows_gold_review_state_machine() -> None:
    first = review_signature("confirmed", [])
    same = review_signature("confirmed", [])
    different = review_signature("needs_adjustment", ["evidence_gap"])
    assert (
        next_item_status(
            independent_signatures=[], new_signature=first, review_kind="independent"
        )
        == "single_review"
    )
    assert (
        next_item_status(
            independent_signatures=[first], new_signature=same, review_kind="independent"
        )
        == "consensus"
    )
    assert (
        next_item_status(
            independent_signatures=[first],
            new_signature=different,
            review_kind="independent",
        )
        == "disputed"
    )
    assert (
        next_item_status(
            independent_signatures=[first, different],
            new_signature=same,
            review_kind="arbitration",
        )
        == "arbitrated"
    )


def test_summarize_l4_signals_groups_by_rule_dimension() -> None:
    contents = [
        {
            "diagnosis_signals": [
                {"item_id": "basis_traceability", "action": "accept"},
                {"item_id": "basis_traceability", "action": "ignore"},
                {"item_id": "objective_evidence_alignment", "action": "edit"},
            ]
        },
        {
            "diagnosis_signals": [
                {"item_id": "basis_traceability", "action": "accept"},
                {"item_id": "task_feasibility", "action": "request_expert"},
            ]
        },
    ]
    summary = summarize_l4_signals(contents)
    assert summary["signal_level"] == "L4"
    assert summary["authorized_for_training"] is False
    assert summary["disclaimer"] == L4_SUMMARY_DISCLAIMER
    assert summary["total_signals"] == 5
    by_dimension = {row["dimension"]: row for row in summary["dimensions"]}
    assert set(by_dimension) == {"依据可追溯", "目标—证据一致", "任务可实施"}
    basis = by_dimension["依据可追溯"]
    assert basis["total_signals"] == 3
    assert basis["actions"] == {
        "accept": 2,
        "ignore": 1,
        "edit": 0,
        "request_expert": 0,
    }
    assert basis["rules"] == [
        {
            "rule_id": "basis_traceability",
            "total_signals": 3,
            "actions": {"accept": 2, "ignore": 1, "edit": 0, "request_expert": 0},
        }
    ]


def test_summarize_l4_signals_uses_content_dimension_for_unregistered_rules() -> None:
    contents = [
        {
            "diagnosis": {
                "items": [
                    {"item_id": "future_rule", "dimension": "分学段量规候选"},
                ]
            },
            "diagnosis_signals": [
                {"item_id": "future_rule", "action": "accept"},
                {"item_id": "totally_unknown", "action": "ignore"},
            ],
        }
    ]
    summary = summarize_l4_signals(contents)
    by_dimension = {row["dimension"]: row for row in summary["dimensions"]}
    assert by_dimension["分学段量规候选"]["total_signals"] == 1
    assert by_dimension["未登记维度"]["total_signals"] == 1


def test_summarize_l4_signals_skips_malformed_entries() -> None:
    contents = [
        {"diagnosis_signals": "not-a-list"},
        {
            "diagnosis_signals": [
                "not-a-dict",
                {"item_id": 42, "action": "accept"},
                {"item_id": "basis_traceability", "action": "unknown_action"},
            ]
        },
        {},
    ]
    summary = summarize_l4_signals(contents)
    assert summary["total_signals"] == 0
    assert summary["dimensions"] == []


def test_disclaimers_state_internal_engineering_and_training_ban() -> None:
    assert "L4" in SPOT_CHECK_DISCLAIMER
    assert "authorized_for_training=false" in SPOT_CHECK_DISCLAIMER
    assert "不代表专家验收" in SPOT_CHECK_DISCLAIMER
    assert "不得进入训练" in L4_SUMMARY_DISCLAIMER
