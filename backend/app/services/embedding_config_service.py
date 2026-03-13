# AIMETA P=嵌入配置服务_RAG配置业务逻辑|R=配置管理_模型选择|NR=不含向量调用|E=EmbeddingConfigService|X=internal|A=服务类|D=sqlalchemy,httpx|S=db,net|RD=./README.ai
from typing import List, Optional
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import EmbeddingConfig
from ..repositories.embedding_config_repository import EmbeddingConfigRepository
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..schemas.embedding_config import EmbeddingConfigCreate, EmbeddingConfigRead
from .llm_config_service import LLMConfigService


logger = logging.getLogger(__name__)


class EmbeddingConfigService:
    """用户自定义的 RAG / Embedding 配置服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EmbeddingConfigRepository(session)
        self.llm_repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.llm_config_service = LLMConfigService(session)

    def _serialize_url(self, value: Optional[object]) -> Optional[str]:
        return str(value) if value is not None else None

    def _to_read(self, instance: EmbeddingConfig) -> EmbeddingConfigRead:
        return EmbeddingConfigRead(
            user_id=instance.user_id,
            embedding_provider=instance.embedding_provider,
            embedding_base_url=instance.embedding_base_url,
            embedding_api_key=None,
            embedding_model=instance.embedding_model,
            embedding_model_vector_size=instance.embedding_model_vector_size,
            has_api_key=bool(instance.embedding_api_key),
        )

    async def upsert_config(self, user_id: int, payload: EmbeddingConfigCreate) -> EmbeddingConfigRead:
        instance = await self.repo.get_by_user(user_id)
        data = payload.model_dump(exclude_unset=True)
        if "embedding_base_url" in data and data["embedding_base_url"] is not None:
            data["embedding_base_url"] = str(data["embedding_base_url"])
        if instance:
            for key, value in data.items():
                setattr(instance, key, value)
            await self.session.flush()
        else:
            instance = EmbeddingConfig(user_id=user_id, **data)
            await self.repo.add(instance)
        await self.session.commit()
        return self._to_read(instance)

    async def get_config(self, user_id: int) -> Optional[EmbeddingConfigRead]:
        instance = await self.repo.get_by_user(user_id)
        return self._to_read(instance) if instance else None

    async def delete_config(self, user_id: int) -> bool:
        instance = await self.repo.get_by_user(user_id)
        if not instance:
            return False
        await self.repo.delete(instance)
        await self.session.commit()
        return True

    async def get_available_models(
        self,
        *,
        user_id: Optional[int],
        provider: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> List[str]:
        """根据提供方获取可用的嵌入模型列表。"""
        runtime = await self.resolve_runtime_config(
            user_id=user_id,
            override_provider=provider,
            override_base_url=base_url,
            override_api_key=api_key,
        )
        runtime_provider = runtime["provider"] or "openai"
        runtime_base_url = runtime["base_url"]
        runtime_api_key = runtime["api_key"]

        if runtime_provider == "ollama":
            return await self._get_ollama_models(runtime_base_url)
        if not runtime_api_key:
            logger.warning("获取嵌入模型列表失败：OpenAI 兼容接口缺少 API Key")
            return []
        models = await self.llm_config_service.get_available_models(
            api_key=runtime_api_key,
            base_url=runtime_base_url,
        )
        return self._filter_embedding_models(models)

    async def resolve_runtime_config(
        self,
        *,
        user_id: Optional[int],
        override_provider: Optional[str] = None,
        override_base_url: Optional[str] = None,
        override_api_key: Optional[str] = None,
    ) -> dict[str, Optional[str]]:
        user_config = await self.repo.get_by_user(user_id) if user_id else None
        user_llm_config = await self.llm_repo.get_by_user(user_id) if user_id else None

        provider = (
            override_provider
            or (user_config.embedding_provider if user_config and user_config.embedding_provider else None)
            or await self._get_system_value("embedding.provider")
            or settings.embedding_provider
            or "openai"
        ).lower()

        if provider == "ollama":
            return {
                "provider": "ollama",
                "api_key": None,
                "base_url": (
                    override_base_url
                    or (user_config.embedding_base_url if user_config and user_config.embedding_base_url else None)
                    or await self._get_system_value("ollama.embedding_base_url")
                    or await self._get_system_value("embedding.base_url")
                    or self._serialize_url(settings.ollama_embedding_base_url)
                    or self._serialize_url(settings.embedding_base_url)
                    or "http://127.0.0.1:11434"
                ),
                "model": (
                    user_config.embedding_model if user_config and user_config.embedding_model else None
                ) or await self._get_system_value("ollama.embedding_model")
                or settings.ollama_embedding_model,
                "vector_size": (
                    str(user_config.embedding_model_vector_size)
                    if user_config and user_config.embedding_model_vector_size is not None
                    else None
                ) or await self._get_system_value("embedding.model_vector_size")
                or self._serialize_url(settings.embedding_model_vector_size),
            }

        return {
            "provider": "openai",
            "api_key": (
                override_api_key
                or (user_config.embedding_api_key if user_config and user_config.embedding_api_key else None)
                or (
                    user_llm_config.llm_provider_api_key
                    if user_llm_config and user_llm_config.llm_provider_api_key
                    else None
                )
                or await self._get_system_value("embedding.api_key")
                or await self._get_system_value("llm.api_key")
                or settings.embedding_api_key
                or settings.openai_api_key
            ),
            "base_url": (
                override_base_url
                or (user_config.embedding_base_url if user_config and user_config.embedding_base_url else None)
                or (
                    user_llm_config.llm_provider_url
                    if user_llm_config and user_llm_config.llm_provider_url
                    else None
                )
                or await self._get_system_value("embedding.base_url")
                or await self._get_system_value("llm.base_url")
                or self._serialize_url(settings.embedding_base_url)
                or self._serialize_url(settings.openai_base_url)
            ),
            "model": (
                user_config.embedding_model if user_config and user_config.embedding_model else None
            ) or await self._get_system_value("embedding.model") or settings.embedding_model,
            "vector_size": (
                str(user_config.embedding_model_vector_size)
                if user_config and user_config.embedding_model_vector_size is not None
                else None
            ) or await self._get_system_value("embedding.model_vector_size")
            or self._serialize_url(settings.embedding_model_vector_size),
        }

    def _filter_embedding_models(self, models: List[str]) -> List[str]:
        """过滤掉明显不适合作为 embedding 的模型。"""
        filtered: List[str] = []
        for model in models:
            normalized = model.lower()
            if "reranker" in normalized or "ranker" in normalized:
                continue
            if "embedding" in normalized or normalized.startswith("text-embedding"):
                filtered.append(model)
        return filtered

    async def _get_system_value(self, key: str) -> Optional[str]:
        record = await self.system_config_repo.get_by_key(key)
        return record.value if record else None

    async def _get_ollama_models(self, base_url: Optional[str]) -> List[str]:
        host = (base_url or "http://127.0.0.1:11434").rstrip("/")
        url = f"{host}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
            payload = response.json()
            models = payload.get("models", [])
            names = [model.get("name") for model in models if model.get("name")]
            logger.info("成功获取 %d 个 Ollama 模型", len(names))
            return sorted(names)
        except Exception as exc:
            logger.error("获取 Ollama 模型列表失败: base_url=%s error=%s", host, exc, exc_info=True)
            return []
