from typing import Literal, Any

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message_id: str = Field(description="消息唯一id")
    type: Literal["text", "object"] = Field(description="消息内容的类型")
    content: dict[str, Any] = Field(description="消息的内容、普通文本的内容、对象内容")


class CurrentUser(BaseModel):
    user_id: str = Field(description="用户id")
    role: Literal["user", "admin", "staff"] = Field(default="user", description="用户角色")


class ReplyMessageRequest(BaseModel):
    text: str = Field(description="人工回复的消息")
