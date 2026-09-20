from app.services.dispatch_engine import (
    CallRequest,
    CarState,
    PeakPolicy,
    pick_car,
    score_car,
)


def test_reject_when_full():
    car = CarState(1, 5, "idle", load=8, capacity=8)
    call = CallRequest(1, 5, "up", passengers=1)
    r = score_car(car, call)
    assert r.accepted is False
    assert "满员" in r.reason


def test_same_direction_beats_far_idle():
    cars = [
        CarState(1, 2, "up", load=1, capacity=10),
        CarState(2, 12, "idle", load=0, capacity=10),
    ]
    call = CallRequest(9, 4, "up", 1)
    best = pick_car(cars, call)
    assert best is not None
    assert best.car_id == 1


def test_closer_idle_wins_when_opposite():
    cars = [
        CarState(1, 10, "down", load=0, capacity=10),
        CarState(2, 3, "idle", load=0, capacity=10),
    ]
    call = CallRequest(3, 2, "up", 1)
    best = pick_car(cars, call)
    assert best is not None
    assert best.car_id == 2


# --- 早高峰模式：大厅层上行呼梯优先大厅驻点车 ---

LOBBY = 2


def _lobby_scene():
    """大厅 idle 空车(120) vs 楼下同向上行近车(135)：普通评分近车胜。"""
    cars = [
        CarState(1, LOBBY, "idle", load=0, capacity=8),   # 大厅驻点空车
        CarState(2, LOBBY - 1, "up", load=1, capacity=10),  # 同向上行近车，普通分更高
    ]
    call = CallRequest(1, LOBBY, "up", passengers=1)
    return cars, call


def test_peak_off_keeps_normal_winner():
    cars, call = _lobby_scene()
    best = pick_car(cars, call, PeakPolicy(enabled=False, lobby_floor=LOBBY))
    assert best is not None
    assert best.car_id == 2
    assert best.peak_override is False


def test_peak_on_rewrites_winner_to_lobby_car():
    cars, call = _lobby_scene()
    best = pick_car(cars, call, PeakPolicy(enabled=True, lobby_floor=LOBBY))
    assert best is not None
    assert best.car_id == 1
    assert best.peak_override is True


def test_peak_seed_scene_lobby_idle_beats_upper_up_car():
    # 种子场景：大厅(1F) idle 空车，上层另有同向上行近车 → 派大厅车
    policy = PeakPolicy(enabled=True, lobby_floor=1)
    cars = [
        CarState(1, 1, "idle", load=0, capacity=8),
        CarState(2, 3, "up", load=2, capacity=10),
    ]
    call = CallRequest(1, 1, "up", passengers=2)
    best = pick_car(cars, call, policy)
    assert best is not None
    assert best.car_id == 1


def test_peak_full_lobby_car_not_overloaded():
    # 大厅车满员：高峰规则不得强行超载，改派次选
    cars = [
        CarState(1, LOBBY, "idle", load=8, capacity=8),
        CarState(2, LOBBY - 1, "up", load=1, capacity=10),
    ]
    call = CallRequest(1, LOBBY, "up", passengers=1)
    best = pick_car(cars, call, PeakPolicy(enabled=True, lobby_floor=LOBBY))
    assert best is not None
    assert best.car_id == 2
    assert best.peak_override is False


def test_peak_all_full_rejects():
    cars = [
        CarState(1, LOBBY, "idle", load=8, capacity=8),
        CarState(2, LOBBY - 1, "up", load=10, capacity=10),
    ]
    call = CallRequest(1, LOBBY, "up", passengers=1)
    assert pick_car(cars, call, PeakPolicy(enabled=True, lobby_floor=LOBBY)) is None


def test_peak_ignores_non_lobby_calls():
    cars = [
        CarState(1, LOBBY, "idle", load=0, capacity=8),
        CarState(2, 4, "up", load=1, capacity=10),
    ]
    call = CallRequest(1, 5, "up", passengers=1)
    best = pick_car(cars, call, PeakPolicy(enabled=True, lobby_floor=LOBBY))
    assert best is not None
    assert best.car_id == 2
    assert best.peak_override is False
