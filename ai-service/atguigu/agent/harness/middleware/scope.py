from typing import Callable, Awaitable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse

from atguigu.agent.harness.rules.skill import SKILL_CATALOG
from atguigu.agent.harness.run.context import AgentRunState, AgentRunContext
from atguigu.agent.llm.output import AgentOutput


class SkillScopeMiddleware(AgentMiddleware[AgentRunState, AgentRunContext, AgentOutput]):
    """
    对工具进行裁剪（根据领域）
    """

    async def awrap_model_call(
            self,
            request: ModelRequest[AgentRunContext],
            handler: Callable[[ModelRequest[AgentRunContext]], Awaitable[ModelResponse[AgentOutput]]],
    ) -> ModelResponse[AgentOutput]:
        """
        在llm调用之前，可以进行增强（也可以调用handler（llm）后进行处理）这里只进行调用前的增强
        根据领域码找该领域的工具
        """
        # 1. 获取领域码
        skill_code = request.state.get('skill_code')

        all_tool_name = ["load_skill"]

        # 2.获取技能对象
        if skill_code is not None:
            skill_definition = SKILL_CATALOG.get_skill_definition(skill_code)
            all_tool_name.extend(skill_definition.tools)

        # 3,获取真正的工具对象
        allowed_tools = [tool for tool in request.tools if tool.name in all_tool_name]

        # 4.handler给模型工具
        return await handler(request.override(tools=allowed_tools, model_settings={"parallel_tool_calls": False}))
