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
    ExportArtifactInput,
    ExportArtifactOutput,
    GenerateSectionInput,
    GenerateSectionOutput,
    VersionDiffResponse,
    VersionDiffSection,
)
from src.apps.api.services.diagnostic_rules import evaluate_diagnostic_rules
from src.apps.api.services.knowledge_service import checksum, put_object, search_chunks
from src.apps.api.services.project_service import create_version, get_owned_project

TEMPLATE_VERSION = "word-standard-v2"


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
    professional_input = source.content.get("professional_input")
    if isinstance(professional_input, dict) and not professional_input.get(
        "ready_for_alignment"
    ):
        raise BusinessError(
            "专业输入仍有冲突或未确认假设，请先重新检查",
            status_code=409,
            error_code="professional_input_not_ready",
        )
    search_result = await search_chunks(
        db,
        project_id=project.id,
        user_id=user.id,
        query=payload.basis_query,
        limit=5,
    )
    citations = [BasisCitation(**row) for row in search_result.citations]
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
    # 诊断维度由规则字典 v2 驱动（services/diagnostic_rules.py），新增维度只需注册规则。
    checks, blocking = evaluate_diagnostic_rules(
        {
            "alignment_card": alignment,
            "design_blueprint": blueprint,
            "lesson_design": design,
        }
    )
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


def _paragraph(text: object, *, style: str = "Normal", bold: bool = False) -> str:
    run_properties = "<w:b/>" if bold else ""
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f'<w:r><w:rPr>{run_properties}</w:rPr><w:t xml:space="preserve">'
        f"{escape(str(text))}</w:t></w:r></w:p>"
    )


def _bullet(text: object) -> str:
    return _paragraph(f"• {text}")


def _table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object, *, header: bool = False) -> str:
        shading = '<w:shd w:val="clear" w:fill="DDE8E2"/>' if header else ""
        return (
            f"<w:tc><w:tcPr>{shading}<w:tcMar>"
            '<w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/>'
            f"</w:tcMar></w:tcPr>{_paragraph(value, bold=header)}</w:tc>"
        )

    border = '<w:sz w:val="4"/><w:val w:val="single"/><w:color w:val="B7C8BF"/>'
    table_properties = (
        '<w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="autofit"/>'
        f"<w:tblBorders><w:top>{border}</w:top><w:left>{border}</w:left>"
        f"<w:bottom>{border}</w:bottom><w:right>{border}</w:right>"
        f"<w:insideH>{border}</w:insideH><w:insideV>{border}</w:insideV>"
        "</w:tblBorders></w:tblPr>"
    )
    header_row = "<w:tr>" + "".join(cell(item, header=True) for item in headers) + "</w:tr>"
    body_rows = ["<w:tr>" + "".join(cell(item) for item in row) + "</w:tr>" for row in rows]
    return f"<w:tbl>{table_properties}{header_row}{''.join(body_rows)}</w:tbl>{_paragraph('')}"


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="100" w:line="320" '
        'w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/>'
        '<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn '
        'w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/>'
        '</w:pPr><w:rPr><w:b/><w:color w:val="173F35"/><w:sz w:val="36"/>'
        '<w:szCs w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="260" '
        'w:after="120"/></w:pPr><w:rPr><w:b/><w:color w:val="173F35"/><w:sz w:val="28"/>'
        '<w:szCs w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
        '<w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="160" '
        'w:after="80"/></w:pPr><w:rPr><w:b/><w:color w:val="286B58"/><w:sz w:val="23"/>'
        '<w:szCs w:val="23"/></w:rPr></w:style></w:styles>'
    )


def build_docx(project: TeachingProject, content: dict) -> bytes:
    """生成带标题、列表和教学表格的可交付 Word 成果。"""
    alignment = content.get("alignment_card", {})
    blueprint = content.get("design_blueprint", {})
    design = content.get("lesson_design", {})
    diagnosis = content.get("diagnosis", {})

    parts = [
        _paragraph(project.title, style="Title"),
        _paragraph(f"{project.stage} · {project.course_type}", bold=True),
        _paragraph("课程依据对齐卡", style="Heading1"),
        _paragraph("核心议题", style="Heading2"),
        _paragraph(alignment.get("core_question", "待补")),
        _paragraph("教学目标", style="Heading2"),
        *[_bullet(item) for item in alignment.get("objectives", [])],
    ]
    citations = alignment.get("citations", [])
    if citations:
        parts.append(_paragraph("依据引用", style="Heading2"))
        parts.extend(
            _bullet(
                f"{item.get('filename', '未知资料')} · {item.get('location_label', '位置待补')}"
                f" · 相关度 {item.get('relevance', '-')}"
            )
            for item in citations
        )
    for warning in alignment.get("warnings", []):
        parts.append(_paragraph(f"提示：{warning}"))

    learning_tasks = blueprint.get("learning_tasks", [])
    parts.extend(
        [
            _paragraph("目标—证据—任务蓝图", style="Heading1"),
            _paragraph("评价证据", style="Heading2"),
            *[_bullet(item) for item in blueprint.get("evidence", [])],
            _table(
                ["序号", "学习任务", "时间", "评价证据"],
                [
                    [
                        index,
                        item.get("title", ""),
                        f"{item.get('minutes', 0)} 分钟",
                        item.get("evidence", ""),
                    ]
                    for index, item in enumerate(learning_tasks, 1)
                ],
            ),
        ]
    )

    activities = design.get("activities", [])
    parts.extend(
        [
            _paragraph(design.get("section_name", "课时设计"), style="Heading1"),
            _paragraph("课堂导入", style="Heading2"),
            _paragraph(design.get("opening", "待补")),
            _table(
                ["环节", "时间", "教师活动", "学生活动", "评价证据"],
                [
                    [
                        item.get("title", ""),
                        f"{item.get('minutes', 0)} 分钟",
                        item.get("teacher_action", ""),
                        item.get("student_action", ""),
                        item.get("evidence", ""),
                    ]
                    for item in activities
                ],
            ),
            _paragraph("教师提示", style="Heading2"),
            *[_bullet(item) for item in design.get("teacher_notes", [])],
        ]
    )

    status_labels = {"aligned": "符合", "needs_attention": "需关注"}
    diagnosis_items = diagnosis.get("items", [])
    parts.extend(
        [
            _paragraph("形成性诊断", style="Heading1"),
            _paragraph(diagnosis.get("conclusion", "待完成诊断"), bold=True),
            _table(
                ["诊断维度", "状态", "证据", "改进建议"],
                [
                    [
                        item.get("dimension", ""),
                        status_labels.get(item.get("status", ""), item.get("status", "")),
                        item.get("evidence", ""),
                        item.get("suggestion", ""),
                    ]
                    for item in diagnosis_items
                ],
            ),
        ]
    )
    blocking_issues = diagnosis.get("blocking_issues", [])
    if blocking_issues:
        parts.append(_paragraph("阻断问题", style="Heading2"))
        parts.extend(_bullet(item) for item in blocking_issues)

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(parts)}<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" '
        'w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    document_relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/_rels/document.xml.rels", document_relationships)
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
