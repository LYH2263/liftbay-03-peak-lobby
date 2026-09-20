from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    floors: Mapped[int] = mapped_column(Integer)
    # 大厅层由种子指定；早高峰仅对该层的上行呼梯生效。
    lobby_floor: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    peak_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    cars: Mapped[list["ElevatorCar"]] = relationship(back_populates="building")


class ElevatorCar(Base):
    __tablename__ = "elevator_cars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    label: Mapped[str] = mapped_column(String(40))
    floor: Mapped[int] = mapped_column(Integer, default=1)
    direction: Mapped[str] = mapped_column(String(10), default="idle")
    load: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    building: Mapped[Building] = relationship(back_populates="cars")


class CallTicket(Base):
    __tablename__ = "call_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    floor: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(10))
    passengers: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    assigned_car_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DispatchLog(Base):
    __tablename__ = "dispatch_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("call_tickets.id"))
    car_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
