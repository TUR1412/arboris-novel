# AIMETA P=AI评审服务_多版本对比选优|R=版本评分_最佳选择_改进建议|NR=不含数据存储|E=none|X=internal|A=评审_对比|D=openai|S=net|RD=./README.ai
"""
AIReviewService: AI 评审服务

核心职责：
1. 对多个生成版本进行对比评审
2. 根据起点中文网爆款标准打分
3. 选出最佳版本并给出改进建议
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """评审结果"""
    best_version_index: int
    scores: Dict[str, int]  # immersion, pacing, hook, character
    overall_evaluation: str
    critical_flaws: List[str]
    refinement_suggestions: str
    final_recommendation: str
    raw_response: Optional[str] = None


class AIReviewService:
    """
    AI 评审服务 - 金牌编辑模式
    
    使用 editor_review 提示词对多个版本进行对比评审，
    选出最具爆款潜力的版本。
    """

    def __init__(self, llm_service: LLMService, prompt_service: PromptService):
        self.llm_service = llm_service
        self.prompt_service = prompt_service

    async def review_versions(
        self,
        versions: List[str],
        chapter_mission: Optional[dict] = None,
        user_id: int = 0,
        expected_perspective: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """
        对多个版本进行评审，返回评审结果。

        Args:
            versions: 多个版本的正文内容
            chapter_mission: 章节导演脚本（用于评估是否符合预期）
            user_id: 用户 ID

        Returns:
            ReviewResult: 评审结果，如果失败返回 None
        """
        if not versions:
            logger.warning("没有版本可供评审")
            return None

        if len(versions) == 1:
            logger.info("只有一个版本，跳过对比评审")
            return ReviewResult(
                best_version_index=0,
                scores={"immersion": 0, "pacing": 0, "hook": 0, "character": 0},
                overall_evaluation="单版本，无需对比",
                critical_flaws=[],
                refinement_suggestions="",
                final_recommendation="采用唯一版本",
            )

        # 获取评审提示词
        review_prompt = await self.prompt_service.get_prompt("editor_review")
        if not review_prompt:
            logger.warning("未配置 editor_review 提示词，跳过 AI 评审")
            return None

        # 构建评审输入
        review_input = self._build_review_input(versions, chapter_mission, expected_perspective)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=review_prompt,
                conversation_history=[{"role": "user", "content": review_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=180.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            
            result = self._parse_review_response(normalized, len(versions))
            result.raw_response = cleaned
            
            logger.info(
                "AI 评审完成: 最佳版本=%s, 综合评分=%.1f",
                result.best_version_index,
                sum(result.scores.values()) / len(result.scores) if result.scores else 0,
            )
            return result
        except Exception as exc:
            logger.exception("AI 评审失败: %s", exc)
            return None

    def _build_review_input(
        self,
        versions: List[str],
        chapter_mission: Optional[dict],
        expected_perspective: Optional[str],
    ) -> str:
        """构建评审输入文本"""
        lines = []

        if chapter_mission:
            lines.append("[章节导演脚本]")
            lines.append(json.dumps(chapter_mission, ensure_ascii=False, indent=2))
            lines.append("")

        if expected_perspective:
            lines.append("[叙述视角硬约束]")
            lines.append(
                "本书必须保持"
                + ("第一人称" if expected_perspective == "first_person" else "第三人称")
                + "叙述。若某个版本人称明显跑偏，即使文句更华丽，也不能推荐为最佳版本。"
            )
            lines.append("")

        lines.append("[待评审版本]")
        for i, content in enumerate(versions):
            lines.append(f"--- 版本 {i + 1} ---")
            if len(content) > 3200:
                truncated = (
                    f"{content[:1800]}\n\n"
                    f"...[中段省略 {len(content) - 3000} 字]...\n\n"
                    f"{content[-1200:]}"
                )
            else:
                truncated = content
            lines.append(truncated)
            if len(content) > 3200:
                lines.append(f"... (已保留开头与结尾关键片段，原文共 {len(content)} 字)")
            lines.append("")

        lines.append("[评审要求]")
        lines.append("请对每个版本都分别给出评估，并在最后做横向对比。")
        lines.append("版本编号必须从 1 开始，严禁输出 version0、版本0。")
        lines.append("请仅返回 JSON，推荐结构如下：")
        lines.append(
            json.dumps(
                {
                    "best_choice": 1,
                    "reason_for_choice": "为什么推荐该版本",
                    "evaluation": {
                        "version1": {
                            "overall_review": "综合评价",
                            "pros": ["优点1", "优点2"],
                            "cons": ["缺点1", "缺点2"],
                        }
                    },
                    "scores": {
                        "immersion": 8,
                        "pacing": 8,
                        "hook": 8,
                        "character": 8,
                    },
                    "refinement_suggestions": "整体改进建议",
                    "critical_flaws": ["关键问题1"],
                    "final_recommendation": "最终推荐结论",
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return "\n".join(lines)

    def _parse_review_response(self, response: str, version_count: int) -> ReviewResult:
        """解析评审响应"""
        try:
            data = json.loads(response)
            best_version_index = self._coerce_best_version_index(data, version_count)
            return ReviewResult(
                best_version_index=best_version_index,
                scores=data.get("scores", {}),
                overall_evaluation=data.get("overall_evaluation", "") or data.get("reason_for_choice", ""),
                critical_flaws=data.get("critical_flaws", []),
                refinement_suggestions=data.get("refinement_suggestions", ""),
                final_recommendation=data.get("final_recommendation", "") or data.get("reason_for_choice", ""),
            )
        except json.JSONDecodeError:
            logger.warning("评审响应不是有效 JSON，使用默认结果")
            return ReviewResult(
                best_version_index=0,
                scores={},
                overall_evaluation=response[:500] if response else "",
                critical_flaws=[],
                refinement_suggestions="",
                final_recommendation="解析失败，建议人工审核",
            )

    @staticmethod
    def _coerce_best_version_index(data: Dict[str, Any], version_count: int) -> int:
        raw_choice = data.get("best_choice")
        raw_index = data.get("best_version_index")
        candidate = raw_choice if raw_choice is not None else raw_index
        if candidate is None:
            return 0

        if isinstance(candidate, str):
            match = re.search(r"(\d+)", candidate)
            candidate = int(match.group(1)) if match else 0

        if not isinstance(candidate, int):
            return 0

        if raw_choice is not None:
            if 1 <= candidate <= version_count:
                return candidate - 1
            if 0 <= candidate < version_count:
                return candidate

        if 0 <= candidate < version_count:
            return candidate
        if 1 <= candidate <= version_count:
            return candidate - 1
        return 0

    async def auto_select_best_version(
        self,
        versions: List[str],
        chapter_mission: Optional[dict] = None,
        user_id: int = 0,
        expected_perspective: Optional[str] = None,
    ) -> int:
        """
        自动选择最佳版本的索引。

        Args:
            versions: 多个版本的正文内容
            chapter_mission: 章节导演脚本
            user_id: 用户 ID

        Returns:
            最佳版本的索引（从 0 开始）
        """
        result = await self.review_versions(
            versions,
            chapter_mission,
            user_id,
            expected_perspective=expected_perspective,
        )
        if result:
            return result.best_version_index
        return 0  # 默认返回第一个版本
