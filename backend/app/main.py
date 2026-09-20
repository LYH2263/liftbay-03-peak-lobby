from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_peak_columns() -> None:
    """create_all 不会给已存在的表补列；为旧库幂等补齐高峰字段。"""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS lobby_floor INTEGER NOT NULL DEFAULT 1"
        ))
        conn.execute(text(
            "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS peak_mode BOOLEAN NOT NULL DEFAULT FALSE"
        ))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_peak_columns()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="LiftBay", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
