"""教学项目与版本服务。"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.models import ProjectVersion, TeachingProject


async def get_owned_project(db: AsyncSession, project_id: int, user_id: int) -> TeachingProject:
    result = await db.execute(
        select(TeachingProject).where(
            TeachingProject.id == project_id,
            TeachingProject.owner_id == user_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="教学项目不存在")
    return project


async def create_version(
    db: AsyncSession,
    project: TeachingProject,
    user_id: int,
    content: dict,
    version_status: str,
) -> ProjectVersion:
    version_result = await db.execute(
        select(func.max(ProjectVersion.version_number)).where(
            ProjectVersion.project_id == project.id
        )
    )
    version_number = (version_result.scalar() or 0) + 1
    version = ProjectVersion(
        project_id=project.id,
        version_number=version_number,
        status=version_status,
        content=content,
        created_by=user_id,
    )
    db.add(version)
    await db.flush()
    return version
