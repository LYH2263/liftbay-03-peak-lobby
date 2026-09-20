"""API 级集成测试：高峰开关持久化、派工胜者、回放记录。

使用 sqlite 内存库覆盖 get_db，不触碰 postgres；TestClient 不以上下文
管理器方式使用，因此不会触发 lifespan（不会连真实库、不会自动种子）。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Building, ElevatorCar
from app.services.seed import seed_if_empty

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def _make_building(name: str, lobby_floor: int, peak: bool, cars: list[dict]) -> int:
    db = TestingSession()
    try:
        b = Building(name=name, floors=10, lobby_floor=lobby_floor, peak_mode=peak)
        db.add(b)
        db.flush()
        db.add_all(ElevatorCar(building_id=b.id, **c) for c in cars)
        db.commit()
        return b.id
    finally:
        db.close()


def _new_lobby_call(building_id: int, floor: int) -> dict:
    r = client.post(
        "/api/calls",
        json={"building_id": building_id, "floor": floor, "direction": "up", "passengers": 1},
    )
    assert r.status_code == 200
    return r.json()


def _dispatch(call_id: int):
    return client.post("/api/dispatch", json={"call_id": call_id})


def _cars_by_label(building_id: int) -> dict:
    return {
        c["label"]: c
        for c in client.get("/api/cars").json()
        if c["building_id"] == building_id
    }


def _log_detail(call_id: int) -> str:
    logs = client.get("/api/replay").json()
    return next(l["detail"] for l in logs if l["call_id"] == call_id)


def test_seeded_lobby_call_goes_to_lobby_car():
    """种子场景：大厅 idle 空车 + 上层同向上行近车，大厅上行呼梯派大厅车。"""
    db = TestingSession()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    calls = client.get("/api/calls").json()
    lobby_call = next(c for c in calls if c["floor"] == 1 and c["status"] == "waiting")
    r = _dispatch(lobby_call["id"])
    assert r.status_code == 200
    cars = {c["label"]: c for c in client.get("/api/cars").json()}
    assert r.json()["assigned_car_id"] == cars["A3"]["id"]
    assert "早高峰" in _log_detail(lobby_call["id"])


def test_peak_toggle_changes_winner_and_persists():
    """高峰开与关两种胜者不同；开关状态入库，再次读取仍是库中状态。"""
    bid = _make_building(
        "切换楼",
        lobby_floor=2,
        peak=False,
        cars=[
            {"label": "L", "floor": 2, "direction": "idle", "load": 0, "capacity": 8},
            {"label": "U", "floor": 1, "direction": "up", "load": 1, "capacity": 10},
        ],
    )
    # 高峰关：普通评分，楼下同向上行车(135)胜过大厅 idle 车(120)
    call1 = _new_lobby_call(bid, floor=2)
    r = _dispatch(call1["id"])
    assert r.status_code == 200
    assert r.json()["assigned_car_id"] == _cars_by_label(bid)["U"]["id"]
    assert "早高峰" not in _log_detail(call1["id"])

    # 打开高峰开关，状态入库
    r = client.patch(f"/api/buildings/{bid}", json={"peak_mode": True})
    assert r.status_code == 200
    assert r.json()["peak_mode"] is True
    again = next(b for b in client.get("/api/buildings").json() if b["id"] == bid)
    assert again["peak_mode"] is True
    assert again["lobby_floor"] == 2

    # 复位被首次派工改写的轿厢状态，重放同一场景
    db = TestingSession()
    try:
        for car in db.scalars(select(ElevatorCar).where(ElevatorCar.building_id == bid)):
            if car.label == "U":
                car.floor, car.direction, car.load = 1, "up", 1
            else:
                car.floor, car.direction, car.load = 2, "idle", 0
        db.commit()
    finally:
        db.close()

    # 高峰开：大厅驻点车改写胜者
    call2 = _new_lobby_call(bid, floor=2)
    r = _dispatch(call2["id"])
    assert r.status_code == 200
    assert r.json()["assigned_car_id"] == _cars_by_label(bid)["L"]["id"]
    assert "高峰规则改写胜者" in _log_detail(call2["id"])


def test_peak_full_lobby_car_not_overloaded():
    """满员大厅车不被高峰规则强行超载，改派次选。"""
    bid = _make_building(
        "满员楼",
        lobby_floor=2,
        peak=True,
        cars=[
            {"label": "L", "floor": 2, "direction": "idle", "load": 8, "capacity": 8},
            {"label": "U", "floor": 1, "direction": "up", "load": 1, "capacity": 10},
        ],
    )
    call = _new_lobby_call(bid, floor=2)
    r = _dispatch(call["id"])
    assert r.status_code == 200
    cars = _cars_by_label(bid)
    assert r.json()["assigned_car_id"] == cars["U"]["id"]
    assert cars["L"]["load"] == 8  # 大厅车未被超载
    assert "未改写胜者" in _log_detail(call["id"])


def test_peak_all_full_rejects():
    """高峰开启但全部满员：拒绝派工且不超载。"""
    bid = _make_building(
        "全满楼",
        lobby_floor=2,
        peak=True,
        cars=[
            {"label": "L", "floor": 2, "direction": "idle", "load": 8, "capacity": 8},
            {"label": "U", "floor": 1, "direction": "up", "load": 10, "capacity": 10},
        ],
    )
    call = _new_lobby_call(bid, floor=2)
    r = _dispatch(call["id"])
    assert r.status_code == 409
    assert "满员" in _log_detail(call["id"])
    cars = _cars_by_label(bid)
    assert cars["L"]["load"] == 8
    assert cars["U"]["load"] == 10
