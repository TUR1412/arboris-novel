# AIMETA P=嵌入配置模式_RAG配置请求响应|R=Embedding配置结构|NR=不含业务逻辑|E=EmbeddingConfigSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


EmbeddingProvider = Literal["openai", "ollama"]


class EmbeddingConfigBase(BaseModel):
    embedding_provider: Optional[EmbeddingProvider] = Field(
        default=None,
        description="嵌入模型提供方，支持 openai 或 ollama",
    )
    embedding_base_url: Optional[HttpUrl] = Field(default=None, description="嵌入模型服务地址")
    embedding_api_key: Optional[str] = Field(default=None, description="嵌入模型 API Key")
    embedding_model: Optional[str] = Field(default=None, description="嵌入模型名称")
    embedding_model_vector_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="嵌入向量维度，留空则自动检测",
    )


class EmbeddingConfigCreate(EmbeddingConfigBase):
    pass


class EmbeddingConfigRead(EmbeddingConfigBase):
    user_id: int
    has_api_key: bool = Field(default=False, description="是否已保存自定义嵌入模型 API Key")

    class Config:
        from_attributes = True


class EmbeddingModelListRequest(BaseModel):
    embedding_provider: EmbeddingProvider = Field(..., description="嵌入模型提供方")
    embedding_base_url: Optional[str] = Field(default=None, description="嵌入模型服务地址")
    embedding_api_key: Optional[str] = Field(default=None, description="嵌入模型 API Key")
