import time
from typing import Any
import logging

from fastapi import HTTPException, status
from langchain_core.messages import SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.callbacks import UsageMetadataCallbackHandler

from atguigu.agent.harness.run.context import build_messages, AgentRunContext
from atguigu.agent.harness.validator.validator import Validator, ValidateAgentOutError
from atguigu.app.models.enums import AgentTraceStatus
from atguigu.app.models.models import AgentTrace
from atguigu.app.schemas import CurrentUser, AgentRunRequest
from atguigu.common.settings import get_settings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class AgentExecutor:
    def __init__(self, session: AsyncSession, agent: Any):
        self._settings = get_settings()
        self._session = session
        self._agent = agent
        self._validator = Validator(session)

    async def start_run(self, payload: AgentRunRequest, current_user: CurrentUser) -> dict[str, Any]:
        """
        运行agent的逻辑主入口
        职责:
        1.创建Agent的一次运行的轨迹，【1.1 一次agent运行不等于只调用一次llm 1.2 用一张表存储agent的运行过程】
        2.调用agent执行（进行推理）
        3.根据agent的执行情况（正常 or 出错） 记录状态
        4.提交
        5.返回
        """
        # 1. 创建agentTrace
        agent_trace = AgentTrace(
            conversation_id=payload.conversation_id,
            status=AgentTraceStatus.RUNNING,
            model_name=self._settings.llm_model,
            prompt_version=self._settings.prompt_version
        )

        self._session.add(agent_trace)
        await self._session.commit()

        # 2. 调用agent
        start_time = time.perf_counter()
        try:
            run_result = await self._invoke_agent(payload, current_user, agent_trace)
        except Exception as e:
            logger.exception(f"agent推理会话{payload.conversation_id}任务期间出错")
            agent_trace.status = AgentTraceStatus.FAILED
            agent_trace.result = {"text": f"ai 执行出错,原因{e}"}
            agent_trace.latency_ms = int((time.perf_counter() - start_time) * 1000)
            await self._session.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI智能体执行出错")

        # 3.修改agent_trace的轨迹
        agent_trace.status = AgentTraceStatus.COMPLETED
        agent_trace.result = run_result
        agent_trace.latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 4.提交
        await self._session.commit()

        # 返回
        return run_result

    async def _invoke_agent(self, payload: AgentRunRequest,
                            current_user: CurrentUser,
                            agent_trace: AgentTrace) -> dict[str, Any] | None:
        """
        职责：调用agent完成真正的推理
        """
        # 1. 构建langchain标准的消息对象
        messages = build_messages(payload)

        # 2.构建上下文
        context = AgentRunContext(
            access_token=current_user.access_token,
            trace_id=agent_trace.id
        )

        callback = UsageMetadataCallbackHandler()
        # 3. agent运行
        # 3.1 调用agent
        for attempt in range(self._settings.agent_max_attempts):
            agent_output = await self._agent.ainvoke({"messages": messages}, context=context,
                                                     config={
                                                         "callbacks": [callback]
                                                     })
            for i,v in dict(agent_output).items():
                print(f"{i}: {v}")
            try:
                return await self._validator.validate_agent_output(agent_output['structured_response'],
                                                                   context.trace_id,
                                                                   agent_output.get("skill_code"))
                # 3.2 调用出错
            except ValidateAgentOutError as e:
                if attempt == self._settings.agent_max_attempts - 1:
                    raise e
                # 3.3 重试纠错（把执行完的结果以及【我要求你根据上一次结果的信息，给我重试】指令）
                logger.exception(f"执行Agent期间出现了护栏校验异常，原因%s", str(e))
                messages = [
                    *agent_output["messages"],
                    SystemMessage(content=f"上一次回复未通过校验：{e}，请修正后重新回复。")
                ]

            finally:
                # 3.5 统计token用量
                input_tokens, output_tokens = self._summary_tokens(callback)
                agent_trace.input_tokens = input_tokens
                agent_trace.output_tokens = output_tokens

    def _summary_tokens(self, callback: UsageMetadataCallbackHandler) -> tuple[int, int]:
        """
        职责：统计agent的token用量
        """
        usage_tokens: list[dict[str, Any]] = list(callback.usage_metadata.values())

        input_tokens = sum(usage_token.get("input_tokens", 0) for usage_token in usage_tokens)
        output_tokens = sum(usage_token.get("output_tokens", 0) for usage_token in usage_tokens)

        return input_tokens, output_tokens
