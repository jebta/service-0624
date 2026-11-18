from enum import StrEnum


class ConversationMode(StrEnum):
    """
    会话模式
    """
    AI = "AI"
    QUEUED = "QUEUED"
    HUMAN = "HUMAN"
    CLOSED = "CLOSED"


class TurnStatus(StrEnum):
    """
    轮次状态
    """
    COLLECTING = "COLLECTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"  # 完成状态，AI-service期间，没有用户进行插画
    FAILED = "FAILED"  # 失败状态，AI-service重试三次失败
    SUPERSED = "SUPERSED"  # 过期状态，AI-service期间，用户插话


class MessageRole(StrEnum):
    """
       消息角色
    """
    USER = "USER"
    AI = "AI"
    HUMAN = "HUMAN"


class HandoffStatus(StrEnum):
    """
    工单状态
    """

    WAITING = "WAITING"  # 有效(客服暂未接入)
    ACTIVE = "ACTIVE"  # 有效(客服已经接入)
    RESOLVED = "RESOLVED"  # 无效(客服关闭工单)