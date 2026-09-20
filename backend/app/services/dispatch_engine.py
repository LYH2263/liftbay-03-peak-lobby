"""Elevator dispatch: same-direction preference + floor distance; reject if car full.

早高峰模式（peak_mode）：开启后，大厅层（由楼栋种子指定 lobby_floor）的
上行呼梯硬优先派给当前停在大厅、且空闲或同向上行的轿厢——即使远处同向轿厢
按普通距离评分更高。满员判定始终先于高峰优先：高峰不能让任何轿厢超载，
大厅车满员时改派次选，全部不可用则拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CarState:
    car_id: int
    floor: int
    direction: str  # "up" | "down" | "idle"
    load: int
    capacity: int


@dataclass(frozen=True)
class CallRequest:
    call_id: int
    floor: int
    direction: str  # desired travel after boarding
    passengers: int = 1


@dataclass(frozen=True)
class ScoreResult:
    car_id: int
    score: float
    accepted: bool
    reason: str
    peak_priority: bool = False  # 该车吃到了早高峰大厅优先


@dataclass(frozen=True)
class DispatchDecision:
    winner: ScoreResult
    peak_rewrote: bool  # 高峰是否把胜者从普通评分的胜者改写掉
    normal_winner: ScoreResult  # 关闭高峰时本应胜出的轿厢
    scores: tuple[ScoreResult, ...] = field(default_factory=tuple)


SAME_DIR_BONUS = 40.0
IDLE_BONUS = 20.0
DISTANCE_WEIGHT = 5.0

# 早高峰大厅优先加成：取足够大的值，使任何停在大厅的 idle/上行车
# 都稳定压过普通“同向 + 距离”评分最高的车（硬优先，而非微调）。
PEAK_LOBBY_BONUS = 100_000.0


def is_lobby_up(call: CallRequest, lobby_floor: int) -> bool:
    return call.floor == lobby_floor and call.direction == "up"


def peak_eligible(car: CarState, call: CallRequest, lobby_floor: int) -> bool:
    """大厅上行呼梯 + 轿厢正停在大厅且空闲/同向上行。"""
    return (
        is_lobby_up(call, lobby_floor)
        and car.floor == lobby_floor
        and car.direction in ("idle", "up")
    )


def score_car(
    car: CarState,
    call: CallRequest,
    peak_mode: bool = False,
    lobby_floor: int = 1,
) -> ScoreResult:
    # 满员判定先于一切，高峰规则同样不得超载。
    if car.load + call.passengers > car.capacity:
        return ScoreResult(car.car_id, -1e9, False, "轿厢满员")

    distance = abs(car.floor - call.floor)
    score = 100.0 - distance * DISTANCE_WEIGHT

    if car.direction == "idle":
        score += IDLE_BONUS
    elif car.direction == call.direction:
        # approaching or already going same way
        if car.direction == "up" and car.floor <= call.floor:
            score += SAME_DIR_BONUS
        elif car.direction == "down" and car.floor >= call.floor:
            score += SAME_DIR_BONUS
        else:
            score -= 15.0  # same dir but already passed
    else:
        score -= 25.0

    peak_priority = False
    if peak_mode and peak_eligible(car, call, lobby_floor):
        score += PEAK_LOBBY_BONUS
        peak_priority = True

    return ScoreResult(car.car_id, score, True, "ok", peak_priority)


def pick_car(
    cars: list[CarState],
    call: CallRequest,
    peak_mode: bool = False,
    lobby_floor: int = 1,
) -> DispatchDecision | None:
    # 高峰视角评分（含大厅优先加成）。
    peak_scores = [
        score_car(c, call, peak_mode=peak_mode, lobby_floor=lobby_floor) for c in cars
    ]
    accepted = [r for r in peak_scores if r.accepted]
    if not accepted:
        return None
    winner = max(accepted, key=lambda r: r.score)

    # 普通（现网）评分下的胜者，用于判定本次是否因高峰改写胜者。
    normal_scores = [
        score_car(c, call, peak_mode=False, lobby_floor=lobby_floor) for c in cars
    ]
    normal_accepted = [r for r in normal_scores if r.accepted]
    normal_winner = max(normal_accepted, key=lambda r: r.score)
    peak_rewrote = bool(
        peak_mode
        and is_lobby_up(call, lobby_floor)
        and winner.peak_priority
        and normal_winner.car_id != winner.car_id
    )

    return DispatchDecision(
        winner=winner,
        peak_rewrote=peak_rewrote,
        normal_winner=normal_winner,
        scores=tuple(peak_scores),
    )


def congestion_by_floor(calls: list[CallRequest]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in calls:
        counts[c.floor] = counts.get(c.floor, 0) + c.passengers
    return counts
