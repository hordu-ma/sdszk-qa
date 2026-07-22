"""WP2.4 第二增量：SkillRun/诊断产物抽检队列与双评仲裁。

复用金标治理的状态机口径：两位不同复核人独立复核，签名完全一致
形成共识；不一致进入分歧，只能由未参与前两次复核的第三人仲裁。
抽检结论只回答诊断输出是否成立（confirmed / needs_adjustment），
不产生分数或排名；自助开发模式（§0.5）下复核人为内部代理，
所有记录均为 signal_level=L4 且 authorized_for_training=false 的工程信号。
"""

from datetime import UTC, datetime
from random import SystemRandom
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import SkillRun, SpotCheckItem, SpotCheckReview, User
from src.apps.api.services.model_asset_service import release_manifest
from src.apps.api.services.rbac import owner_in_actor_scope, scope_owner_ids

SPOT_CHECK_DISCLAIMER = (
    "内部工程抽检：复核人为内部代理，结论仅用于诊断质量回看与规则字典迭代，"
    "记录为 L4 信号且 authorized_for_training=false，不代表专家验收或客户确认。"
)

SPOT_CHECK_VERDICTS = {"confirmed", "needs_adjustment"}

_SAMPLE_CANDIDATE_WINDOW = 200
_random = SystemRandom()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_reviewer(user: User) -> None:
    if user.role not in {"admin", "reviewer"}:
        raise BusinessError(
            "只有审核员或管理员可以操作抽检队列",
            status_code=403,
            error_code="spot_check_forbidden",
        )


def review_signature(verdict: str, issue_tags: list[str]) -> tuple[str, tuple[str, ...]]:
    """双评一致性签名：结论 + 排序去重后的问题标签。"""
    return (verdict, tuple(sorted(set(issue_tags))))


def next_item_status(
    *,
    independent_signatures: list[tuple[str, tuple[str, ...]]],
    new_signature: tuple[str, tuple[str, ...]],
    review_kind: str,
) -> str:
    """给定既有独立复核签名与新提交，返回抽检项的下一个状态。"""
    if review_kind == "arbitration":
        return "arbitrated"
    if not independent_signatures:
        return "single_review"
    if independent_signatures[0] == new_signature:
        return "consensus"
    return "disputed"


async def sample_spot_checks(
    db: AsyncSession,
    *,
    reviewer: User,
    skill_id: str,
    sample_size: int,
) -> list[SpotCheckItem]:
    """从最近完成的 SkillRun 中随机抽取未复核的运行进入抽检队列。"""
    _require_reviewer(reviewer)
    sampled = await db.execute(select(SpotCheckItem.skill_run_id))
    sampled_run_ids = set(sampled.scalars())
    stmt = (
        select(SkillRun)
        .where(SkillRun.skill_id == skill_id, SkillRun.status == "completed")
        .order_by(SkillRun.id.desc())
        .limit(_SAMPLE_CANDIDATE_WINDOW)
    )
    # 跨组织隔离：reviewer 只能抽检本组织成员的运行，平台 admin 不限
    stmt = scope_owner_ids(stmt, reviewer, SkillRun.user_id)
    result = await db.execute(stmt)
    candidates = [run for run in result.scalars() if run.id not in sampled_run_ids]
    if not candidates:
        raise BusinessError(
            "没有可抽检的已完成 SkillRun",
            status_code=409,
            error_code="spot_check_no_candidates",
        )
    chosen = (
        candidates
        if len(candidates) <= sample_size
        else _random.sample(candidates, sample_size)
    )
    items = [
        SpotCheckItem(
            skill_run_id=run.id,
            project_id=run.project_id,
            sampled_by=reviewer.id,
            sample_source="random_recent",
            skill_id=run.skill_id,
            skill_version=run.skill_version,
            status="pending",
            context_snapshot={
                "release_manifest": release_manifest(),
                "sampled_at": _utcnow().isoformat(),
                "signal_level": "L4",
                "authorized_for_training": False,
            },
            resolved_issue_tags=[],
        )
        for run in sorted(chosen, key=lambda run: run.id)
    ]
    db.add_all(items)
    await db.commit()
    for item in items:
        await db.refresh(item)
    return items


async def list_spot_checks(
    db: AsyncSession, *, reviewer: User, status: str | None = None
) -> list[SpotCheckItem]:
    _require_reviewer(reviewer)
    query = select(SpotCheckItem).order_by(SpotCheckItem.id)
    if status is not None:
        query = query.where(SpotCheckItem.status == status)
    # 跨组织隔离：按被抽检运行的所有者组织过滤（join SkillRun.user_id）
    query = query.join(SkillRun, SkillRun.id == SpotCheckItem.skill_run_id)
    query = scope_owner_ids(query, reviewer, SkillRun.user_id)
    result = await db.execute(query)
    return list(result.scalars())


async def _get_item(db: AsyncSession, item_id: int) -> SpotCheckItem:
    result = await db.execute(
        select(SpotCheckItem).where(SpotCheckItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise BusinessError(
            "抽检项不存在", status_code=404, error_code="spot_check_not_found"
        )
    return item


async def _item_reviews(db: AsyncSession, item_id: int) -> list[SpotCheckReview]:
    result = await db.execute(
        select(SpotCheckReview)
        .where(SpotCheckReview.item_id == item_id)
        .order_by(SpotCheckReview.id)
    )
    return list(result.scalars())


async def _require_item_in_scope(
    db: AsyncSession, reviewer: User, run: SkillRun | None
) -> None:
    """跨组织隔离：抽检项按被抽检运行的所有者组织判定可见性。"""
    owner_id = run.user_id if run is not None else None
    if owner_id is None or not await owner_in_actor_scope(
        db, actor=reviewer, owner_id=owner_id
    ):
        raise BusinessError(
            "无权访问其他组织的抽检项",
            status_code=403,
            error_code="spot_check_forbidden",
        )


async def get_spot_check_detail(
    db: AsyncSession, *, item_id: int, reviewer: User
) -> dict[str, Any]:
    """抽检项详情：SkillRun 输入输出证据、模型清单快照与全部复核记录。"""
    _require_reviewer(reviewer)
    item = await _get_item(db, item_id)
    run_result = await db.execute(
        select(SkillRun).where(SkillRun.id == item.skill_run_id)
    )
    run = run_result.scalar_one_or_none()
    await _require_item_in_scope(db, reviewer, run)
    reviews = await _item_reviews(db, item.id)
    return {
        "item": item,
        "skill_run": run,
        "reviews": reviews,
        "disclaimer": SPOT_CHECK_DISCLAIMER,
    }


async def submit_spot_check_review(
    db: AsyncSession,
    *,
    item_id: int,
    reviewer: User,
    review_kind: str,
    verdict: str,
    issue_tags: list[str],
    rubric_feedback: str | None,
    rationale: str,
) -> SpotCheckReview:
    """提交独立复核或仲裁；状态机与金标复核同口径。"""
    _require_reviewer(reviewer)
    if verdict not in SPOT_CHECK_VERDICTS:
        raise BusinessError(
            "抽检结论只能是 confirmed 或 needs_adjustment",
            status_code=422,
            error_code="spot_check_verdict_invalid",
        )
    item = await _get_item(db, item_id)
    run_result = await db.execute(
        select(SkillRun).where(SkillRun.id == item.skill_run_id)
    )
    await _require_item_in_scope(db, reviewer, run_result.scalar_one_or_none())
    reviews = await _item_reviews(db, item.id)
    independent = [row for row in reviews if row.review_kind == "independent"]
    arbitration = [row for row in reviews if row.review_kind == "arbitration"]
    if review_kind == "independent":
        if any(row.reviewer_id == reviewer.id for row in independent):
            raise BusinessError(
                "同一复核人不能重复提交独立复核",
                status_code=409,
                error_code="spot_check_review_duplicate",
            )
        if len(independent) >= 2:
            raise BusinessError(
                "独立复核已满两份，请按状态进入仲裁",
                status_code=409,
                error_code="spot_check_review_limit",
            )
    else:
        if item.status != "disputed" or len(independent) != 2 or arbitration:
            raise BusinessError(
                "仅双评存在分歧且尚未仲裁的抽检项可以提交仲裁",
                status_code=409,
                error_code="spot_check_arbitration_not_ready",
            )
        if any(row.reviewer_id == reviewer.id for row in independent):
            raise BusinessError(
                "仲裁人不能同时是前两位独立复核人",
                status_code=409,
                error_code="spot_check_arbitrator_not_independent",
            )
    review = SpotCheckReview(
        item_id=item.id,
        reviewer_id=reviewer.id,
        review_kind=review_kind,
        verdict=verdict,
        issue_tags=sorted(set(issue_tags)),
        rubric_feedback=(rubric_feedback or "").strip() or None,
        rationale=rationale,
    )
    db.add(review)
    await db.flush()
    signature = review_signature(verdict, issue_tags)
    item.status = next_item_status(
        independent_signatures=[
            review_signature(row.verdict, list(row.issue_tags)) for row in independent
        ],
        new_signature=signature,
        review_kind=review_kind,
    )
    if item.status in {"consensus", "arbitrated"}:
        item.resolved_verdict = verdict
        item.resolved_issue_tags = sorted(set(issue_tags))
    await db.commit()
    await db.refresh(review)
    return review


def queue_status_counts(items: list[SpotCheckItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return dict(sorted(counts.items()))
