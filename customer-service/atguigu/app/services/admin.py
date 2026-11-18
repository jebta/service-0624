from typing import Any, Tuple

from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from atguigu.app.models.enums import HandoffStatus, ConversationMode, MessageRole
from atguigu.app.models.models import Handoff, Message, Conversation
from atguigu.app.schemas import ReplyMessageRequest
from atguigu.app.services.realtime import RealtimeService
from atguigu.common.utils import get_uid, get_utcnow


class AdminService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._realtime_service = RealtimeService(session)

    async def get_handoffs(self) -> list[Handoff]:
        """
        获取所有用户的工单【有效状态】列表信息
        """
        stmt = select(Handoff).where(Handoff.status.in_([HandoffStatus.WAITING, HandoffStatus.ACTIVE])).order_by(
            Handoff.created_at)

        return list((await self._session.scalars(stmt)).all())

    async def get_handoffs_messages(self, handoff_id: str) -> dict[str, Any]:
        """
        获取工单id的会话信息
        """
        stmt = select(Message).join(Handoff, Message.conversation_id == Handoff.conversation_id).where(
            Handoff.id == handoff_id
        ).order_by(Message.id)

        conversation_messages = (await self._session.scalars(stmt)).all()
        return {"messages": conversation_messages}

    async def accept_handoff(self, handoff_id: str, staff_id: str):
        """
        接收工单（1.接收的是哪个，2是谁接收的）

        """
        # 1. 获取工单以及工单对应的会话信息
        handoff, conversation = await self._get_handoff_conversation(handoff_id)
        # 2. 获取工单状态，active表示已被接收，返回报错，防止两个人抢一个工单
        if handoff.status == HandoffStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该工单已被接入，请勿重复抢单")

        # 3. 修改工单的状态以及会话的模式
        # 3.1 修改工单的信息
        handoff.status = HandoffStatus.ACTIVE
        handoff.staff_id = staff_id

        # 3.2 修改会话的模式
        conversation.mode = ConversationMode.HUMAN

        # 4. 保存人工客服的回复(引导语:开场白)
        await self._save_human_reply(conversation, reply_text=f"客服 {staff_id} 已经接入工单，请问您有什么需要帮助的?")

        # 5. 提交
        await self._session.commit()

    async def _get_handoff_conversation(self, handoff_id: str) -> Tuple[Handoff, Conversation]:
        # 防止两个客服抢单 锁 3
        handoff: Handoff = await self._session.scalar(select(Handoff).where(Handoff.id == handoff_id).with_for_update())
        # 防止结束工单过程中用户发数据，锁4
        conversation = await self._session.scalar(
            select(Conversation).where(Conversation.id == handoff.conversation_id).with_for_update())
        return handoff, conversation

    async def _save_human_reply(self, conversation: Conversation, reply_text: str):
        """
        保存人工客服的回复（这是接收工单的提示信息）
        1.将回复保存到messages中
        2.将回复添加到realtime中通知用户
        """
        message = Message(
            message_id=get_uid("msg"),
            conversation_id=conversation.id,
            role=MessageRole.HUMAN,
            message_type="text",
            content={"text": reply_text},
        )

        self._session.add(message)

        # 更新会话激活时间
        conversation.last_active_at = get_utcnow()

        # 放入add_event
        self._realtime_service.add_event(message, conversation, notify_user=True)

    async def post_messages(self, handoff_id: str, reply_message: ReplyMessageRequest):
        """
        人工回复的消息进行保存，并交给RealtimeEvent
        """
        # 获取对话
        _, conversation = await self._get_handoff_conversation(handoff_id)

        # 保存人工信息，并且把
        await self._save_human_reply(conversation, reply_text=reply_message.text)

        # 提交
        await self._session.commit()

    async def resolve_handoff(self, handoff_id: str):
        """
        结束人工客服服务，
        """
        handoff, conversation = await self._get_handoff_conversation(handoff_id)
        # 1.关闭工单状态
        handoff.status = HandoffStatus.RESOLVED
        # 2.修改会话mode
        conversation.mode = ConversationMode.AI

        # 3.保存人工客服的结束语
        await self._save_human_reply(conversation, reply_text="人工客服已经结束，稍后由AI 继续为你服务。")

        await self._session.commit()

    def create_handoff(self, conversation: Conversation, *, summary: str):
        """
        创建工单
        """
        handoff = Handoff(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            summary=summary,
            status=HandoffStatus.WAITING
        )
        self._session.add(handoff)

    async def get_metrics(self)->dict[str, Any]:
        """获取相关指标信息"""
        return {
            "conversations": await self._get_count(Conversation.id),
            "handoffs": await self._get_count(Handoff.id),
            "queued": await self._get_count(Conversation.id,Conversation.mode == ConversationMode.QUEUED),
            "human": await self._get_count(Conversation.id,Conversation.mode == ConversationMode.HUMAN)
        }


    async def _get_count(self,col,*condition_expr):
        """
        col:获取哪一个字段，condition_expr:查询条件
        """
        return await self._session.scalar(select(func.count(col)).where(*condition_expr))