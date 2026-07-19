"""阶段 2 专业输入确认与确定性冲突检查。"""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import ProjectVersion, SkillRun, TeachingProject, User
from src.apps.api.schemas.workbench import (
    ProfessionalInputConflict,
    ProfessionalInputInput,
    ProfessionalInputOutput,
)
from src.apps.api.services.project_service import create_version, get_owned_project

DOWNSTREAM_SECTIONS = (
    "alignment_card",
    "design_blueprint",
    "lesson_design",
    "diagnosis",
)
DIGITAL_INTENT_TERMS = ("数字化", "视频", "在线", "平板", "网络")
NO_DEVICE_TERMS = ("无设备", "没有设备", "无网络", "不可使用设备", "不具备设备")


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


def evaluate_professional_input(
    project: TeachingProject,
    payload: ProfessionalInputInput,
) -> tuple[list[ProfessionalInputConflict], list[str]]:
    """只检查显式字段冲突，不推断教师或学生能力。"""
    conflicts: list[ProfessionalInputConflict] = []
    assumptions: list[str] = []

    if payload.course_type.strip() != project.course_type.strip():
        conflicts.append(
            ProfessionalInputConflict(
                conflict_id="course_type_mismatch",
                severity="blocking",
                field="course_type",
                message=(
                    f"本次课型“{payload.course_type}”与项目课型“{project.course_type}”不一致。"
                ),
                resolution="确认并统一项目课型与本次教学课型后重新检查。",
            )
        )
    if payload.lesson_minutes > payload.available_minutes:
        conflicts.append(
            ProfessionalInputConflict(
                conflict_id="lesson_time_exceeds_available",
                severity="blocking",
                field="lesson_minutes",
                message=(
                    f"计划课时 {payload.lesson_minutes} 分钟超过可用时间 "
                    f"{payload.available_minutes} 分钟。"
                ),
                resolution="缩短计划课时或确认可用时间后重新检查。",
            )
        )

    intent = payload.teacher_intent.strip()
    resources = payload.available_resources.strip()
    if any(term in intent for term in DIGITAL_INTENT_TERMS) and any(
        term in resources for term in NO_DEVICE_TERMS
    ):
        conflicts.append(
            ProfessionalInputConflict(
                conflict_id="digital_activity_without_devices",
                severity="blocking",
                field="available_resources",
                message="教师意图包含数字化活动，但资源条件明确表示设备或网络不可用。",
                resolution="改用非数字化活动，或补充可用设备与网络条件后重新检查。",
            )
        )

    if not payload.course_basis.strip():
        assumptions.append("课程依据暂未填写；进入对齐卡后必须通过审核资料补齐依据。")
    if not payload.class_context.strip():
        assumptions.append("班情暂未填写；当前内部样板不据此推断学生能力或教师绩效。")
    if not resources:
        assumptions.append("资源条件暂未填写；默认只使用普通教室可执行的低技术活动。")
    return conflicts, assumptions


async def confirm_professional_input_handler(
    db: AsyncSession,
    user: User,
    payload: ProfessionalInputInput,
    run: SkillRun,
) -> ProfessionalInputOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    run.project_id = project.id
    conflicts, assumptions = evaluate_professional_input(project, payload)
    ready_for_alignment = not any(item.severity == "blocking" for item in conflicts) and (
        not assumptions or payload.assumptions_confirmed
    )
    invalidated_sections = [
        section for section in DOWNSTREAM_SECTIONS if section in source.content
    ]
    confirmed_input = payload.model_dump(
        exclude={"project_id", "assumptions_confirmed"}
    )
    professional_input = {
        "confirmed_input": confirmed_input,
        "conflicts": [item.model_dump() for item in conflicts],
        "assumptions": assumptions,
        "assumptions_confirmed": payload.assumptions_confirmed,
        "ready_for_alignment": ready_for_alignment,
        "memory_refs": list(run.memory_refs),
        "invalidated_sections": invalidated_sections,
    }
    content = deepcopy(source.content)
    for section in DOWNSTREAM_SECTIONS:
        content.pop(section, None)
    content["professional_input"] = professional_input
    content["_trace"] = {
        "skill_run_id": run.id,
        "skill_id": run.skill_id,
        "skill_version": run.skill_version,
        "source_version": source.version_number,
    }
    version = await create_version(db, project, user.id, content, "draft")
    return ProfessionalInputOutput(
        **professional_input,
        version_number=version.version_number,
    )
