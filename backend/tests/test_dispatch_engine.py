from app.services.dispatch_engine import (
    CallRequest,
    CarState,
    pick_car,
    score_car,
)

# 关键几何事实：在现有“同向 + 距离”评分下，同向上行车要在普通分赢过
# 停在大厅的 idle 车（120 分），必须处于上行接近途中（floor <= 呼梯层, +40）。
# 对“大厅上行呼梯”，这种普通分更高的同向上行近车位于大厅下方、正驶向大厅；
# 而位于大厅上方的上行车已越过站厅（-15），现网本就不会赢。高峰硬优先就是
# 用来在上述“普通分他车更高”的情况下把胜者改写回大厅车。


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
    decision = pick_car(cars, call)
    assert decision is not None
    assert decision.winner.car_id == 1


def test_closer_idle_wins_when_opposite():
    cars = [
        CarState(1, 10, "down", load=0, capacity=10),
        CarState(2, 3, "idle", load=0, capacity=10),
    ]
    call = CallRequest(3, 2, "up", 1)
    decision = pick_car(cars, call)
    assert decision is not None
    assert decision.winner.car_id == 2


def test_seed_scene_lobby_up_goes_to_lobby_car():
    """种子场景：大厅 1 层 idle 空车 A3 + 上层 3 层同向上行 A1，大厅上行派 A3。"""
    a1 = CarState(1, 3, "up", load=2, capacity=10)
    a3 = CarState(3, 1, "idle", load=0, capacity=8)
    cars = [a1, a3]
    call = CallRequest(100, 1, "up", passengers=1)

    off = pick_car(cars, call, peak_mode=False, lobby_floor=1)
    on = pick_car(cars, call, peak_mode=True, lobby_floor=1)
    assert off is not None and on is not None
    # 上层上行车已越过大厅（-15），现网本就派大厅车；高峰同样派大厅车并打标。
    assert off.winner.car_id == 3
    assert on.winner.car_id == 3
    assert on.winner.peak_priority is True
    assert off.winner.peak_priority is False
    # 胜者一致，因此不算“改写”。
    assert on.peak_rewrote is False


def test_peak_on_off_choose_different_winners():
    """锁：同向上行近车普通分更高（130>120），高峰关它赢；高峰开改写为大厅车。"""
    lobby_car = CarState(10, 3, "idle", load=0, capacity=10)       # 停在大厅(3F)的空车
    approaching = CarState(11, 1, "up", load=0, capacity=10)       # 同向上行、普通分更高的近车
    cars = [lobby_car, approaching]
    call = CallRequest(200, 3, "up", passengers=1)

    off = pick_car(cars, call, peak_mode=False, lobby_floor=3)
    on = pick_car(cars, call, peak_mode=True, lobby_floor=3)
    assert off is not None and on is not None

    # 现网：同向上行近车 130 分 > 大厅 idle 120 分。
    assert off.winner.car_id == 11
    assert off.peak_rewrote is False
    # 高峰：胜者改写成大厅车，并标记高峰优先 / 改写。
    assert on.winner.car_id == 10
    assert on.winner.peak_priority is True
    assert on.peak_rewrote is True


def test_peak_full_lobby_car_is_not_overloaded_falls_back():
    """满员大厅车不得被高峰强行超载，改派次选。"""
    lobby_full = CarState(20, 1, "idle", load=8, capacity=8)   # 大厅满员，1 人上不去
    upstairs = CarState(21, 3, "up", load=0, capacity=10)      # 上层上行车，可接纳
    cars = [lobby_full, upstairs]
    call = CallRequest(300, 1, "up", passengers=1)

    on = pick_car(cars, call, peak_mode=True, lobby_floor=1)
    assert on is not None
    # 大厅满员车被容量判掉，胜者为次选上层车，而非超载大厅车。
    assert on.winner.car_id == 21
    assert on.winner.peak_priority is False
    rejected = {s.car_id: s for s in on.scores if not s.accepted}
    assert 20 in rejected
    assert "满员" in rejected[20].reason
    # 容量恒等式：任何被接受的车都不会超载。
    for s in on.scores:
        if s.accepted:
            state = next(c for c in cars if c.car_id == s.car_id)
            assert state.load + call.passengers <= state.capacity


def test_peak_rejects_when_all_full():
    """大厅车满员且其余车也满员：高峰也不能无中生有，拒绝（返回 None）。"""
    cars = [
        CarState(30, 1, "idle", load=8, capacity=8),
        CarState(31, 5, "up", load=10, capacity=10),
    ]
    call = CallRequest(400, 1, "up", passengers=1)
    assert pick_car(cars, call, peak_mode=True, lobby_floor=1) is None


def test_non_lobby_call_unaffected_by_peak():
    """非大厅层呼梯即使开高峰也走现网同向+距离评分，不产生改写。"""
    cars = [
        CarState(40, 2, "up", load=1, capacity=10),
        CarState(41, 12, "idle", load=0, capacity=10),
    ]
    call = CallRequest(500, 4, "up", passengers=1)  # 呼叫层 4，大厅层 1
    off = pick_car(cars, call, peak_mode=False, lobby_floor=1)
    on = pick_car(cars, call, peak_mode=True, lobby_floor=1)
    assert off is not None and on is not None
    assert off.winner.car_id == on.winner.car_id == 40
    assert on.winner.peak_priority is False
    assert on.peak_rewrote is False
