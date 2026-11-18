import asyncio
import json
import logging

from redis import RedisError

from atguigu.app.models.models import RealtimeEvent
from atguigu.app.services.realtime import RealtimeService
from atguigu.common.event_loop import run_async
from atguigu.common.settings import get_settings
from atguigu.infrastucture.db import session_factory
from atguigu.infrastucture.redis import redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealtimeWorker:
    def __init__(self):
        self._settings = get_settings()
        self._redis_client = redis_client

    async def start(self):
        """
        Realtime worker 启动
        """
        logger.info("Realtime Worker 启动")
        while True:
            claim_event = await self._process_claim_event()
            if not claim_event:
                await asyncio.sleep(1)  # 睡眠

    async def _process_claim_event(self):
        """
        处理领到的事件，把未发布的事件发送到redis
        """

        async with session_factory() as session:
            # 1.实例化realtime_service
            realtime_service = RealtimeService(session)

            # 2.查询为被发布的事件
            event: RealtimeEvent = await realtime_service.get_unpublish_event()

            # 3.没有查到
            if event is None:
                return False

            # 4.发布事件到redis（发给哪个通道，发送什么数据）
            try:
                await self._redis_client.publish(event.target, json.dumps(event.data, ensure_ascii=False))
            except RedisError as e:
                logger.exception(f"发送给Redis服务的{event.target}失败，原因{str(e)}")
                return False

            # 5.修改事件的publish_at
            await realtime_service.marked_published_event(event)

            return True

if __name__ == '__main__':
    realtime_worker = RealtimeWorker()
    run_async(realtime_worker.start())