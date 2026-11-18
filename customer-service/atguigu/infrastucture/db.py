import asyncio
import selectors
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from atguigu.app.models.models import Base
from atguigu.common.event_loop import run_async
from atguigu.common.settings import get_settings

# 创建数据库引擎
db_engine = create_async_engine(get_settings().database_url, echo=False)

# 创建session工厂 expire_on_commit表示commit之后属性值不过期
session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator:
    async with session_factory() as session:
        yield session


async def init_database() -> None:
    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


if __name__ == '__main__':

    run_async(init_database())
    # 方案二
    # asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    # asyncio.run(main()
