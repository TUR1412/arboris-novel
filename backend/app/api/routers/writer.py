# AIMETA P=写作API_章节生成和大纲创建|R=章节生成_大纲生成_评审_L2导演脚本_护栏检查|NR=不含数据存储|E=route:POST_/api/writer/*|X=http|A=生成_评审_过滤|D=fastapi,openai|S=net,db|RD=./README.ai
"""
Writer API Router - 人类化起点长篇写作系统

核心架构：
- L1 Planner：全知规划层（蓝图/大纲）
- L2 Director：章节导演脚本（ChapterMission）
- L3 Writer：有限视角正文生成

关键改进：
1. 信息可见性过滤：L3 Writer 只能看到已登场角色
2. 跨章 1234 逻辑：通过 ChapterMission 控制每章只写一个节拍
3. 后置护栏检查：自动检测并修复违规内容
"""
import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...models.novel import Chapter, ChapterOutline, ChapterVersion
from ...schemas.novel import (
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    FinalizeChapterRequest,
    FinalizeChapterResponse,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.novel_service import _normalize_version_content
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...services.writer_context_builder import WriterContextBuilder
from ...services.chapter_guardrails import ChapterGuardrails
from ...services.ai_review_service import AIReviewService, ReviewResult
from ...services.finalize_service import FinalizeService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository
from ...services.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


async def _resolve_version_count(session: AsyncSession) -> int:
    """
    解析章节版本数量配置，优先级：
    1) SystemConfig: writer.chapter_versions
    2) SystemConfig: writer.version_count（兼容旧键）
    3) ENV: WRITER_CHAPTER_VERSION_COUNT / WRITER_CHAPTER_VERSIONS（与 config.py 对齐）
    4) ENV: WRITER_VERSION_COUNT（兼容旧）
    5) settings.writer_chapter_versions（默认=2）
    """
    repo = SystemConfigRepository(session)
    # 1) 新键优先，兼容旧键
    for key in ("writer.chapter_versions", "writer.version_count"):
        record = await repo.get_by_key(key)
        if record and record.value:
            try:
                val = int(record.value)
                if val >= 1:
                    return val
            except ValueError:
                pass
    # 2) 环境变量（与 Settings 对齐）
    for env in ("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS", "WRITER_VERSION_COUNT"):
        v = os.getenv(env)
        if v:
            try:
                val = int(v)
                if val >= 1:
                    return val
            except ValueError:
                pass
    # 3) 默认值
    return int(settings.writer_chapter_versions)


async def _generate_chapter_mission(
    llm_service: LLMService,
    prompt_service: PromptService,
    blueprint_dict: dict,
    previous_summary: str,
    previous_tail: str,
    outline_title: str,
    outline_summary: str,
    writing_notes: str,
    introduced_characters: List[str],
    all_characters: List[str],
    user_id: int,
) -> Optional[dict]:
    """
    L2 Director: 生成章节导演脚本（ChapterMission）
    """
    plan_prompt = await prompt_service.get_prompt("chapter_plan")
    if not plan_prompt:
        logger.warning("未配置 chapter_plan 提示词，跳过导演脚本生成")
        return None

    plan_input = f"""
[上一章摘要]
{previous_summary or "暂无（这是第一章）"}

[上一章结尾]
{previous_tail or "暂无（这是第一章）"}

[当前章节大纲]
标题：{outline_title}
摘要：{outline_summary}

[已登场角色]
{json.dumps(introduced_characters, ensure_ascii=False) if introduced_characters else "暂无"}

[全部角色]
{json.dumps(all_characters, ensure_ascii=False)}

[写作指令]
{writing_notes or "无额外指令"}
"""

    try:
        response = await llm_service.get_llm_response(
            system_prompt=plan_prompt,
            conversation_history=[{"role": "user", "content": plan_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=120.0,
        )
        cleaned = remove_think_tags(response)
        normalized = unwrap_markdown_json(cleaned)
        mission = json.loads(normalized)
        logger.info("成功生成章节导演脚本: macro_beat=%s", mission.get("macro_beat"))
        return mission
    except Exception as exc:
        logger.warning("生成章节导演脚本失败，将使用默认模式: %s", exc)
        return None


async def _rewrite_with_guardrails(
    llm_service: LLMService,
    prompt_service: PromptService,
    original_text: str,
    chapter_mission: Optional[dict],
    violations_text: str,
    user_id: int,
) -> str:
    """
    使用护栏修复提示词重写违规内容
    """
    rewrite_prompt = await prompt_service.get_prompt("rewrite_guardrails")
    if not rewrite_prompt:
        logger.warning("未配置 rewrite_guardrails 提示词，跳过自动修复")
        return original_text

    rewrite_input = f"""
[原文]
{original_text}

[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无"}

[违规列表]
{violations_text}
"""

    try:
        response = await llm_service.get_llm_response(
            system_prompt=rewrite_prompt,
            conversation_history=[{"role": "user", "content": rewrite_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=300.0,
            response_format=None,
        )
        cleaned = remove_think_tags(response)
        logger.info("成功修复违规内容")
        return cleaned
    except Exception as exc:
        logger.warning("自动修复失败，返回原文: %s", exc)
        return original_text


def _resolve_chapter_text(candidate_text: str, fallback_text: str) -> str:
    normalized_candidate = _normalize_version_content(candidate_text, None)
    if normalized_candidate:
        return normalized_candidate

    normalized_fallback = _normalize_version_content(fallback_text, None)
    if normalized_fallback:
        logger.warning("护栏重写未返回有效正文，已回退到修复前文本")
        return normalized_fallback

    return ""


def _build_ai_review_feedback(
    review_result: ReviewResult,
    version_count: int,
    *,
    perspective_notes: Optional[Dict[int, str]] = None,
    best_choice: Optional[int] = None,
) -> str:
    if review_result.raw_response:
        try:
            parsed = json.loads(unwrap_markdown_json(review_result.raw_response))
            if isinstance(parsed, dict):
                candidate = parsed.get("best_choice", parsed.get("best_version_index", review_result.best_version_index))
                if isinstance(candidate, str):
                    match = re.search(r"(\d+)", candidate)
                    candidate = int(match.group(1)) if match else review_result.best_version_index + 1
                if not isinstance(candidate, int):
                    candidate = review_result.best_version_index + 1
                if "best_version_index" in parsed and "best_choice" not in parsed:
                    resolved_best_choice = candidate + 1 if 0 <= candidate < version_count else max(1, min(candidate, version_count))
                else:
                    resolved_best_choice = candidate if 1 <= candidate <= version_count else candidate + 1
                final_best_choice = best_choice if best_choice is not None else resolved_best_choice
                parsed["best_choice"] = max(1, min(final_best_choice, version_count))
                parsed["reason_for_choice"] = parsed.get("reason_for_choice") or (
                    review_result.final_recommendation or review_result.overall_evaluation
                )
                if isinstance(parsed.get("evaluation"), dict):
                    normalized_evaluation: Dict[str, Dict[str, object]] = {}
                    for raw_key, raw_value in parsed["evaluation"].items():
                        match = re.search(r"(\d+)", str(raw_key))
                        if not match:
                            continue
                        raw_number = int(match.group(1))
                        display_number = raw_number + 1 if raw_number == 0 else raw_number
                        if not 1 <= display_number <= version_count:
                            continue
                        review_payload = raw_value if isinstance(raw_value, dict) else {}
                        normalized_evaluation[f"version{display_number}"] = {
                            "overall_review": review_payload.get("overall_review", "待补充"),
                            "pros": review_payload.get("pros", []),
                            "cons": review_payload.get("cons", []),
                        }
                    if normalized_evaluation:
                        for display_number in range(1, version_count + 1):
                            normalized_evaluation.setdefault(
                                f"version{display_number}",
                                {
                                    "overall_review": "该版本暂无完整评审明细，建议结合正文人工判断。",
                                    "pros": ["AI 未返回这一版的单独优点"],
                                    "cons": ["AI 未返回这一版的单独缺点"],
                                },
                            )
                            if perspective_notes and (display_number - 1) in perspective_notes:
                                normalized_evaluation[f"version{display_number}"]["cons"].append(
                                    perspective_notes[display_number - 1]
                                )
                                normalized_evaluation[f"version{display_number}"]["overall_review"] = (
                                    f"{normalized_evaluation[f'version{display_number}']['overall_review']} "
                                    f"{perspective_notes[display_number - 1]}"
                                ).strip()
                        parsed["evaluation"] = normalized_evaluation
                        return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            logger.warning("AI 评审原始返回无法直接转换为详情 JSON，将使用兼容结构")

    evaluations: Dict[str, Dict[str, object]] = {}
    for index in range(version_count):
        is_best = index == review_result.best_version_index
        pros = ["AI 推荐优先采用此版本"] if is_best else ["可作为备选版本参考"]
        cons: List[str] = []

        if is_best:
            if review_result.final_recommendation:
                pros.append(review_result.final_recommendation)
            if review_result.refinement_suggestions:
                cons.append(review_result.refinement_suggestions)
            cons.extend(review_result.critical_flaws)
        else:
            cons.append("综合表现不及最佳版本，建议仅作参考。")
        if perspective_notes and index in perspective_notes:
            cons.append(perspective_notes[index])

        evaluations[f"version{index + 1}"] = {
            "overall_review": (
                review_result.overall_evaluation
                if is_best
                else "AI 未将该版本评为最佳版本，可结合正文自行判断取舍。"
            ),
            "pros": pros,
            "cons": cons or ["暂无明显问题"],
        }

    payload = {
        "best_choice": best_choice or (review_result.best_version_index + 1),
        "reason_for_choice": review_result.final_recommendation or review_result.overall_evaluation,
        "evaluation": evaluations,
        "scores": review_result.scores,
        "refinement_suggestions": review_result.refinement_suggestions,
        "critical_flaws": review_result.critical_flaws,
    }
    return json.dumps(payload, ensure_ascii=False)


def _outline_has_terminal_signal(title: str, summary: str) -> bool:
    combined = f"{title} {summary}"
    return any(keyword in combined for keyword in ("终章", "尾声", "大结局", "完结", "落幕", "终局"))


def _outline_has_meta_language(text: str) -> bool:
    patterns = (
        r"距离.{0,8}完结",
        r"还有.{0,8}章.{0,8}完结",
        r"倒数第.{0,6}章",
        r"后续计划",
        r"即将完结",
        r"本章作为",
        r"为最终.{0,8}做铺垫",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _outline_title_is_generic(title: str) -> bool:
    return bool(re.fullmatch(r"(第\s*\d+\s*章|章节\s*\d+|\d+)", title.strip()))


def _format_outline_context(outlines: List[ChapterOutline]) -> str:
    if not outlines:
        return "暂无"

    if len(outlines) <= 18:
        target_outlines = outlines
    else:
        target_outlines = [*outlines[:6], *outlines[-12:]]

    return "\n".join(
        f"第{o.chapter_number}章 - {o.title}: {o.summary}"
        for o in target_outlines
    )


def _validate_generated_outlines(
    chapters: List[dict],
    expected_start: int,
    expected_count: int,
    *,
    avoid_ending: bool,
) -> List[str]:
    issues: List[str] = []
    if len(chapters) != expected_count:
        issues.append(f"需要返回 {expected_count} 章，实际返回 {len(chapters)} 章。")

    for index, item in enumerate(chapters):
        expected_number = expected_start + index
        chapter_number = item.get("chapter_number")
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()

        if chapter_number != expected_number:
            issues.append(f"第 {index + 1} 个返回项的章节号应为 {expected_number}。")
        if not title or len(title) < 2:
            issues.append(f"第 {expected_number} 章标题过短或为空。")
        elif _outline_title_is_generic(title):
            issues.append(f"第 {expected_number} 章标题过于泛化：{title}")
        if not summary or len(summary) < 12:
            issues.append(f"第 {expected_number} 章摘要过短。")
        if _outline_has_meta_language(f"{title} {summary}"):
            issues.append(f"第 {expected_number} 章出现了“距离完结/后续计划”这类元话术。")
        if avoid_ending and _outline_has_terminal_signal(title, summary):
            issues.append(f"第 {expected_number} 章仍然出现了提前完结信号。")

    return issues


def _strip_dialogue_for_perspective(text: str) -> str:
    stripped = text
    for pattern in (r"“[^”]*”", r"\"[^\"]*\"", r"『[^』]*』", r"「[^」]*」"):
        stripped = re.sub(pattern, "", stripped)
    return stripped


def _detect_narrative_perspective(text: str) -> str:
    cleaned = _strip_dialogue_for_perspective(text)
    first_person_score = sum(cleaned.count(token) for token in ("我", "我们", "咱", "咱们", "俺"))
    third_person_score = sum(cleaned.count(token) for token in ("他", "她", "他们", "她们"))

    if first_person_score >= max(8, int(third_person_score * 1.5)):
        return "first_person"
    if third_person_score >= max(8, int(first_person_score * 1.2)):
        return "third_person"
    return "mixed"


def _infer_expected_narrative_perspective(project: NovelProjectSchema | object, chapter_number: int) -> Optional[str]:
    blueprint = getattr(project, "blueprint", None)
    context_parts = [
        getattr(project, "initial_prompt", "") or "",
        getattr(blueprint, "style", "") or "",
        getattr(blueprint, "tone", "") or "",
        getattr(blueprint, "one_sentence_summary", "") or "",
        getattr(blueprint, "full_synopsis", "") or "",
    ]
    context_text = "\n".join(part for part in context_parts if part)

    if any(keyword in context_text for keyword in ("第一人称", "我视角", "主角自述")):
        return "first_person"
    if any(keyword in context_text for keyword in ("第三人称", "全知视角", "上帝视角", "旁观视角", "他视角", "她视角")):
        return "third_person"

    chapters = sorted(getattr(project, "chapters", []) or [], key=lambda item: item.chapter_number)
    perspective_votes: List[str] = []
    for chapter in chapters:
        if chapter.chapter_number >= chapter_number:
            continue
        if chapter.selected_version and chapter.selected_version.content:
            normalized = _normalize_version_content(
                chapter.selected_version.content,
                chapter.selected_version.metadata,
            )
            if normalized:
                perspective_votes.append(_detect_narrative_perspective(normalized))

    first_votes = perspective_votes.count("first_person")
    third_votes = perspective_votes.count("third_person")
    if first_votes > third_votes and first_votes >= 2:
        return "first_person"
    if third_votes > first_votes and third_votes >= 2:
        return "third_person"
    return None


async def _refresh_edit_summary_and_ingest(
    project_id: str,
    chapter_number: int,
    content: str,
    user_id: Optional[int],
) -> None:
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)

        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        if not chapter:
            return

        summary_text = None
        try:
            summary = await llm_service.get_summary(
                content,
                temperature=0.15,
                user_id=user_id,
            )
            summary_text = remove_think_tags(summary)
        except Exception as exc:
            logger.warning("编辑章节后自动生成摘要失败: %s", exc)

        if summary_text and chapter.selected_version and chapter.selected_version.content == content:
            chapter.real_summary = summary_text
            await session.commit()

        try:
            outline_stmt = select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
            outline_result = await session.execute(outline_stmt)
            outline = outline_result.scalars().first()
            title = outline.title if outline and outline.title else f"第{chapter_number}章"
            ingest_service = ChapterIngestionService(llm_service=llm_service)
            await ingest_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                content=content,
                summary=None,
                user_id=user_id or 0,
            )
            logger.info("章节 %s 向量化入库成功", chapter_number)
        except Exception as exc:
            logger.error("章节 %s 向量化入库失败: %s", chapter_number, exc)


async def _finalize_chapter_async(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)

        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.versions))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        if not chapter:
            return

        selected_version = next(
            (v for v in chapter.versions if v.id == selected_version_id),
            None,
        )
        selected_content = _normalize_version_content(
            selected_version.content if selected_version else None,
            selected_version.metadata if selected_version else None,
        )
        if not selected_version or not selected_content:
            return

        if selected_version.content != selected_content:
            selected_version.content = selected_content
        chapter.selected_version_id = selected_version.id
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.word_count = len(selected_content)
        await session.commit()

        vector_store = None
        if settings.vector_store_enabled:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过定稿写入: %s", exc)

        sync_session = getattr(session, "sync_session", session)
        finalize_service = FinalizeService(sync_session, llm_service, vector_store)
        await finalize_service.finalize_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_text=selected_content,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
        )


def _schedule_finalize_task(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
    asyncio.create_task(
        _finalize_chapter_async(
            project_id=project_id,
            chapter_number=chapter_number,
            selected_version_id=selected_version_id,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
        )
    )


@router.post("/advanced/generate", response_model=AdvancedGenerateResponse)
async def advanced_generate_chapter(
    request: AdvancedGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AdvancedGenerateResponse:
    """
    高级写作入口：通过 PipelineOrchestrator 统一编排生成流程。
    """
    orchestrator = PipelineOrchestrator(session)
    result = await orchestrator.generate_chapter(
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        writing_notes=request.writing_notes,
        user_id=current_user.id,
        flow_config=request.flow_config.model_dump(),
    )

    flow_config = request.flow_config
    if flow_config.async_finalize and result.get("variants"):
        best_index = result.get("best_version_index", 0)
        variants = result["variants"]
        if 0 <= best_index < len(variants):
            selected_version_id = variants[best_index]["version_id"]
            background_tasks.add_task(
                _schedule_finalize_task,
                request.project_id,
                request.chapter_number,
                selected_version_id,
                current_user.id,
                False,
            )

    return AdvancedGenerateResponse(**result)


@router.post("/chapters/{chapter_number}/finalize", response_model=FinalizeChapterResponse)
async def finalize_chapter(
    chapter_number: int,
    request: FinalizeChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> FinalizeChapterResponse:
    """
    定稿入口：选中版本后触发 FinalizeService 进行记忆更新与快照写入。
    """
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    stmt = (
        select(Chapter)
        .options(selectinload(Chapter.versions))
        .where(
            Chapter.project_id == request.project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    selected_version = next(
        (v for v in chapter.versions if v.id == request.selected_version_id),
        None,
    )
    selected_content = _normalize_version_content(
        selected_version.content if selected_version else None,
        selected_version.metadata if selected_version else None,
    )
    if not selected_version or not selected_content:
        raise HTTPException(status_code=400, detail="选中的版本不存在或内容为空")

    if selected_version.content != selected_content:
        selected_version.content = selected_content
    chapter.selected_version_id = selected_version.id
    chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
    chapter.word_count = len(selected_content)
    await session.commit()

    vector_store = None
    if settings.vector_store_enabled and not request.skip_vector_update:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过定稿写入: %s", exc)

    sync_session = getattr(session, "sync_session", session)
    finalize_service = FinalizeService(sync_session, LLMService(session), vector_store)
    finalize_result = await finalize_service.finalize_chapter(
        project_id=request.project_id,
        chapter_number=chapter_number,
        chapter_text=selected_content,
        user_id=current_user.id,
        skip_vector_update=request.skip_vector_update or False,
    )

    return FinalizeChapterResponse(
        project_id=request.project_id,
        chapter_number=chapter_number,
        selected_version_id=selected_version.id,
        result=finalize_result,
    )


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """
    生成章节正文 - 三层架构流程：
    1. 收集上下文和历史摘要
    2. L2 Director: 生成章节导演脚本（ChapterMission）
    3. 信息可见性过滤：裁剪蓝图，移除未登场角色
    4. L3 Writer: 生成正文（使用 writing_v2 提示词）
    5. 护栏检查：检测并修复违规内容
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)
    context_builder = WriterContextBuilder()
    guardrails = ChapterGuardrails()

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    
    # ========== 1. 收集历史上下文 ==========
    completed_chapters = []
    completed_summaries = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            summary = await llm_service.get_summary(
                existing.selected_version.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            existing.real_summary = remove_think_tags(summary)
            await session.commit()
        completed_chapters.append({
            "chapter_number": existing.chapter_number,
            "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
            "summary": existing.real_summary,
        })
        completed_summaries.append(existing.real_summary or "")
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    # 处理关系字段名
    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    # 提取所有角色名
    all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

    # ========== 2. L2 Director: 生成章节导演脚本 ==========
    chapter_mission = await _generate_chapter_mission(
        llm_service=llm_service,
        prompt_service=prompt_service,
        blueprint_dict=blueprint_dict,
        previous_summary=previous_summary_text,
        previous_tail=previous_tail_excerpt,
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        introduced_characters=[],  # 将在下一步填充
        all_characters=all_characters,
        user_id=current_user.id,
    )

    # 从导演脚本中提取允许登场的新角色
    allowed_new_characters = []
    if chapter_mission:
        allowed_new_characters = chapter_mission.get("allowed_new_characters", [])

    # ========== 3. 信息可见性过滤 ==========
    visibility_context = context_builder.build_visibility_context(
        blueprint=blueprint_dict,
        completed_summaries=completed_summaries,
        previous_tail=previous_tail_excerpt,
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        allowed_new_characters=allowed_new_characters,
    )

    writer_blueprint = visibility_context["writer_blueprint"]
    forbidden_characters = visibility_context["forbidden_characters"]
    introduced_characters = visibility_context["introduced_characters"]

    logger.info(
        "项目 %s 第 %s 章信息可见性: 已登场=%s, 允许新登场=%s, 禁止=%s",
        project_id,
        request.chapter_number,
        len(introduced_characters),
        len(allowed_new_characters),
        len(forbidden_characters),
    )

    # ========== 4. 准备 RAG 上下文 ==========
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"

    # ========== 5. 构建写作提示词 ==========
    # 优先使用 writing_v2，fallback 到 writing
    writer_prompt = await prompt_service.get_prompt("writing_v2")
    if not writer_prompt:
        writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")

    # 使用裁剪后的蓝图（移除了 full_synopsis 和未登场角色）
    blueprint_text = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)
    
    # 构建导演脚本文本
    mission_text = json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无导演脚本"
    
    # 构建禁止角色列表
    forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

    prompt_sections = [
        ("[世界蓝图](JSON，已裁剪)", blueprint_text),
        ("[上一章摘要]", previous_summary_text or "暂无（这是第一章）"),
        ("[上一章结尾]", previous_tail_excerpt or "暂无（这是第一章）"),
        ("[章节导演脚本](JSON)", mission_text),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要](Markdown)", rag_summaries_text),
        ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
        ("[禁止角色](本章不允许提及)", forbidden_text),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词长度: %s 字符", len(prompt_input))

    # ========== 6. L3 Writer: 生成正文 ==========
    async def _generate_single_version(idx: int, version_style_hint: Optional[str] = None) -> Dict:
        """生成单个版本，支持差异化风格提示"""
        try:
            # 如果有版本风格提示，添加到 prompt_input
            final_prompt_input = prompt_input
            if version_style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{version_style_hint}"

            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
                response_format=None,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            
            # ========== 7. 护栏检查 ==========
            guardrail_result = guardrails.check(
                generated_text=normalized,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
            )

            final_content = normalized
            guardrail_metadata = {"passed": guardrail_result.passed, "violations": []}

            if not guardrail_result.passed:
                logger.warning(
                    "项目 %s 第 %s 章版本 %s 检测到 %s 个违规",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    len(guardrail_result.violations),
                )
                guardrail_metadata["violations"] = [
                    {"type": v.type, "severity": v.severity, "description": v.description}
                    for v in guardrail_result.violations
                ]

                # 尝试自动修复
                violations_text = guardrails.format_violations_for_rewrite(guardrail_result)
                final_content = await _rewrite_with_guardrails(
                    llm_service=llm_service,
                    prompt_service=prompt_service,
                    original_text=normalized,
                    chapter_mission=chapter_mission,
                    violations_text=violations_text,
                    user_id=current_user.id,
                )

            def _extract_text(value: object) -> Optional[str]:
                if not value:
                    return None
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    for key in ("content", "chapter_content", "chapter_text", "text", "body", "story"):
                        if value.get(key):
                            nested = _extract_text(value.get(key))
                            if nested:
                                return nested
                    return None
                if isinstance(value, list):
                    for item in value:
                        nested = _extract_text(item)
                        if nested:
                            return nested
                return None

            parsed_json = None
            extracted_text = None
            try:
                parsed_json = json.loads(final_content)
                extracted_text = _extract_text(parsed_json)
            except Exception:
                parsed_json = None

            resolved_content = _resolve_chapter_text(extracted_text or final_content, normalized)
            if not resolved_content.strip():
                raise HTTPException(
                    status_code=500,
                    detail=f"生成章节第 {idx + 1} 个版本时未得到有效正文",
                )

            return {
                "content": resolved_content,
                "parsed_json": parsed_json,
                "guardrail": guardrail_metadata,
                "chapter_mission": chapter_mission,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )

    # 版本差异化风格提示
    version_style_hints = [
        "情绪更细腻，节奏更慢，多写内心戏和感官描写",
        "冲突更强，节奏更快，多写动作和对话",
        "悬念更重，多埋伏笔，结尾钩子更强",
    ]

    raw_versions = []
    try:
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            raw_versions.append(await _generate_single_version(idx, style_hint))
    except Exception as exc:
        logger.exception("项目 %s 生成第 %s 章时发生异常: %s", project_id, request.chapter_number, exc)
        chapter.status = "failed"
        await session.commit()
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=500,
            detail=f"生成章节失败: {str(exc)[:200]}"
        )

    contents: List[str] = []
    metadata: List[Dict] = []
    for variant in raw_versions:
        if isinstance(variant, dict):
            if "content" in variant and isinstance(variant["content"], str):
                contents.append(variant["content"])
            elif "chapter_content" in variant:
                contents.append(str(variant["chapter_content"]))
            else:
                contents.append(json.dumps(variant, ensure_ascii=False))
            metadata.append(variant)
        else:
            contents.append(str(variant))
            metadata.append({"raw": variant})

    # ========== 8. AI Review: 自动评审多版本 ==========
    ai_review_result = None
    if len(contents) > 1:
        try:
            ai_review_service = AIReviewService(llm_service, prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=current_user.id,
            )
            if ai_review_result:
                logger.info(
                    "项目 %s 第 %s 章 AI 评审完成: 推荐版本=%s",
                    project_id,
                    request.chapter_number,
                    ai_review_result.best_version_index,
                )
                # 将评审结果附加到 metadata
                for i, m in enumerate(metadata):
                    m["ai_review"] = {
                        "is_best": i == ai_review_result.best_version_index,
                        "scores": ai_review_result.scores,
                        "evaluation": ai_review_result.overall_evaluation if i == ai_review_result.best_version_index else None,
                        "flaws": ai_review_result.critical_flaws if i == ai_review_result.best_version_index else None,
                        "suggestions": ai_review_result.refinement_suggestions if i == ai_review_result.best_version_index else None,
                    }
        except Exception as exc:
            logger.warning("AI 评审失败，跳过: %s", exc)

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    # 使用 novel_service.select_chapter_version 确保排序一致
    # 该函数会按 created_at 排序并校验索引
    selected_version = await novel_service.select_chapter_version(chapter, request.version_index)
    
    # 校验内容是否为空
    if not selected_version.content or len(selected_version.content.strip()) == 0:
        # 回滚状态，不标记为 successful
        await session.rollback()
        raise HTTPException(status_code=400, detail="选中的版本内容为空，无法确认为最终版")

    # 异步触发向量化入库
    try:
        llm_service = LLMService(session)
        ingest_service = ChapterIngestionService(llm_service=llm_service)
        await ingest_service.ingest_chapter(
            project_id=project_id,
            chapter_number=request.chapter_number,
            title=chapter.title or f"第{request.chapter_number}章",
            content=selected_version.content,
            summary=None
        )
        logger.info(f"章节 {request.chapter_number} 向量化入库成功")
    except Exception as e:
        logger.error(f"章节 {request.chapter_number} 向量化入库失败: {e}")
        # 向量化失败不应阻止版本选择，仅记录错误

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    stmt = (
        select(Chapter)
        .options(selectinload(Chapter.selected_version), selectinload(Chapter.versions))
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()

    if not chapter:
        chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    sorted_versions = sorted(chapter.versions or [], key=lambda item: item.created_at)
    if not sorted_versions:
        raise HTTPException(status_code=400, detail="该章节还没有生成任何版本，无法进行评审")

    version_texts = [
        _normalize_version_content(version.content, version.metadata)
        for version in sorted_versions
    ]
    if not all(text.strip() for text in version_texts):
        raise HTTPException(
            status_code=400,
            detail="当前章节存在无效版本正文，请先重新生成后再进行 AI 评审",
        )

    chapter_mission = None
    for version in sorted_versions:
        if isinstance(version.metadata, dict) and version.metadata.get("chapter_mission"):
            chapter_mission = version.metadata["chapter_mission"]
            break

    expected_perspective = _infer_expected_narrative_perspective(project, request.chapter_number)
    review_indices = list(range(len(sorted_versions)))
    perspective_notes: Dict[int, str] = {}
    if expected_perspective:
        matched_indices: List[int] = []
        expected_label = "第一人称" if expected_perspective == "first_person" else "第三人称"
        for index, text in enumerate(version_texts):
            detected_perspective = _detect_narrative_perspective(text)
            if detected_perspective in (expected_perspective, "mixed"):
                matched_indices.append(index)
                continue
            detected_label = "第一人称" if detected_perspective == "first_person" else "第三人称"
            perspective_notes[index] = (
                f"叙述人称与全书既有设定不一致：本书应保持{expected_label}，"
                f"该版本更接近{detected_label}，不应优先采用。"
            )
        if matched_indices:
            review_indices = matched_indices

    chapter.status = "evaluating"
    await session.commit()

    try:
        ai_review_service = AIReviewService(llm_service, prompt_service)
        review_result = await ai_review_service.review_versions(
            versions=[version_texts[index] for index in review_indices],
            chapter_mission=chapter_mission,
            user_id=current_user.id,
            expected_perspective=expected_perspective,
        )
        if not review_result:
            raise ValueError("AI 评审未返回有效结果")

        best_index_within_review = max(0, min(review_result.best_version_index, len(review_indices) - 1))
        best_index = review_indices[best_index_within_review]
        evaluation_text = _build_ai_review_feedback(
            review_result,
            len(sorted_versions),
            perspective_notes=perspective_notes,
            best_choice=best_index + 1,
        )
        await novel_service.add_chapter_evaluation(
            chapter=chapter,
            version=sorted_versions[best_index],
            feedback=evaluation_text,
            decision="reviewed",
        )
        logger.info("项目 %s 第 %s 章评审成功", project_id, request.chapter_number)
    except Exception as exc:
        logger.exception("项目 %s 第 %s 章评审失败: %s", project_id, request.chapter_number, exc)
        # 回滚事务，恢复状态
        await session.rollback()
        
        # 重新加载 chapter 对象（因为 rollback 后对象已脱离 session）
        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == request.chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        
        if chapter:
            # 使用 add_chapter_evaluation 创建失败记录
            # 注意：这里不能再用 add_chapter_evaluation，因为它会设置状态为 waiting_for_confirm
            # 失败时应该设置为 evaluation_failed
            from app.models.novel import ChapterEvaluation
            evaluation_record = ChapterEvaluation(
                chapter_id=chapter.id,
                version_id=sorted_versions[-1].id if sorted_versions else None,
                decision="failed",
                feedback=f"评审失败: {str(exc)}",
                score=None
            )
            session.add(evaluation_record)
            chapter.status = "evaluation_failed"
            await session.commit()
        
        # 抛出异常，让前端知道评审失败
        raise HTTPException(status_code=500, detail=f"评审失败: {str(exc)}")
    
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    for ch_num in request.chapter_numbers:
        await novel_service.delete_chapter(project_id, ch_num)

    await session.commit()
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapters_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    
    # 获取蓝图信息
    project_schema = await novel_service._serialize_project(project)
    blueprint_text = json.dumps(project_schema.blueprint.model_dump(), ensure_ascii=False, indent=2)

    sorted_outlines = sorted(project.outlines, key=lambda x: x.chapter_number)
    avoid_ending = request.avoid_ending
    planning_notes = request.planning_notes or "无额外扩展要求"
    generation_start = request.start_chapter
    generation_count = request.num_chapters
    effective_outlines = sorted_outlines
    replanning_reason = "保持当前主线推进，优先补足冲突、伏笔和人物推进。"

    if (
        avoid_ending
        and sorted_outlines
        and _outline_has_terminal_signal(sorted_outlines[-1].title or "", sorted_outlines[-1].summary or "")
    ):
        effective_outlines = sorted_outlines[:-1]
        generation_start = sorted_outlines[-1].chapter_number
        generation_count = request.num_chapters + 1
        replanning_reason = (
            "当前最后一章已经带有终章/完结信号。本次需要把终局后移，"
            "从该章开始重做后续章节，让故事重新获得推进空间。"
        )

    existing_outlines_text = _format_outline_context(effective_outlines)

    outline_prompt = await prompt_service.get_prompt("outline_generation")
    if not outline_prompt:
        raise HTTPException(status_code=500, detail="未配置大纲生成提示词")

    prompt_input = f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
{existing_outlines_text}

[任务性质]
这不是机械地“往后加几章”，而是一次后续剧情规划升级。
{replanning_reason}

[硬性规则]
1. 标题必须像正式小说章节名，禁止只写数字、`第X章`、`后续计划`、`距离完结还有几章` 之类的元话术。
2. 摘要必须写真实剧情推进，不要对读者解释“这是过渡章”“离完结还有多远”。
3. 除非用户明确要求完结，否则不要让新增章节直接终章、尾声或大结局。
4. 每一章都要有可感知的戏剧动作：冲突升级、关系变化、信息揭示、伏笔推进、局势反转至少命中其一。
5. 新增章节的质量必须与蓝图阶段产出一致，不能退化成占位标题或流水账摘要。

[扩展重点]
{planning_notes}

[生成任务]
请从第 {generation_start} 章开始，重新规划接下来的 {generation_count} 章大纲。
要求返回 JSON 格式，包含一个 chapters 数组，每个元素包含 chapter_number, title, summary。
"""

    validation_feedback = ""
    new_outlines: List[dict] = []
    for attempt in range(2):
        response = await llm_service.get_llm_response(
            system_prompt=outline_prompt,
            conversation_history=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt_input}\n\n[上轮问题]\n{validation_feedback}"
                        if validation_feedback
                        else prompt_input
                    ),
                }
            ],
            temperature=0.7,
            user_id=current_user.id,
        )

        cleaned = remove_think_tags(response)
        normalized = unwrap_markdown_json(cleaned)
        try:
            data = json.loads(normalized)
            candidate_outlines = data.get("chapters", [])
        except Exception as exc:
            logger.warning("后续大纲第 %s 次解析失败: %s", attempt + 1, exc)
            validation_feedback = f"返回内容未能解析成合法 JSON：{exc}"
            continue

        issues = _validate_generated_outlines(
            candidate_outlines,
            generation_start,
            generation_count,
            avoid_ending=avoid_ending,
        )
        if not issues:
            new_outlines = candidate_outlines
            break

        validation_feedback = "请严格修正以下问题后重写整个 chapters 数组：\n- " + "\n- ".join(issues)
        logger.warning("后续大纲第 %s 次质量校验未通过: %s", attempt + 1, issues)

    if not new_outlines:
        raise HTTPException(status_code=500, detail="后续大纲生成失败：返回内容质量不达标，请重试")

    try:
        for item in new_outlines:
            await novel_service.update_or_create_outline(
                project_id,
                item["chapter_number"],
                item["title"],
                item["summary"]
            )
        await session.commit()
    except Exception as exc:
        logger.exception("生成大纲落库失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {str(exc)}")

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter_content(
    project_id: str,
    request: EditChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    
    await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    
    # 更新内容：优先更新选中版本，否则选最新版本或创建新版本
    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = request.content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=request.content,
            version_label="manual_edit",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id
    
    chapter.status = "successful"
    chapter.word_count = len(request.content or "")
    await session.commit()

    background_tasks.add_task(
        _refresh_edit_summary_and_ingest,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
    )

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit-fast", response_model=ChapterSchema)
async def edit_chapter_content_fast(
    project_id: str,
    request: EditChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = request.content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=request.content,
            version_label="manual_edit",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id

    chapter.status = "successful"
    chapter.word_count = len(request.content or "")
    await session.commit()

    background_tasks.add_task(
        _refresh_edit_summary_and_ingest,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
    )

    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.versions),
            selectinload(Chapter.evaluations),
            selectinload(Chapter.selected_version),
        )
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    outline_stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == request.chapter_number,
    )
    outline_result = await session.execute(outline_stmt)
    outline = outline_result.scalars().first()

    title = outline.title if outline else f"第{request.chapter_number}章"
    summary = outline.summary if outline else ""
    real_summary = chapter.real_summary
    content = (
        _normalize_version_content(chapter.selected_version.content, chapter.selected_version.metadata)
        if chapter.selected_version
        else None
    )
    versions = (
        [
            _normalize_version_content(v.content, v.metadata)
            for v in sorted(chapter.versions, key=lambda item: item.created_at)
        ]
        if chapter.versions
        else None
    )
    evaluation_text = None
    if chapter.evaluations:
        latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
        evaluation_text = latest.feedback or latest.decision
    status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value

    return ChapterSchema(
        chapter_number=request.chapter_number,
        title=title,
        summary=summary,
        real_summary=real_summary,
        content=content,
        versions=versions,
        evaluation=evaluation_text,
        generation_status=ChapterGenerationStatus(status_value),
        word_count=chapter.word_count or 0,
    )
