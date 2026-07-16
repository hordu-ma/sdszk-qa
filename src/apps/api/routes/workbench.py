"""阶段 1A 教学工作台路由。"""

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select

from src.apps.api.config import settings
from src.apps.api.dependencies import CurrentUser, DbSession
from src.apps.api.models import KnowledgeDocument, ProjectVersion, TaskRun, TeachingProject
from src.apps.api.schemas.workbench import (
    BasisCitation,
    DocumentResponse,
    DocumentReviewRequest,
    ProjectCreate,
    ProjectResponse,
    ProjectVersionCreate,
    ProjectVersionResponse,
    RetrieveBasisRequest,
    RetrieveBasisResponse,
    TaskResponse,
    UploadAccepted,
)
from src.apps.api.services.audit import write_audit_log
from src.apps.api.services.knowledge_service import (
    SUPPORTED_SUFFIXES,
    checksum,
    process_document_task,
    put_object,
    retrieve_basis,
)
from src.apps.api.services.project_service import create_version, get_owned_project

router = APIRouter()


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
async def get_project(
    project_id: int, db: DbSession, current_user: CurrentUser
) -> ProjectResponse:
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
    project = await get_owned_project(db, project_id, current_user.id)
    version = await create_version(db, project, current_user.id, data.content, data.status)
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
    document = KnowledgeDocument(
        project_id=project_id,
        owner_id=current_user.id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        object_key=object_key,
        checksum_sha256=digest,
        status="processing",
        review_status="pending",
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
    # 阶段 1A 审核范围为全库：审核员/管理员可审任意用户的资料；
    # 组织级隔离（试点组织白名单）按开发计划 WP2.5 在阶段 2 引入。
    if current_user.role not in {"admin", "reviewer"}:
        raise HTTPException(status_code=403, detail="只有审核员或管理员可以审核资料")
    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="资料不存在")
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


@router.post("/skills/retrieve-basis", response_model=RetrieveBasisResponse)
async def run_retrieve_basis(
    data: RetrieveBasisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RetrieveBasisResponse:
    run, citations = await retrieve_basis(
        db,
        project_id=data.project_id,
        user_id=current_user.id,
        query=data.query,
        limit=data.limit,
    )
    return RetrieveBasisResponse(
        skill_run_id=run.id,
        insufficient_basis=not citations,
        citations=[BasisCitation(**citation) for citation in citations],
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
    }
