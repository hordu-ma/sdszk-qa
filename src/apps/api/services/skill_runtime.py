"""产品 Skills 运行时：注册表、权限、Schema 校验、Memory 注入与 SkillRun 审计。

对齐开发计划 §2.5.1/§2.5.3 与 WP1.3b：
- 业务路由只做鉴权与入参编排，Skill 执行统一经 `run_skill`。
- 代码内注册表是阶段 1A 的事实来源；`skill_definitions` 表提供运维
  可见性与 status 停用开关。
- Memory 只经用户显式传入的 `memory_refs` 进入 Skill 输入，注入前
  校验归属并写 MemoryInjectionAudit；不写入不可见系统指令旁路。
- 其余阶段 1 Skills 的输入输出 Schema 属阶段 0《产品 Skills 目录 v1》
  冻结范围，本运行时不代替专家发明契约。
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.logging_config import logger
from src.apps.api.models import (
    ClassContextProfile,
    MemoryInjectionAudit,
    SkillDefinition,
    SkillRun,
    User,
    UserPreference,
)
from src.apps.api.schemas.workbench import (
    AlignmentCardInput,
    AlignmentCardOutput,
    DesignBlueprintInput,
    DesignBlueprintOutput,
    DiagnoseArtifactInput,
    DiagnoseArtifactOutput,
    ExportArtifactInput,
    ExportArtifactOutput,
    GenerateSectionInput,
    GenerateSectionOutput,
    MemoryRef,
    ProfessionalInputInput,
    ProfessionalInputOutput,
    RetrieveBasisInput,
    RetrieveBasisOutput,
)
from src.apps.api.services.knowledge_service import retrieve_basis_handler
from src.apps.api.services.professional_input_service import (
    RULE_SET_VERSION as PROFESSIONAL_INPUT_RULE_SET_VERSION,
)
from src.apps.api.services.professional_input_service import confirm_professional_input_handler
from src.apps.api.services.structured_generation_service import (
    generate_structured_content_handler,
)
from src.apps.api.services.vertical_sample_service import (
    alignment_card_handler,
    design_blueprint_handler,
    diagnose_artifact_handler,
    export_artifact_handler,
)

SkillHandler = Callable[[AsyncSession, User, BaseModel, SkillRun], Awaitable[BaseModel]]


@dataclass(frozen=True)
class RegisteredSkill:
    """代码内 Skill 注册项（阶段 1A 事实来源）。"""

    skill_id: str
    skill_version: str
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: SkillHandler
    execution_mode: str = "sync"
    maturity: str = "baseline"
    required_roles: tuple[str, ...] = ()  # 空表示所有已认证用户
    quota_class: str = "standard"
    timeout_ms: int = 30_000
    max_retries: int = 0
    model_logic_name: str | None = None
    rule_set_version: str | None = None
    knowledge_scope: str | None = None
    degradation_policy: str | None = None


SKILL_REGISTRY: dict[str, RegisteredSkill] = {}


def register_skill(skill: RegisteredSkill) -> None:
    if "score" in skill.skill_id or "rank" in skill.skill_id:
        raise ValueError("禁止注册评分/排名类 Skill（计划 §2.4 非范围）")
    SKILL_REGISTRY[skill.skill_id] = skill


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def input_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def ensure_definition(db: AsyncSession, skill: RegisteredSkill) -> SkillDefinition:
    """按代码注册表懒同步 skill_definitions 行；status 以数据库为准（运维开关）。"""
    result = await db.execute(
        select(SkillDefinition).where(SkillDefinition.skill_id == skill.skill_id)
    )
    definition = result.scalar_one_or_none()
    if definition is None:
        definition = SkillDefinition(
            skill_id=skill.skill_id,
            skill_version=skill.skill_version,
            name=skill.name,
            execution_mode=skill.execution_mode,
            maturity=skill.maturity,
            input_schema=skill.input_model.model_json_schema(),
            output_schema=skill.output_model.model_json_schema(),
            required_roles=list(skill.required_roles),
            quota_class=skill.quota_class,
            timeout_ms=skill.timeout_ms,
            max_retries=skill.max_retries,
            model_logic_name=skill.model_logic_name,
            rule_set_version=skill.rule_set_version,
            knowledge_scope=skill.knowledge_scope,
            degradation_policy=skill.degradation_policy,
        )
        db.add(definition)
        await db.flush()
    elif definition.skill_version != skill.skill_version:
        definition.skill_version = skill.skill_version
        definition.input_schema = skill.input_model.model_json_schema()
        definition.output_schema = skill.output_model.model_json_schema()
        definition.maturity = skill.maturity
        definition.execution_mode = skill.execution_mode
        definition.required_roles = list(skill.required_roles)
        definition.quota_class = skill.quota_class
        definition.timeout_ms = skill.timeout_ms
        definition.max_retries = skill.max_retries
        definition.model_logic_name = skill.model_logic_name
        definition.rule_set_version = skill.rule_set_version
        definition.knowledge_scope = skill.knowledge_scope
        definition.degradation_policy = skill.degradation_policy
        await db.flush()
    return definition


async def sync_skill_registry(db: AsyncSession) -> None:
    """应用启动时同步全部注册 Skill 到数据库（运维可见性）。"""
    for skill in SKILL_REGISTRY.values():
        await ensure_definition(db, skill)
    await db.commit()


async def resolve_memory_refs(db: AsyncSession, user: User, refs: list[MemoryRef]) -> list[dict]:
    """解析用户显式确认的记忆引用；已删除或越权引用一律拒绝。"""
    resolved: list[dict] = []
    for ref in refs:
        if ref.memory_type == "user_preference":
            result = await db.execute(
                select(UserPreference).where(
                    UserPreference.id == ref.memory_id,
                    UserPreference.user_id == user.id,
                )
            )
            item = result.scalar_one_or_none()
            snapshot = (
                None
                if item is None
                else {
                    "default_stage": item.default_stage,
                    "default_course_type": item.default_course_type,
                    "textbook_version": item.textbook_version,
                    "export_template": item.export_template,
                    "extra": item.extra,
                }
            )
        else:
            result = await db.execute(
                select(ClassContextProfile).where(
                    ClassContextProfile.id == ref.memory_id,
                    ClassContextProfile.user_id == user.id,
                )
            )
            profile = result.scalar_one_or_none()
            item = profile
            snapshot = (
                None if profile is None else {"name": profile.name, "context": profile.context}
            )
        if item is None or snapshot is None:
            raise BusinessError(
                "记忆引用不存在或已清除，请重新确认后再执行",
                status_code=422,
                error_code="memory_ref_not_found",
            )
        resolved.append(
            {
                "memory_type": ref.memory_type,
                "memory_id": ref.memory_id,
                "snapshot": snapshot,
            }
        )
    return resolved


async def run_skill(
    db: AsyncSession,
    *,
    skill_id: str,
    user: User,
    payload: dict,
    memory_refs: list[MemoryRef] | None = None,
) -> tuple[SkillRun, BaseModel]:
    """统一 Skill 执行入口：权限 → 校验 → 注入审计 → 执行 → 运行留痕。"""
    skill = SKILL_REGISTRY.get(skill_id)
    if skill is None:
        raise BusinessError("Skill 不存在", status_code=404, error_code="skill_not_found")
    definition = await ensure_definition(db, skill)
    if definition.status != "enabled":
        raise BusinessError("Skill 已停用", status_code=409, error_code="skill_disabled")
    if skill.required_roles and user.role not in skill.required_roles:
        raise BusinessError(
            "当前角色无权执行该 Skill", status_code=403, error_code="skill_forbidden"
        )
    try:
        validated = skill.input_model(**payload)
    except ValidationError as exc:
        raise BusinessError(
            f"Skill 输入不符合契约: {exc.errors()[0].get('msg', 'invalid')}",
            status_code=422,
            error_code="skill_input_invalid",
        ) from exc

    refs = memory_refs or []
    resolved_memory = await resolve_memory_refs(db, user, refs)

    run = SkillRun(
        user_id=user.id,
        skill_id=skill.skill_id,
        skill_version=skill.skill_version,
        status="running",
        input_hash=input_hash(payload),
        memory_refs=[
            {"memory_type": item["memory_type"], "memory_id": item["memory_id"]}
            for item in resolved_memory
        ],
        input_payload=payload,
        started_at=_utcnow(),
    )
    db.add(run)
    await db.flush()
    for item in resolved_memory:
        db.add(
            MemoryInjectionAudit(
                user_id=user.id,
                skill_run_id=run.id,
                memory_type=item["memory_type"],
                memory_id=item["memory_id"],
                snapshot=item["snapshot"],
            )
        )

    try:
        output = await skill.handler(db, user, validated, run)
    except Exception as exc:
        run.status = "failed"
        run.error_code = getattr(exc, "error_code", None) or "skill_execution_error"
        run.error_message = str(exc)[:1000]
        run.finished_at = _utcnow()
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("SkillRun 失败留痕写入失败", skill_id=skill_id, run_id=run.id)
        raise

    run.status = "completed"
    run.output_payload = output.model_dump()
    run.finished_at = _utcnow()
    await db.commit()
    await db.refresh(run)
    return run, output


# ---- 阶段 1 Skill 注册：查依据—备课—诊断—导出纵向样板 ----

register_skill(
    RegisteredSkill(
        skill_id="skill.retrieve_basis",
        skill_version="1.2.0",
        name="检索课标/教材/政策依据",
        input_model=RetrieveBasisInput,
        output_model=RetrieveBasisOutput,
        handler=retrieve_basis_handler,  # pyright: ignore[reportArgumentType]
        maturity="baseline",
        knowledge_scope="approved_project_documents",
        degradation_policy="explicit_insufficient_basis",
    )
)

register_skill(
    RegisteredSkill(
        skill_id="skill.confirm_professional_input",
        skill_version="1.1.0",
        name="确认专业输入并检查显式冲突",
        input_model=ProfessionalInputInput,
        output_model=ProfessionalInputOutput,
        handler=confirm_professional_input_handler,  # pyright: ignore[reportArgumentType]
        maturity="vertical_sample",
        rule_set_version=PROFESSIONAL_INPUT_RULE_SET_VERSION,
        degradation_policy="save_assumptions_and_block_unresolved_conflicts",
    )
)

register_skill(
    RegisteredSkill(
        skill_id="skill.alignment_card",
        skill_version="1.0.0",
        name="生成课程依据对齐卡",
        input_model=AlignmentCardInput,
        output_model=AlignmentCardOutput,
        handler=alignment_card_handler,  # pyright: ignore[reportArgumentType]
        maturity="vertical_sample",
        knowledge_scope="approved_project_documents",
        degradation_policy="draft_with_basis_warning",
    )
)

register_skill(
    RegisteredSkill(
        skill_id="skill.design_blueprint",
        skill_version="1.0.0",
        name="生成目标—证据—任务蓝图",
        input_model=DesignBlueprintInput,
        output_model=DesignBlueprintOutput,
        handler=design_blueprint_handler,  # pyright: ignore[reportArgumentType]
        maturity="vertical_sample",
        rule_set_version="high-school-inquiry-v1",
        degradation_policy="require_alignment_card",
    )
)

register_skill(
    RegisteredSkill(
        skill_id="skill.generate_section",
        skill_version="1.1.0",
        name="结构化生成、局部重生成与多成果派生",
        input_model=GenerateSectionInput,
        output_model=GenerateSectionOutput,
        handler=generate_structured_content_handler,  # pyright: ignore[reportArgumentType]
        maturity="vertical_sample",
        rule_set_version="stage2-structured-gen-v1",
        degradation_policy="require_blueprint_and_preserve_locked_paths",
    )
)

register_skill(
    RegisteredSkill(
        skill_id="skill.diagnose_artifact",
        skill_version="1.0.0",
        name="执行证据化轻量诊断",
        input_model=DiagnoseArtifactInput,
        output_model=DiagnoseArtifactOutput,
        handler=diagnose_artifact_handler,  # pyright: ignore[reportArgumentType]
        maturity="vertical_sample",
        rule_set_version="high-school-inquiry-v1",
        degradation_policy="return_attention_items_without_total_value",
    )
)

register_skill(
    RegisteredSkill(
        skill_id="skill.export_artifact",
        skill_version="1.0.0",
        name="导出标准 Word 教学成果",
        input_model=ExportArtifactInput,
        output_model=ExportArtifactOutput,
        handler=export_artifact_handler,  # pyright: ignore[reportArgumentType]
        maturity="vertical_sample",
        degradation_policy="require_diagnosis",
    )
)
