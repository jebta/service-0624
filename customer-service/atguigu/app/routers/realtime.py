import asyncio
import logging

from fastapi import APIRouter, WebSocket, status

from atguigu.app.schemas import CurrentUser
from atguigu.app.services.auth import decode_access_token
from atguigu.infrastucture.redis import redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(tags=["实时事件推送的路由"])


@router.websocket("/api/v1/realtime")
async def get_realtime_endpoint(ws: WebSocket):
    """
    负责将redis的数据传给前端
    调用时机：页面加载时，立即触发
    """

    # 1.建立websocket连接
    await ws.accept()
    # 2.获取前端发过来的认证信息
    try:
        auth_info = await ws.receive_json()
        access_token = auth_info["token"]
    except Exception as e:
        logger.exception(f"用户认证信息获取失败:{str(e)}")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="用户认证失败")
        return
    # 3，根据认证信息获取用户信息
    current_user: CurrentUser = decode_access_token(access_token)
    target_channel = current_user.user_id if current_user.role == "user" else "staff"

    # 4.注册通道到Redis
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(target_channel)

    # 5.发送成功注册通道到Redis中
    await ws.send_json({"event_type": "connected"})

    # 6.接收指定通道的数据
    async def forward_event():
        async for message in pubsub.listen():  # 不断监听redis的数据
            if message["type"] == "message":
                event_data = message["data"]
                await ws.send_text(event_data)  # send_text只需要字符串，send_json要先json.dumps（）

    # 7.监听客户端ws通道有没有关闭
    async def disconnect():
        while True:
            await ws.receive_text()

    # 将两个协程放入事件循环，等待事件循环调用
    tasks = [
        asyncio.create_task(forward_event()),
        asyncio.create_task(disconnect())
    ]

    # 当某一个任务完成，才会停止【1.任务完成，2.任务异常】，返回done（完成的协程），pending（未完成的协程）
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for pend in pending:
        pend.cancel()  # 给事件循环发送一个CancelError 的信号

    # 主协程让出控制权，交给事件循环，事件循环去取消未完成的事件，
    # 但是把握不好时间，如果未完成的协程有数据库等操作，不应该这么早取消，而是等数据库操作做完才取消
    # await asyncio.sleep(3)

    # 加了gather，发送取消CancelError信号后，不会立即取消，而是执行未完成的pend，等到执行到下一个await时就会结束
    await asyncio.gather(*tasks,return_exceptions=True)
