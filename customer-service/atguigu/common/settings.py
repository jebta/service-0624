from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = Field(
        "postgresql+psycopg://customer_service:customer_service@192.168.200.166:5432/customer_service",
        description="PgSQL数据库连接")
    jwt_secret: str = Field("ecommerce-secret", description="JWT密钥")
    jwt_algorithm: str = Field("HS256", description="JWT加密算法")
    api_host: str = Field("0.0.0.0", description="api地址")
    api_port: int = Field("8000", description="api端口")

    # 跨域
    cor_origins: list[str] = Field(
        ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
        description="跨域允许的源地址（前端地址）"
    )

    conversation_idle_timeout_minutes: int = Field(30, description="AI对话空闲关闭时间，分钟")
    message_merge_delay_ms: int = Field(800, description="首条消息进入轮次后，等待后续消息的窗口,毫秒")

    internal_service_token: str = Field("customer-internal-token", description="服务内部访问令牌")

    ai_worker_poll_interval_ms: int = Field(100, description="Woker领取Turn时间")
    ai_timeout_seconds: int = Field(30, description="请求AI Service的http超时时间")
    ai_service_url: str = Field("http://127.0.0.1:8002", description="AI Service服务地址")
    ai_worker_max_attempts: int = Field(3, description="当前轮次重试AI Service调用次数")
    ai_worker_retry_delay_seconds: int = Field(2, description="重试延时")

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


if __name__ == '__main__':
    settings = get_settings()
    print(settings.database_url)
    print(settings.jwt_secret)
