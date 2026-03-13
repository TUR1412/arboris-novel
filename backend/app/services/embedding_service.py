# AIMETA P=嵌入服务_文本向量化|R=文本嵌入_向量生成|NR=不含存储逻辑|E=EmbeddingService|X=internal|A=嵌入生成|D=openai|S=none|RD=./README.ai
"""
嵌入服务 (EmbeddingService)

优先复用 LLMService 的统一配置解析链，避免出现与设置页不一致的旁路。
若未传入 session，则退回到兼容模式，仅使用 settings 中的默认配置。
"""
import hashlib
import logging
from typing import List, Optional, Sequence

from ..core.config import settings
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class EmbeddingService:
    """文本嵌入服务，优先复用统一的运行时配置解析。"""

    def __init__(self, session=None, *, user_id: Optional[int] = None, model: Optional[str] = None):
        self._cache: dict[str, List[float]] = {}
        self._user_id = user_id
        self._model = model or settings.embedding_model or "text-embedding-3-large"
        self._llm_service = LLMService(session) if session is not None else None
        self._client = None
        if self._llm_service is None:
            self._init_legacy_client()

    def _init_legacy_client(self) -> None:
        """兼容旧路径，仅在未提供 session 时启用。"""
        try:
            from openai import AsyncOpenAI

            api_key = settings.embedding_api_key or settings.openai_api_key
            base_url = str(settings.embedding_base_url) if settings.embedding_base_url else (
                str(settings.openai_base_url) if settings.openai_base_url else None
            )
            if api_key:
                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                logger.info("兼容模式嵌入服务初始化成功")
            else:
                logger.warning("未配置可用的默认嵌入 API Key，兼容模式嵌入服务不可用")
        except ImportError:
            logger.warning("未安装 openai 包，嵌入服务不可用")
        except Exception as exc:  # noqa: BLE001
            logger.error("初始化嵌入服务失败: %s", exc)

    async def get_embedding(
        self,
        text: str,
        use_cache: bool = True,
    ) -> Optional[List[float]]:
        """获取单段文本的嵌入向量。"""
        if not text:
            return None

        cache_key = self._get_cache_key(text)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        embedding: Optional[List[float]] = None
        if self._llm_service is not None:
            result = await self._llm_service.get_embedding(
                text,
                user_id=self._user_id,
                model=self._model,
            )
            embedding = result or None
        elif self._client is not None:
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=text[:8000],
                )
                embedding = response.data[0].embedding
            except Exception as exc:  # noqa: BLE001
                logger.error("生成嵌入向量失败: %s", exc)
                embedding = None

        if use_cache and embedding:
            self._cache[cache_key] = embedding
        return embedding

    async def get_embeddings_batch(
        self,
        texts: Sequence[str],
        use_cache: bool = True,
    ) -> List[Optional[List[float]]]:
        """批量获取文本嵌入。"""
        results: List[Optional[List[float]]] = []
        for text in texts:
            results.append(await self.get_embedding(text, use_cache=use_cache))
        return results

    def _get_cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def clear_cache(self) -> None:
        self._cache.clear()

    @property
    def is_available(self) -> bool:
        return self._llm_service is not None or self._client is not None


__all__ = ["EmbeddingService"]
