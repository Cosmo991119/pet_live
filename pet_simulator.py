"""
Virtual pet simulator V1.

This module runs a virtual pet world locally. It does not call the LLM and does
not require HTTP. Rules and probabilities generate structured events; the
message agent can later turn those events into pet-like language.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Optional


VIRTUAL_BEHAVIORS = {"eat", "drink", "poop", "play", "sleep_start", "sleep_end"}
OWNER_ACTIONS = {"feed", "refill", "play", "clean", "pet", "lullaby"}


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


@dataclass
class PetState:
    hunger: float = 35
    thirst: float = 35
    energy: float = 70
    mood: float = 70
    cleanliness: float = 80
    affection: float = 50
    is_sleeping: bool = False
    last_poop_at: Optional[datetime] = None
    last_play_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ["last_poop_at", "last_play_at"]:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "PetState":
        values = dict(data)
        for key in ["last_poop_at", "last_play_at"]:
            if values.get(key):
                values[key] = datetime.fromisoformat(values[key])
        return cls(**values)


@dataclass
class SimulatedEvent:
    pet_id: int
    behavior: str
    location_name: str
    occurred_at: str
    confidence: float
    source: str = "virtual_simulator"

    def to_payload(self) -> dict:
        return asdict(self)


class PetSimulator:
    def __init__(
        self,
        pet_id: int,
        personality: str = "gentle",
        start_time: Optional[datetime] = None,
        state: Optional[PetState] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.pet_id = pet_id
        self.personality = personality
        self.now = start_time or datetime.now(timezone(timedelta(hours=8)))
        self.state = state or PetState()
        self.random = random.Random(seed)
        self._lullaby_until: Optional[datetime] = None

    def tick(self, minutes: int = 10) -> Optional[SimulatedEvent]:
        """Advance simulated time and maybe emit one behavior event."""
        self.now = self.now + timedelta(minutes=minutes)
        self._natural_state_change(minutes)
        return self._maybe_generate_event()

    def apply_owner_action(self, action: str) -> Optional[SimulatedEvent]:
        """Apply one owner action and optionally emit a virtual behavior event."""
        if action not in OWNER_ACTIONS:
            raise ValueError(f"action must be one of {sorted(OWNER_ACTIONS)}")

        if action == "feed":
            self.state.hunger = clamp(self.state.hunger - 55)
            self.state.mood = clamp(self.state.mood + 6)
            self.state.affection = clamp(self.state.affection + 4)
            return self._event("eat", "饭盆", confidence=0.99)

        if action == "refill":
            self.state.thirst = clamp(self.state.thirst - 20)
            self.state.mood = clamp(self.state.mood + 3)
            return None

        if action == "play":
            self.state.energy = clamp(self.state.energy - 18)
            self.state.thirst = clamp(self.state.thirst + 10)
            self.state.mood = clamp(self.state.mood + 18)
            self.state.affection = clamp(self.state.affection + 12)
            self.state.last_play_at = self.now
            return self._event("play", "客厅", confidence=0.99)

        if action == "clean":
            self.state.cleanliness = clamp(self.state.cleanliness + 45)
            self.state.mood = clamp(self.state.mood + 7)
            return None

        if action == "pet":
            self.state.mood = clamp(self.state.mood + 10)
            self.state.affection = clamp(self.state.affection + 12)
            return None

        self._lullaby_until = self.now + timedelta(minutes=30)
        self.state.mood = clamp(self.state.mood + 5)
        return None

    def snapshot(self) -> dict:
        return {
            "pet_id": self.pet_id,
            "personality": self.personality,
            "now": self.now.isoformat(),
            "state": self.state.to_dict(),
        }

    def _natural_state_change(self, minutes: int) -> None:
        if self.state.is_sleeping:
            self.state.energy = clamp(self.state.energy + 0.9 * minutes)
            self.state.hunger = clamp(self.state.hunger + 0.06 * minutes)
            self.state.thirst = clamp(self.state.thirst + 0.08 * minutes)
            self.state.mood = clamp(self.state.mood + 0.02 * minutes)
            return

        personality_energy_factor = 0.75 if self.personality == "energetic" else 1.0
        self.state.hunger = clamp(self.state.hunger + 0.18 * minutes)
        self.state.thirst = clamp(self.state.thirst + 0.22 * minutes)
        self.state.energy = clamp(self.state.energy - 0.16 * minutes * personality_energy_factor)
        self.state.cleanliness = clamp(self.state.cleanliness - 0.06 * minutes)

        if self.state.cleanliness < 35:
            self.state.mood = clamp(self.state.mood - 0.05 * minutes)
        elif self.state.affection > 70:
            self.state.mood = clamp(self.state.mood + 0.02 * minutes)

    def _maybe_generate_event(self) -> Optional[SimulatedEvent]:
        if self.state.is_sleeping:
            if self.state.energy >= 92 or self._roll(0.08):
                self.state.is_sleeping = False
                return self._event("sleep_end", "窝", confidence=0.96)
            return None

        if self.state.energy < 22 or self._lullaby_active():
            probability = 0.65 if self._lullaby_active() else 0.35
            if self._roll(probability):
                self.state.is_sleeping = True
                return self._event("sleep_start", "窝", confidence=0.96)

        if self.state.thirst > 72 and self._roll(self._scaled_probability(self.state.thirst)):
            self.state.thirst = clamp(self.state.thirst - 48)
            self.state.mood = clamp(self.state.mood + 3)
            return self._event("drink", "水碗", confidence=0.94)

        if self.state.hunger > 74 and self._roll(self._scaled_probability(self.state.hunger)):
            self.state.hunger = clamp(self.state.hunger - 58)
            self.state.mood = clamp(self.state.mood + 5)
            return self._event("eat", "饭盆", confidence=0.94)

        if self._should_poop() and self._roll(0.18):
            self.state.cleanliness = clamp(self.state.cleanliness - 15)
            self.state.last_poop_at = self.now
            return self._event("poop", "厕所", confidence=0.93)

        if self._should_play() and self._roll(0.12):
            self.state.energy = clamp(self.state.energy - 12)
            self.state.thirst = clamp(self.state.thirst + 8)
            self.state.mood = clamp(self.state.mood + 8)
            self.state.last_play_at = self.now
            return self._event("play", "客厅", confidence=0.92)

        return None

    def _event(self, behavior: str, location_name: str, confidence: float) -> SimulatedEvent:
        return SimulatedEvent(
            pet_id=self.pet_id,
            behavior=behavior,
            location_name=location_name,
            occurred_at=self.now.isoformat(),
            confidence=confidence,
        )

    def _roll(self, probability: float) -> bool:
        return self.random.random() < clamp(probability, 0, 1)

    def _scaled_probability(self, value: float) -> float:
        return clamp((value - 65) / 45, 0.05, 0.85)

    def _lullaby_active(self) -> bool:
        return self._lullaby_until is not None and self.now <= self._lullaby_until

    def _should_poop(self) -> bool:
        if self.state.hunger < 45:
            return False
        if self.state.last_poop_at is None:
            return True
        return self.now - self.state.last_poop_at > timedelta(hours=6)

    def _should_play(self) -> bool:
        if self.state.energy < 35 or self.state.mood < 45:
            return False
        if self.state.last_play_at is None:
            return self.personality in {"energetic", "sweet"}
        return self.now - self.state.last_play_at > timedelta(hours=3)


if __name__ == "__main__":
    sim = PetSimulator(
        pet_id=1,
        personality="energetic",
        start_time=datetime(2026, 5, 7, 8, 0, tzinfo=timezone(timedelta(hours=8))),
        seed=7,
    )
    print("initial:", sim.snapshot())
    for _ in range(24):
        event = sim.tick(minutes=30)
        if event:
            print("event:", event.to_payload())
    print("after ticks:", sim.snapshot())
    print("owner action:", sim.apply_owner_action("play"))
    print("final:", sim.snapshot())
