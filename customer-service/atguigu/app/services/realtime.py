from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from atguigu.app.models.models import Message, Conversation, RealtimeEvent
from atguigu.common.utils import get_utcnow


class RealtimeService:
    def __init__(self, session: AsyncSession):
        self._session = session

    def add_event(self, message: Message, conversation: Conversation, *, notify_user: bool = False,
                  notify_staff: bool = False):
        """
        职责：供需要发送事件的调用方调用
        """
        # 1.确认通道目标
        target_channels = []
        if notify_user:
            target_channels.append(conversation.user_id)
        if notify_staff:
            target_channels.append("staff")

        # 2.构建通道的数据
        event_data = {
            "role": message.role,  # 区分前端的显示【AI/人工客服】
            "content": message.content,  # 前端展示的内容【消息】
            "conversation_mode": conversation.mode  # 前端展示右上角的会长区域【AI客服、等待人工、人工服务中】，保证每一条数据发送后实时更新
        }

        # 3.遍历通道，加入数据库
        for target_channel in target_channels:
            self._session.add(RealtimeEvent(target=target_channel, data=event_data))

    async def get_unpublish_event(self) -> RealtimeEvent:
        """查询单挑未发布的事件"""
        # 查询未发布给redis的事件
        stmt = select(RealtimeEvent).where(RealtimeEvent.published_at.is_(None)).order_by(RealtimeEvent.id).limit(1)
        return await self._session.scalar(stmt)

    async def marked_published_event(self, event: RealtimeEvent):
        """修改发布的状态"""
        event.published_at = get_utcnow()
        await self._session.commit()
