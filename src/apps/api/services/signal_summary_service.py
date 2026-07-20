"""WP2.4 第二增量：教师 L4 诊断决定按规则维度汇总。

WP2.3 起每条教师逐条决定（accept / ignore / edit / request_expert）都以
signal_level=L4、authorized_for_training=false 写入 ProjectVersion 内容。
本服务把这些信号按诊断规则字典的维度聚合，用于量规回看与规则迭代；
只做计数汇总，不为任何教师或项目生成分数、排名或绩效指标，
汇总结果也不构成训练授权（授权、脱敏和质检门在阶段 4 另行建设）。
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import ProjectVersion, TeachingProject, User
from src.apps.api.services.diagnostic_rules import diagnostic_rules

L4_SUMMARY_DISCLAIMER = (
    "内部工程信号汇总：L4 教师决定信号仅用于诊断规则字典与量规迭代回看，"
    "authorized_for_training=false，未经授权、脱敏和质检不得进入训练；"
    "不构成对教师或项目的任何评价。"
)

SIGNAL_ACTIONS = ("accept", "ignore", "edit", "request_expert")

_UNKNOWN_DIMENSION = "未登记维度"


def _dimension_lookup(contents: list[dict[str, Any]]) -> dict[str, str]:
    """item_id → 维度映射：规则字典优先，其次从版本内容中的诊断项回溯。"""
    lookup = {rule.rule_id: rule.dimension for rule in diagnostic_rules()}
    for content in contents:
        candidates: list[Any] = []
        diagnosis = content.get("diagnosis")
        if isinstance(diagnosis, dict):
            candidates.append(diagnosis.get("items"))
        history = content.get("diagnosis_history")
        if isinstance(history, list):
            for entry in history:
                if isinstance(entry, dict):
                    candidates.append(entry.get("items"))
        for items in candidates:
            if not isinstance(items, list):
                continue
            for item in items:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("item_id"), str)
                    and isinstance(item.get("dimension"), str)
                ):
                    lookup.setdefault(item["item_id"], item["dimension"])
    return lookup


def summarize_l4_signals(contents: list[dict[str, Any]]) -> dict[str, Any]:
    """把若干项目最新版本内容中的 L4 信号按维度和规则聚合。"""
    lookup = _dimension_lookup(contents)
    rule_actions: dict[str, dict[str, int]] = {}
    total = 0
    for content in contents:
        signals = content.get("diagnosis_signals")
        if not isinstance(signals, list):
            continue
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            item_id = signal.get("item_id")
            action = signal.get("action")
            if not isinstance(item_id, str) or action not in SIGNAL_ACTIONS:
                continue
            actions = rule_actions.setdefault(
                item_id, dict.fromkeys(SIGNAL_ACTIONS, 0)
            )
            actions[action] += 1
            total += 1
    dimension_rows: dict[str, dict[str, Any]] = {}
    for item_id, actions in sorted(rule_actions.items()):
        dimension = lookup.get(item_id, _UNKNOWN_DIMENSION)
        row = dimension_rows.setdefault(
            dimension,
            {
                "dimension": dimension,
                "total_signals": 0,
                "actions": dict.fromkeys(SIGNAL_ACTIONS, 0),
                "rules": [],
            },
        )
        rule_total = sum(actions.values())
        row["total_signals"] += rule_total
        for name in SIGNAL_ACTIONS:
            row["actions"][name] += actions[name]
        row["rules"].append(
            {"rule_id": item_id, "total_signals": rule_total, "actions": dict(actions)}
        )
    return {
        "signal_level": "L4",
        "authorized_for_training": False,
        "disclaimer": L4_SUMMARY_DISCLAIMER,
        "total_signals": total,
        "dimensions": sorted(
            dimension_rows.values(), key=lambda row: str(row["dimension"])
        ),
    }


async def _latest_contents(
    db: AsyncSession, project_ids: list[int]
) -> list[dict[str, Any]]:
    if not project_ids:
        return []
    latest = (
        select(
            ProjectVersion.project_id,
            func.max(ProjectVersion.version_number).label("max_version"),
        )
        .where(ProjectVersion.project_id.in_(project_ids))
        .group_by(ProjectVersion.project_id)
        .subquery()
    )
    result = await db.execute(
        select(ProjectVersion.content).join(
            latest,
            (ProjectVersion.project_id == latest.c.project_id)
            & (ProjectVersion.version_number == latest.c.max_version),
        )
    )
    return [content for content in result.scalars() if isinstance(content, dict)]


async def l4_signal_summary(
    db: AsyncSession, *, user: User, project_id: int | None
) -> dict[str, Any]:
    """项目级（本人或复核角色）或全局级（仅复核角色）的 L4 信号汇总。"""
    if project_id is not None:
        result = await db.execute(
            select(TeachingProject).where(TeachingProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise BusinessError(
                "教学项目不存在", status_code=404, error_code="project_not_found"
            )
        if project.owner_id != user.id and user.role not in {"admin", "reviewer"}:
            raise BusinessError(
                "无权查看该项目的信号汇总",
                status_code=403,
                error_code="signal_summary_forbidden",
            )
        project_ids = [project.id]
        scope = "project"
    else:
        if user.role not in {"admin", "reviewer"}:
            raise BusinessError(
                "全局信号汇总仅限审核员或管理员查看",
                status_code=403,
                error_code="signal_summary_forbidden",
            )
        result = await db.execute(select(TeachingProject.id))
        project_ids = list(result.scalars())
        scope = "global"
    contents = await _latest_contents(db, project_ids)
    summary = summarize_l4_signals(contents)
    summary["scope"] = scope
    summary["project_count"] = len(project_ids)
    return summary
