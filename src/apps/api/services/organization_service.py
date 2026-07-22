"""WP2.5 试点组织管理与默认组织回填助手。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import Organization, User
from src.apps.api.models.organization import (
    DEFAULT_PILOT_ORG_CODE,
    DEFAULT_PILOT_ORG_NAME,
    ORG_STATUS_ACTIVE,
    ORG_STATUSES,
)


async def ensure_default_pilot_org(db: AsyncSession) -> Organization:
    """确保默认试点组织存在（幂等）；seed 与测试夹具共用，口径与迁移一致。"""
    result = await db.execute(
        select(Organization).where(Organization.code == DEFAULT_PILOT_ORG_CODE)
    )
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(
            code=DEFAULT_PILOT_ORG_CODE,
            name=DEFAULT_PILOT_ORG_NAME,
            status=ORG_STATUS_ACTIVE,
        )
        db.add(org)
        await db.flush()
    return org


def _require_platform_admin(actor: User) -> None:
    if actor.role != "admin":
        raise BusinessError(
            "只有平台管理员可以管理试点组织",
            status_code=403,
            error_code="org_admin_forbidden",
        )


async def create_organization(
    db: AsyncSession, *, actor: User, code: str, name: str, note: str | None
) -> Organization:
    _require_platform_admin(actor)
    existing = await db.execute(
        select(Organization).where(Organization.code == code)
    )
    if existing.scalar_one_or_none() is not None:
        raise BusinessError(
            "组织 code 已存在", status_code=409, error_code="org_code_duplicate"
        )
    org = Organization(code=code, name=name, status=ORG_STATUS_ACTIVE, note=note)
    db.add(org)
    await db.flush()
    return org


async def set_organization_status(
    db: AsyncSession, *, actor: User, org_id: int, status: str
) -> Organization:
    _require_platform_admin(actor)
    if status not in ORG_STATUSES:
        raise BusinessError(
            "组织状态非法", status_code=422, error_code="org_status_invalid"
        )
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise BusinessError("组织不存在", status_code=404, error_code="org_not_found")
    org.status = status
    await db.flush()
    return org


async def assign_user_organization(
    db: AsyncSession, *, actor: User, user_id: int, org_id: int | None
) -> User:
    _require_platform_admin(actor)
    if org_id is not None:
        org_result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        if org_result.scalar_one_or_none() is None:
            raise BusinessError(
                "组织不存在", status_code=404, error_code="org_not_found"
            )
    user_result = await db.execute(select(User).where(User.id == user_id))
    target = user_result.scalar_one_or_none()
    if target is None:
        raise BusinessError("用户不存在", status_code=404, error_code="user_not_found")
    target.organization_id = org_id
    await db.flush()
    return target


async def list_organizations(db: AsyncSession, *, actor: User) -> list[Organization]:
    _require_platform_admin(actor)
    result = await db.execute(select(Organization).order_by(Organization.id))
    return list(result.scalars())
