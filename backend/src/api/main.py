from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.core.config import settings
from src.core.database import create_tables
from src.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure both tables exist before accepting any requests
    create_tables()
    yield
    # Shutdown: nothing to tear down (connection pool is process-scoped)


app = FastAPI(
    title="VortexQueue API",
    description="Production-grade distributed task queue — no Celery, raw Redis primitives.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
