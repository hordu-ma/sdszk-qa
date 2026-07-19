"""阶段 2 WP2.1 专业输入确认与可扩展冲突规则字典。"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

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

RULE_SET_VERSION = "stage2-input-conflict-v2"
DOWNSTREAM_SECTIONS = (
    "alignment_card",
    "design_blueprint",
    "lesson_design",
    "diagnosis",
    "teaching_artifacts",
    "editor_state",
)
FORBIDDEN_RULE_TOKENS = {
    "score",
    "scores",
    "scoring",
    "rank",
    "ranks",
    "ranking",
    "rankings",
    "rating",
    "ratings",
    "leaderboard",
    "kpi",
}

RuleEvaluator = Callable[
    [TeachingProject, ProfessionalInputInput], ProfessionalInputConflict | None
]


@dataclass(frozen=True)
class ProfessionalInputRule:
    rule_id: str
    fields: tuple[str, ...]
    evaluate: RuleEvaluator


_RULES: OrderedDict[str, ProfessionalInputRule] = OrderedDict()


def _forbidden_hits(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens |= set(re.findall(r"[a-z]+", value.lower()))
    return tokens & FORBIDDEN_RULE_TOKENS


def register_professional_input_rule(rule: ProfessionalInputRule) -> ProfessionalInputRule:
    """注册冲突规则，并阻止评分/排名标识符和重复注册。"""
    hits = _forbidden_hits(rule.rule_id, *rule.fields)
    if hits:
        raise ValueError(f"专业输入规则禁止评分/排名类标识符: {sorted(hits)}")
    if rule.rule_id in _RULES:
        raise ValueError(f"专业输入规则重复注册: {rule.rule_id}")
    _RULES[rule.rule_id] = rule
    return rule


def professional_input_rules() -> tuple[ProfessionalInputRule, ...]:
    return tuple(_RULES.values())


def _conflict(
    conflict_id: str,
    field: str,
    message: str,
    resolution: str,
) -> ProfessionalInputConflict:
    return ProfessionalInputConflict(
        conflict_id=conflict_id,
        severity="blocking",
        field=field,
        message=message,
        resolution=resolution,
    )


def _course_type_conflict(
    project: TeachingProject, payload: ProfessionalInputInput
) -> ProfessionalInputConflict | None:
    if payload.course_type.strip() == project.course_type.strip():
        return None
    return _conflict(
        "course_type_mismatch",
        "course_type",
        f"本次课型“{payload.course_type}”与项目课型“{project.course_type}”不一致。",
        "确认并统一项目课型与本次教学课型后重新检查。",
    )


def _lesson_time_conflict(
    _project: TeachingProject, payload: ProfessionalInputInput
) -> ProfessionalInputConflict | None:
    if payload.lesson_minutes <= payload.available_minutes:
        return None
    return _conflict(
        "lesson_time_exceeds_available",
        "lesson_minutes",
        f"计划课时 {payload.lesson_minutes} 分钟超过可用时间 {payload.available_minutes} 分钟。",
        "缩短计划课时或确认可用时间后重新检查。",
    )


def _digital_resource_conflict(
    _project: TeachingProject, payload: ProfessionalInputInput
) -> ProfessionalInputConflict | None:
    intent_terms = ("数字化", "视频", "在线", "平板", "网络")
    unavailable_terms = ("无设备", "没有设备", "无网络", "不可使用设备", "不具备设备")
    if not any(term in payload.teacher_intent for term in intent_terms) or not any(
        term in payload.available_resources for term in unavailable_terms
    ):
        return None
    return _conflict(
        "digital_activity_without_devices",
        "available_resources",
        "教师意图包含数字化活动，但资源条件明确表示设备或网络不可用。",
        "改用非数字化活动，或补充可用设备与网络条件后重新检查。",
    )


def _objective_activity_conflict(
    _project: TeachingProject, payload: ProfessionalInputInput
) -> ProfessionalInputConflict | None:
    practice_terms = ("实践", "操作", "制作", "演练", "展示")
    if payload.activity_format != "讲授" or not any(
        term in payload.learning_objectives for term in practice_terms
    ):
        return None
    return _conflict(
        "practice_objective_without_activity",
        "activity_format",
        "教学目标包含实践、操作或展示要求，但活动形式仅为讲授。",
        "增加实践/混合活动，或调整教学目标后重新检查。",
    )


def _public_use_resource_conflict(
    _project: TeachingProject, payload: ProfessionalInputInput
) -> ProfessionalInputConflict | None:
    restricted_terms = ("仅内部", "不可公开", "未授权", "禁止传播")
    if payload.intended_use == "日常教学" or not any(
        term in payload.available_resources for term in restricted_terms
    ):
        return None
    return _conflict(
        "restricted_resource_for_public_use",
        "intended_use",
        f"本次用途为“{payload.intended_use}”，但资源条件包含未授权或不可公开限制。",
        "更换为已授权资源，或将用途调整为许可范围内的日常教学。",
    )


def _collaboration_condition_conflict(
    _project: TeachingProject, payload: ProfessionalInputInput
) -> ProfessionalInputConflict | None:
    collaboration_terms = ("小组", "合作", "讨论", "辩论")
    restricted_terms = ("无法分组", "不可分组", "不可讨论", "禁止讨论")
    if not any(term in payload.teacher_intent for term in collaboration_terms) or not any(
        term in payload.class_context for term in restricted_terms
    ):
        return None
    return _conflict(
        "collaboration_condition_conflict",
        "class_context",
        "教师意图要求合作或讨论，但班情条件明确表示无法开展。",
        "调整活动组织方式，或确认可解除的班情限制后重新检查。",
    )


register_professional_input_rule(
    ProfessionalInputRule("course_type_mismatch", ("course_type",), _course_type_conflict)
)
register_professional_input_rule(
    ProfessionalInputRule(
        "lesson_time_exceeds_available",
        ("lesson_minutes", "available_minutes"),
        _lesson_time_conflict,
    )
)
register_professional_input_rule(
    ProfessionalInputRule(
        "digital_activity_without_devices",
        ("teacher_intent", "available_resources"),
        _digital_resource_conflict,
    )
)
register_professional_input_rule(
    ProfessionalInputRule(
        "practice_objective_without_activity",
        ("learning_objectives", "activity_format"),
        _objective_activity_conflict,
    )
)
register_professional_input_rule(
    ProfessionalInputRule(
        "restricted_resource_for_public_use",
        ("intended_use", "available_resources"),
        _public_use_resource_conflict,
    )
)
register_professional_input_rule(
    ProfessionalInputRule(
        "collaboration_condition_conflict",
        ("teacher_intent", "class_context"),
        _collaboration_condition_conflict,
    )
)


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
    conflicts = [
        conflict
        for rule in _RULES.values()
        if (conflict := rule.evaluate(project, payload)) is not None
    ]
    assumptions: list[str] = []
    if not payload.course_basis.strip():
        assumptions.append("课程依据暂未填写；进入对齐卡后必须通过审核资料补齐依据。")
    if not payload.learning_objectives.strip():
        assumptions.append("教学目标暂未填写；进入蓝图前必须由教师确认目标。")
    if not payload.class_context.strip():
        assumptions.append("班情暂未填写；当前内部样板不据此推断学生能力或教师绩效。")
    if not payload.available_resources.strip():
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
        "rule_set_version": RULE_SET_VERSION,
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
        "rule_set_version": RULE_SET_VERSION,
    }
    version = await create_version(db, project, user.id, content, "draft")
    return ProfessionalInputOutput(
        **professional_input,
        version_number=version.version_number,
    )
