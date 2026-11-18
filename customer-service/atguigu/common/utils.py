import uuid
from datetime import datetime, UTC


# 生成随机id
def get_uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"  # hex去掉-间隔符


# 获取当前时间UTC代表带时区
def get_utcnow():
    return datetime.now(tz=UTC)
