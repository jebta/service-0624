from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from atguigu.agent.harness.middleware.scope import SkillScopeMiddleware
from atguigu.agent.harness.run.context import AgentRunContext, AgentRunState
from atguigu.agent.harness.tools.catalog import TOOL_CATALOG
from atguigu.agent.llm.adapter import get_llm_client
from atguigu.agent.llm.output import AgentOutput
from atguigu.agent.llm.prompt import build_system_prompt


def create_ai_agent():
    return create_agent(  # type:ignore
        model=get_llm_client(),
        tools=TOOL_CATALOG.get_agent_tools(),
        middleware=[SkillScopeMiddleware()],
        system_prompt=build_system_prompt(),
        response_format=ToolStrategy(AgentOutput),
        context_schema=AgentRunContext,  # 类型提示，不传没关系
        state_schema=AgentRunState
    )


if __name__ == '__main__':
    ai_agent = create_ai_agent()
    state = ai_agent.invoke({"messages": "最近ai行情"})
    for index,value in dict(state).items():
        print(f"{index}:{value}\n")
