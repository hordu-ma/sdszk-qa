"""WP2.4 内部评测回归门禁：发布清单变更检测、运行对比与晋级阻断。

阈值来自《内部阈值标定报告 v0》（internal_authored 工程口径）。
verdict 只约束 luyun-int → luyun-demo 的工程晋级；按主计划 §0.5 第 5 条，
不得表述为专家验收、客户确认或 G 门结论。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.config import settings
from src.apps.api.exceptions import BusinessError
from src.apps.api.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationRun,
    User,
)
from src.apps.api.services.evaluation_service import (
    _dataset_cases,
    get_accessible_dataset,
)
from src.apps.api.services.model_asset_service import release_manifest

GATE_DISCLAIMER = (
    "内部工程门禁：阈值来自 internal_authored 内部标定，"
    "结论仅用于工程晋级判断，不代表专家验收、客户确认或 G 门通过。"
)

_FINISHED_RUN_STATUSES = ("completed", "completed_with_errors")


def flatten_manifest(node: Any, prefix: str = "") -> dict[str, Any]:
    """把发布清单展平为「点路径 → 标量值」，便于逐项对比。

    模型列表以 asset_type 作为稳定键，避免列表顺序变化被误报为变更。
    """
    flat: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            flat.update(flatten_manifest(value, child))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            key = (
                str(item.get("asset_type", index))
                if isinstance(item, dict)
                else str(index)
            )
            flat.update(flatten_manifest(item, f"{prefix}[{key}]"))
    else:
        flat[prefix] = node
    return flat


def manifest_changes(baseline: dict, current: dict) -> list[dict]:
    """对比两份发布清单，返回逐项差异（含新增与移除的键）。"""
    base_flat = flatten_manifest(baseline)
    curr_flat = flatten_manifest(current)
    return [
        {"path": path, "baseline": base_flat.get(path), "current": curr_flat.get(path)}
        for path in sorted(set(base_flat) | set(curr_flat))
        if base_flat.get(path) != curr_flat.get(path)
    ]


def compute_gate_metrics(
    cases: list[EvaluationCase], results: list[EvaluationCaseResult]
) -> dict:
    """由逐案例结果计算门禁指标；不产生任何教师/学生评价。"""
    result_by_case = {item.case_id: item for item in results}
    matched = sum(1 for item in results if item.status == "matched")
    errors = sum(1 for item in results if item.status == "error")
    top1_total = 0
    top1_hits = 0
    insufficient_basis_misses = 0
    for case_item in cases:
        result = result_by_case.get(case_item.id)
        if result is None:
            continue
        if case_item.expected_document_ids:
            top1_total += 1
            if (
                result.returned_document_ids
                and result.returned_document_ids[0]
                in set(case_item.expected_document_ids)
            ):
                top1_hits += 1
        if (
            case_item.expected_insufficient_basis
            and result.status != "error"
            and not result.insufficient_basis
        ):
            insufficient_basis_misses += 1
    total = len(cases)
    return {
        "total_cases": total,
        "matched_cases": matched,
        "error_cases": errors,
        "match_rate": (matched / total) if total else 0.0,
        "top1_total": top1_total,
        "top1_hits": top1_hits,
        "top1_hit_rate": (top1_hits / top1_total) if top1_total else None,
        "insufficient_basis_misses": insufficient_basis_misses,
    }


def evaluate_gate(
    metrics: dict, *, min_match_rate: float, min_top1_hit_rate: float
) -> tuple[list[dict], bool]:
    """按内部阈值逐项判定；返回 (checks, 全部通过)。"""
    checks = [
        {
            "check": "match_rate",
            "threshold": f">={min_match_rate}",
            "observed": round(metrics["match_rate"], 4),
            "passed": metrics["match_rate"] >= min_match_rate,
        },
        {
            "check": "top1_hit_rate",
            "threshold": f">={min_top1_hit_rate}",
            "observed": (
                None
                if metrics["top1_hit_rate"] is None
                else round(metrics["top1_hit_rate"], 4)
            ),
            # 数据集没有指定预期文档的案例时该项不适用，视为通过
            "passed": (
                metrics["top1_hit_rate"] is None
                or metrics["top1_hit_rate"] >= min_top1_hit_rate
            ),
        },
        {
            "check": "insufficient_basis_misses",
            "threshold": "=0",
            "observed": metrics["insufficient_basis_misses"],
            "passed": metrics["insufficient_basis_misses"] == 0,
        },
        {
            "check": "error_cases",
            "threshold": "=0",
            "observed": metrics["error_cases"],
            "passed": metrics["error_cases"] == 0,
        },
    ]
    return checks, all(item["passed"] for item in checks)


def case_status_changes(
    cases: list[EvaluationCase],
    baseline_results: list[EvaluationCaseResult],
    current_results: list[EvaluationCaseResult],
) -> dict[str, list[str]]:
    """对比两次运行的逐案例状态，按 case_key 列出回退、修复与持续失败。"""
    key_by_id = {item.id: item.case_key for item in cases}
    baseline_status = {item.case_id: item.status for item in baseline_results}
    current_status = {item.case_id: item.status for item in current_results}
    regressed: list[str] = []
    improved: list[str] = []
    still_failed: list[str] = []
    for case_id, key in key_by_id.items():
        before = baseline_status.get(case_id)
        after = current_status.get(case_id)
        if after is None or before is None:
            continue
        if before == "matched" and after != "matched":
            regressed.append(key)
        elif before != "matched" and after == "matched":
            improved.append(key)
        elif before != "matched" and after != "matched":
            still_failed.append(key)
    return {
        "regressed_case_keys": sorted(regressed),
        "improved_case_keys": sorted(improved),
        "still_failed_case_keys": sorted(still_failed),
    }


async def _run_results(
    db: AsyncSession, run_id: int
) -> list[EvaluationCaseResult]:
    result = await db.execute(
        select(EvaluationCaseResult)
        .where(EvaluationCaseResult.run_id == run_id)
        .order_by(EvaluationCaseResult.id)
    )
    return list(result.scalars())


async def regression_gate_report(
    db: AsyncSession, *, dataset_id: int, user: User
) -> dict:
    """生成冻结数据集的回归门禁报告。

    verdict 取值：
    - ``no_run``：尚无已完成运行，阻断晋级。
    - ``stale``：当前发布清单相对最近一次运行已变更（模型 revision、
      检索参数、Skill 版本等），必须重新运行后再评估，阻断晋级。
    - ``blocked``：最近一次运行未达到内部阈值。
    - ``promotable``：最近一次运行在当前配置下达到全部内部阈值。
    """
    dataset = await get_accessible_dataset(db, dataset_id=dataset_id, user=user)
    if dataset.status != "frozen":
        raise BusinessError(
            "回归门禁只针对已冻结数据集",
            status_code=409,
            error_code="dataset_not_frozen",
        )
    runs_result = await db.execute(
        select(EvaluationRun)
        .where(
            EvaluationRun.dataset_id == dataset.id,
            EvaluationRun.status.in_(_FINISHED_RUN_STATUSES),
        )
        .order_by(EvaluationRun.id.desc())
        .limit(2)
    )
    runs = list(runs_result.scalars())
    report: dict = {
        "dataset_id": dataset.id,
        "dataset_key": dataset.dataset_key,
        "data_origin": dataset.data_origin,
        "disclaimer": GATE_DISCLAIMER,
        "verdict": "no_run",
        "can_promote": False,
        "latest_run_id": None,
        "metrics": None,
        "checks": [],
        "pending_manifest_changes": [],
        "baseline": None,
    }
    if not runs:
        return report
    latest = runs[0]
    report["latest_run_id"] = latest.id
    cases = await _dataset_cases(db, dataset.id)
    latest_results = await _run_results(db, latest.id)
    metrics = compute_gate_metrics(cases, latest_results)
    checks, passed = evaluate_gate(
        metrics,
        min_match_rate=settings.EVAL_GATE_MIN_MATCH_RATE,
        min_top1_hit_rate=settings.EVAL_GATE_MIN_TOP1_HIT_RATE,
    )
    report["metrics"] = metrics
    report["checks"] = checks
    pending = manifest_changes(latest.release_manifest, release_manifest())
    report["pending_manifest_changes"] = pending
    if len(runs) > 1:
        previous = runs[1]
        previous_results = await _run_results(db, previous.id)
        report["baseline"] = {
            "baseline_run_id": previous.id,
            "manifest_changes": manifest_changes(
                previous.release_manifest, latest.release_manifest
            ),
            **case_status_changes(cases, previous_results, latest_results),
        }
    if pending:
        report["verdict"] = "stale"
    elif passed:
        report["verdict"] = "promotable"
        report["can_promote"] = True
    else:
        report["verdict"] = "blocked"
    return report
