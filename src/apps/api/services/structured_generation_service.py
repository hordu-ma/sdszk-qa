"""WP2.2 结构化生成、锁定、局部重生成和版本恢复。"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import ProjectVersion, SkillRun, TeachingProject, User
from src.apps.api.schemas.workbench import GenerateSectionInput, GenerateSectionOutput
from src.apps.api.services.project_service import create_version, get_owned_project

LOCK_STATE_SECTION = "editor_state"
LOCK_STATE_KEY = "locked_paths"
ARTIFACT_SECTION = "teaching_artifacts"

_LOCK_PATH_PATTERNS = (
    re.compile(r"^alignment_card\.(topic|core_question|objectives)$"),
    re.compile(r"^design_blueprint\.(objectives|evidence|learning_tasks)(\.\d+)?$"),
    re.compile(
        r"^lesson_design\.(section_name|opening|activities|assessment_evidence|teacher_notes)"
        r"(\.\d+)?$"
    ),
    re.compile(
        r"^teaching_artifacts\.(task_sheet|rubric|board_plan|slide_outline|practice_task)$"
    ),
)

_REGEN_TARGET_PATTERNS = (
    re.compile(r"^lesson_design\.(opening|assessment_evidence|teacher_notes)$"),
    re.compile(
        r"^lesson_design\.activities\.\d+\."
        r"(title|teacher_action|student_action|evidence)$"
    ),
    re.compile(r"^design_blueprint\.evidence$"),
    re.compile(r"^design_blueprint\.learning_tasks\.\d+\.(title|evidence)$"),
)

_MISSING = object()


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


def _require_source_version(source: ProjectVersion, expected: int | None) -> None:
    if expected is not None and source.version_number != expected:
        raise BusinessError(
            f"项目已更新到 v{source.version_number}，请刷新后重试",
            status_code=409,
            error_code="source_version_conflict",
        )


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def _get_path(content: object, path: str, default: object = _MISSING) -> object:
    value = content
    for part in _path_parts(path):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return default
    return value


def _set_path(content: dict[str, Any], path: str, value: object) -> None:
    parts = _path_parts(path)
    current: object = content
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current:
                raise BusinessError(
                    "局部重生成目标不存在",
                    status_code=409,
                    error_code="target_missing",
                )
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise BusinessError(
                "局部重生成目标不存在",
                status_code=409,
                error_code="target_missing",
            )
    last = parts[-1]
    if isinstance(current, dict) and last in current:
        current[last] = value
        return
    if isinstance(current, list) and last.isdigit() and int(last) < len(current):
        current[int(last)] = value
        return
    raise BusinessError("局部重生成目标不存在", status_code=409, error_code="target_missing")


def _validate_lock_path(path: str) -> None:
    if not any(pattern.fullmatch(path) for pattern in _LOCK_PATH_PATTERNS):
        raise BusinessError(
            f"不支持锁定字段：{path}", status_code=422, error_code="invalid_lock_path"
        )


def _validate_regeneration_target(path: str) -> None:
    if not any(pattern.fullmatch(path) for pattern in _REGEN_TARGET_PATTERNS):
        raise BusinessError(
            f"不支持局部重生成字段：{path}",
            status_code=422,
            error_code="invalid_regeneration_target",
        )


def locked_paths(content: dict[str, Any]) -> list[str]:
    state = content.get(LOCK_STATE_SECTION)
    if not isinstance(state, dict) or not isinstance(state.get(LOCK_STATE_KEY), list):
        return []
    return [path for path in state[LOCK_STATE_KEY] if isinstance(path, str)]


def _paths_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}.") or right.startswith(f"{left}.")


def _locked_overlap(path: str, locks: list[str]) -> str | None:
    return next((locked for locked in locks if _paths_overlap(path, locked)), None)


async def save_teacher_edit_version(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    proposed_content: dict,
    status: str,
    source_version: int | None,
) -> ProjectVersion:
    project, source = await _latest_version(db, project_id, user_id)
    _require_source_version(source, source_version)
    locks = locked_paths(source.content)
    for path in locks:
        if _get_path(source.content, path) != _get_path(proposed_content, path):
            raise BusinessError(
                f"字段已锁定，不能修改：{path}",
                status_code=409,
                error_code="locked_content_changed",
            )
    content = deepcopy(proposed_content)
    if LOCK_STATE_SECTION in source.content:
        content[LOCK_STATE_SECTION] = deepcopy(source.content[LOCK_STATE_SECTION])
    trace_value = content.get("_trace")
    trace: dict[str, Any] = deepcopy(trace_value) if isinstance(trace_value, dict) else {}
    content["_trace"] = {
        **trace,
        "action": "teacher_edit",
        "source_version": source.version_number,
    }
    return await create_version(db, project, user_id, content, status)


async def update_version_locks(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    source_version: int,
    paths: list[str],
) -> ProjectVersion:
    project, source = await _latest_version(db, project_id, user_id)
    _require_source_version(source, source_version)
    normalized = sorted({path.strip() for path in paths if path.strip()})
    for path in normalized:
        _validate_lock_path(path)
        if _get_path(source.content, path) is _MISSING:
            raise BusinessError(
                f"锁定字段不存在：{path}", status_code=409, error_code="lock_target_missing"
            )
    content = deepcopy(source.content)
    content[LOCK_STATE_SECTION] = {LOCK_STATE_KEY: normalized}
    content["_trace"] = {
        "action": "update_locks",
        "source_version": source.version_number,
        "locked_paths": normalized,
    }
    return await create_version(db, project, user_id, content, "draft")


async def restore_project_version(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    source_version: int,
    restore_version: int,
) -> ProjectVersion:
    project, source = await _latest_version(db, project_id, user_id)
    _require_source_version(source, source_version)
    result = await db.execute(
        select(ProjectVersion).where(
            ProjectVersion.project_id == project_id,
            ProjectVersion.version_number == restore_version,
        )
    )
    restored = result.scalar_one_or_none()
    if restored is None:
        raise BusinessError("恢复版本不存在", status_code=404, error_code="version_not_found")
    if restored.version_number == source.version_number:
        raise BusinessError(
            "当前已经是该版本", status_code=409, error_code="restore_current_version"
        )
    content = deepcopy(restored.content)
    content["_trace"] = {
        "action": "restore_version",
        "source_version": source.version_number,
        "restored_version": restored.version_number,
    }
    return await create_version(db, project, user_id, content, restored.status)


def _lesson_draft(blueprint: dict[str, Any], payload: GenerateSectionInput) -> dict[str, Any]:
    tasks = list(blueprint.get("learning_tasks", []))
    activities = [
        {
            "sequence": index,
            "title": str(task.get("title", f"学习任务 {index}")),
            "minutes": int(task.get("minutes", 0)),
            "teacher_action": "提供问题、审核资料片段和追问支架",
            "student_action": "形成观点、引用依据、回应同伴并修正表达",
            "evidence": str(task.get("evidence", "课堂过程证据")),
        }
        for index, task in enumerate(tasks, 1)
        if isinstance(task, dict)
    ]
    return {
        "section_name": payload.section_name,
        "opening": f"以“{blueprint['core_question']}”为主问题进入课堂探究。",
        "activities": activities,
        "assessment_evidence": list(blueprint.get("evidence", [])),
        "teacher_notes": [
            "所有结论均要求回到已审核资料或课堂事实",
            "允许学生保留不同观点，但必须说明依据",
            payload.guidance or "根据现场生成性问题调整追问，不改变核心目标",
        ],
    }


def _artifact_draft(
    kind: str, blueprint: dict[str, Any], lesson: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    core_question = str(blueprint.get("core_question", "待确认核心议题"))
    objectives = list(blueprint.get("objectives", []))
    evidence = list(blueprint.get("evidence", []))
    tasks = [item for item in blueprint.get("learning_tasks", []) if isinstance(item, dict)]
    activities = [item for item in lesson.get("activities", []) if isinstance(item, dict)]
    if kind == "task_sheet":
        return "课堂任务单", {
            "title": f"任务单：{core_question}",
            "objectives": objectives,
            "instructions": "围绕核心议题完成任务，并为每个观点标注依据。",
            "tasks": [
                {
                    "title": item.get("title", "学习任务"),
                    "evidence": item.get("evidence", "过程记录"),
                    "submission": "观点、依据与修正记录",
                }
                for item in tasks
            ],
        }
    if kind == "rubric":
        return "非评分观察量规", {
            "title": "课堂证据观察量规（不计分、不排名）",
            "criteria": [
                {
                    "dimension": item,
                    "aligned_description": "能够提供可定位证据并解释其与主张的关系",
                    "attention_prompt": "证据不足时继续追问来源、关联和反例",
                }
                for item in evidence
            ],
        }
    if kind == "board_plan":
        return "板书设计", {
            "title": core_question,
            "sections": [
                {"heading": "核心概念", "content": objectives},
                {"heading": "观点与依据", "content": evidence},
                {"heading": "课堂结论", "content": ["保留分歧，回到依据"]},
            ],
        }
    if kind == "slide_outline":
        return "课件提纲", {
            "title": core_question,
            "slides": [
                {"title": "情境导入", "purpose": lesson.get("opening", "进入核心议题")},
                *[
                    {
                        "title": item.get("title", "课堂活动"),
                        "purpose": item.get("student_action", "形成课堂证据"),
                    }
                    for item in activities
                ],
                {"title": "证据回看", "purpose": "核对主张、依据和回应"},
            ],
        }
    return "实践任务", {
        "title": f"实践任务：{core_question}",
        "scenario": "选择一个与核心议题相关的真实校园或社区情境。",
        "steps": [item.get("title", "完成探究") for item in tasks],
        "evidence_requirements": evidence,
        "reflection": "说明方案依据、可能影响以及根据反馈所作的修改。",
    }


def _regenerated_value(current: object, guidance: str) -> object:
    instruction = guidance.strip() or "增强依据与课堂证据的对应关系"
    if isinstance(current, str):
        return f"{current.rstrip('。')}；按“{instruction}”完成调整。"
    if isinstance(current, list):
        values = deepcopy(current)
        values.append(f"调整要求：{instruction}")
        return values
    raise BusinessError(
        "当前字段不支持局部重生成", status_code=422, error_code="unsupported_target_type"
    )


def _invalidate_unlocked_artifacts(content: dict[str, Any], locks: list[str]) -> None:
    artifacts = content.get(ARTIFACT_SECTION)
    if not isinstance(artifacts, dict):
        return
    preserved = {
        kind: value
        for kind, value in artifacts.items()
        if f"{ARTIFACT_SECTION}.{kind}" in locks
    }
    if preserved:
        content[ARTIFACT_SECTION] = preserved
    else:
        content.pop(ARTIFACT_SECTION, None)


async def generate_structured_content_handler(
    db: AsyncSession, user: User, payload: GenerateSectionInput, run: SkillRun
) -> GenerateSectionOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    _require_source_version(source, payload.source_version)
    run.project_id = project.id
    blueprint = source.content.get("design_blueprint")
    if not isinstance(blueprint, dict):
        raise BusinessError(
            "请先完成目标—证据—任务蓝图",
            status_code=409,
            error_code="workflow_prerequisite_missing",
        )
    content = deepcopy(source.content)
    locks = locked_paths(content)
    changed_paths: list[str]
    output_content: dict[str, Any]
    section_name: str

    if payload.artifact_kind != "lesson_design":
        if payload.target_path is not None:
            raise BusinessError(
                "多成果生成不接受局部字段",
                status_code=422,
                error_code="artifact_target_not_allowed",
            )
        target = f"{ARTIFACT_SECTION}.{payload.artifact_kind}"
        locked = _locked_overlap(target, locks)
        if locked:
            raise BusinessError(
                f"目标已锁定：{locked}", status_code=409, error_code="target_locked"
            )
        lesson = content.get("lesson_design")
        if not isinstance(lesson, dict):
            raise BusinessError(
                "请先生成课时设计",
                status_code=409,
                error_code="workflow_prerequisite_missing",
            )
        section_name, output_content = _artifact_draft(
            payload.artifact_kind, blueprint, lesson
        )
        artifacts = content.setdefault(ARTIFACT_SECTION, {})
        assert isinstance(artifacts, dict)
        artifacts[payload.artifact_kind] = output_content
        changed_paths = [target]
    elif payload.target_path:
        _validate_regeneration_target(payload.target_path)
        locked = _locked_overlap(payload.target_path, locks)
        if locked:
            raise BusinessError(
                f"目标已锁定：{locked}", status_code=409, error_code="target_locked"
            )
        current = _get_path(content, payload.target_path)
        if current is _MISSING:
            raise BusinessError(
                "局部重生成目标不存在", status_code=409, error_code="target_missing"
            )
        _set_path(content, payload.target_path, _regenerated_value(current, payload.guidance))
        lesson = content.get("lesson_design")
        assert isinstance(lesson, dict)
        output_content = lesson
        section_name = str(lesson.get("section_name", payload.section_name))
        changed_paths = [payload.target_path]
        content.pop("diagnosis", None)
        _invalidate_unlocked_artifacts(content, locks)
    else:
        draft = _lesson_draft(blueprint, payload)
        existing = content.get("lesson_design")
        for path in locks:
            if not path.startswith("lesson_design.") or not isinstance(existing, dict):
                continue
            previous = _get_path(content, path)
            if previous is not _MISSING:
                relative = path.removeprefix("lesson_design.")
                try:
                    _set_path(draft, relative, deepcopy(previous))
                except BusinessError:
                    continue
        content["lesson_design"] = draft
        content.pop("diagnosis", None)
        _invalidate_unlocked_artifacts(content, locks)
        output_content = draft
        section_name = str(draft["section_name"])
        changed_paths = ["lesson_design"]

    content["_trace"] = {
        "skill_run_id": run.id,
        "skill_id": run.skill_id,
        "skill_version": run.skill_version,
        "action": "local_regeneration" if payload.target_path else "structured_generation",
        "source_version": source.version_number,
        "artifact_kind": payload.artifact_kind,
        "target_path": payload.target_path,
        "changed_paths": changed_paths,
        "preserved_locked_paths": locks,
    }
    version = await create_version(db, project, user.id, content, "draft")
    lesson_output = output_content if payload.artifact_kind == "lesson_design" else {}
    return GenerateSectionOutput(
        artifact_kind=payload.artifact_kind,
        section_name=section_name,
        opening=str(lesson_output.get("opening", "")),
        activities=list(lesson_output.get("activities", [])),
        assessment_evidence=list(lesson_output.get("assessment_evidence", [])),
        teacher_notes=list(lesson_output.get("teacher_notes", [])),
        content=output_content,
        changed_paths=changed_paths,
        preserved_locked_paths=locks,
        version_number=version.version_number,
    )
