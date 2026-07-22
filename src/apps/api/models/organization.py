"""WP2.5 试点组织与白名单模型。

组织即试点单位（学校/教研组织）。只有 status=pilot_active 的组织在白名单内，
其成员才能使用试点工作台能力；status=suspended 的组织成员被门禁拦截。
跨组织隔离：reviewer 只能复核本组织资源；平台 admin 为内部运营角色，
组织无关、负责白名单开关（详见《WP2.5 收口记录》对该缺口的说明）。
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

# 默认试点组织：迁移回填存量用户、seed 与测试夹具共用这一固定 code。
DEFAULT_PILOT_ORG_CODE = "luyun-pilot-default"
DEFAULT_PILOT_ORG_NAME = "鲁韵内部试点默认组织"

ORG_STATUS_ACTIVE = "pilot_active"
ORG_STATUS_SUSPENDED = "suspended"
ORG_STATUSES = (ORG_STATUS_ACTIVE, ORG_STATUS_SUSPENDED)


class Organization(Base, TimestampMixin):
    """试点组织登记表。"""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    # pilot_active 在白名单内；suspended 暂停试点，成员被门禁拦截
    status: Mapped[str] = mapped_column(String(30), default=ORG_STATUS_ACTIVE, index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
