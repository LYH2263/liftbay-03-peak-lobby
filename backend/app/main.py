from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_building_columns() -> None:
    """为已存在的 buildings 表补齐早高峰新增列（create_all 不改老表）。"""
    inspector = inspect(engine)
    if "buildings" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("buildings")}
    with engine.begin() as conn:
        if "lobby_floor" not in existing:
            conn.execute(text("ALTER TABLE buildings ADD COLUMN lobby_floor INTEGER DEFAULT 1"))
        if "peak_mode" not in existing:
            conn.execute(text("ALTER TABLE buildings ADD COLUMN peak_mode BOOLEAN DEFAULT FALSE"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_building_columns()
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
