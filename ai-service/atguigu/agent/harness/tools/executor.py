import json
import time
from typing import Any

from langchain.tools import ToolRuntime
from pydantic import BaseModel

from atguigu.agent.harness.run.context import AgentRunContext
from atguigu.app.models.enums import ToolResultCode
from atguigu.app.models.models import AgentToolCall
from atguigu.infrastructure.db import async_session_factory


class ToolResult(BaseModel):
    """
    调用工具的返回数据
    """
    success: bool
    code: str
    message: str
    data: Any | None = None  # dict[str,Any]  list[dict[str,Any]]


class ToolExecutor:
    async def execute_tool(self,
                           runtime: ToolRuntime[AgentRunContext],
                           tool_name: str,
                           arguments: dict[str, Any],
                           *,
                           operator: Any):
        # 1. 发送请求获取接口数据
        start_time = time.perf_counter()
        try:
            response: dict[str, Any] = await operator()  # 执行失败（调用电商服务，【网络抖动、超时、电商服务宕机】）
            tool_result: ToolResult = ToolResult.model_validate(response)
        except Exception as e:
            # 不跑出异常，返回异常结果给llm看
            tool_result = ToolResult(
                success=False,
                code=ToolResultCode.TOOL_CALL_FAILED,  # 业务工具调用失败，TOOL_CALL_FAILED===直接降级
                message=f"业务工具调用失败，无法获取可靠依据，异常原因:{e}"
            )

        # 2. 入库
        await self._save_tool_result(
            trace_id=runtime.context.trace_id,
            tool_call_id=runtime.tool_call_id,  # 在runtime中会记录agent的调用工具的id
            tool_name=tool_name,
            arguments=arguments,
            result=tool_result.model_dump(),  # 等于把tool_result变为字典
            success=tool_result.success,
            latency_ms=int((time.perf_counter() - start_time) * 1000)
        )

        # 3. 返回结果
        return json.dumps(tool_result.model_dump(), ensure_ascii=False)  # 对象要转换成字典才能转换

    async def _save_tool_result(self,
                                trace_id: str,
                                tool_call_id: str,
                                tool_name: str,
                                arguments: dict[str, Any],
                                result: dict[str, Any],
                                success: bool,
                                latency_ms: int):
        """
        保存工具调用结果
        """

        async with async_session_factory() as session:
            # 创建AgentToolCall对象
            agent_tool_call = AgentToolCall(
                trace_id=trace_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                success=success,
                latency_ms=latency_ms
            )
            # 入库
            session.add(agent_tool_call)

            await session.commit()


tool_executor = ToolExecutor()
