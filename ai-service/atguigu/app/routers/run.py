from typing import Annotated

from fastapi import APIRouter,Depends

from atguigu.app.dependencies import UserDep, require_internal_service, AgentExecutorDep
from atguigu.app.schemas import AgentRunRequest

router = APIRouter(tags=["ai service 运行路由"])

@router.post("/internal/v1/agent/runs")
async def start_run_endpoint(
        payload:AgentRunRequest,
        current_user: UserDep,
        _:Annotated[None,Depends(require_internal_service)],
        agent_executor:AgentExecutorDep
):
    return await agent_executor.start_run(payload,current_user)