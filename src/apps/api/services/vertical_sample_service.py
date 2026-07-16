"""高中议题式教学纵向样板的受控 Skills 执行体。"""

from __future__ import annotations

import io
import zipfile
from copy import deepcopy
from html import escape
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import ArtifactExport, ProjectVersion, SkillRun, TeachingProject, User
from src.apps.api.schemas.workbench import (
    AlignmentCardInput,
    AlignmentCardOutput,
    BasisCitation,
    DesignBlueprintInput,
    DesignBlueprintOutput,
    DiagnoseArtifactInput,
    DiagnoseArtifactOutput,
    DiagnosisItem,
    ExportArtifactInput,
    ExportArtifactOutput,
    GenerateSectionInput,
    GenerateSectionOutput,
    VersionDiffResponse,
    VersionDiffSection,
)
from src.apps.api.services.knowledge_service import checksum, put_object, search_chunks
from src.apps.api.services.project_service import create_version, get_owned_project

TEMPLATE_VERSION = "word-standard-v1"


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


async def _save_step(
    db: AsyncSession,
    *,
    project: TeachingProject,
    source: ProjectVersion,
    user_id: int,
    step: str,
    payload: dict,
    skill_run: SkillRun,
) -> ProjectVersion:
    content = deepcopy(source.content)
    content[step] = payload
    content["_trace"] = {
        "skill_run_id": skill_run.id,
        "skill_id": skill_run.skill_id,
        "skill_version": skill_run.skill_version,
        "source_version": source.version_number,
    }
    version = await create_version(db, project, user_id, content, "draft")
    return version


def _require_section(content: dict, section: str, message: str) -> dict:
    value = content.get(section)
    if not isinstance(value, dict):
        raise BusinessError(message, status_code=409, error_code="workflow_prerequisite_missing")
    return value


async def alignment_card_handler(
    db: AsyncSession, user: User, payload: AlignmentCardInput, run: SkillRun
) -> AlignmentCardOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    run.project_id = project.id
    rows = await search_chunks(
        db,
        project_id=project.id,
        user_id=user.id,
        query=payload.basis_query,
        limit=5,
    )
    citations = [BasisCitation(**row) for row in rows]
    objectives = [
        f"围绕“{payload.core_question}”解释核心概念并形成有依据的判断",
        f"结合“{payload.topic}”真实情境比较不同选择及其影响",
        "在课堂任务中提出主张、引用依据并回应不同观点",
    ]
    draft = {
        "topic": payload.topic,
        "core_question": payload.core_question,
        "objectives": objectives,
        "basis_summary": [item.content[:180] for item in citations],
        "citations": [item.model_dump() for item in citations],
        "warnings": [] if citations else ["当前审核资料不足，后续设计只能作为待补依据草案"],
    }
    version = await _save_step(
        db,
        project=project,
        source=source,
        user_id=user.id,
        step="alignment_card",
        payload=draft,
        skill_run=run,
    )
    return AlignmentCardOutput(**draft, version_number=version.version_number)


async def design_blueprint_handler(
    db: AsyncSession, user: User, payload: DesignBlueprintInput, run: SkillRun
) -> DesignBlueprintOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    run.project_id = project.id
    alignment = _require_section(source.content, "alignment_card", "请先完成课程依据对齐卡")
    objectives = list(alignment.get("objectives", []))
    if not objectives:
        raise BusinessError(
            "对齐卡缺少教学目标", status_code=409, error_code="alignment_incomplete"
        )
    first = max(5, payload.lesson_minutes // 5)
    second = max(10, payload.lesson_minutes * 2 // 5)
    third = payload.lesson_minutes - first - second
    learning_tasks = [
        {"title": "情境导入与问题提出", "minutes": first, "evidence": "学生初步立场"},
        {"title": "依据研读与观点交锋", "minutes": second, "evidence": "引用原文的论证记录"},
        {"title": "形成判断与行动迁移", "minutes": third, "evidence": "可观察的课堂成果"},
    ]
    draft = {
        "core_question": str(alignment["core_question"]),
        "objectives": objectives,
        "evidence": ["观点陈述", "依据引用", "同伴回应", "迁移建议"],
        "learning_tasks": learning_tasks,
        "lesson_minutes": payload.lesson_minutes,
    }
    version = await _save_step(
        db,
        project=project,
        source=source,
        user_id=user.id,
        step="design_blueprint",
        payload=draft,
        skill_run=run,
    )
    return DesignBlueprintOutput(**draft, version_number=version.version_number)


async def generate_section_handler(
    db: AsyncSession, user: User, payload: GenerateSectionInput, run: SkillRun
) -> GenerateSectionOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    run.project_id = project.id
    blueprint = _require_section(source.content, "design_blueprint", "请先完成目标—证据—任务蓝图")
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
    ]
    draft = {
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
    version = await _save_step(
        db,
        project=project,
        source=source,
        user_id=user.id,
        step="lesson_design",
        payload=draft,
        skill_run=run,
    )
    return GenerateSectionOutput(**draft, version_number=version.version_number)


async def diagnose_artifact_handler(
    db: AsyncSession, user: User, payload: DiagnoseArtifactInput, run: SkillRun
) -> DiagnoseArtifactOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    run.project_id = project.id
    alignment = _require_section(source.content, "alignment_card", "请先完成课程依据对齐卡")
    blueprint = _require_section(source.content, "design_blueprint", "请先完成教学蓝图")
    design = _require_section(source.content, "lesson_design", "请先生成课时设计")
    checks = [
        DiagnosisItem(
            dimension="依据可追溯",
            status="aligned" if alignment.get("citations") else "needs_attention",
            evidence=f"引用片段 {len(alignment.get('citations', []))} 条",
            suggestion="补充并审核权威资料后重新运行对齐卡"
            if not alignment.get("citations")
            else "保留引用卡并在导出前复核有效期",
        ),
        DiagnosisItem(
            dimension="目标—证据一致",
            status="aligned"
            if blueprint.get("objectives") and blueprint.get("evidence")
            else "needs_attention",
            evidence="蓝图同时包含目标与可观察证据",
            suggestion="逐项目标补充对应证据" if not blueprint.get("evidence") else "保持一一对应",
        ),
        DiagnosisItem(
            dimension="任务可实施",
            status="aligned" if design.get("activities") else "needs_attention",
            evidence=f"课时活动 {len(design.get('activities', []))} 个",
            suggestion="补充分工、时长和教师支架"
            if not design.get("activities")
            else "试教后记录调整原因",
        ),
    ]
    blocking = [item.dimension for item in checks if item.status == "needs_attention"]
    draft = {
        "conclusion": "可进入教师确认" if not blocking else "需补充关键证据后再确认",
        "items": [item.model_dump() for item in checks],
        "blocking_issues": blocking,
    }
    version = await _save_step(
        db,
        project=project,
        source=source,
        user_id=user.id,
        step="diagnosis",
        payload=draft,
        skill_run=run,
    )
    return DiagnoseArtifactOutput(**draft, version_number=version.version_number)


def _paragraph(text: str, *, heading: bool = False) -> str:
    style = '<w:pStyle w:val="Heading1"/>' if heading else ""
    return (
        f'<w:p><w:pPr>{style}</w:pPr><w:r><w:t xml:space="preserve">'
        f"{escape(text)}</w:t></w:r></w:p>"
    )


def build_docx(project: TeachingProject, content: dict) -> bytes:
    """用 OOXML 最小包生成可由 Word/LibreOffice 打开的标准导出件。"""
    paragraphs = [_paragraph(project.title, heading=True)]
    alignment = content.get("alignment_card", {})
    blueprint = content.get("design_blueprint", {})
    design = content.get("lesson_design", {})
    diagnosis = content.get("diagnosis", {})
    sections: list[tuple[str, list[str]]] = [
        (
            "课程依据对齐卡",
            [str(alignment.get("core_question", "待补")), *alignment.get("objectives", [])],
        ),
        ("目标—证据—任务蓝图", [str(item) for item in blueprint.get("learning_tasks", [])]),
        (
            str(design.get("section_name", "课时设计")),
            [str(item) for item in design.get("activities", [])],
        ),
        ("形成性诊断", [str(item) for item in diagnosis.get("items", [])]),
    ]
    for title, lines in sections:
        paragraphs.append(_paragraph(title, heading=True))
        paragraphs.extend(_paragraph(line) for line in lines)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(paragraphs)}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


async def export_artifact_handler(
    db: AsyncSession, user: User, payload: ExportArtifactInput, run: SkillRun
) -> ExportArtifactOutput:
    project, source = await _latest_version(db, payload.project_id, user.id)
    run.project_id = project.id
    _require_section(source.content, "diagnosis", "请先完成轻量诊断再导出")
    data = build_docx(project, source.content)
    filename = f"{project.title}-v{source.version_number}.docx".replace("/", "-")
    object_key = f"users/{user.id}/projects/{project.id}/exports/{uuid4().hex}.docx"
    await put_object(
        object_key,
        data,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    artifact = ArtifactExport(
        project_id=project.id,
        user_id=user.id,
        skill_run_id=run.id,
        version_id=source.id,
        filename=filename,
        object_key=object_key,
        checksum_sha256=checksum(data),
        template_version=TEMPLATE_VERSION,
    )
    db.add(artifact)
    await db.flush()
    return ExportArtifactOutput(
        export_id=artifact.id,
        filename=filename,
        download_url=f"/api/workbench/exports/{artifact.id}/download",
        template_version=TEMPLATE_VERSION,
        version_number=source.version_number,
    )


async def diff_versions(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    from_version: int,
    to_version: int,
) -> VersionDiffResponse:
    await get_owned_project(db, project_id, user_id)
    result = await db.execute(
        select(ProjectVersion).where(
            ProjectVersion.project_id == project_id,
            ProjectVersion.version_number.in_([from_version, to_version]),
        )
    )
    by_number = {item.version_number: item for item in result.scalars()}
    if from_version not in by_number or to_version not in by_number:
        raise BusinessError("版本不存在", status_code=404, error_code="version_not_found")
    before = by_number[from_version].content
    after = by_number[to_version].content
    sections = sorted((set(before) | set(after)) - {"_trace"})
    changed = [
        VersionDiffSection(section=key, before=before.get(key), after=after.get(key))
        for key in sections
        if before.get(key) != after.get(key)
    ]
    return VersionDiffResponse(
        project_id=project_id,
        from_version=from_version,
        to_version=to_version,
        changed_sections=changed,
    )
