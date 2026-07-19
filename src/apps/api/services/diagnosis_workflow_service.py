"""WP2.3 教案结构确认、逐条诊断决策与采纳项修订。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import ProjectVersion, SkillRun, TeachingProject, User
from src.apps.api.schemas.workbench import (
    ApplyRevisionInput,
    ApplyRevisionOutput,
    DiagnosisDecisionRequest,
    DiagnosisStructureNode,
)
from src.apps.api.services.project_service import create_version, get_owned_project
from src.apps.api.services.structured_generation_service import locked_paths


async def _latest_version(
    db: AsyncSession, project_id: int, user_id: int
) -> tuple[TeachingProject, ProjectVersion]:
    project = await get_owned_project(db, project_id, user_id)
    result = await db.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
        .limit(1)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise BusinessError("教学项目没有可用版本", status_code=409, error_code="version_missing")
    return project, version


def _require_source(source: ProjectVersion, expected: int | None) -> None:
    if expected is not None and source.version_number != expected:
        raise BusinessError(
            f"项目已更新到 v{source.version_number}，请刷新后重试",
            status_code=409,
            error_code="source_version_conflict",
        )


def detect_diagnosis_structure(content: dict[str, Any]) -> list[DiagnosisStructureNode]:
    labels = {
        "alignment_card": "课程依据对齐卡",
        "design_blueprint": "目标—证据—任务蓝图",
        "lesson_design": "课时设计",
    }
    nodes: list[DiagnosisStructureNode] = []
    for path, title in labels.items():
        value = content.get(path)
        if not isinstance(value, dict):
            continue
        excerpt = str(value.get("section_name") or value.get("core_question") or "")
        nodes.append(
            DiagnosisStructureNode(
                path=path, section_type=path, title=title, excerpt=excerpt[:1000]
            )
        )
    return nodes


async def confirm_diagnosis_structure(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    source_version: int,
    nodes: list[DiagnosisStructureNode],
) -> ProjectVersion:
    project, source = await _latest_version(db, project_id, user_id)
    _require_source(source, source_version)
    required = {"alignment_card", "design_blueprint", "lesson_design"}
    paths = {node.path for node in nodes}
    if not required.issubset(paths):
        raise BusinessError(
            "结构识别必须保留依据卡、教学蓝图和课时设计",
            status_code=422,
            error_code="diagnosis_structure_incomplete",
        )
    content = deepcopy(source.content)
    content.pop("diagnosis", None)
    content["diagnosis_structure"] = {
        "confirmed": True,
        "nodes": [node.model_dump() for node in nodes],
    }
    content["_trace"] = {
        "action": "confirm_diagnosis_structure",
        "source_version": source.version_number,
    }
    return await create_version(db, project, user_id, content, "draft")


async def save_diagnosis_decision(
    db: AsyncSession,
    *,
    project_id: int,
    item_id: str,
    user_id: int,
    request: DiagnosisDecisionRequest,
) -> ProjectVersion:
    project, source = await _latest_version(db, project_id, user_id)
    _require_source(source, request.source_version)
    diagnosis = source.content.get("diagnosis")
    if not isinstance(diagnosis, dict):
        raise BusinessError("请先运行诊断", status_code=409, error_code="diagnosis_missing")
    items = diagnosis.get("items")
    item = next(
        (row for row in items if isinstance(row, dict) and row.get("item_id") == item_id),
        None,
    ) if isinstance(items, list) else None
    if item is None:
        raise BusinessError("诊断项不存在", status_code=404, error_code="diagnosis_item_missing")
    edited = (request.edited_suggestion or "").strip()
    if request.action == "edit" and not edited:
        raise BusinessError(
            "编辑后建议不能为空", status_code=422, error_code="edited_suggestion_required"
        )
    content = deepcopy(source.content)
    saved = content["diagnosis"]
    decisions = saved.setdefault("decisions", {})
    decisions[item_id] = {
        "action": request.action,
        "edited_suggestion": edited or None,
        "signal_level": "L4",
        "authorized_for_training": False,
    }
    signals = content.setdefault("diagnosis_signals", [])
    signals.append({
        "item_id": item_id,
        "action": request.action,
        "signal_level": "L4",
        "authorized_for_training": False,
        "source_version": source.version_number,
    })
    content["_trace"] = {
        "action": "diagnosis_decision",
        "item_id": item_id,
        "decision": request.action,
        "source_version": source.version_number,
    }
    return await create_version(db, project, user_id, content, "draft")


def _append_revision(content: dict[str, Any], path: str, value: str) -> None:
    section_name, field_name = path.split(".", 1)
    section = content.get(section_name)
    if not isinstance(section, dict):
        raise BusinessError("修订目标不存在", status_code=409, error_code="revision_target_missing")
    current = section.get(field_name)
    if not isinstance(current, list):
        raise BusinessError(
            "修订目标不是列表", status_code=409, error_code="revision_target_invalid"
        )
    if value not in current:
        current.append(value)


async def apply_revision_handler(
    db: AsyncSession, user: User, payload: ApplyRevisionInput, run: SkillRun
) -> ApplyRevisionOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    _require_source(source, payload.source_version)
    run.project_id = project.id
    diagnosis = source.content.get("diagnosis")
    if not isinstance(diagnosis, dict):
        raise BusinessError("请先运行诊断", status_code=409, error_code="diagnosis_missing")
    raw_items = diagnosis.get("items")
    items: list[Any] = raw_items if isinstance(raw_items, list) else []
    raw_decisions = diagnosis.get("decisions")
    decisions: dict[str, Any] = raw_decisions if isinstance(raw_decisions, dict) else {}
    locks = locked_paths(source.content)
    content = deepcopy(source.content)
    applied: list[str] = []
    skipped: list[str] = []
    changed: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("item_id"), str):
            continue
        item_id = item["item_id"]
        decision = decisions.get(item_id)
        decision_data: dict[str, Any] = decision if isinstance(decision, dict) else {}
        action = decision_data.get("action")
        if action not in {"accept", "edit"}:
            skipped.append(item_id)
            continue
        target = str(item.get("revision_target_path") or "")
        overlaps_lock = any(
            target == lock
            or target.startswith(f"{lock}.")
            or lock.startswith(f"{target}.")
            for lock in locks
        )
        if overlaps_lock:
            raise BusinessError(
                f"修订目标已锁定：{target}", status_code=409, error_code="revision_target_locked"
            )
        suggestion = str(
            decision_data.get("edited_suggestion")
            if action == "edit"
            else item.get("example_revision")
        ).strip()
        _append_revision(content, target, suggestion)
        applied.append(item_id)
        if target not in changed:
            changed.append(target)
    if not applied:
        raise BusinessError("没有可应用的采纳项", status_code=409, error_code="no_accepted_items")
    content.setdefault("diagnosis_history", []).append(deepcopy(diagnosis))
    content.pop("diagnosis", None)
    content["revision_application"] = {
        "applied_item_ids": applied,
        "skipped_item_ids": skipped,
        "changed_paths": changed,
        "source_version": source.version_number,
    }
    content["_trace"] = {
        "action": "apply_revision",
        "skill_run_id": run.id,
        "source_version": source.version_number,
        "applied_item_ids": applied,
    }
    version = await create_version(db, project, user.id, content, "draft")
    return ApplyRevisionOutput(
        applied_item_ids=applied,
        skipped_item_ids=skipped,
        changed_paths=changed,
        version_number=version.version_number,
    )
