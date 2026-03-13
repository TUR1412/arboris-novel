# AIMETA P=嵌入配置仓库_RAG配置数据访问|R=配置CRUD|NR=不含业务逻辑|E=EmbeddingConfigRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai
from typing import Optional

from sqlalchemy import select

from .base import BaseRepository
from ..models import EmbeddingConfig


class EmbeddingConfigRepository(BaseRepository[EmbeddingConfig]):
    model = EmbeddingConfig

    async def get_by_user(self, user_id: int) -> Optional[EmbeddingConfig]:
        result = await self.session.execute(
            select(EmbeddingConfig).where(EmbeddingConfig.user_id == user_id)
        )
        return result.scalars().first()
