"""核心用户 Memory 服务：偏好、班情档案、清除与导出（WP1.3c）。

边界（计划 §2.5.2）：仅本人可读写；清除后新 SkillRun 不得再解析已删项；
不做任何推断、评级或画像；注入审计由 skill_runtime 承担。
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.models import PinnedMemoryItem, TeachingProject, UserPreference
from src.apps.api.models.memory import ClassContextProfile
from src.apps.api.schemas.workbench import (
    ClassProfileCreate,
    PinnedItemCreate,
    UserPreferenceUpdate,
)


async def get_preference(db: AsyncSession, user_id: int) -> UserPreference | None:
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_preference(
    db: AsyncSession, user_id: int, data: UserPreferenceUpdate
) -> UserPreference:
    preference = await get_preference(db, user_id)
    if preference is None:
        preference = UserPreference(user_id=user_id)
        db.add(preference)
    preference.default_stage = data.default_stage
    preference.default_course_type = data.default_course_type
    preference.textbook_version = data.textbook_version
    preference.export_template = data.export_template
    preference.extra = data.extra
    await db.flush()
    return preference


async def list_class_profiles(db: AsyncSession, user_id: int) -> list[ClassContextProfile]:
    result = await db.execute(
        select(ClassContextProfile)
        .where(ClassContextProfile.user_id == user_id)
        .order_by(ClassContextProfile.updated_at.desc())
    )
    return list(result.scalars())


async def create_class_profile(
    db: AsyncSession, user_id: int, data: ClassProfileCreate
) -> ClassContextProfile:
    profile = ClassContextProfile(user_id=user_id, name=data.name, context=data.context)
    db.add(profile)
    await db.flush()
    return profile


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def delete_class_profile(db: AsyncSession, user_id: int, profile_id: int) -> bool:
    result = await db.execute(
        delete(ClassContextProfile).where(
            ClassContextProfile.id == profile_id,
            ClassContextProfile.user_id == user_id,
        )
    )
    return _rowcount(result) > 0


async def list_pinned_items(db: AsyncSession, user_id: int) -> list[PinnedMemoryItem]:
    result = await db.execute(
        select(PinnedMemoryItem)
        .where(PinnedMemoryItem.user_id == user_id)
        .order_by(PinnedMemoryItem.updated_at.desc())
    )
    return list(result.scalars())


async def create_pinned_item(
    db: AsyncSession, user_id: int, data: PinnedItemCreate
) -> PinnedMemoryItem:
    if data.item_type == "project":
        if data.project_id is None:
            raise ValueError("钉选项目必须提供 project_id")
        result = await db.execute(
            select(TeachingProject).where(
                TeachingProject.id == data.project_id,
                TeachingProject.owner_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("只能钉选本人教学项目")
    item = PinnedMemoryItem(user_id=user_id, **data.model_dump())
    db.add(item)
    await db.flush()
    return item


async def delete_pinned_item(db: AsyncSession, user_id: int, item_id: int) -> bool:
    result = await db.execute(
        delete(PinnedMemoryItem).where(
            PinnedMemoryItem.id == item_id,
            PinnedMemoryItem.user_id == user_id,
        )
    )
    return _rowcount(result) > 0


async def clear_memory(db: AsyncSession, user_id: int) -> tuple[bool, int, int]:
    """一键清除本人全部 Memory；注入审计保留（历史留痕，不含可再注入内容）。"""
    preference_result = await db.execute(
        delete(UserPreference).where(UserPreference.user_id == user_id)
    )
    profiles_result = await db.execute(
        delete(ClassContextProfile).where(ClassContextProfile.user_id == user_id)
    )
    pinned_result = await db.execute(
        delete(PinnedMemoryItem).where(PinnedMemoryItem.user_id == user_id)
    )
    return (
        _rowcount(preference_result) > 0,
        _rowcount(profiles_result),
        _rowcount(pinned_result),
    )
