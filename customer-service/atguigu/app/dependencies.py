from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from atguigu.app.schemas import CurrentUser
from atguigu.app.services.admin import AdminService
from atguigu.app.services.auth import authorized_user
from atguigu.app.services.chat import ChatService
from atguigu.infrastucture.db import get_async_session

# -----------------------user--------------
# 获取会话依赖
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


def get_chat_service(session: SessionDep) -> ChatService:
    return ChatService(session)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]

# 3，从请求头获取bearer，传入方法
AuthorizationDep = Annotated[str | None, Header()]


# 2.调用鉴定方法
def require_user_role_auth(authorization: AuthorizationDep) -> CurrentUser:
    return authorized_user(authorization, "user")


# 1.依赖注入
UserRoleDep = Annotated[CurrentUser, Depends(require_user_role_auth)]


# ---------------------admin------------------


def get_admin_service(session: SessionDep) -> AdminService:
    return AdminService(session)


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]

# 3，从请求头获取bearer，传入方法
AuthorizationDep = Annotated[str | None, Header()]


# 2.调用鉴定方法
def require_admin_role_auth(authorization: AuthorizationDep) -> CurrentUser:
    return authorized_user(authorization, "admin")


# 1.依赖注入
AdminRoleDep = Annotated[CurrentUser, Depends(require_admin_role_auth)]

# --------------------staff--------------------
# 3，从请求头获取bearer，传入方法
AuthorizationDep = Annotated[str | None, Header()]


# 2.调用鉴定方法
def require_staff_role_auth(authorization: AuthorizationDep) -> CurrentUser:
    return authorized_user(authorization, "staff")


# 1.依赖注入
StaffRoleDep = Annotated[CurrentUser, Depends(require_staff_role_auth)]
