# AIMETA P=嵌入配置API_RAG配置管理|R=Embedding配置CRUD|NR=不含向量调用|E=route:GET_POST_/api/embedding-config/*|X=http|A=配置CRUD|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.embedding_config import (
    EmbeddingConfigCreate,
    EmbeddingConfigRead,
    EmbeddingModelListRequest,
)
from ...schemas.user import UserInDB
from ...services.embedding_config_service import EmbeddingConfigService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embedding-config", tags=["Embedding Configuration"])


def get_embedding_config_service(
    session: AsyncSession = Depends(get_session),
) -> EmbeddingConfigService:
    return EmbeddingConfigService(session)


@router.get("", response_model=EmbeddingConfigRead)
async def read_embedding_config(
    service: EmbeddingConfigService = Depends(get_embedding_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> EmbeddingConfigRead:
    config = await service.get_config(current_user.id)
    if not config:
        logger.warning("用户 %s 尚未设置 RAG 配置", current_user.id)
        raise HTTPException(status_code=404, detail="尚未设置自定义配置")
    logger.info("用户 %s 获取 RAG 配置", current_user.id)
    return config


@router.put("", response_model=EmbeddingConfigRead)
async def upsert_embedding_config(
    payload: EmbeddingConfigCreate,
    service: EmbeddingConfigService = Depends(get_embedding_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> EmbeddingConfigRead:
    logger.info("用户 %s 更新 RAG 配置", current_user.id)
    return await service.upsert_config(current_user.id, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_embedding_config(
    service: EmbeddingConfigService = Depends(get_embedding_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    deleted = await service.delete_config(current_user.id)
    if not deleted:
        logger.warning("用户 %s 删除 RAG 配置失败，未找到记录", current_user.id)
        raise HTTPException(status_code=404, detail="未找到配置")
    logger.info("用户 %s 删除 RAG 配置", current_user.id)


@router.post("/models", response_model=List[str])
async def list_embedding_models(
    payload: EmbeddingModelListRequest,
    service: EmbeddingConfigService = Depends(get_embedding_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[str]:
    models = await service.get_available_models(
        user_id=current_user.id,
        provider=payload.embedding_provider,
        base_url=payload.embedding_base_url,
        api_key=payload.embedding_api_key,
    )
    logger.info("用户 %s 获取 RAG 模型列表，返回 %d 个模型", current_user.id, len(models))
    return models
