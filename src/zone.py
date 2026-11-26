"""Multi-phase shrinking Blue Zone logic."""

from __future__ import annotations

import math
import random
from typing import Tuple

import config


class BlueZone:
    """Manages the classic Battle Royale white safe zone and shrinking blue ring."""

    def __init__(self, world_width: int, world_height: int, rng: random.Random) -> None:
        self.world_width = float(world_width)
        self.world_height = float(world_height)
        self.rng = rng

        # Start with the entire map enclosed
        self.current_x = self.world_width * 0.5
        self.current_y = self.world_height * 0.5
        self.current_radius = math.hypot(self.world_width, self.world_height) * 0.54

        self.start_x = self.current_x
        self.start_y = self.current_y
        self.start_radius = self.current_radius

        self.target_x = self.current_x
        self.target_y = self.current_y
        self.target_radius = self.current_radius

        self.phase_index = 0
        self.state = "WAIT"  # "WAIT", "SHRINK", "CLOSED"
        self.timer = 0.0
        self.phase_duration = 1.0
        self.dps = config.ZONE_PHASES[0]["dps"]

        self._begin_phase(0)

    @property
    def phase_number(self) -> int:
        return min(self.phase_index + 1, len(config.ZONE_PHASES))

    @property
    def is_shrinking(self) -> bool:
        return self.state == "SHRINK"

    def _begin_phase(self, idx: int) -> None:
        if idx >= len(config.ZONE_PHASES):
            self.state = "CLOSED"
            self.timer = 0.0
            self.target_radius = 0.0
            self.current_radius = 0.0
            self.dps = config.ZONE_PHASES[-1]["dps"]
            return

        self.phase_index = idx
        phase = config.ZONE_PHASES[idx]
        self.dps = float(phase["dps"])

        self.start_x = self.current_x
        self.start_y = self.current_y
        self.start_radius = self.current_radius

        map_min = min(self.world_width, self.world_height)
        new_radius = map_min * float(phase["radius_ratio"])

        # Pick next safe zone center strictly inside current circle & within map margins
        if new_radius <= 1.0:
            self.target_x = self.current_x
            self.target_y = self.current_y
            self.target_radius = 0.0
        else:
            max_offset = max(0.0, self.current_radius - new_radius - 60.0)
            margin = max(240.0, new_radius * 0.45)
            chosen_x, chosen_y = self.current_x, self.current_y
            for _ in range(25):
                angle = self.rng.uniform(0.0, math.tau)
                dist = self.rng.uniform(0.0, max_offset * 0.72)
                cx = self.current_x + math.cos(angle) * dist
                cy = self.current_y + math.sin(angle) * dist
                cx = max(margin, min(self.world_width - margin, cx))
                cy = max(margin, min(self.world_height - margin, cy))
                if math.hypot(cx - self.current_x, cy - self.current_y) + new_radius <= self.current_radius + 40.0:
                    chosen_x, chosen_y = cx, cy
                    break
            self.target_x = chosen_x
            self.target_y = chosen_y
            self.target_radius = new_radius

        self.state = "WAIT"
        self.phase_duration = float(phase["wait"])
        self.timer = self.phase_duration

    def update(self, dt: float) -> None:
        """Advance zone timers and interpolate shrinking blue ring."""
        if self.state == "CLOSED":
            return

        self.timer -= dt
        if self.state == "WAIT":
            if self.timer <= 0.0:
                phase = config.ZONE_PHASES[self.phase_index]
                self.state = "SHRINK"
                self.phase_duration = max(0.1, float(phase["shrink"]))
                self.timer = self.phase_duration
                self.start_x = self.current_x
                self.start_y = self.current_y
                self.start_radius = self.current_radius
        elif self.state == "SHRINK":
            progress = 1.0 - max(0.0, self.timer) / self.phase_duration
            progress = max(0.0, min(1.0, progress))
            self.current_x = self.start_x + (self.target_x - self.start_x) * progress
            self.current_y = self.start_y + (self.target_y - self.start_y) * progress
            self.current_radius = self.start_radius + (self.target_radius - self.start_radius) * progress
            if self.timer <= 0.0:
                self.current_x = self.target_x
                self.current_y = self.target_y
                self.current_radius = self.target_radius
                self._begin_phase(self.phase_index + 1)

    def is_outside_blue(self, x: float, y: float) -> bool:
        """Return True if point (x, y) is taking Blue Zone damage."""
        if self.current_radius <= 0.5:
            return True
        return math.hypot(x - self.current_x, y - self.current_y) > self.current_radius

    def is_inside_safe(self, x: float, y: float) -> bool:
        """Return True if point (x, y) is inside the next white safe zone."""
        if self.target_radius <= 0.5:
            return math.hypot(x - self.target_x, y - self.target_y) < 35.0
        return math.hypot(x - self.target_x, y - self.target_y) <= self.target_radius

    def random_point_in_safe_zone(self, margin_ratio: float = 0.78) -> Tuple[float, float]:
        """Return a random point inside the target safe zone (used for air drops)."""
        radius = max(120.0, self.target_radius * margin_ratio)
        angle = self.rng.uniform(0.0, math.tau)
        dist = math.sqrt(self.rng.random()) * radius
        x = max(200.0, min(self.world_width - 200.0, self.target_x + math.cos(angle) * dist))
        y = max(200.0, min(self.world_height - 200.0, self.target_y + math.sin(angle) * dist))
        return x, y
