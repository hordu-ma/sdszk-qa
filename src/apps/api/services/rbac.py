"""WP2.5 最小 RBAC 与跨组织隔离的集中判定。

把原先分散在各服务的 `role not in {admin, reviewer}` 判定收敛到一处，并加入
组织维度。设计要点（详见《WP2.5 收口记录》）：

- 平台 admin：内部运营角色，组织无关，可跨全部组织访问、并独占组织白名单开关。
  这是「跨组织隔离」的一处显式缺口，仅限自助内部模式。
- reviewer：组织内复核角色，只能访问本组织资源；必须属于白名单（pilot_active）组织。
- teacher/student：只能访问本人资源；使用试点工作台须属于白名单组织。
"""

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.exceptions import BusinessError
from src.apps.api.models import Organization, User
from src.apps.api.models.organization import ORG_STATUS_ACTIVE


def is_platform_admin(user: User) -> bool:
    return user.role == "admin"


async def require_pilot_membership(db: AsyncSession, user: User) -> None:
    """校验用户可使用试点工作台：平台 admin 放行；其余须属于白名单组织。"""
    if is_platform_admin(user):
        return
    if user.organization_id is None:
        raise BusinessError(
            "账号未加入试点组织，暂无法使用工作台",
            status_code=403,
            error_code="pilot_membership_required",
        )
    result = await db.execute(
        select(Organization.status).where(Organization.id == user.organization_id)
    )
    status = result.scalar_one_or_none()
    if status != ORG_STATUS_ACTIVE:
        raise BusinessError(
            "所属试点组织未在白名单或已暂停",
            status_code=403,
            error_code="pilot_org_not_whitelisted",
        )


async def owner_in_actor_scope(
    db: AsyncSession, *, actor: User, owner_id: int
) -> bool:
    """actor 是否有权跨用户访问 owner 拥有的资源（本人、平台 admin 或同组织 reviewer）。"""
    if owner_id == actor.id:
        return True
    if is_platform_admin(actor):
        return True
    if actor.role != "reviewer" or actor.organization_id is None:
        return False
    result = await db.execute(
        select(User.organization_id).where(User.id == owner_id)
    )
    owner_org = result.scalar_one_or_none()
    return owner_org is not None and owner_org == actor.organization_id


def scope_owner_ids(stmt: Select, actor: User, owner_column) -> Select:  # noqa: ANN001
    """给列表/队列查询叠加组织可见范围过滤。

    平台 admin 不加限制；reviewer 限定资源所有者与其同组织；其他角色限本人。
    owner_column 必须是可 join 到 users 的所有者外键列。
    """
    if is_platform_admin(actor):
        return stmt
    if actor.role == "reviewer" and actor.organization_id is not None:
        owner = select(User.id).where(User.organization_id == actor.organization_id)
        return stmt.where(owner_column.in_(owner))
    return stmt.where(owner_column == actor.id)
