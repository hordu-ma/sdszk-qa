"""内部金标 v0：自研检索评测语料与双评/仲裁全流程演练（自助开发模式 §0.5）。

- 语料与案例均为内部自研，data_origin=internal_authored，永远不得表述为专家金标。
- 资料正文不包含案例查询原文（无泄漏），用于真实测量语义检索链。
- 两位内部审核账号独立双评，预置分歧案例由管理员仲裁，走完整治理流程。
"""

import asyncio
import hashlib
import os

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.config import settings
from src.apps.api.dependencies import AsyncSessionLocal
from src.apps.api.models import (
    EvaluationCase,
    EvaluationDataset,
    KnowledgeChunk,
    KnowledgeDocument,
    ProjectVersion,
    TeachingProject,
    User,
)
from src.apps.api.services.evaluation_service import (
    EvaluationCaseInput,
    add_cases_bulk,
    freeze_dataset,
    review_dataset,
    submit_case_review,
)
from src.apps.api.services.knowledge_service import (
    chunk_document,
    put_object,
    rebuild_project_index,
)

DISCLAIMER = "内部自研模拟数据，仅用于工程回归与流程演练；不是专家金标，不得作为专业验收结论。"
PROJECT_TITLE = "[模拟] 内部金标 v0 检索评测"
DATASET_KEY = "stage1-internal-gold"

# topic -> (议题情境, 关键活动词, 证据词, 误区词)
TOPICS: dict[str, tuple[str, list[str], list[str], str]] = {
    "家国情怀": (
        "以身边劳动者的奋斗故事切入，讨论个人选择与国家需要之间的关系",
        ["人物访谈", "口述史整理", "成长坐标绘制"],
        ["访谈记录", "价值排序说明", "行动承诺卡"],
        "把宏大叙事直接灌输给学生而缺少真实人物与具体情境",
    ),
    "法治意识": (
        "围绕校园欺凌处置流程，辨析未成年人保护法与学校规章的边界",
        ["模拟法庭", "条文检索比对", "处置流程图绘制"],
        ["庭审角色陈述稿", "条文引用清单", "流程图批注"],
        "只讲法条记忆而不安排真实两难情境中的行为选择",
    ),
    "劳动教育": (
        "从校园餐厅的一餐饭追溯食材生产、加工与配送的完整劳动链条",
        ["岗位体验轮换", "劳动过程记录", "工序改进提案"],
        ["体验日志", "工序观察表", "改进提案说明"],
        "把劳动窄化为打扫卫生而缺少对劳动价值的认识与反思",
    ),
    "中华优秀传统文化": (
        "从家乡的节气习俗出发，探究传统智慧在当代生活中的转化表达",
        ["习俗田野调查", "老物件故事会", "文化转译设计"],
        ["调查手记", "故事音频稿", "转译作品说明卡"],
        "停留在符号展示层面而不追问文化背后的价值观念",
    ),
    "国家安全": (
        "以一次网络钓鱼事件为例，梳理个人信息保护与总体国家安全观的联系",
        ["风险情景推演", "案例链条分析", "防护清单制订"],
        ["推演记录", "链条分析图", "防护自查清单"],
        "把安全教育等同于恐吓式宣传而缺少可执行的行为指引",
    ),
    "生态文明": (
        "统计班级一周的垃圾产生量，估算碳足迹并设计减量方案",
        ["垃圾称重统计", "碳足迹核算", "减量方案路演"],
        ["统计台账", "核算过程单", "路演评议表"],
        "只喊环保口号而没有可量化的观察数据与改进闭环",
    ),
    "科技创新": (
        "复盘一次国产芯片攻关的公开报道，讨论科学精神与工程伦理",
        ["报道文本细读", "技术路线复盘", "伦理立场辩论"],
        ["细读批注", "复盘时间轴", "辩论立论卡"],
        "把创新简化为发明成果罗列而忽视失败过程与伦理讨论",
    ),
    "社会责任": (
        "针对社区停车难问题组织协商议事，形成可提交的治理建议",
        ["议事规则演练", "利益相关方地图", "建议书撰写"],
        ["议事记录", "相关方分析图", "建议书文本"],
        "让学生扮演旁观评论者而不是真实公共事务的参与者",
    ),
    "数字素养与网络文明": (
        "解剖一条热搜谣言的传播路径，练习信息核查与理性表达",
        ["信源交叉核查", "传播路径还原", "澄清短文写作"],
        ["核查工作单", "路径还原图", "澄清短文"],
        "只禁止使用网络而不培养辨别与负责任表达的能力",
    ),
    "人类命运共同体": (
        "跟踪一批跨国抗旱物资的流转，理解全球议题中的协作与担当",
        ["物资流转追踪", "多国立场比较", "协作方案设计"],
        ["追踪日志", "立场比较矩阵", "方案说明书"],
        "把国际议题讲成遥远新闻而不落到学生可感的具体联系",
    ),
    "乡村振兴": (
        "为一个真实村庄的农产品设计助农直播脚本并核算收益分配",
        ["村情资料研读", "直播脚本编写", "收益分配测算"],
        ["研读摘记", "脚本定稿", "测算说明"],
        "把乡村想象成落后符号而忽视在地资源与农民主体性",
    ),
    "志愿服务与公共参与": (
        "策划一次面向社区老人的数字反诈服务日并复盘服务效果",
        ["需求走访", "服务方案设计", "效果回访复盘"],
        ["走访记录", "方案任务分工表", "回访复盘报告"],
        "以完成志愿时长为目标而不关注服务对象的真实需要",
    ),
}

# 每主题 10 条查询模板：0-2 含主题名（易），3-6 靠活动/证据词（中），7-9 意译（难）
QUERY_TEMPLATES = [
    "{topic}单元的教学目标怎么落到可观察的行为",
    "{topic}主题下如何组织学习任务",
    "{topic}课堂用什么证据判断学生真的理解了",
    "围绕「{scenario_head}」这类情境如何展开教学",
    "{activity0}这类活动的设计要点是什么",
    "{activity1}应该怎么组织学生参与",
    "用{evidence0}来评价学生合适吗",
    "备课时想避免「{misconception_head}」的问题该怎么办",
    "学生完成{activity2}之后，下一步的深化任务怎么设计",
    "期末想围绕{evidence2}组织成果展示，评价要点是什么",
]

INSUFFICIENT_QUERIES = [
    "微积分极限概念的引入顺序怎么安排",
    "有机化学实验室的通风要求是什么",
    "篮球半场人盯人战术如何训练",
    "编译器词法分析器的实现步骤",
    "天体物理中黑洞吸积盘的观测方法",
    "小提琴换把练习的进阶曲目推荐",
    "法语动词变位的记忆规律",
    "桥梁桩基础施工的质量验收标准",
    "咖啡烘焙曲线如何影响风味",
    "羽毛球反手高远球的发力要领",
    "水彩画湿画法的纸张选择",
    "无人机航拍的镜头运动设计",
    "面包酵母发酵温度如何控制",
    "围棋官子阶段的收束次序",
    "露营帐篷的抗风绳结打法",
    "吉他扫弦节奏型的分解练习",
    "盆栽多肉植物的配土比例",
    "游泳蛙泳蹬腿的常见纠错",
    "木工榫卯结构的画线方法",
    "菜园轮作倒茬的安排原则",
]

DISPUTED_COUNT = 8


def _doc_body(
    topic: str,
    scenario: str,
    activities: list[str],
    evidences: list[str],
    misconception: str,
) -> str:
    activity_lines = "\n".join(
        f"{index}. **{name}**：围绕议题推进一步，明确学生要产出的中间成果。"
        for index, name in enumerate(activities, 1)
    )
    evidence_lines = "\n".join(f"- {name}" for name in evidences)
    return (
        f"# 模拟教学资料：{topic}\n\n"
        f"> {DISCLAIMER}\n\n"
        f"## 单元定位与目标\n\n"
        f"本单元以{topic}为核心议题。目标设计强调把价值认同拆解为认知理解、情感态度与"
        f"行动倾向三个层次，并为每一层写出可观察、可收集的表现描述，避免使用无法判断的抽象口号。\n\n"
        f"## 议题与情境\n\n"
        f"建议的进入情境：{scenario}。情境要贴近学生生活经验，保留真实的复杂性与两难感，"
        f"让不同立场都能得到严肃讨论。\n\n"
        f"## 学习任务序列\n\n{activity_lines}\n\n"
        f"任务之间保持递进关系：先建立事实理解，再组织价值辨析，最后落到个人或集体的行动设计。\n\n"
        f"## 评价证据与观察点\n\n"
        f"课堂上应持续收集以下过程性证据，而不是只看最终发言：\n\n{evidence_lines}\n\n"
        f"证据用于形成性反馈：教师依据证据指出改进方向，不给学生打分或排名。\n\n"
        f"## 常见设计误区\n\n"
        f"最需要避免的问题是：{misconception}。此外，任务数量过多而缺少深入展开，"
        f"同样会让议题讨论流于表面。\n\n"
        f"（{DISCLAIMER}）\n"
    )


def _topic_queries(
    topic: str,
    scenario: str,
    activities: list[str],
    evidences: list[str],
    misconception: str,
) -> list[str]:
    context = {
        "topic": topic,
        "scenario_head": scenario[:12],
        "activity0": activities[0],
        "activity1": activities[1],
        "activity2": activities[2],
        "evidence0": evidences[0],
        "evidence2": evidences[2],
        "misconception_head": misconception[:14],
    }
    return [template.format(**context) for template in QUERY_TEMPLATES]


async def _ensure_reviewers(db: AsyncSession) -> tuple[User, User]:
    password = os.environ.get("GOLD_REVIEWER_PASSWORD") or os.environ["DEMO_PASSWORD"]
    reviewers: list[User] = []
    for username, full_name in (
        ("gold_reviewer_a", "内部金标审核员A"),
        ("gold_reviewer_b", "内部金标审核员B"),
    ):
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                hashed_password=bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode(),
                full_name=full_name,
                role="reviewer",
                is_active=True,
            )
            db.add(user)
            await db.flush()
        reviewers.append(user)
    await db.commit()
    return reviewers[0], reviewers[1]


async def _get_admin(db: AsyncSession) -> User:
    username = os.getenv("DEMO_ADMIN_USERNAME", "demo_admin")
    result = await db.execute(select(User).where(User.username == username))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise RuntimeError("请先运行 seed_demo 创建管理员账号")
    return admin


async def _ensure_project(db: AsyncSession, admin: User) -> TeachingProject:
    result = await db.execute(
        select(TeachingProject).where(
            TeachingProject.owner_id == admin.id,
            TeachingProject.title == PROJECT_TITLE,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        project = TeachingProject(
            owner_id=admin.id,
            title=PROJECT_TITLE,
            stage="高中",
            course_type="议题式",
            status="draft",
        )
        db.add(project)
        await db.flush()
        db.add(
            ProjectVersion(
                project_id=project.id,
                version_number=1,
                status="draft",
                content={"data_origin": "internal_authored", "disclaimer": DISCLAIMER},
                created_by=admin.id,
            )
        )
    return project


async def _ensure_documents(
    db: AsyncSession, project: TeachingProject, admin: User
) -> dict[str, KnowledgeDocument]:
    documents: dict[str, KnowledgeDocument] = {}
    for index, (topic, (scenario, activities, evidences, misconception)) in enumerate(
        TOPICS.items(), 1
    ):
        filename = f"synthetic-internal-gold-{index:02d}.md"
        body = _doc_body(topic, scenario, activities, evidences, misconception).encode()
        digest = hashlib.sha256(body).hexdigest()
        object_key = f"synthetic/internal-gold/{digest}-{filename}"
        await put_object(object_key, body, "text/markdown")
        result = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.project_id == project.id,
                KnowledgeDocument.filename == filename,
            )
        )
        document = result.scalar_one_or_none()
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
        pieces = chunk_document(body.decode())
        existing = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
        )
        if not list(existing.scalars()):
            db.add_all(
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=piece.content,
                    location_label=piece.location_label,
                    page_number=piece.page_number,
                    paragraph_start=piece.paragraph_start,
                    paragraph_end=piece.paragraph_end,
                )
                for chunk_index, piece in enumerate(pieces)
            )
        documents[topic] = document
    await db.commit()
    return documents


def _case_inputs(documents: dict[str, KnowledgeDocument]) -> list[EvaluationCaseInput]:
    inputs: list[EvaluationCaseInput] = []
    tiers = ["easy"] * 3 + ["medium"] * 4 + ["hard"] * 3
    for topic_index, (topic, (scenario, activities, evidences, misconception)) in enumerate(
        TOPICS.items(), 1
    ):
        for query_index, query in enumerate(
            _topic_queries(topic, scenario, activities, evidences, misconception), 1
        ):
            inputs.append(
                EvaluationCaseInput(
                    case_key=f"gold-{topic_index:02d}-{query_index:02d}",
                    query=query,
                    expected_document_ids=[documents[topic].id],
                    expected_insufficient_basis=False,
                    case_metadata={
                        "data_origin": "internal_authored",
                        "internal_gold": "v0",
                        "difficulty": tiers[query_index - 1],
                        "topic": topic,
                        "disclaimer": DISCLAIMER,
                    },
                )
            )
    retrieval_queries = [item["query"] for item in inputs]
    if len(retrieval_queries) != len(set(retrieval_queries)):
        raise RuntimeError(
            "内部金标查询存在跨主题重复：同一查询不能指向不同预期资料"
        )
    for query_index, query in enumerate(INSUFFICIENT_QUERIES, 1):
        inputs.append(
            EvaluationCaseInput(
                case_key=f"gold-ib-{query_index:02d}",
                query=query,
                expected_document_ids=[],
                expected_insufficient_basis=True,
                case_metadata={
                    "data_origin": "internal_authored",
                    "internal_gold": "v0",
                    "difficulty": "insufficient",
                    "disclaimer": DISCLAIMER,
                },
            )
        )
    return inputs


async def _run_gold_governance(
    db: AsyncSession,
    dataset: EvaluationDataset,
    admin: User,
    reviewer_a: User,
    reviewer_b: User,
) -> dict[str, int]:
    cases_result = await db.execute(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset.id)
        .order_by(EvaluationCase.case_key)
    )
    cases = list(cases_result.scalars())
    disputed_keys = {case.case_key for case in cases[:DISPUTED_COUNT]}
    stats = {"consensus": 0, "arbitrated": 0}
    for case in cases:
        await submit_case_review(
            db,
            case_id=case.id,
            reviewer=reviewer_a,
            review_kind="independent",
            expected_document_ids=list(case.expected_document_ids),
            expected_insufficient_basis=case.expected_insufficient_basis,
            critical_error_tags=[],
            rationale="内部双评演练：确认查询与预期资料指向一致。",
        )
        if case.case_key in disputed_keys:
            await submit_case_review(
                db,
                case_id=case.id,
                reviewer=reviewer_b,
                review_kind="independent",
                expected_document_ids=[],
                expected_insufficient_basis=not case.expected_insufficient_basis,
                critical_error_tags=["internal_dispute_rehearsal"],
                rationale="内部双评演练：预置分歧意见，验证仲裁流程。",
            )
            await submit_case_review(
                db,
                case_id=case.id,
                reviewer=admin,
                review_kind="arbitration",
                expected_document_ids=list(case.expected_document_ids),
                expected_insufficient_basis=case.expected_insufficient_basis,
                critical_error_tags=[],
                rationale="内部仲裁演练：采纳原始预期，分歧标签不成立。",
            )
            stats["arbitrated"] += 1
        else:
            await submit_case_review(
                db,
                case_id=case.id,
                reviewer=reviewer_b,
                review_kind="independent",
                expected_document_ids=list(case.expected_document_ids),
                expected_insufficient_basis=case.expected_insufficient_basis,
                critical_error_tags=[],
                rationale="内部双评演练：独立复核结论与首评一致。",
            )
            stats["consensus"] += 1
    return stats


async def seed_internal_gold() -> None:
    async with AsyncSessionLocal() as db:
        admin = await _get_admin(db)
        reviewer_a, reviewer_b = await _ensure_reviewers(db)
        project = await _ensure_project(db, admin)
        existing = await db.execute(
            select(EvaluationDataset).where(
                EvaluationDataset.project_id == project.id,
                EvaluationDataset.dataset_key == DATASET_KEY,
            )
        )
        dataset = existing.scalars().first()
        if dataset is not None:
            print(
                f"internal gold dataset already present: {DATASET_KEY} "
                f"v{dataset.version_number} status={dataset.status}; skip"
            )
            return
        documents = await _ensure_documents(db, project, admin)
        semantic_note = "semantic index skipped: SEMANTIC_RAG_ENABLED=false"
        if settings.SEMANTIC_RAG_ENABLED:
            try:
                index_version = await rebuild_project_index(
                    db, project_id=project.id, user_id=admin.id
                )
                semantic_note = (
                    f"semantic index v{index_version.version_number} active "
                    f"({index_version.chunk_count} chunks)"
                )
            except Exception as exc:
                semantic_note = f"semantic index degraded: {exc}"
        dataset = EvaluationDataset(
            project_id=project.id,
            owner_id=admin.id,
            dataset_key=DATASET_KEY,
            version_number=1,
            name="内部金标 v0（内部自研，非专家数据）",
            description=DISCLAIMER,
            data_origin="internal_authored",
            review_status="pending",
            status="draft",
            case_count=0,
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)
        cases = await add_cases_bulk(
            db, user=admin, dataset_id=dataset.id, case_inputs=_case_inputs(documents)
        )
        stats = await _run_gold_governance(db, dataset, admin, reviewer_a, reviewer_b)
        await review_dataset(
            db,
            dataset_id=dataset.id,
            reviewer=reviewer_a,
            review_status="approved",
            review_note=(
                "内部来源审核演练：确认语料与案例均为内部自研模拟数据，"
                "允许冻结用于工程回归；不构成专家或客户审核。"
            ),
        )
        dataset = await freeze_dataset(db, dataset_id=dataset.id, user_id=admin.id)
        print(
            f"internal gold v0 ready: dataset={dataset.dataset_key} v{dataset.version_number} "
            f"cases={len(cases)} consensus={stats['consensus']} arbitrated={stats['arbitrated']} "
            f"hash={dataset.content_hash}; {semantic_note}"
        )


if __name__ == "__main__":
    asyncio.run(seed_internal_gold())
