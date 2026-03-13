# AIMETA P=嵌入配置模型_RAG向量模型配置存储|R=Embedding配置表|NR=不含配置逻辑|E=EmbeddingConfig|X=internal|A=ORM模型|D=sqlalchemy|S=none|RD=./README.ai
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class EmbeddingConfig(Base):
    """用户自定义的 RAG / Embedding 配置。"""

    __tablename__ = "embedding_configs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(32))
    embedding_base_url: Mapped[str | None] = mapped_column(Text())
    embedding_api_key: Mapped[str | None] = mapped_column(Text())
    embedding_model: Mapped[str | None] = mapped_column(Text())
    embedding_model_vector_size: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship("User", back_populates="embedding_config")
