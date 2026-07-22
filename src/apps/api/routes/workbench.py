"""阶段 1A 教学工作台路由。"""

from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select

from src.apps.api.config import settings
from src.apps.api.dependencies import CurrentUser, DbSession, get_pilot_user
from src.apps.api.models import (
    ArtifactExport,
    KnowledgeDocument,
    KnowledgeIndexVersion,
    ModelAsset,
    ProjectVersion,
    TaskRun,
    TeachingProject,
)
from src.apps.api.schemas.workbench import (
    AlignmentCardOutput,
    AlignmentCardRequest,
    AlignmentCardResponse,
    ApplyRevisionOutput,
    ApplyRevisionRequest,
    ApplyRevisionResponse,
    ClassProfileCreate,
    ClassProfileResponse,
    DesignBlueprintOutput,
    DesignBlueprintRequest,
    DesignBlueprintResponse,
    DiagnoseArtifactOutput,
    DiagnoseArtifactRequest,
    DiagnoseArtifactResponse,
    DiagnosisDecisionRequest,
    DiagnosisStructureConfirm,
    DiagnosisStructureNode,
    DocumentResponse,
    DocumentReviewRequest,
    EvaluationCaseBulkImport,
    EvaluationCaseCreate,
    EvaluationCaseResponse,
    EvaluationCaseResultResponse,
    EvaluationCaseReviewCreate,
    EvaluationCaseReviewResponse,
    EvaluationDatasetCreate,
    EvaluationDatasetReportResponse,
    EvaluationDatasetResponse,
    EvaluationDatasetReviewRequest,
    EvaluationGateReportResponse,
    EvaluationRunResponse,
    ExportArtifactOutput,
    ExportArtifactRequest,
    ExportArtifactResponse,
    GenerateSectionOutput,
    GenerateSectionRequest,
    GenerateSectionResponse,
    KnowledgeIndexVersionResponse,
    L4SignalSummaryResponse,
    MemoryClearResponse,
    MemoryExportResponse,
    ModelAssetResponse,
    PinnedItemCreate,
    PinnedItemResponse,
    ProfessionalInputOutput,
    ProfessionalInputRequest,
    ProfessionalInputResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectVersionCreate,
    ProjectVersionLockUpdate,
    ProjectVersionResponse,
    ProjectVersionRestore,
    RetrieveBasisOutput,
    RetrieveBasisRequest,
    RetrieveBasisResponse,
    SkillInfo,
    SpotCheckDetailResponse,
    SpotCheckItemResponse,
    SpotCheckQueueResponse,
    SpotCheckReviewCreate,
    SpotCheckReviewResponse,
    SpotCheckSampleRequest,
    TaskResponse,
    UploadAccepted,
    UserPreferenceResponse,
    UserPreferenceUpdate,
    VersionDiffResponse,
)
from src.apps.api.services.audit import write_audit_log
from src.apps.api.services.diagnosis_workflow_service import (
    confirm_diagnosis_structure,
    detect_diagnosis_structure,
    save_diagnosis_decision,
)
from src.apps.api.services.evaluation_gate_service import regression_gate_report
from src.apps.api.services.evaluation_service import (
    EvaluationCaseInput,
    add_case,
    add_cases_bulk,
    create_dataset,
    dataset_report,
    freeze_dataset,
    get_owned_run,
    list_case_reviews,
    list_dataset_cases,
    list_datasets,
    list_review_queue,
    list_run_results,
    review_dataset,
    run_dataset,
    submit_case_review,
)
from src.apps.api.services.knowledge_service import (
    SUPPORTED_SUFFIXES,
    UploadContentError,
    checksum,
    get_object,
    process_document_task,
    put_object,
    rebuild_project_index,
    validate_upload_content,
)
from src.apps.api.services.memory_service import (
    clear_memory,
    create_class_profile,
    create_pinned_item,
    delete_class_profile,
    delete_pinned_item,
    get_preference,
    list_class_profiles,
    list_pinned_items,
    upsert_preference,
)
from src.apps.api.services.project_service import create_version, get_owned_project
from src.apps.api.services.rbac import owner_in_actor_scope
from src.apps.api.services.signal_summary_service import l4_signal_summary
from src.apps.api.services.skill_runtime import SKILL_REGISTRY, ensure_definition, run_skill
from src.apps.api.services.spot_check_service import (
    SPOT_CHECK_DISCLAIMER,
    get_spot_check_detail,
    list_spot_checks,
    queue_status_counts,
    sample_spot_checks,
    submit_spot_check_review,
)
from src.apps.api.services.structured_generation_service import (
    restore_project_version,
    save_teacher_edit_version,
    update_version_locks,
)
from src.apps.api.services.vertical_sample_service import diff_versions

# WP2.5：整个工作台受试点白名单门禁保护（平台 admin 放行，其余须属白名单组织）
router = APIRouter(dependencies=[Depends(get_pilot_user)])


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: Request,
    data: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    project = TeachingProject(owner_id=current_user.id, **data.model_dump())
    db.add(project)
    await db.flush()
    await create_version(db, project, current_user.id, {}, "draft")
    await write_audit_log(
        db,
        request,
        "create_teaching_project",
        current_user.id,
        "teaching_project",
        str(project.id),
    )
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(db: DbSession, current_user: CurrentUser) -> list[ProjectResponse]:
    result = await db.execute(
        select(TeachingProject)
        .where(TeachingProject.owner_id == current_user.id)
        .order_by(TeachingProject.updated_at.desc())
    )
    return [ProjectResponse.model_validate(item) for item in result.scalars()]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: DbSession, current_user: CurrentUser) -> ProjectResponse:
    project = await get_owned_project(db, project_id, current_user.id)
    return ProjectResponse.model_validate(project)


@router.post(
    "/projects/{project_id}/versions",
    response_model=ProjectVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_version(
    project_id: int,
    data: ProjectVersionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectVersionResponse:
    version = await save_teacher_edit_version(
        db,
        project_id=project_id,
        user_id=current_user.id,
        proposed_content=data.content,
        status=data.status,
        source_version=data.source_version,
    )
    await db.commit()
    await db.refresh(version)
    return ProjectVersionResponse.model_validate(version)


@router.post(
    "/projects/{project_id}/versions/locks",
    response_model=ProjectVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def update_project_version_locks(
    project_id: int,
    data: ProjectVersionLockUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectVersionResponse:
    version = await update_version_locks(
        db,
        project_id=project_id,
        user_id=current_user.id,
        source_version=data.source_version,
        paths=data.locked_paths,
    )
    await db.commit()
    await db.refresh(version)
    return ProjectVersionResponse.model_validate(version)


@router.post(
    "/projects/{project_id}/versions/restore",
    response_model=ProjectVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def restore_project_version_route(
    project_id: int,
    data: ProjectVersionRestore,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectVersionResponse:
    version = await restore_project_version(
        db,
        project_id=project_id,
        user_id=current_user.id,
        source_version=data.source_version,
        restore_version=data.restore_version,
    )
    await db.commit()
    await db.refresh(version)
    return ProjectVersionResponse.model_validate(version)


@router.get("/projects/{project_id}/versions", response_model=list[ProjectVersionResponse])
async def list_project_versions(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProjectVersionResponse]:
    await get_owned_project(db, project_id, current_user.id)
    result = await db.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
    )
    return [ProjectVersionResponse.model_validate(item) for item in result.scalars()]


@router.get("/projects/{project_id}/versions/diff", response_model=VersionDiffResponse)
async def compare_project_versions(
    project_id: int,
    from_version: int,
    to_version: int,
    db: DbSession,
    current_user: CurrentUser,
) -> VersionDiffResponse:
    return await diff_versions(
        db,
        project_id=project_id,
        user_id=current_user.id,
        from_version=from_version,
        to_version=to_version,
    )


@router.post(
    "/projects/{project_id}/documents",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    request: Request,
    project_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
    valid_from: Annotated[datetime | None, Form()] = None,
    valid_until: Annotated[datetime | None, Form()] = None,
) -> UploadAccepted:
    await get_owned_project(db, project_id, current_user.id)
    filename = Path(file.filename or "document.txt").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=415, detail="仅支持 DOCX、文本型 PDF、Markdown 和 TXT")
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="上传文件为空")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过上传大小限制")
    try:
        validate_upload_content(filename, data)
    except UploadContentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    digest = checksum(data)
    idempotency_key = f"document:{project_id}:{digest}"
    existing_task_result = await db.execute(
        select(TaskRun).where(TaskRun.idempotency_key == idempotency_key)
    )
    existing_task = existing_task_result.scalar_one_or_none()
    if existing_task is not None:
        document = await db.get(KnowledgeDocument, int(existing_task.input_payload["document_id"]))
        if document is not None:
            return UploadAccepted(
                document=DocumentResponse.model_validate(document),
                task=TaskResponse.model_validate(existing_task),
            )

    object_key = f"users/{current_user.id}/projects/{project_id}/{uuid4().hex}-{filename}"
    await put_object(object_key, data, file.content_type or "application/octet-stream")
    if valid_from is not None and valid_until is not None and valid_from > valid_until:
        raise HTTPException(status_code=422, detail="资料生效时间不能晚于失效时间")
    document = KnowledgeDocument(
        project_id=project_id,
        owner_id=current_user.id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        object_key=object_key,
        checksum_sha256=digest,
        status="processing",
        review_status="pending",
        valid_from=valid_from.replace(tzinfo=None) if valid_from else None,
        valid_until=valid_until.replace(tzinfo=None) if valid_until else None,
    )
    db.add(document)
    await db.flush()
    task = TaskRun(
        user_id=current_user.id,
        project_id=project_id,
        task_type="document_parse",
        status="queued",
        progress=0,
        idempotency_key=idempotency_key,
        input_payload={"document_id": document.id, "filename": filename},
    )
    db.add(task)
    await db.flush()
    await write_audit_log(
        db,
        request,
        "upload_knowledge_document",
        current_user.id,
        "knowledge_document",
        str(document.id),
        {"task_id": task.id, "checksum_sha256": digest},
    )
    await db.commit()
    await db.refresh(document)
    await db.refresh(task)
    background_tasks.add_task(process_document_task, task.id, document.id)
    return UploadAccepted(
        document=DocumentResponse.model_validate(document),
        task=TaskResponse.model_validate(task),
    )


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    project_id: int, db: DbSession, current_user: CurrentUser
) -> list[DocumentResponse]:
    await get_owned_project(db, project_id, current_user.id)
    result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.owner_id == current_user.id,
        )
        .order_by(KnowledgeDocument.created_at.desc())
    )
    return [DocumentResponse.model_validate(item) for item in result.scalars()]


@router.post("/documents/{document_id}/review", response_model=DocumentResponse)
async def review_document(
    request: Request,
    document_id: int,
    data: DocumentReviewRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentResponse:
    # WP2.5：审核员/管理员可审核资料，但 reviewer 仅限本组织成员的资料；
    # 平台 admin 覆盖全部（跨组织隔离缺口，见《WP2.5 收口记录》）。
    if current_user.role not in {"admin", "reviewer"}:
        raise HTTPException(status_code=403, detail="只有审核员或管理员可以审核资料")
    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    if not await owner_in_actor_scope(db, actor=current_user, owner_id=document.owner_id):
        raise HTTPException(status_code=403, detail="无权审核其他组织的资料")
    document.review_status = data.review_status
    await write_audit_log(
        db,
        request,
        "review_knowledge_document",
        current_user.id,
        "knowledge_document",
        str(document.id),
        {"review_status": data.review_status},
    )
    await db.commit()
    await db.refresh(document)
    return DocumentResponse.model_validate(document)


@router.get("/skills", response_model=list[SkillInfo])
async def list_skills(db: DbSession, current_user: CurrentUser) -> list[SkillInfo]:
    """列出注册 Skills 及成熟度；status 以数据库运维开关为准。"""
    del current_user
    items: list[SkillInfo] = []
    for skill in SKILL_REGISTRY.values():
        definition = await ensure_definition(db, skill)
        items.append(
            SkillInfo(
                skill_id=skill.skill_id,
                skill_version=skill.skill_version,
                name=skill.name,
                status=definition.status,
                execution_mode=skill.execution_mode,
                maturity=skill.maturity,
                required_roles=list(skill.required_roles),
                quota_class=skill.quota_class,
                timeout_ms=skill.timeout_ms,
                degradation_policy=skill.degradation_policy,
            )
        )
    await db.commit()
    return items


@router.post("/skills/retrieve-basis", response_model=RetrieveBasisResponse)
async def run_retrieve_basis(
    data: RetrieveBasisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RetrieveBasisResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.retrieve_basis",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, RetrieveBasisOutput)
    return RetrieveBasisResponse(
        skill_run_id=run.id,
        skill_version=run.skill_version,
        insufficient_basis=output.insufficient_basis,
        insufficiency_reason=output.insufficiency_reason,
        retrieval_mode=output.retrieval_mode,
        citations=output.citations,
    )


@router.post(
    "/skills/confirm-professional-input",
    response_model=ProfessionalInputResponse,
)
async def run_confirm_professional_input(
    data: ProfessionalInputRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ProfessionalInputResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.confirm_professional_input",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, ProfessionalInputOutput)
    return ProfessionalInputResponse(
        skill_run_id=run.id,
        skill_version=run.skill_version,
        **output.model_dump(),
    )


@router.post("/skills/alignment-card", response_model=AlignmentCardResponse)
async def run_alignment_card(
    data: AlignmentCardRequest, db: DbSession, current_user: CurrentUser
) -> AlignmentCardResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.alignment_card",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, AlignmentCardOutput)
    return AlignmentCardResponse(
        skill_run_id=run.id, skill_version=run.skill_version, **output.model_dump()
    )


@router.post("/skills/design-blueprint", response_model=DesignBlueprintResponse)
async def run_design_blueprint(
    data: DesignBlueprintRequest, db: DbSession, current_user: CurrentUser
) -> DesignBlueprintResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.design_blueprint",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, DesignBlueprintOutput)
    return DesignBlueprintResponse(
        skill_run_id=run.id, skill_version=run.skill_version, **output.model_dump()
    )


@router.post("/skills/generate-section", response_model=GenerateSectionResponse)
async def run_generate_section(
    data: GenerateSectionRequest, db: DbSession, current_user: CurrentUser
) -> GenerateSectionResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.generate_section",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, GenerateSectionOutput)
    return GenerateSectionResponse(
        skill_run_id=run.id, skill_version=run.skill_version, **output.model_dump()
    )


@router.post("/skills/diagnose-artifact", response_model=DiagnoseArtifactResponse)
async def run_diagnose_artifact(
    data: DiagnoseArtifactRequest, db: DbSession, current_user: CurrentUser
) -> DiagnoseArtifactResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.diagnose_artifact",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, DiagnoseArtifactOutput)
    return DiagnoseArtifactResponse(
        skill_run_id=run.id, skill_version=run.skill_version, **output.model_dump()
    )


@router.get(
    "/projects/{project_id}/diagnosis/structure",
    response_model=list[DiagnosisStructureNode],
)
async def preview_diagnosis_structure(
    project_id: int, db: DbSession, current_user: CurrentUser
) -> list[DiagnosisStructureNode]:
    project = await get_owned_project(db, project_id, current_user.id)
    result = await db.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project.id)
        .order_by(ProjectVersion.version_number.desc())
        .limit(1)
    )
    version = result.scalar_one_or_none()
    if version is None:
        return []
    return detect_diagnosis_structure(version.content)


@router.post(
    "/projects/{project_id}/diagnosis/structure",
    response_model=ProjectVersionResponse,
)
async def confirm_diagnosis_structure_route(
    project_id: int,
    data: DiagnosisStructureConfirm,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectVersionResponse:
    version = await confirm_diagnosis_structure(
        db,
        project_id=project_id,
        user_id=current_user.id,
        source_version=data.source_version,
        nodes=data.nodes,
    )
    await db.commit()
    await db.refresh(version)
    return ProjectVersionResponse.model_validate(version)


@router.post(
    "/projects/{project_id}/diagnosis/items/{item_id}/decision",
    response_model=ProjectVersionResponse,
)
async def decide_diagnosis_item(
    project_id: int,
    item_id: str,
    data: DiagnosisDecisionRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectVersionResponse:
    version = await save_diagnosis_decision(
        db,
        project_id=project_id,
        item_id=item_id,
        user_id=current_user.id,
        request=data,
    )
    await db.commit()
    await db.refresh(version)
    return ProjectVersionResponse.model_validate(version)


@router.post("/skills/apply-revision", response_model=ApplyRevisionResponse)
async def run_apply_revision(
    data: ApplyRevisionRequest, db: DbSession, current_user: CurrentUser
) -> ApplyRevisionResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.apply_revision",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, ApplyRevisionOutput)
    return ApplyRevisionResponse(
        skill_run_id=run.id, skill_version=run.skill_version, **output.model_dump()
    )


@router.post("/skills/export-artifact", response_model=ExportArtifactResponse)
async def run_export_artifact(
    data: ExportArtifactRequest, db: DbSession, current_user: CurrentUser
) -> ExportArtifactResponse:
    run, output = await run_skill(
        db,
        skill_id="skill.export_artifact",
        user=current_user,
        payload=data.model_dump(exclude={"memory_refs"}),
        memory_refs=data.memory_refs,
    )
    assert isinstance(output, ExportArtifactOutput)
    return ExportArtifactResponse(
        skill_run_id=run.id, skill_version=run.skill_version, **output.model_dump()
    )


@router.get("/memory/preference", response_model=UserPreferenceResponse | None)
async def read_preference(
    db: DbSession, current_user: CurrentUser
) -> UserPreferenceResponse | None:
    preference = await get_preference(db, current_user.id)
    if preference is None:
        return None
    return UserPreferenceResponse.model_validate(preference)


@router.put("/memory/preference", response_model=UserPreferenceResponse)
async def write_preference(
    request: Request,
    data: UserPreferenceUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> UserPreferenceResponse:
    preference = await upsert_preference(db, current_user.id, data)
    await write_audit_log(
        db,
        request,
        "update_user_preference",
        current_user.id,
        "user_preference",
        str(preference.id),
    )
    await db.commit()
    await db.refresh(preference)
    return UserPreferenceResponse.model_validate(preference)


@router.get("/memory/class-profiles", response_model=list[ClassProfileResponse])
async def read_class_profiles(
    db: DbSession, current_user: CurrentUser
) -> list[ClassProfileResponse]:
    profiles = await list_class_profiles(db, current_user.id)
    return [ClassProfileResponse.model_validate(item) for item in profiles]


@router.post(
    "/memory/class-profiles",
    response_model=ClassProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_class_profile(
    request: Request,
    data: ClassProfileCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ClassProfileResponse:
    profile = await create_class_profile(db, current_user.id, data)
    await write_audit_log(
        db,
        request,
        "create_class_context_profile",
        current_user.id,
        "class_context_profile",
        str(profile.id),
    )
    await db.commit()
    await db.refresh(profile)
    return ClassProfileResponse.model_validate(profile)


@router.delete("/memory/class-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_class_profile(
    request: Request,
    profile_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    deleted = await delete_class_profile(db, current_user.id, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="班情档案不存在")
    await write_audit_log(
        db,
        request,
        "delete_class_context_profile",
        current_user.id,
        "class_context_profile",
        str(profile_id),
    )
    await db.commit()


@router.get("/memory/pinned-items", response_model=list[PinnedItemResponse])
async def read_pinned_items(db: DbSession, current_user: CurrentUser) -> list[PinnedItemResponse]:
    items = await list_pinned_items(db, current_user.id)
    return [PinnedItemResponse.model_validate(item) for item in items]


@router.post(
    "/memory/pinned-items",
    response_model=PinnedItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_pinned_item(
    request: Request,
    data: PinnedItemCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PinnedItemResponse:
    try:
        item = await create_pinned_item(db, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await write_audit_log(
        db,
        request,
        "create_pinned_memory_item",
        current_user.id,
        "pinned_memory_item",
        str(item.id),
        {"item_type": item.item_type, "project_id": item.project_id},
    )
    await db.commit()
    await db.refresh(item)
    return PinnedItemResponse.model_validate(item)


@router.delete("/memory/pinned-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_pinned_item(
    request: Request,
    item_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    if not await delete_pinned_item(db, current_user.id, item_id):
        raise HTTPException(status_code=404, detail="钉选项不存在")
    await write_audit_log(
        db,
        request,
        "delete_pinned_memory_item",
        current_user.id,
        "pinned_memory_item",
        str(item_id),
    )
    await db.commit()


@router.get("/memory/export", response_model=MemoryExportResponse)
async def export_memory(db: DbSession, current_user: CurrentUser) -> MemoryExportResponse:
    """导出个人记忆清单（计划 WP1.3c）。"""
    preference = await get_preference(db, current_user.id)
    profiles = await list_class_profiles(db, current_user.id)
    pinned_items = await list_pinned_items(db, current_user.id)
    return MemoryExportResponse(
        preference=(UserPreferenceResponse.model_validate(preference) if preference else None),
        class_profiles=[ClassProfileResponse.model_validate(item) for item in profiles],
        pinned_items=[PinnedItemResponse.model_validate(item) for item in pinned_items],
    )


@router.post("/memory/clear", response_model=MemoryClearResponse)
async def clear_all_memory(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> MemoryClearResponse:
    """一键清除本人全部 Memory；清除后的引用不可再注入新 SkillRun。"""
    cleared_preference, cleared_profiles, cleared_pinned_items = await clear_memory(
        db, current_user.id
    )
    await write_audit_log(
        db,
        request,
        "clear_user_memory",
        current_user.id,
        "user_memory",
        str(current_user.id),
        {
            "cleared_preference": cleared_preference,
            "cleared_class_profiles": cleared_profiles,
            "cleared_pinned_items": cleared_pinned_items,
        },
    )
    await db.commit()
    return MemoryClearResponse(
        cleared_preference=cleared_preference,
        cleared_class_profiles=cleared_profiles,
        cleared_pinned_items=cleared_pinned_items,
    )


@router.get("/exports/{export_id}/download")
async def download_export(export_id: int, db: DbSession, current_user: CurrentUser) -> Response:
    result = await db.execute(
        select(ArtifactExport).where(
            ArtifactExport.id == export_id,
            ArtifactExport.user_id == current_user.id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="导出件不存在")
    data = await get_object(artifact.object_key)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(artifact.filename)}"},
    )


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int | None = None,
) -> list[TaskResponse]:
    query = select(TaskRun).where(TaskRun.user_id == current_user.id)
    if project_id is not None:
        query = query.where(TaskRun.project_id == project_id)
    result = await db.execute(query.order_by(TaskRun.created_at.desc()).limit(100))
    return [TaskResponse.model_validate(item) for item in result.scalars()]


async def _owned_task(db: DbSession, task_id: int, user_id: int) -> TaskRun:
    result = await db.execute(
        select(TaskRun).where(TaskRun.id == task_id, TaskRun.user_id == user_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: int, db: DbSession, current_user: CurrentUser) -> TaskResponse:
    task = await _owned_task(db, task_id, current_user.id)
    if task.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="当前任务状态不可取消")
    task.status = "cancelled"
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> TaskResponse:
    task = await _owned_task(db, task_id, current_user.id)
    if task.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="只有失败或已取消任务可以重试")
    document_id = int(task.input_payload["document_id"])
    task.status = "queued"
    task.progress = 0
    task.attempt += 1
    task.error_message = None
    task.finished_at = None
    await db.commit()
    await db.refresh(task)
    background_tasks.add_task(process_document_task, task.id, document_id)
    return TaskResponse.model_validate(task)


@router.get("/model-status")
async def model_status(current_user: CurrentUser) -> dict[str, str | bool]:
    del current_user
    return {
        "logical_model": settings.LLM_LOGICAL_MODEL,
        "provider": settings.LLM_PROVIDER,
        "provider_model": settings.LLM_MODEL,
        "degraded": settings.LLM_PROVIDER.lower() != "vllm",
        "content_mode": settings.CONTENT_MODE,
        "content_disclaimer": settings.CONTENT_DISCLAIMER,
    }


@router.get("/runtime/model-assets", response_model=list[ModelAssetResponse])
async def list_model_assets(db: DbSession, current_user: CurrentUser) -> list[ModelAssetResponse]:
    del current_user
    result = await db.execute(
        select(ModelAsset).order_by(ModelAsset.asset_type, ModelAsset.created_at.desc())
    )
    return [ModelAssetResponse.model_validate(item) for item in result.scalars()]


@router.get(
    "/projects/{project_id}/knowledge-indexes",
    response_model=list[KnowledgeIndexVersionResponse],
)
async def list_knowledge_indexes(
    project_id: int, db: DbSession, current_user: CurrentUser
) -> list[KnowledgeIndexVersionResponse]:
    await get_owned_project(db, project_id, current_user.id)
    result = await db.execute(
        select(KnowledgeIndexVersion)
        .where(KnowledgeIndexVersion.project_id == project_id)
        .order_by(KnowledgeIndexVersion.version_number.desc())
    )
    return [KnowledgeIndexVersionResponse.model_validate(item) for item in result.scalars()]


@router.post(
    "/projects/{project_id}/knowledge-indexes/rebuild",
    response_model=KnowledgeIndexVersionResponse,
)
async def rebuild_knowledge_index(
    project_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> KnowledgeIndexVersionResponse:
    try:
        version = await rebuild_project_index(
            db, project_id=project_id, user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await write_audit_log(
        db,
        request,
        "rebuild_knowledge_index",
        current_user.id,
        "knowledge_index_version",
        str(version.id),
        {"project_id": project_id, "version_number": version.version_number},
    )
    await db.commit()
    return KnowledgeIndexVersionResponse.model_validate(version)


@router.post(
    "/evaluation/datasets",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_dataset(
    payload: EvaluationDatasetCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> EvaluationDatasetResponse:
    dataset = await create_dataset(
        db,
        user=current_user,
        project_id=payload.project_id,
        dataset_key=payload.dataset_key,
        name=payload.name,
        description=payload.description,
        data_origin=payload.data_origin,
    )
    await write_audit_log(
        db,
        request,
        "create_evaluation_dataset",
        current_user.id,
        "evaluation_dataset",
        str(dataset.id),
        {"dataset_key": dataset.dataset_key, "version_number": dataset.version_number},
    )
    await db.commit()
    return EvaluationDatasetResponse.model_validate(dataset)


@router.post(
    "/evaluation/datasets/{dataset_id}/review",
    response_model=EvaluationDatasetResponse,
)
async def review_evaluation_dataset(
    dataset_id: int,
    payload: EvaluationDatasetReviewRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> EvaluationDatasetResponse:
    dataset = await review_dataset(
        db,
        dataset_id=dataset_id,
        reviewer=current_user,
        review_status=payload.review_status,
        review_note=payload.review_note,
    )
    await write_audit_log(
        db,
        request,
        "review_evaluation_dataset",
        current_user.id,
        "evaluation_dataset",
        str(dataset.id),
        {"data_origin": dataset.data_origin, "review_status": dataset.review_status},
    )
    await db.commit()
    return EvaluationDatasetResponse.model_validate(dataset)


@router.get(
    "/evaluation/datasets", response_model=list[EvaluationDatasetResponse]
)
async def list_evaluation_datasets(
    project_id: int, db: DbSession, current_user: CurrentUser
) -> list[EvaluationDatasetResponse]:
    datasets = await list_datasets(db, project_id=project_id, user_id=current_user.id)
    return [EvaluationDatasetResponse.model_validate(item) for item in datasets]


@router.get(
    "/evaluation/review-queue", response_model=list[EvaluationDatasetResponse]
)
async def get_evaluation_review_queue(
    db: DbSession, current_user: CurrentUser
) -> list[EvaluationDatasetResponse]:
    datasets = await list_review_queue(db, reviewer=current_user)
    return [EvaluationDatasetResponse.model_validate(item) for item in datasets]


@router.post(
    "/evaluation/datasets/{dataset_id}/cases",
    response_model=EvaluationCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case(
    dataset_id: int,
    payload: EvaluationCaseCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> EvaluationCaseResponse:
    case_item = await add_case(
        db,
        user=current_user,
        dataset_id=dataset_id,
        case_key=payload.case_key,
        query=payload.query,
        expected_document_ids=payload.expected_document_ids,
        expected_insufficient_basis=payload.expected_insufficient_basis,
        case_metadata=payload.case_metadata,
    )
    return EvaluationCaseResponse.model_validate(case_item)


@router.post(
    "/evaluation/datasets/{dataset_id}/cases/import",
    response_model=list[EvaluationCaseResponse],
    status_code=status.HTTP_201_CREATED,
)
async def import_evaluation_cases(
    dataset_id: int,
    payload: EvaluationCaseBulkImport,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> list[EvaluationCaseResponse]:
    cases = await add_cases_bulk(
        db,
        user=current_user,
        dataset_id=dataset_id,
        case_inputs=[
            EvaluationCaseInput(
                case_key=item.case_key,
                query=item.query,
                expected_document_ids=item.expected_document_ids,
                expected_insufficient_basis=item.expected_insufficient_basis,
                case_metadata=item.case_metadata,
            )
            for item in payload.cases
        ],
    )
    await write_audit_log(
        db,
        request,
        "import_evaluation_cases",
        current_user.id,
        "evaluation_dataset",
        str(dataset_id),
        {"case_count": len(cases), "case_keys": [item.case_key for item in cases]},
    )
    await db.commit()
    return [EvaluationCaseResponse.model_validate(item) for item in cases]


@router.get(
    "/evaluation/datasets/{dataset_id}/cases",
    response_model=list[EvaluationCaseResponse],
)
async def get_evaluation_cases(
    dataset_id: int, db: DbSession, current_user: CurrentUser
) -> list[EvaluationCaseResponse]:
    cases = await list_dataset_cases(db, dataset_id=dataset_id, user=current_user)
    return [EvaluationCaseResponse.model_validate(item) for item in cases]


@router.post(
    "/evaluation/cases/{case_id}/reviews",
    response_model=EvaluationCaseReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case_review(
    case_id: int,
    payload: EvaluationCaseReviewCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> EvaluationCaseReviewResponse:
    review = await submit_case_review(
        db,
        case_id=case_id,
        reviewer=current_user,
        review_kind=payload.review_kind,
        expected_document_ids=payload.expected_document_ids,
        expected_insufficient_basis=payload.expected_insufficient_basis,
        critical_error_tags=payload.critical_error_tags,
        rationale=payload.rationale,
    )
    await write_audit_log(
        db,
        request,
        "create_evaluation_case_review",
        current_user.id,
        "evaluation_case",
        str(case_id),
        {"review_kind": review.review_kind},
    )
    await db.commit()
    return EvaluationCaseReviewResponse.model_validate(review)


@router.get(
    "/evaluation/cases/{case_id}/reviews",
    response_model=list[EvaluationCaseReviewResponse],
)
async def get_evaluation_case_reviews(
    case_id: int, db: DbSession, current_user: CurrentUser
) -> list[EvaluationCaseReviewResponse]:
    reviews = await list_case_reviews(db, case_id=case_id, user=current_user)
    return [EvaluationCaseReviewResponse.model_validate(item) for item in reviews]


@router.get(
    "/evaluation/datasets/{dataset_id}/report",
    response_model=EvaluationDatasetReportResponse,
)
async def get_evaluation_dataset_report(
    dataset_id: int, db: DbSession, current_user: CurrentUser
) -> EvaluationDatasetReportResponse:
    report = await dataset_report(db, dataset_id=dataset_id, user=current_user)
    return EvaluationDatasetReportResponse.model_validate(report)


@router.get(
    "/evaluation/datasets/{dataset_id}/regression-gate",
    response_model=EvaluationGateReportResponse,
)
async def get_evaluation_regression_gate(
    dataset_id: int, db: DbSession, current_user: CurrentUser
) -> EvaluationGateReportResponse:
    report = await regression_gate_report(db, dataset_id=dataset_id, user=current_user)
    return EvaluationGateReportResponse.model_validate(report)


@router.post(
    "/evaluation/datasets/{dataset_id}/freeze",
    response_model=EvaluationDatasetResponse,
)
async def freeze_evaluation_dataset(
    dataset_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> EvaluationDatasetResponse:
    dataset = await freeze_dataset(db, dataset_id=dataset_id, user_id=current_user.id)
    await write_audit_log(
        db,
        request,
        "freeze_evaluation_dataset",
        current_user.id,
        "evaluation_dataset",
        str(dataset.id),
        {"content_hash": dataset.content_hash, "case_count": dataset.case_count},
    )
    await db.commit()
    return EvaluationDatasetResponse.model_validate(dataset)


@router.post(
    "/evaluation/datasets/{dataset_id}/runs",
    response_model=EvaluationRunResponse,
)
async def run_evaluation_dataset(
    dataset_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> EvaluationRunResponse:
    run = await run_dataset(db, dataset_id=dataset_id, user=current_user)
    await write_audit_log(
        db,
        request,
        "run_evaluation_dataset",
        current_user.id,
        "evaluation_run",
        str(run.id),
        {
            "dataset_id": dataset_id,
            "matched_cases": run.matched_cases,
            "failed_cases": run.failed_cases,
            "error_cases": run.error_cases,
        },
    )
    await db.commit()
    return EvaluationRunResponse.model_validate(run)


@router.get("/evaluation/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(
    run_id: int, db: DbSession, current_user: CurrentUser
) -> EvaluationRunResponse:
    run = await get_owned_run(db, run_id, current_user.id)
    return EvaluationRunResponse.model_validate(run)


@router.get(
    "/evaluation/runs/{run_id}/results",
    response_model=list[EvaluationCaseResultResponse],
)
async def get_evaluation_results(
    run_id: int, db: DbSession, current_user: CurrentUser
) -> list[EvaluationCaseResultResponse]:
    results = await list_run_results(db, run_id, current_user.id)
    return [EvaluationCaseResultResponse.model_validate(item) for item in results]


@router.post(
    "/spot-checks/sample",
    response_model=SpotCheckQueueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sample_spot_check_queue(
    payload: SpotCheckSampleRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> SpotCheckQueueResponse:
    items = await sample_spot_checks(
        db,
        reviewer=current_user,
        skill_id=payload.skill_id,
        sample_size=payload.sample_size,
    )
    await write_audit_log(
        db,
        request,
        "sample_spot_checks",
        current_user.id,
        "spot_check_queue",
        payload.skill_id,
        {"sampled": len(items), "sample_size": payload.sample_size},
    )
    await db.commit()
    return SpotCheckQueueResponse(
        items=[SpotCheckItemResponse.model_validate(item) for item in items],
        status_counts=queue_status_counts(items),
        disclaimer=SPOT_CHECK_DISCLAIMER,
    )


@router.get("/spot-checks", response_model=SpotCheckQueueResponse)
async def list_spot_check_queue(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: str | None = None,
) -> SpotCheckQueueResponse:
    items = await list_spot_checks(db, reviewer=current_user, status=status_filter)
    return SpotCheckQueueResponse(
        items=[SpotCheckItemResponse.model_validate(item) for item in items],
        status_counts=queue_status_counts(items),
        disclaimer=SPOT_CHECK_DISCLAIMER,
    )


@router.get("/spot-checks/{item_id}", response_model=SpotCheckDetailResponse)
async def get_spot_check_item(
    item_id: int, db: DbSession, current_user: CurrentUser
) -> SpotCheckDetailResponse:
    detail = await get_spot_check_detail(db, item_id=item_id, reviewer=current_user)
    return SpotCheckDetailResponse.model_validate(detail, from_attributes=True)


@router.post(
    "/spot-checks/{item_id}/reviews",
    response_model=SpotCheckReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_spot_check_review(
    item_id: int,
    payload: SpotCheckReviewCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> SpotCheckReviewResponse:
    review = await submit_spot_check_review(
        db,
        item_id=item_id,
        reviewer=current_user,
        review_kind=payload.review_kind,
        verdict=payload.verdict,
        issue_tags=payload.issue_tags,
        rubric_feedback=payload.rubric_feedback,
        rationale=payload.rationale,
    )
    await write_audit_log(
        db,
        request,
        "create_spot_check_review",
        current_user.id,
        "spot_check_item",
        str(item_id),
        {"review_kind": review.review_kind, "verdict": review.verdict},
    )
    await db.commit()
    return SpotCheckReviewResponse.model_validate(review)


@router.get("/signals/l4-summary", response_model=L4SignalSummaryResponse)
async def get_l4_signal_summary(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int | None = None,
) -> L4SignalSummaryResponse:
    summary = await l4_signal_summary(db, user=current_user, project_id=project_id)
    return L4SignalSummaryResponse.model_validate(summary)
