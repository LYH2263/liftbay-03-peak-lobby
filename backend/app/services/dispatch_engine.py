"""Elevator dispatch: same-direction preference + floor distance; reject if car full.

Morning-peak mode: for up calls at the building's lobby floor, cars currently
parked at the lobby (idle or heading up) take priority over every other car,
even when a distant same-direction car scores higher on the normal formula.
Capacity is never violated: a full lobby car is simply not a peak candidate,
so dispatch falls back to the next-best accepted car or rejects outright.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


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
class PeakPolicy:
    enabled: bool
    lobby_floor: int = 1


@dataclass(frozen=True)
class ScoreResult:
    car_id: int
    score: float
    accepted: bool
    reason: str
    peak_override: bool = False  # True when the peak rule rewrote the normal winner


SAME_DIR_BONUS = 40.0
IDLE_BONUS = 20.0
DISTANCE_WEIGHT = 5.0


def score_car(car: CarState, call: CallRequest) -> ScoreResult:
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

    return ScoreResult(car.car_id, score, True, "ok")


def is_peak_candidate(car: CarState, call: CallRequest, policy: PeakPolicy) -> bool:
    """Lobby up-call peak rule: car parked at the lobby, idle or heading up."""
    return (
        policy.enabled
        and call.direction == "up"
        and call.floor == policy.lobby_floor
        and car.floor == policy.lobby_floor
        and car.direction in ("idle", "up")
    )


def pick_car(
    cars: list[CarState], call: CallRequest, policy: PeakPolicy | None = None
) -> ScoreResult | None:
    results = [score_car(c, call) for c in cars]
    accepted = [r for r in results if r.accepted]
    if not accepted:
        return None
    normal = max(accepted, key=lambda r: r.score)
    if policy and policy.enabled:
        # Full cars are already unaccepted, so the peak pool can never overload.
        peak = [
            r
            for r, c in zip(results, cars)
            if r.accepted and is_peak_candidate(c, call, policy)
        ]
        if peak:
            winner = max(peak, key=lambda r: r.score)
            return replace(winner, peak_override=winner.car_id != normal.car_id)
    return normal


def congestion_by_floor(calls: list[CallRequest]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in calls:
        counts[c.floor] = counts.get(c.floor, 0) + c.passengers
    return counts
