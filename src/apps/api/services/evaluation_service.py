"""版本化检索评测数据集与可复现运行。"""

import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationCaseReview,
    EvaluationDataset,
    EvaluationRun,
    KnowledgeDocument,
    User,
)
from src.apps.api.services.knowledge_service import assess_insufficiency, search_chunks
from src.apps.api.services.model_asset_service import release_manifest
from src.apps.api.services.project_service import get_owned_project
from src.apps.api.services.rbac import owner_in_actor_scope, scope_owner_ids


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class EvaluationCaseInput(TypedDict):
    case_key: str
    query: str
    expected_document_ids: list[int]
    expected_insufficient_basis: bool
    case_metadata: dict


async def create_dataset(
    db: AsyncSession,
    *,
    user: User,
    project_id: int,
    dataset_key: str,
    name: str,
    description: str | None,
    data_origin: str,
) -> EvaluationDataset:
    await get_owned_project(db, project_id, user.id)
    latest = await db.execute(
        select(func.max(EvaluationDataset.version_number)).where(
            EvaluationDataset.project_id == project_id,
            EvaluationDataset.dataset_key == dataset_key,
        )
    )
    dataset = EvaluationDataset(
        project_id=project_id,
        owner_id=user.id,
        dataset_key=dataset_key,
        version_number=int(latest.scalar() or 0) + 1,
        name=name,
        description=description,
        data_origin=data_origin,
        review_status="not_applicable" if data_origin == "synthetic" else "pending",
        status="draft",
        case_count=0,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def review_dataset(
    db: AsyncSession,
    *,
    dataset_id: int,
    reviewer: User,
    review_status: str,
    review_note: str,
) -> EvaluationDataset:
    if reviewer.role not in {"admin", "reviewer"}:
        raise BusinessError(
            "只有审核员或管理员可以审核评测数据集",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    result = await db.execute(
        select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise BusinessError(
            "评测数据集不存在", status_code=404, error_code="dataset_not_found"
        )
    if not await owner_in_actor_scope(db, actor=reviewer, owner_id=dataset.owner_id):
        raise BusinessError(
            "无权审核其他组织的评测数据集",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    if dataset.data_origin == "synthetic":
        raise BusinessError(
            "模拟数据集不能标记为专业审核通过，请导入真实资料后创建新版本",
            status_code=409,
            error_code="synthetic_dataset_not_approvable",
        )
    dataset.review_status = review_status
    dataset.review_note = review_note
    dataset.reviewed_by = reviewer.id
    dataset.reviewed_at = _utcnow()
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def get_owned_dataset(
    db: AsyncSession, dataset_id: int, user_id: int
) -> EvaluationDataset:
    result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.owner_id == user_id,
        )
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise BusinessError("评测数据集不存在", status_code=404, error_code="dataset_not_found")
    return dataset


async def get_accessible_dataset(
    db: AsyncSession, *, dataset_id: int, user: User
) -> EvaluationDataset:
    result = await db.execute(
        select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise BusinessError("评测数据集不存在", status_code=404, error_code="dataset_not_found")
    if not await owner_in_actor_scope(db, actor=user, owner_id=dataset.owner_id):
        raise BusinessError(
            "无权查看该评测数据集",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    return dataset


async def add_case(
    db: AsyncSession,
    *,
    user: User,
    dataset_id: int,
    case_key: str,
    query: str,
    expected_document_ids: list[int],
    expected_insufficient_basis: bool,
    case_metadata: dict,
) -> EvaluationCase:
    cases = await add_cases_bulk(
        db,
        user=user,
        dataset_id=dataset_id,
        case_inputs=[
            {
                "case_key": case_key,
                "query": query,
                "expected_document_ids": expected_document_ids,
                "expected_insufficient_basis": expected_insufficient_basis,
                "case_metadata": case_metadata,
            }
        ],
    )
    return cases[0]


async def _validate_document_ids(
    db: AsyncSession, *, dataset: EvaluationDataset, document_ids: set[int]
) -> None:
    if not document_ids:
        return
    documents = await db.execute(
        select(KnowledgeDocument.id).where(
            KnowledgeDocument.id.in_(document_ids),
            KnowledgeDocument.project_id == dataset.project_id,
            KnowledgeDocument.owner_id == dataset.owner_id,
        )
    )
    if set(documents.scalars()) != document_ids:
        raise BusinessError(
            "预期资料不属于当前项目",
            status_code=422,
            error_code="evaluation_document_invalid",
        )


async def add_cases_bulk(
    db: AsyncSession,
    *,
    user: User,
    dataset_id: int,
    case_inputs: list[EvaluationCaseInput],
) -> list[EvaluationCase]:
    dataset = await get_owned_dataset(db, dataset_id, user.id)
    if dataset.status != "draft":
        raise BusinessError(
            "冻结数据集不可修改，请创建新版本",
            status_code=409,
            error_code="dataset_frozen",
        )
    case_keys = [item["case_key"] for item in case_inputs]
    if len(case_keys) != len(set(case_keys)):
        raise BusinessError(
            "批量导入中存在重复 case_key",
            status_code=409,
            error_code="evaluation_case_duplicate",
        )
    existing = await db.execute(
        select(EvaluationCase.case_key).where(
            EvaluationCase.dataset_id == dataset.id,
            EvaluationCase.case_key.in_(case_keys),
        )
    )
    if existing.first() is not None:
        raise BusinessError(
            "case_key 已存在",
            status_code=409,
            error_code="evaluation_case_duplicate",
        )
    for item in case_inputs:
        if item["expected_document_ids"] and item["expected_insufficient_basis"]:
            raise BusinessError(
                "资料不足案例不能同时指定预期文档",
                status_code=422,
                error_code="evaluation_gold_conflict",
            )
    document_ids = {
        document_id
        for item in case_inputs
        for document_id in item["expected_document_ids"]
    }
    await _validate_document_ids(db, dataset=dataset, document_ids=document_ids)
    cases = [
        EvaluationCase(
            dataset_id=dataset.id,
            case_key=item["case_key"],
            query=item["query"],
            expected_document_ids=item["expected_document_ids"],
            expected_insufficient_basis=item["expected_insufficient_basis"],
            case_metadata=item["case_metadata"],
            gold_status=(
                "not_applicable" if dataset.data_origin == "synthetic" else "pending"
            ),
        )
        for item in case_inputs
    ]
    db.add_all(cases)
    dataset.case_count += len(cases)
    await db.commit()
    for case_item in cases:
        await db.refresh(case_item)
    return cases


async def _dataset_cases(db: AsyncSession, dataset_id: int) -> list[EvaluationCase]:
    result = await db.execute(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset_id)
        .order_by(EvaluationCase.case_key, EvaluationCase.id)
    )
    return list(result.scalars())


def _content_hash(cases: list[EvaluationCase]) -> str:
    payload = [
        {
            "case_key": item.case_key,
            "query": item.query,
            "expected_document_ids": item.expected_document_ids,
            "expected_insufficient_basis": item.expected_insufficient_basis,
            "case_metadata": item.case_metadata,
            "gold_status": item.gold_status,
        }
        for item in cases
    ]
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def freeze_dataset(
    db: AsyncSession, *, dataset_id: int, user_id: int
) -> EvaluationDataset:
    dataset = await get_owned_dataset(db, dataset_id, user_id)
    if dataset.status == "frozen":
        return dataset
    cases = await _dataset_cases(db, dataset.id)
    if not cases:
        raise BusinessError(
            "空数据集不可冻结", status_code=422, error_code="dataset_empty"
        )
    if dataset.data_origin != "synthetic":
        ready_statuses = {"consensus", "arbitrated"}
        if dataset.review_status != "approved" or any(
            item.gold_status not in ready_statuses for item in cases
        ) or any(item.case_metadata.get("placeholder") is True for item in cases):
            raise BusinessError(
                "正式数据集须审核通过、移除占位案例且全部案例完成双评共识或仲裁后才能冻结",
                status_code=409,
                error_code="evaluation_gold_not_ready",
            )
    dataset.status = "frozen"
    dataset.case_count = len(cases)
    dataset.content_hash = _content_hash(cases)
    dataset.frozen_at = _utcnow()
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def list_datasets(
    db: AsyncSession, *, project_id: int, user_id: int
) -> list[EvaluationDataset]:
    await get_owned_project(db, project_id, user_id)
    result = await db.execute(
        select(EvaluationDataset)
        .where(
            EvaluationDataset.project_id == project_id,
            EvaluationDataset.owner_id == user_id,
        )
        .order_by(EvaluationDataset.dataset_key, EvaluationDataset.version_number.desc())
    )
    return list(result.scalars())


async def list_review_queue(db: AsyncSession, *, reviewer: User) -> list[EvaluationDataset]:
    if reviewer.role not in {"admin", "reviewer"}:
        raise BusinessError(
            "只有审核员或管理员可以查看复核队列",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    stmt = (
        select(EvaluationDataset)
        .where(
            EvaluationDataset.data_origin != "synthetic",
            EvaluationDataset.status == "draft",
        )
        .order_by(EvaluationDataset.created_at, EvaluationDataset.id)
    )
    # 跨组织隔离：reviewer 只见本组织资源，平台 admin 不限
    stmt = scope_owner_ids(stmt, reviewer, EvaluationDataset.owner_id)
    result = await db.execute(stmt)
    return list(result.scalars())


async def list_dataset_cases(
    db: AsyncSession, *, dataset_id: int, user: User
) -> list[EvaluationCase]:
    await get_accessible_dataset(db, dataset_id=dataset_id, user=user)
    return await _dataset_cases(db, dataset_id)


def _review_signature(
    review: EvaluationCaseReview,
) -> tuple[tuple[int, ...], bool, tuple[str, ...]]:
    return (
        tuple(sorted(review.expected_document_ids)),
        review.expected_insufficient_basis,
        tuple(sorted(review.critical_error_tags)),
    )


def _apply_gold(case_item: EvaluationCase, review: EvaluationCaseReview, status: str) -> None:
    case_item.expected_document_ids = sorted(set(review.expected_document_ids))
    case_item.expected_insufficient_basis = review.expected_insufficient_basis
    case_item.case_metadata = {
        **case_item.case_metadata,
        "gold": {
            "critical_error_tags": sorted(set(review.critical_error_tags)),
            "resolved_by": status,
        },
    }
    case_item.gold_status = status


async def submit_case_review(
    db: AsyncSession,
    *,
    case_id: int,
    reviewer: User,
    review_kind: str,
    expected_document_ids: list[int],
    expected_insufficient_basis: bool,
    critical_error_tags: list[str],
    rationale: str,
) -> EvaluationCaseReview:
    if reviewer.role not in {"admin", "reviewer"}:
        raise BusinessError(
            "只有审核员或管理员可以提交专家金标复核",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    result = await db.execute(
        select(EvaluationCase, EvaluationDataset)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationCase.dataset_id)
        .where(EvaluationCase.id == case_id)
    )
    row = result.one_or_none()
    if row is None:
        raise BusinessError(
            "评测案例不存在", status_code=404, error_code="evaluation_case_not_found"
        )
    case_item, dataset = row
    if not await owner_in_actor_scope(db, actor=reviewer, owner_id=dataset.owner_id):
        raise BusinessError(
            "无权复核其他组织的评测案例",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    if dataset.data_origin == "synthetic":
        raise BusinessError(
            "模拟案例不进入专家金标流程",
            status_code=409,
            error_code="synthetic_case_not_reviewable",
        )
    if dataset.status != "draft":
        raise BusinessError(
            "冻结数据集不可新增复核记录",
            status_code=409,
            error_code="dataset_frozen",
        )
    if expected_document_ids and expected_insufficient_basis:
        raise BusinessError(
            "资料不足案例不能同时指定预期文档",
            status_code=422,
            error_code="evaluation_gold_conflict",
        )
    await _validate_document_ids(
        db, dataset=dataset, document_ids=set(expected_document_ids)
    )
    reviews_result = await db.execute(
        select(EvaluationCaseReview)
        .where(EvaluationCaseReview.case_id == case_id)
        .order_by(EvaluationCaseReview.id)
    )
    reviews = list(reviews_result.scalars())
    independent = [item for item in reviews if item.review_kind == "independent"]
    arbitration = [item for item in reviews if item.review_kind == "arbitration"]
    if review_kind == "independent":
        if any(item.reviewer_id == reviewer.id for item in independent):
            raise BusinessError(
                "同一审核人不能重复提交独立复核",
                status_code=409,
                error_code="evaluation_review_duplicate",
            )
        if len(independent) >= 2:
            raise BusinessError(
                "独立复核已满两份，请按状态进入仲裁",
                status_code=409,
                error_code="evaluation_review_limit",
            )
    else:
        if case_item.gold_status != "disputed" or len(independent) != 2 or arbitration:
            raise BusinessError(
                "仅双评存在分歧且尚未仲裁的案例可以提交仲裁",
                status_code=409,
                error_code="evaluation_arbitration_not_ready",
            )
        if any(item.reviewer_id == reviewer.id for item in independent):
            raise BusinessError(
                "仲裁人不能同时是前两位独立复核人",
                status_code=409,
                error_code="evaluation_arbitrator_not_independent",
            )
    review = EvaluationCaseReview(
        case_id=case_item.id,
        reviewer_id=reviewer.id,
        review_kind=review_kind,
        expected_document_ids=sorted(set(expected_document_ids)),
        expected_insufficient_basis=expected_insufficient_basis,
        critical_error_tags=sorted(set(critical_error_tags)),
        rationale=rationale,
    )
    db.add(review)
    await db.flush()
    if review_kind == "arbitration":
        _apply_gold(case_item, review, "arbitrated")
    elif not independent:
        case_item.gold_status = "single_review"
    else:
        first_review = independent[0]
        if _review_signature(first_review) == _review_signature(review):
            _apply_gold(case_item, review, "consensus")
        else:
            case_item.gold_status = "disputed"
    await db.commit()
    await db.refresh(review)
    return review


async def list_case_reviews(
    db: AsyncSession, *, case_id: int, user: User
) -> list[EvaluationCaseReview]:
    case_result = await db.execute(
        select(EvaluationCase, EvaluationDataset)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationCase.dataset_id)
        .where(EvaluationCase.id == case_id)
    )
    row = case_result.one_or_none()
    if row is None:
        raise BusinessError(
            "评测案例不存在", status_code=404, error_code="evaluation_case_not_found"
        )
    _, dataset = row
    if not await owner_in_actor_scope(db, actor=user, owner_id=dataset.owner_id):
        raise BusinessError(
            "无权查看该案例复核记录",
            status_code=403,
            error_code="evaluation_review_forbidden",
        )
    result = await db.execute(
        select(EvaluationCaseReview)
        .where(EvaluationCaseReview.case_id == case_id)
        .order_by(EvaluationCaseReview.id)
    )
    return list(result.scalars())


async def dataset_report(
    db: AsyncSession, *, dataset_id: int, user: User
) -> dict:
    dataset = await get_accessible_dataset(db, dataset_id=dataset_id, user=user)
    cases = await _dataset_cases(db, dataset.id)
    gold_counts = Counter(item.gold_status for item in cases)
    latest_run_result = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.dataset_id == dataset.id)
        .order_by(EvaluationRun.id.desc())
        .limit(1)
    )
    latest_run = latest_run_result.scalar_one_or_none()
    ready_statuses = {"consensus", "arbitrated"}
    placeholder_cases = sum(
        item.case_metadata.get("placeholder") is True for item in cases
    )
    ready_for_freeze = bool(cases) and (
        dataset.data_origin == "synthetic"
        or (
            dataset.review_status == "approved"
            and placeholder_cases == 0
            and all(item.gold_status in ready_statuses for item in cases)
        )
    )
    return {
        "dataset_id": dataset.id,
        "data_origin": dataset.data_origin,
        "review_status": dataset.review_status,
        "dataset_status": dataset.status,
        "total_cases": len(cases),
        "placeholder_cases": placeholder_cases,
        "gold_status_counts": dict(sorted(gold_counts.items())),
        "ready_for_freeze": ready_for_freeze,
        "latest_run": (
            None
            if latest_run is None
            else {
                "id": latest_run.id,
                "status": latest_run.status,
                "total_cases": latest_run.total_cases,
                "matched_cases": latest_run.matched_cases,
                "failed_cases": latest_run.failed_cases,
                "error_cases": latest_run.error_cases,
                "dataset_hash": latest_run.dataset_hash,
            }
        ),
    }


async def run_dataset(
    db: AsyncSession, *, dataset_id: int, user: User
) -> EvaluationRun:
    dataset = await get_owned_dataset(db, dataset_id, user.id)
    if dataset.status != "frozen" or not dataset.content_hash:
        raise BusinessError(
            "只能运行已冻结数据集", status_code=409, error_code="dataset_not_frozen"
        )
    cases = await _dataset_cases(db, dataset.id)
    run = EvaluationRun(
        dataset_id=dataset.id,
        user_id=user.id,
        status="running",
        dataset_hash=dataset.content_hash,
        release_manifest=release_manifest(),
        total_cases=len(cases),
        matched_cases=0,
        failed_cases=0,
        error_cases=0,
    )
    db.add(run)
    await db.flush()
    for case_item in cases:
        started = time.monotonic()
        try:
            search_result = await search_chunks(
                db,
                project_id=dataset.project_id,
                user_id=user.id,
                query=case_item.query,
                limit=10,
            )
            returned_ids = list(
                dict.fromkeys(int(item["document_id"]) for item in search_result.citations)
            )
            insufficient, _ = assess_insufficiency(search_result.citations)
            basis_check = insufficient == case_item.expected_insufficient_basis
            document_check = not case_item.expected_document_ids or bool(
                set(returned_ids) & set(case_item.expected_document_ids)
            )
            matched = basis_check and document_check
            result_status = "matched" if matched else "failed"
            if matched:
                run.matched_cases += 1
            else:
                run.failed_cases += 1
            db.add(
                EvaluationCaseResult(
                    run_id=run.id,
                    case_id=case_item.id,
                    status=result_status,
                    returned_document_ids=returned_ids,
                    insufficient_basis=insufficient,
                    checks={
                        "insufficient_basis": basis_check,
                        "expected_document_present": document_check,
                        "retrieval_mode": search_result.mode,
                    },
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            )
        except Exception as exc:
            run.error_cases += 1
            db.add(
                EvaluationCaseResult(
                    run_id=run.id,
                    case_id=case_item.id,
                    status="error",
                    returned_document_ids=[],
                    insufficient_basis=True,
                    checks={},
                    error_message=str(exc)[:1000],
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            )
    run.status = "completed_with_errors" if run.error_cases else "completed"
    run.finished_at = _utcnow()
    await db.commit()
    await db.refresh(run)
    return run


async def get_owned_run(db: AsyncSession, run_id: int, user_id: int) -> EvaluationRun:
    result = await db.execute(
        select(EvaluationRun)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationRun.dataset_id)
        .where(EvaluationRun.id == run_id, EvaluationDataset.owner_id == user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise BusinessError(
            "评测运行不存在", status_code=404, error_code="evaluation_run_not_found"
        )
    return run


async def list_run_results(
    db: AsyncSession, run_id: int, user_id: int
) -> list[EvaluationCaseResult]:
    await get_owned_run(db, run_id, user_id)
    result = await db.execute(
        select(EvaluationCaseResult)
        .where(EvaluationCaseResult.run_id == run_id)
        .order_by(EvaluationCaseResult.id)
    )
    return list(result.scalars())
