"""创建 base-spark 演示账号和首个思政主题。"""

import asyncio
import hashlib
import os

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.dependencies import AsyncSessionLocal
from src.apps.api.models import (
    Case,
    EvaluationCase,
    EvaluationDataset,
    KnowledgeChunk,
    KnowledgeDocument,
    ProjectVersion,
    TeachingProject,
    User,
)
from src.apps.api.services.evaluation_service import freeze_dataset
from src.apps.api.services.knowledge_service import put_object

SYNTHETIC_DISCLAIMER = "模拟数据，仅用于工程验证；不得作为专业验收结论。"
SYNTHETIC_TOPICS = [
    ("家国情怀", "个人理想、国家发展、责任担当与评价证据应形成一致链路。"),
    ("法治意识", "规则意识、权利义务、真实案例与依法行动应形成一致链路。"),
    ("劳动教育", "劳动价值、实践任务、过程观察与反思证据应形成一致链路。"),
    ("中华优秀传统文化", "文化理解、当代表达、实践任务与价值辨析应形成一致链路。"),
    ("国家安全", "总体国家安全观、风险辨识、责任边界与行动建议应形成一致链路。"),
    ("生态文明", "绿色发展、生活情境、证据分析与行动改进应形成一致链路。"),
    ("科技创新", "创新精神、科学伦理、问题探究与成果论证应形成一致链路。"),
    ("社会责任", "公共参与、协商合作、责任判断与实践反馈应形成一致链路。"),
]
SYNTHETIC_QUERY_PATTERNS = [
    "{topic}教学目标应如何设置",
    "{topic}需要哪些学习任务",
    "{topic}如何收集评价证据",
    "{topic}议题式教学如何设计",
    "{topic}课堂活动怎样保持目标一致",
    "{topic}教学中如何体现学生行动",
    "{topic}形成性诊断应关注什么",
    "{topic}课时设计需要哪些可靠依据",
]


async def seed() -> None:
    users = _demo_users()
    async with AsyncSessionLocal() as db:
        seeded_users: dict[str, User] = {}
        for item in users:
            user_result = await db.execute(select(User).where(User.username == item["username"]))
            user = user_result.scalar_one_or_none()
            if user is None:
                user = User(
                    username=item["username"],
                    hashed_password=bcrypt.hashpw(
                        item["password"].encode()[:72], bcrypt.gensalt()
                    ).decode(),
                    full_name=item["full_name"],
                    role=item["role"],
                    is_active=True,
                )
                db.add(user)
            else:
                user.full_name = item["full_name"]
                user.role = item["role"]
                user.is_active = True
            await db.flush()
            seeded_users[item["role"]] = user
        case_result = await db.execute(
            select(Case).where(
                Case.title.in_(
                    ["高中家国情怀议题式教学", "[模拟] 高中家国情怀议题式教学"]
                )
            )
        )
        demo_case = case_result.scalars().first()
        if demo_case is None:
            db.add(
                Case(
                    title="[模拟] 高中家国情怀议题式教学",
                    difficulty="medium",
                    department="高中",
                    context_info={"grade": "高一", "class_size": 45},
                    core_question="如何围绕家国情怀设计目标、任务和评价证据",
                    scenario_text=SYNTHETIC_DISCLAIMER,
                    supplementary_info={
                        "constraints": ["45 分钟"],
                        "data_origin": "synthetic",
                    },
                    reference_answer={"primary": "目标、任务与评价证据保持一致"},
                    key_points=["家国情怀", "议题式教学", "评价证据"],
                    source="synthetic",
                    generation_meta={
                        "data_origin": "synthetic",
                        "disclaimer": SYNTHETIC_DISCLAIMER,
                    },
                    is_active=True,
                )
            )
        else:
            demo_case.title = "[模拟] 高中家国情怀议题式教学"
            demo_case.scenario_text = SYNTHETIC_DISCLAIMER
            demo_case.source = "synthetic"
            demo_case.generation_meta = {
                "data_origin": "synthetic",
                "disclaimer": SYNTHETIC_DISCLAIMER,
            }
        await db.commit()
        dataset = await _seed_synthetic_stage1(db, seeded_users["admin"])
    print(
        "demo users and synthetic stage 1 dataset ready: "
        + ", ".join(item["username"] for item in users)
        + f"; dataset={dataset.dataset_key} v{dataset.version_number} cases={dataset.case_count}"
    )


async def _seed_synthetic_stage1(
    db: AsyncSession, admin: User
) -> EvaluationDataset:
    project_result = await db.execute(
        select(TeachingProject).where(
            TeachingProject.owner_id == admin.id,
            TeachingProject.title == "[模拟] 阶段 1 高中议题式工程验收",
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        project = TeachingProject(
            owner_id=admin.id,
            title="[模拟] 阶段 1 高中议题式工程验收",
            stage="高中",
            course_type="议题式",
            status="draft",
        )
        db.add(project)
        await db.flush()
    version_result = await db.execute(
        select(ProjectVersion).where(ProjectVersion.project_id == project.id)
    )
    if version_result.scalars().first() is None:
        db.add(
            ProjectVersion(
                project_id=project.id,
                version_number=1,
                status="draft",
                content={
                    "data_origin": "synthetic",
                    "disclaimer": SYNTHETIC_DISCLAIMER,
                },
                created_by=admin.id,
            )
        )

    documents: dict[str, KnowledgeDocument] = {}
    for index, (topic, guidance) in enumerate(SYNTHETIC_TOPICS, 1):
        filename = f"synthetic-stage1-basis-{index:02d}.md"
        queries = "\n".join(
            f"- {pattern.format(topic=topic)}" for pattern in SYNTHETIC_QUERY_PATTERNS
        )
        body = (
            f"# 模拟资料：{topic}\n\n"
            f"> {SYNTHETIC_DISCLAIMER}\n\n"
            f"{topic}教学工程样例：{guidance}\n\n"
            f"## 工程检索问题\n\n{queries}\n\n"
            "本资料为可替换占位内容，不对应真实课程标准、教材或政策原文。"
        ).encode()
        digest = hashlib.sha256(body).hexdigest()
        object_key = f"synthetic/stage1/{digest}-{filename}"
        await put_object(object_key, body, "text/markdown")
        document_result = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.project_id == project.id,
                KnowledgeDocument.filename == filename,
            )
        )
        document = document_result.scalar_one_or_none()
        if document is None:
            document = KnowledgeDocument(
                project_id=project.id,
                owner_id=admin.id,
                filename=filename,
                content_type="text/markdown",
                object_key=object_key,
                checksum_sha256=digest,
                status="ready",
                review_status="approved",
                version_number=1,
            )
            db.add(document)
            await db.flush()
        else:
            document.object_key = object_key
            document.checksum_sha256 = digest
            document.status = "ready"
            document.review_status = "approved"
        chunk_result = await db.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document.id,
                KnowledgeChunk.chunk_index == 0,
            )
        )
        chunk = chunk_result.scalar_one_or_none()
        if chunk is None:
            chunk = KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                content=body.decode(),
                location_label="模拟分块 1",
            )
            db.add(chunk)
        else:
            chunk.content = body.decode()
            chunk.embedding = None
            chunk.embedding_model = None
            chunk.embedding_revision = None
            chunk.index_version_id = None
            chunk.semantic_indexed_at = None
        documents[topic] = document

    dataset_result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.project_id == project.id,
            EvaluationDataset.dataset_key == "stage1-synthetic-g0",
            EvaluationDataset.version_number == 1,
        )
    )
    dataset = dataset_result.scalar_one_or_none()
    if dataset is None:
        dataset = EvaluationDataset(
            project_id=project.id,
            owner_id=admin.id,
            dataset_key="stage1-synthetic-g0",
            version_number=1,
            name="阶段 1 模拟 G0 工程评测集",
            description=SYNTHETIC_DISCLAIMER,
            data_origin="synthetic",
            review_status="not_applicable",
            status="draft",
            case_count=0,
        )
        db.add(dataset)
        await db.flush()
        cases: list[EvaluationCase] = []
        for topic_index, (topic, _) in enumerate(SYNTHETIC_TOPICS, 1):
            for query_index, pattern in enumerate(SYNTHETIC_QUERY_PATTERNS, 1):
                cases.append(
                    EvaluationCase(
                        dataset_id=dataset.id,
                        case_key=f"synthetic-{topic_index:02d}-{query_index:02d}",
                        query=pattern.format(topic=topic),
                        expected_document_ids=[documents[topic].id],
                        expected_insufficient_basis=False,
                        case_metadata={
                            "data_origin": "synthetic",
                            "external_review": "not_applicable",
                            "disclaimer": SYNTHETIC_DISCLAIMER,
                            "replacement_key": f"topic-{topic_index:02d}",
                        },
                    )
                )
        db.add_all(cases)
        dataset.case_count = len(cases)
        await db.commit()
        dataset = await freeze_dataset(db, dataset_id=dataset.id, user_id=admin.id)
    await db.commit()
    await db.refresh(dataset)
    return dataset


def _demo_users() -> list[dict[str, str]]:
    shared_password = os.environ["DEMO_PASSWORD"]
    return [
        {
            "username": os.getenv("DEMO_ADMIN_USERNAME", "demo_admin"),
            "password": os.getenv("DEMO_ADMIN_PASSWORD", shared_password),
            "full_name": os.getenv("DEMO_ADMIN_FULL_NAME", "鲁韵验证管理员"),
            "role": "admin",
        },
        {
            "username": os.getenv(
                "DEMO_TEACHER_USERNAME", os.getenv("DEMO_USERNAME", "demo_teacher")
            ),
            "password": os.getenv("DEMO_TEACHER_PASSWORD", shared_password),
            "full_name": os.getenv(
                "DEMO_TEACHER_FULL_NAME", os.getenv("DEMO_FULL_NAME", "鲁韵验证教师")
            ),
            "role": "teacher",
        },
    ]


if __name__ == "__main__":
    asyncio.run(seed())
