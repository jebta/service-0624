import json
from dataclasses import dataclass
from typing import Any, NotRequired

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain.agents import AgentState

from atguigu.agent.harness.rules.skill import SkillCode
from atguigu.app.schemas import AgentRunRequest
from atguigu.common.settings import get_settings


@dataclass(frozen=True, slots=True)
class AgentRunContext:
    """
     上下文，不会改变
    """
    access_token: str  # 工具执行的时候要用（调用电商服务，要求提供认证信息）
    trace_id: str  # 工具执行的时候要用（工具结果要保存到agent_tool_call表中）


class AgentRunState(AgentState):
    """
    动态改变的数据
    """
    skill_code: NotRequired[str]


def build_messages(payload: AgentRunRequest) -> list[BaseMessage]:
    """
    构建标准化消息对象为langchain的消息对象
    """
    # 1. 获取历史消息
    history_messages: list[dict[str, Any]] = _build_history_message(payload.history)

    # 2. 标准化消息对象
    messages: list[BaseMessage] = [
        HumanMessage(content=_formate_message(history_message))
        if history_message["role"] == "USER" else
        AIMessage(content=_formate_message(history_message))
        for history_message in history_messages
    ]
    # 3.当前轮次消息
    current_messages: str = _build_current_messages(payload.messages)

    messages.append(HumanMessage(content=current_messages))

    # 4。返回（历史+当前）消息
    return messages


def _build_history_message(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
        构建历史消息（裁剪）
        裁剪策略
        1.根据历史条数（30条）
        2.字符内容长度（12000）、
        3.预留历史消息列表中的第一条消息是user角色开始的
       """
    settings = get_settings()

    # 1.历史消息裁剪

    candidate_history_messages = history[-settings.history_message_limit:]

    usage_total = 0
    # 2. 控制消息的长度
    messages = []
    for history_message in reversed(candidate_history_messages):
        history_content = _formate_message(history_message)

        if usage_total + len(history_content) > settings.history_character_budget:
            break
        messages.append(history_message)
        usage_total += len(history_content)

    messages.reverse()
    # 3. 历史上消息列表第一位是user开始的
    user_messages_index = next((index for index, message in enumerate(messages)), None)

    return messages[user_messages_index:] if user_messages_index is not None else messages


def _build_current_messages(messages: list[dict[str, Any]]) -> str:
    """
    把最新的消息全部拼接成一个大的字符串
    """
    # 1. 过去当前消息的内容
    message_contents: list[str] = [_formate_message(message) for message in messages]

    # 2. 当前轮次消息（单条）
    if len(message_contents) == 1:
        return message_contents[0]

    # 3.当前内容消息（多条）示例：1.xxx  2.xxx
    contents = "\n".join(f"{index + 1},{content}" for index, content in enumerate(message_contents))
    return "用户发送了多条消息，请你作为一个整体来理解" + contents


def _formate_message(history_message: dict[str, Any]) -> str:
    """
    把消息内容取出来，如果不是text返回一个对象字符串
    """
    if history_message["role"] == "user":
        return history_message["content"].get("text", "")

    history_content = history_message["content"]
    return "消息是一个对象:\n" + json.dumps(history_content, ensure_ascii=False, indent=2)
