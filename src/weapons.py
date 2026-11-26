"""Weapon definitions, state tracking, and factory helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple

import config


@dataclass
class Weapon:
    """Represents a firearm instance with magazine and firing state."""

    name: str
    category: str
    ammo_type: str
    damage: float
    fire_rate: float
    mag_size: int
    reload_time: float
    bullet_speed: float
    spread_deg: float
    range: float
    pellets: int
    auto: bool
    recoil: float
    knockback: float
    barrel_length: float
    color: Tuple[int, int, int]
    tracer_color: Tuple[int, int, int]
    sound_key: str

    ammo_in_mag: int = 0
    cooldown: float = 0.0

    def __post_init__(self) -> None:
        if self.ammo_in_mag <= 0:
            self.ammo_in_mag = self.mag_size

    @property
    def fire_interval(self) -> float:
        return 1.0 / max(0.1, self.fire_rate)

    def update(self, dt: float) -> None:
        """Tick down firing cooldown."""
        if self.cooldown > 0.0:
            self.cooldown = max(0.0, self.cooldown - dt)

    def can_fire(self) -> bool:
        return self.cooldown <= 0.0 and self.ammo_in_mag > 0

    def consume_shot(self) -> bool:
        """Consume one round and trigger cooldown if ready."""
        if not self.can_fire():
            return False
        self.ammo_in_mag -= 1
        self.cooldown = self.fire_interval
        return True

    def needs_reload(self) -> bool:
        return self.ammo_in_mag < self.mag_size

    def clone(self) -> "Weapon":
        """Create an independent copy preserving current magazine count."""
        w = create_weapon(self.name, full_mag=False)
        w.ammo_in_mag = self.ammo_in_mag
        return w


def create_weapon(name: str, full_mag: bool = True) -> Weapon:
    """Instantiate a Weapon from config.WEAPON_SPECS."""
    spec = config.WEAPON_SPECS[name]
    w = Weapon(
        name=name,
        category=spec["category"],
        ammo_type=spec["ammo_type"],
        damage=float(spec["damage"]),
        fire_rate=float(spec["fire_rate"]),
        mag_size=int(spec["mag_size"]),
        reload_time=float(spec["reload_time"]),
        bullet_speed=float(spec["bullet_speed"]),
        spread_deg=float(spec["spread_deg"]),
        range=float(spec["range"]),
        pellets=int(spec["pellets"]),
        auto=bool(spec["auto"]),
        recoil=float(spec["recoil"]),
        knockback=float(spec["knockback"]),
        barrel_length=float(spec["barrel_length"]),
        color=tuple(spec["color"]),
        tracer_color=tuple(spec["tracer_color"]),
        sound_key=str(spec["sound"]),
        ammo_in_mag=int(spec["mag_size"]) if full_mag else 0,
    )
    return w


def choose_random_ground_weapon(rng: random.Random) -> str:
    """Pick a weighted random weapon from the standard ground loot pool."""
    names = []
    weights = []
    for name, spec in config.WEAPON_SPECS.items():
        wt = float(spec.get("weight", 0.0))
        if wt > 0.0:
            names.append(name)
            weights.append(wt)
    return rng.choices(names, weights=weights, k=1)[0]


def weapon_power_score(name: str) -> float:
    """Heuristic score used by AI bots to decide whether to upgrade weapons."""
    scores = {
        "P92": 1.0,
        "S12K": 2.4,
        "UMP45": 3.0,
        "AKM": 4.2,
        "M416": 4.5,
        "AWM": 5.5,
    }
    return scores.get(name, 1.0)
