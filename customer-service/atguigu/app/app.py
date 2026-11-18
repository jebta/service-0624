import asyncio

from atguigu.app.routers import chat, admin, realtime
from atguigu.app.workers.ai import AIWorker
from atguigu.app.workers.realtime import RealtimeWorker
from atguigu.common.settings import get_settings
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


async def lifespan(_: FastAPI):
    asyncio.create_task(AIWorker().start())
    asyncio.create_task(RealtimeWorker().start())
    yield


app = FastAPI(description="电商小二", lifespan=lifespan)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(realtime.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cor_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
