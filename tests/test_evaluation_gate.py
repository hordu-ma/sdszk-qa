"""WP2.4 内部评测回归门禁的纯函数测试。

阈值口径见《内部阈值标定报告 v0》§5；门禁只约束工程晋级，
不产生任何教师/学生评价（见 test_no_scoring_paths 的全局防护）。
"""

from types import SimpleNamespace
from typing import cast

from src.apps.api.models import EvaluationCase, EvaluationCaseResult
from src.apps.api.services.evaluation_gate_service import (
    GATE_DISCLAIMER,
    case_status_changes,
    compute_gate_metrics,
    evaluate_gate,
    flatten_manifest,
    manifest_changes,
)


def _case(
    case_id: int, key: str, expected_ids: list[int], insufficient: bool = False
) -> EvaluationCase:
    return cast(
        "EvaluationCase",
        SimpleNamespace(
            id=case_id,
            case_key=key,
            expected_document_ids=expected_ids,
            expected_insufficient_basis=insufficient,
        ),
    )


def _result(
    case_id: int,
    status: str,
    returned_ids: list[int] | None = None,
    insufficient: bool = False,
) -> EvaluationCaseResult:
    return cast(
        "EvaluationCaseResult",
        SimpleNamespace(
            case_id=case_id,
            status=status,
            returned_document_ids=returned_ids or [],
            insufficient_basis=insufficient,
        ),
    )


MANIFEST_V1 = {
    "application_release": "r1",
    "models": [
        {"asset_type": "generation", "revision": "aaa"},
        {"asset_type": "embedding", "revision": "bbb"},
    ],
    "retrieval": {"lexical_weight": 0.7, "vector_weight": 0.3},
    "skills": {"skill.retrieve_basis": "1.2.0"},
}


def test_flatten_manifest_uses_asset_type_as_stable_key() -> None:
    flat = flatten_manifest(MANIFEST_V1)
    assert flat["models[generation].revision"] == "aaa"
    assert flat["retrieval.lexical_weight"] == 0.7
    assert flat["skills.skill.retrieve_basis"] == "1.2.0"


def test_manifest_changes_detects_revision_and_skill_version() -> None:
    current = {
        **MANIFEST_V1,
        "models": [
            {"asset_type": "generation", "revision": "aaa"},
            {"asset_type": "embedding", "revision": "ccc"},
        ],
        "skills": {"skill.retrieve_basis": "1.3.0"},
    }
    changes = {item["path"]: item for item in manifest_changes(MANIFEST_V1, current)}
    assert changes["models[embedding].revision"]["baseline"] == "bbb"
    assert changes["models[embedding].revision"]["current"] == "ccc"
    assert changes["skills.skill.retrieve_basis"]["current"] == "1.3.0"
    assert "models[generation].revision" not in changes


def test_manifest_changes_ignores_model_list_order() -> None:
    reordered = {
        **MANIFEST_V1,
        "models": list(reversed(MANIFEST_V1["models"])),
    }
    assert manifest_changes(MANIFEST_V1, reordered) == []


def test_compute_gate_metrics_top1_and_insufficient_miss() -> None:
    cases = [
        _case(1, "c1", [10]),
        _case(2, "c2", [20]),
        _case(3, "c3", [], insufficient=True),
        _case(4, "c4", [], insufficient=True),
    ]
    results = [
        _result(1, "matched", [10, 11]),
        _result(2, "matched", [99, 20]),  # 命中但非 top1
        _result(3, "matched", [], insufficient=True),
        _result(4, "failed", [30], insufficient=False),  # 域外查询未判资料不足
    ]
    metrics = compute_gate_metrics(cases, results)
    assert metrics["total_cases"] == 4
    assert metrics["matched_cases"] == 3
    assert metrics["match_rate"] == 0.75
    assert metrics["top1_total"] == 2
    assert metrics["top1_hits"] == 1
    assert metrics["top1_hit_rate"] == 0.5
    assert metrics["insufficient_basis_misses"] == 1
    assert metrics["error_cases"] == 0


def test_evaluate_gate_passes_at_internal_thresholds() -> None:
    metrics = {
        "total_cases": 140,
        "matched_cases": 140,
        "error_cases": 0,
        "match_rate": 1.0,
        "top1_total": 120,
        "top1_hits": 120,
        "top1_hit_rate": 1.0,
        "insufficient_basis_misses": 0,
    }
    checks, passed = evaluate_gate(metrics, min_match_rate=0.95, min_top1_hit_rate=0.90)
    assert passed
    assert {item["check"] for item in checks} == {
        "match_rate",
        "top1_hit_rate",
        "insufficient_basis_misses",
        "error_cases",
    }


def test_evaluate_gate_blocks_on_each_threshold() -> None:
    base = {
        "total_cases": 100,
        "matched_cases": 100,
        "error_cases": 0,
        "match_rate": 1.0,
        "top1_total": 80,
        "top1_hits": 80,
        "top1_hit_rate": 1.0,
        "insufficient_basis_misses": 0,
    }
    for overrides in (
        {"match_rate": 0.94},
        {"top1_hit_rate": 0.89},
        {"insufficient_basis_misses": 1},
        {"error_cases": 1},
    ):
        _, passed = evaluate_gate(
            {**base, **overrides}, min_match_rate=0.95, min_top1_hit_rate=0.90
        )
        assert not passed, overrides


def test_evaluate_gate_top1_not_applicable_when_no_expected_documents() -> None:
    metrics = {
        "total_cases": 20,
        "matched_cases": 20,
        "error_cases": 0,
        "match_rate": 1.0,
        "top1_total": 0,
        "top1_hits": 0,
        "top1_hit_rate": None,
        "insufficient_basis_misses": 0,
    }
    checks, passed = evaluate_gate(metrics, min_match_rate=0.95, min_top1_hit_rate=0.90)
    assert passed
    top1 = next(item for item in checks if item["check"] == "top1_hit_rate")
    assert top1["observed"] is None
    assert top1["passed"]


def test_case_status_changes_classifies_by_case_key() -> None:
    cases = [_case(1, "c1", [1]), _case(2, "c2", [2]), _case(3, "c3", [3]), _case(4, "c4", [4])]
    baseline = [
        _result(1, "matched"),
        _result(2, "failed"),
        _result(3, "failed"),
        _result(4, "matched"),
    ]
    current = [
        _result(1, "failed"),
        _result(2, "matched"),
        _result(3, "error"),
        _result(4, "matched"),
    ]
    changes = case_status_changes(cases, baseline, current)
    assert changes == {
        "regressed_case_keys": ["c1"],
        "improved_case_keys": ["c2"],
        "still_failed_case_keys": ["c3"],
    }


def test_gate_disclaimer_states_internal_engineering_scope() -> None:
    assert "内部" in GATE_DISCLAIMER
    assert "不代表专家验收" in GATE_DISCLAIMER
