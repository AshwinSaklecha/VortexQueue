import socket
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"

    MAIN_QUEUE: str = "vortex:queue:main"

    VISIBILITY_TIMEOUT: int = 300      # seconds — how long a processing lock lives
    HEARTBEAT_INTERVAL: int = 10       # seconds — how often a worker refreshes the lock
    MAX_RETRIES: int = 5
    JANITOR_INTERVAL: int = 60         # seconds — how often the janitor scans for orphans

    FRONTEND_URL: str = "http://localhost:3000"
    LOG_LEVEL: str = "DEBUG"

    # Computed at runtime: unique identity per worker process
    @property
    def WORKER_ID(self) -> str:
        return f"{socket.gethostname()}-{os.getpid()}"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",   # silently drop keys in .env we don't declare (e.g. MAIN_QUEUE_NAME)
    )


settings = Settings()
