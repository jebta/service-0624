from datetime import timedelta

from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from atguigu.app.models.enums import MessageRole, ConversationMode, TurnStatus
from atguigu.app.models.models import Message, Conversation, ConversationTurn
from atguigu.app.schemas import ChatMessageRequest
from atguigu.app.services.admin import AdminService
from atguigu.app.services.realtime import RealtimeService
from atguigu.common.settings import get_settings
from atguigu.common.utils import get_utcnow, get_uid


class ChatService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._settings = get_settings()
        self._realtime_service = RealtimeService(session)
        self._admin_service = AdminService(session)

    async def process_chat_message(self, user_id: str, pyload: ChatMessageRequest):
        """
        职责：处理对话逻辑
        1.获取对话
        2.创建消息
        3.消息根据会话模式进行分流
        3.1 AI模式，创建轮次
        3.2 人工客服模式，发送实时数据
        4.统一提交
        """
        # 1.消息去重
        stmt = select(Message).where(Message.message_id == pyload.message_id)
        message = await self._session.scalar(stmt)
        if message:
            return
        # 2.获取对话
        conversation = await self._create_and_get_conversation(user_id)
        # 3.创建消息
        message = Message(
            message_id=pyload.message_id,
            conversation_id=str(conversation.id),
            role=MessageRole.USER,
            message_type=pyload.type,
            content=pyload.content,
        )
        # 4 保存消息到数据库
        self._session.add(message)

        # 5.更新会话激活时间
        conversation.last_active_at = get_utcnow()

        # 6.消息根据会话模式进行分流
        if conversation.mode == ConversationMode.AI:
            # 6.1 AI模式，创建轮次，后续AI Worker扫描turns表
            await self._create_or_get_turn(str(conversation.id))
        else:
            # 6.2 人工客服模式，发送实时数据，给客服端通知刷新工单，
            self._realtime_service.add_event(message, conversation, notify_staff=True)

        # 7.统一提交
        await self._session.commit()

    async def _create_and_get_conversation(self, user_id):
        """
        职责：返回一个有效的对话（AI/QUEUED/HUMAN）
        如果会话模式有效，如果到期了，创建新的会话，如果没有到期，获取之前的对话
        """
        # 1.查询对话SQL语句 , 加锁1，2，防止结束工单时发信息 锁 4
        stmt = (select(Conversation).where(Conversation.user_id == user_id, Conversation.mode != ConversationMode.CLOSED).with_for_update())

        # 2.执行SQL
        conversation = await self._session.scalar(stmt)

        # 3.判断已有的会话是否过期
        if conversation:
            # 会话模式是AI，比较空闲时间是否超过设定的
            timeout = timedelta(minutes=self._settings.conversation_idle_timeout_minutes)
            if conversation.mode == ConversationMode.AI and get_utcnow() - conversation.last_active_at >= timeout:
                conversation.mode = ConversationMode.CLOSED
            else:
                return conversation

        # 4. 过期或者没有会话就创建
        conversation = Conversation(
            id=get_uid("conv"),
            user_id=user_id,
            mode=ConversationMode.AI
        )
        # 5.保存
        self._session.add(conversation)
        # 6.返回
        return conversation

    async def _create_or_get_turn(self, conversation_id: str):
        # 1.查找turn的SQL语句
        stmt = select(ConversationTurn).where(ConversationTurn.conversation_id == conversation_id,
                                              ConversationTurn.status == TurnStatus.COLLECTING)

        # 2.执行sql，查询turn
        turn = await self._session.scalar(stmt)

        # 3.不存在就创建
        if turn is None:
            turn = ConversationTurn(
                conversation_id=conversation_id,
                status=TurnStatus.COLLECTING,
                collect_until=get_utcnow() + timedelta(milliseconds=self._settings.message_merge_delay_ms)
                # 当前时间 + AI会话空闲过期的时间
            )
            self._session.add(turn)

        return turn

    async def process_chat_history(self, user_id: str) -> dict[str, Any]:
        """
        职责：获取当前用户下所有的会话【活跃，关闭】消息
        """
        # 1.定义SQL
        stmt = select(Message).join(Conversation, Message.conversation_id == Conversation.id).where(
            Conversation.user_id == user_id)
        # 查询
        records = (await self._session.scalars(stmt)).all()

        # 3.过滤消息
        conversation_messages = [
            {
                "conversation_id": record.conversation_id,  # 和当前对话去对比，前端知道哪个是当前会话
                "role": record.role,  # 前端展示历史对话的时候渲染图标角色
                "content": record.content  # 前端展示历史对话的消息内容
            }
            for record in records
        ]

        # 4.获取当前用户的会话
        conversation = await self._create_and_get_conversation(user_id)

        # 返回
        return {
            "conversation_id": conversation.id,
            # 当前活跃会话的会话ID-----1) 供历史消息区域在展示历史消息的时候，能对当前会话的消息，做一个特殊标记【聚合：区分当前会话的消息、以及非当前会话的消息】 2）让客户区域获取到当前会话下的消息
            "conversation_mode": conversation.mode,  # 当前活跃会话的会话模式---前端右上角徽章区域展示用，刷新页面的时候，徽章变化
            "messages": conversation_messages  # 有可能是关闭会话的消息，当前活跃会话的消息
        }

    async def claim_turn_and_payload(self) -> tuple[ConversationTurn, dict[str, Any], str] | None:
        # 1. 领取到满足条件的轮次（1.1轮次状态：collecting 1.2 轮次的时间到期）
        # sql，查询collecting状态，并且collect_until过了窗口时间（800ms没有发信息）
        stmt = select(ConversationTurn).where(ConversationTurn.status == TurnStatus.COLLECTING,
                                              ConversationTurn.collect_until <= get_utcnow()).order_by(
            ConversationTurn.collect_until)  # 可能查询到不同会话的轮次，按照谁来的早先处理哪个
        # 查询
        claim_turn: ConversationTurn = await self._session.scalar(stmt)
        # 2. 判断是否领取
        # 2.1 没有turn
        if claim_turn is None:
            return None
        # 2.2 有turn
        # 查询当前轮次的会话 加锁1
        conversation = await self._session.scalar(
            select(Conversation).where(Conversation.id == claim_turn.conversation_id).with_for_update())
        # 修改轮次状态
        claim_turn.status = TurnStatus.RUNNING
        claim_turn.attempts += 1

        # 获取该轮次最新的一条消息id
        lasted_user_message_id = await self._get_lasted_user_message_id(conversation.id)

        # 1）检验是否插话，2）确定下限
        claim_turn.snapshot_message_id = lasted_user_message_id

        # 3. 构建调用ai-service请求载荷
        payload: dict[str, Any] = await self._build_request_payload(claim_turn, conversation)

        # 4. 提交（必须在此提交，因为后面有调用ai-service，属于不同的i/o）
        await self._session.commit()
        # 5. 返回数据
        return claim_turn, payload, conversation.user_id

    async def _get_lasted_user_message_id(self, conversation_id: str) -> int:
        """
        获取最新的一条message_id
        """
        stmt = select(func.max(Message.id)).where(Message.conversation_id == conversation_id,
                                                  Message.role == MessageRole.USER)
        lasted_user_message_id = await self._session.scalar(stmt)
        return lasted_user_message_id

    async def _build_request_payload(self, claim_turn: ConversationTurn, conversation: Conversation) -> dict[str, Any]:
        """
        职责：构建ai-service请求载荷
        1.构建当前轮次的信息
        2.构建历史轮次信息
        """
        # 1.获取当前轮次的信息
        # 1.1 获取当前轮次信息的上限，就是最新ai或人工回复的信息的下一条
        stmt = select(func.max(Message.id)).where(Message.conversation_id == conversation.id,
                                                  Message.role != MessageRole.USER)
        lasted_reply_message_id = await self._session.scalar(stmt) or 0

        current_turn_messages_stmt = (select(Message).where(Message.conversation_id == conversation.id,
                                                            Message.id > lasted_reply_message_id,
                                                            Message.id <= claim_turn.snapshot_message_id)
                                      .order_by(Message.id))

        current_turn_messages = (await self._session.scalars(current_turn_messages_stmt)).all()

        # 2 构建当前会话的历史信息（裁剪30条）
        history_stmt = select(Message).where(Message.conversation_id == conversation.id,
                                             Message.id < current_turn_messages[0].id).order_by(
            Message.id.desc()).limit(30)

        history_messages = (await self._session.scalars(history_stmt)).all()
        history_messages = reversed(history_messages)

        # 3 返回数据
        return {
            "conversation_id": conversation.id,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "type": message.message_type
                }
                for message in current_turn_messages],
            "history": [
                {
                    "role": history.role,
                    "content": history.content,
                    "type": history.message_type
                }
                for history in history_messages],
        }

    async def finish_turn(self, claim_turn: ConversationTurn, ai_result: dict[str, Any], error: Exception):
        """
        职责:结算轮次相关信息
        """
        # 1.查询当前轮次的会话，锁2
        conversation: Conversation = await self._session.scalar(
            select(Conversation).where(Conversation.id == claim_turn.conversation_id).with_for_update())

        # 2.判断是否插话
        if claim_turn.snapshot_message_id != await self._get_lasted_user_message_id(conversation.id):
            # 插话了，只修改轮次状态
            claim_turn.status = TurnStatus.SUPERSED
            await self._session.commit()
            return

        # 3.调用ai-service失败
        if error is not None:
            # 重试用完，就改为失败
            if claim_turn.attempts > self._settings.ai_worker_max_attempts:
                claim_turn.status = TurnStatus.FAILED
                # 记录失败消息【对内】，让前端看到失败的消息内容【对外】
                await self._save_ai_reply({"kind": "error", "text": "AI Service 服务调用失败，请你稍后重试！"},
                                          conversation)
                await self._session.commit()
                return

            # 进行重试
            claim_turn.status = TurnStatus.COLLECTING
            # 更新轮次的抖动时间（持续时间）给重试加一个时间，让ai调用慢一些，collect_until大就会排在后面
            claim_turn.collect_until = get_utcnow() + timedelta(
                seconds=self._settings.ai_worker_retry_delay_seconds)
            await self._session.commit()
            return

        # 4. 调用ai成功，保存ai-result
        # 4.1 修改状态为完成
        claim_turn.status = TurnStatus.COMPLETED

        # 4.2 回复类型为转人工请求
        if ai_result["reply_type"] == "REQUEST_HANDOFF":
            # 创建工单
            self._admin_service.create_handoff(conversation, summary=ai_result["summary"])
            # 修改会话模式
            conversation.mode = ConversationMode.QUEUED

        # 4.3 正常回答
        # 保存转人工请求到messages和realtime中
        await self._save_ai_reply(ai_result, conversation)

        # 5.统一提交
        await self._session.commit()

    async def _save_ai_reply(self, ai_result: dict[str, Any], conversation: Conversation):
        """
         职责：保存回复内容到messages表和realtime_events表中
        """
        # 1. 保存到messages中
        message = Message(
            message_id=get_uid("msg"),
            conversation_id=conversation.id,
            role=MessageRole.AI,
            message_type="text",  # 回复只支持文本回复
            content=ai_result  # 将ai-result全部字典内容存储到content中
        )
        self._session.add(message)

        # 2.修改会话最后一次活跃时间
        conversation.last_active_at = get_utcnow()

        # 3.保存内容到realtime_event中
        self._realtime_service.add_event(message, conversation, notify_user=True,
                                         notify_staff=conversation.mode == ConversationMode.QUEUED)
