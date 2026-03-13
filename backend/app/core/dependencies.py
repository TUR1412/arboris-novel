# AIMETA P=依赖注入_FastAPI依赖项定义|R=数据库会话_当前用户获取|NR=不含业务逻辑|E=get_db_get_current_user|X=internal|A=依赖函数|D=fastapi,sqlalchemy|S=db|RD=./README.ai
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..db.session import get_session
from ..repositories.user_repository import UserRepository
from ..schemas.user import UserInDB


async def get_current_user(
    session: AsyncSession = Depends(get_session),
) -> UserInDB:
    repo = UserRepository(session)
    user = await repo.get_by_username(settings.admin_default_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未找到本机单用户模式绑定的管理员账号",
        )
    if not user.is_admin or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="本机管理员账号已被禁用或降权，请先恢复默认管理员状态",
        )
    schema = UserInDB.model_validate(user)
    schema.must_change_password = False
    return schema


async def get_current_admin(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    return current_user
