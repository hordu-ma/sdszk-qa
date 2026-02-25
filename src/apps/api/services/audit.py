"""审计日志服务。"""

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.logging_config import logger
from src.apps.api.models import AuditLog


def _get_client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


async def write_audit_log(
    db: AsyncSession,
    request: Request,
    action: str,
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """写入审计日志，失败不影响主流程。"""
    try:
        db.add(
            AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=_get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
        )
        await db.flush()
    except Exception as e:
        logger.warning("写入审计日志失败", action=action, error=str(e))

