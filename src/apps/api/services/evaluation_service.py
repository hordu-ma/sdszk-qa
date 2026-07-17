"""版本化检索评测数据集与可复现运行。"""

import hashlib
import json
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationDataset,
    EvaluationRun,
    KnowledgeDocument,
    User,
)
from src.apps.api.services.knowledge_service import search_chunks
from src.apps.api.services.model_asset_service import release_manifest
from src.apps.api.services.project_service import get_owned_project


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
    dataset = await get_owned_dataset(db, dataset_id, user.id)
    if dataset.status != "draft":
        raise BusinessError(
            "冻结数据集不可修改，请创建新版本",
            status_code=409,
            error_code="dataset_frozen",
        )
    if expected_document_ids:
        documents = await db.execute(
            select(KnowledgeDocument.id).where(
                KnowledgeDocument.id.in_(expected_document_ids),
                KnowledgeDocument.project_id == dataset.project_id,
                KnowledgeDocument.owner_id == user.id,
            )
        )
        if set(documents.scalars()) != set(expected_document_ids):
            raise BusinessError(
                "预期资料不属于当前项目",
                status_code=422,
                error_code="evaluation_document_invalid",
            )
    case = EvaluationCase(
        dataset_id=dataset.id,
        case_key=case_key,
        query=query,
        expected_document_ids=expected_document_ids,
        expected_insufficient_basis=expected_insufficient_basis,
        case_metadata=case_metadata,
    )
    db.add(case)
    dataset.case_count += 1
    await db.commit()
    await db.refresh(case)
    return case


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
            insufficient = not search_result.citations
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
