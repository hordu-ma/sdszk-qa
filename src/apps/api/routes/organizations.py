"""WP2.5 试点组织管理路由（平台 admin 专用，不受试点白名单门禁限制）。"""

from fastapi import APIRouter, Request, status

from src.apps.api.dependencies import CurrentUser, DbSession
from src.apps.api.schemas.organization import (
    OrganizationAssignRequest,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationStatusUpdate,
)
from src.apps.api.schemas.workbench import UserResponseLite
from src.apps.api.services.audit import write_audit_log
from src.apps.api.services.organization_service import (
    assign_user_organization,
    create_organization,
    list_organizations,
    set_organization_status,
)

router = APIRouter()


@router.get("", response_model=list[OrganizationResponse])
async def get_organizations(
    db: DbSession, current_user: CurrentUser
) -> list[OrganizationResponse]:
    orgs = await list_organizations(db, actor=current_user)
    return [OrganizationResponse.model_validate(item) for item in orgs]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def add_organization(
    payload: OrganizationCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> OrganizationResponse:
    org = await create_organization(
        db,
        actor=current_user,
        code=payload.code,
        name=payload.name,
        note=payload.note,
    )
    await write_audit_log(
        db, request, "create_organization", current_user.id, "organization", str(org.id),
        {"code": org.code},
    )
    await db.commit()
    return OrganizationResponse.model_validate(org)


@router.post("/{org_id}/status", response_model=OrganizationResponse)
async def update_organization_status(
    org_id: int,
    payload: OrganizationStatusUpdate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> OrganizationResponse:
    org = await set_organization_status(
        db, actor=current_user, org_id=org_id, status=payload.status
    )
    await write_audit_log(
        db, request, "set_organization_status", current_user.id, "organization",
        str(org.id), {"status": org.status},
    )
    await db.commit()
    return OrganizationResponse.model_validate(org)


@router.post("/assign-user", response_model=UserResponseLite)
async def assign_user(
    payload: OrganizationAssignRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> UserResponseLite:
    user = await assign_user_organization(
        db,
        actor=current_user,
        user_id=payload.user_id,
        org_id=payload.organization_id,
    )
    await write_audit_log(
        db, request, "assign_user_organization", current_user.id, "user",
        str(user.id), {"organization_id": payload.organization_id},
    )
    await db.commit()
    return UserResponseLite.model_validate(user)
