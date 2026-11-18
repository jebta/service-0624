from typing import Annotated
from fastapi import Depends, Header, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from atguigu.agent.harness.run.executor import AgentExecutor
from atguigu.app.schemas import CurrentUser, AgentRunRequest
from atguigu.app.services.admin import AdminService
from atguigu.app.services.auth import get_authorized_user
from atguigu.app.services.knowledge import KnowledgeService
from atguigu.common.settings import get_settings
from atguigu.infrastructure.db import get_async_session

sessionDep = Annotated[AsyncSession, Depends(get_async_session)]


def require_internal_service(token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None):
    """只允许 Customer Service 调用内部接口"""
    if token != get_settings().internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无效的内部访问令牌"
        )


def require_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return get_authorized_user(authorization, "user")


UserDep = Annotated[CurrentUser, Depends(require_user)]


def get_agent_executor(session: sessionDep, request: Request) -> AgentExecutor:
    return AgentExecutor(session, agent=request.app.state.agent)


AgentExecutorDep = Annotated[AgentExecutor, Depends(get_agent_executor)]

# =======================================================================
def get_admin_service(session: sessionDep) -> AdminService:
    return AdminService(session)


def get_knowledge_service(session: sessionDep) -> KnowledgeService:
    return KnowledgeService(session)


def require_admin(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return get_authorized_user(authorization, "admin")

AdminDep = Annotated[CurrentUser, Depends(require_admin)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
KnowledgeServiceDep = Annotated[KnowledgeService, Depends(get_knowledge_service)]