"""Loot items, ground spawns, death crates, and Supply Air Drops."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pygame

import config
from src.weapons import choose_random_ground_weapon


@dataclass
class LootItem:
    """A single pickable ground item."""

    kind: str  # "weapon", "ammo", "vest", "helmet", "first_aid", "bandage", "energy_drink"
    x: float
    y: float
    name: str
    amount: int = 1
    level: int = 0
    weapon_mag: int = -1  # Preserves magazine count when a weapon is dropped

    @property
    def label(self) -> str:
        if self.kind == "weapon":
            return self.name
        if self.kind == "ammo":
            return f"{self.name} x{self.amount}"
        if self.kind == "vest":
            return f"Vest Lv.{self.level}"
        if self.kind == "helmet":
            return f"Helmet Lv.{self.level}"
        if self.kind == "first_aid":
            return "First Aid Kit"
        if self.kind == "bandage":
            return f"Bandage x{self.amount}"
        if self.kind == "energy_drink":
            return "Energy Drink"
        return self.name


@dataclass
class DeathCrate:
    """Lootable wooden crate dropped when a player or bot is eliminated."""

    x: float
    y: float
    owner_name: str
    items: List[LootItem] = field(default_factory=list)
    age: float = 0.0

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


@dataclass
class SupplyDrop:
    """Periodic Supply Air Drop with red smoke plume, Level 3 gear, and AWM."""

    x: float
    y: float
    items: List[LootItem] = field(default_factory=list)
    fall_timer: float = config.AIRDROP_FALL_TIME
    smoke_timer: float = 0.0
    smoke_duration: float = 42.0
    opened: bool = False

    @property
    def landed(self) -> bool:
        return self.fall_timer <= 0.0

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


class LootManager:
    """Manages ground loot spawns, death crates, and supply air drops."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.ground_items: List[LootItem] = []
        self.death_crates: List[DeathCrate] = []
        self.supply_drops: List[SupplyDrop] = []

    def populate_world(self, world) -> None:
        """Spawn balanced loot inside buildings and around outdoor compounds."""
        self.ground_items.clear()
        self.death_crates.clear()
        self.supply_drops.clear()

        # 1. Interior building spawns (high value)
        for building in world.buildings:
            spots = list(building.loot_spots)
            self.rng.shuffle(spots)
            # Guarantee at least 1 weapon + matching ammo in every building
            w_spot = spots[0]
            weapon_name = choose_random_ground_weapon(self.rng)
            ammo_type = config.WEAPON_SPECS[weapon_name]["ammo_type"]
            self.ground_items.append(LootItem("weapon", w_spot[0], w_spot[1], weapon_name))
            self.ground_items.append(
                LootItem(
                    "ammo",
                    w_spot[0] + self.rng.uniform(-16, 16),
                    w_spot[1] + self.rng.uniform(-16, 16),
                    ammo_type,
                    amount=config.AMMO_PACK_AMOUNT[ammo_type],
                )
            )

            # Fill 2-3 additional interior spots with armor, meds, or extra guns/ammo
            for sx, sy in spots[1 : self.rng.randint(3, 4)]:
                self.ground_items.append(self._roll_generic_loot(sx, sy))

        # 2. Scattered outdoor loot near roads and cover
        for _ in range(55):
            lx, ly = world.find_open_spawn(min_margin=160.0, clearance=24.0)
            self.ground_items.append(self._roll_generic_loot(lx, ly))

    def _roll_generic_loot(self, x: float, y: float) -> LootItem:
        roll = self.rng.random()
        if roll < 0.24:
            w = choose_random_ground_weapon(self.rng)
            return LootItem("weapon", x, y, w)
        if roll < 0.50:
            ammo_type = self.rng.choice(["5.56mm", "7.62mm", ".45 ACP", "12 Gauge", "9mm"])
            return LootItem("ammo", x, y, ammo_type, amount=config.AMMO_PACK_AMOUNT[ammo_type])
        if roll < 0.64:
            lvl = self.rng.choices([1, 2, 3], weights=[58, 34, 8], k=1)[0]
            return LootItem("vest", x, y, f"Vest Lv.{lvl}", level=lvl)
        if roll < 0.76:
            lvl = self.rng.choices([1, 2, 3], weights=[58, 34, 8], k=1)[0]
            return LootItem("helmet", x, y, f"Helmet Lv.{lvl}", level=lvl)
        if roll < 0.85:
            return LootItem("first_aid", x, y, "First Aid Kit", amount=1)
        if roll < 0.93:
            return LootItem("bandage", x, y, "Bandage", amount=self.rng.choice([2, 3]))
        return LootItem("energy_drink", x, y, "Energy Drink", amount=1)

    def spawn_death_crate(self, entity) -> DeathCrate:
        """Create a DeathCrate containing the eliminated combatant's gear."""
        items: List[LootItem] = []

        for w in entity.weapons:
            if w is not None and w.name != "P92":
                items.append(LootItem("weapon", entity.x, entity.y, w.name, weapon_mag=w.ammo_in_mag))

        for ammo_type, qty in entity.ammo_reserve.items():
            if qty > 0:
                items.append(LootItem("ammo", entity.x, entity.y, ammo_type, amount=qty))

        if entity.vest_level > 0 and entity.vest_durability > 15.0:
            items.append(
                LootItem("vest", entity.x, entity.y, f"Vest Lv.{entity.vest_level}", level=entity.vest_level)
            )
        if entity.helmet_level > 0 and entity.helmet_durability > 15.0:
            items.append(
                LootItem("helmet", entity.x, entity.y, f"Helmet Lv.{entity.helmet_level}", level=entity.helmet_level)
            )
        if entity.first_aids > 0:
            items.append(LootItem("first_aid", entity.x, entity.y, "First Aid Kit", amount=entity.first_aids))
        if entity.bandages > 0:
            items.append(LootItem("bandage", entity.x, entity.y, "Bandage", amount=entity.bandages))
        if entity.energy_drinks > 0:
            items.append(LootItem("energy_drink", entity.x, entity.y, "Energy Drink", amount=entity.energy_drinks))

        crate = DeathCrate(entity.x, entity.y, entity.name, items)
        self.death_crates.append(crate)
        return crate

    def spawn_supply_drop(self, x: float, y: float) -> SupplyDrop:
        """Spawn a high-tier Supply Air Drop with AWM, .300 Magnum, and Level 3 gear."""
        items = [
            LootItem("weapon", x, y, "AWM", weapon_mag=config.WEAPON_SPECS["AWM"]["mag_size"]),
            LootItem("ammo", x, y, ".300 Magnum", amount=20),
            LootItem("vest", x, y, "Vest Lv.3", level=3),
            LootItem("helmet", x, y, "Helmet Lv.3", level=3),
            LootItem("first_aid", x, y, "First Aid Kit", amount=2),
            LootItem("energy_drink", x, y, "Energy Drink", amount=2),
        ]
        drop = SupplyDrop(x=x, y=y, items=items)
        self.supply_drops.append(drop)
        return drop

    def drop_weapon_on_ground(self, x: float, y: float, weapon) -> None:
        """Drop a replaced weapon cleanly onto the ground with its current mag count."""
        offset_x = self.rng.uniform(-16.0, 16.0)
        offset_y = self.rng.uniform(-16.0, 16.0)
        self.ground_items.append(
            LootItem(
                kind="weapon",
                x=x + offset_x,
                y=y + offset_y,
                name=weapon.name,
                weapon_mag=weapon.ammo_in_mag,
            )
        )

    def update(self, dt: float, particles: list) -> None:
        """Update falling air drops and emit red smoke plume particles."""
        from src.entities import Particle  # Local import avoids circular dependency

        for crate in self.death_crates:
            crate.age += dt

        for drop in self.supply_drops:
            if not drop.landed:
                drop.fall_timer = max(0.0, drop.fall_timer - dt)
            elif drop.smoke_duration > 0.0 and not drop.is_empty:
                drop.smoke_duration -= dt
                drop.smoke_timer -= dt
                if drop.smoke_timer <= 0.0:
                    drop.smoke_timer = 0.09
                    particles.append(
                        Particle(
                            x=drop.x + self.rng.uniform(-8, 8),
                            y=drop.y + self.rng.uniform(-8, 8),
                            vx=self.rng.uniform(-14, 14),
                            vy=self.rng.uniform(-55, -28),
                            radius=self.rng.uniform(7, 13),
                            color=(220, 45, 45),
                            life=1.15,
                            max_life=1.15,
                            grow_rate=10.0,
                        )
                    )

    def find_nearest_interactable(
        self, x: float, y: float
    ) -> Tuple[Optional[str], Optional[object], float]:
        """Find nearest ground item, death crate, or landed supply drop within reach."""
        best_type: Optional[str] = None
        best_obj: Optional[object] = None
        best_dist = config.CRATE_INTERACT_RADIUS

        for drop in self.supply_drops:
            if drop.landed and not drop.is_empty:
                d = math.hypot(drop.x - x, drop.y - y)
                if d < best_dist:
                    best_dist = d
                    best_type = "supply_drop"
                    best_obj = drop

        for crate in self.death_crates:
            if not crate.is_empty:
                d = math.hypot(crate.x - x, crate.y - y)
                if d < best_dist:
                    best_dist = d
                    best_type = "death_crate"
                    best_obj = crate

        ground_cap = min(best_dist, config.LOOT_PICKUP_RADIUS)
        for item in self.ground_items:
            d = math.hypot(item.x - x, item.y - y)
            if d < ground_cap:
                ground_cap = d
                best_dist = d
                best_type = "ground_item"
                best_obj = item

        return best_type, best_obj, best_dist

    # ------------------------------------------------------------------
    # Rendering (Camera-Culled)
    # ------------------------------------------------------------------
    def draw(
        self,
        surface: pygame.Surface,
        cam_x: float,
        cam_y: float,
        view_w: int,
        view_h: int,
        small_font: pygame.font.Font,
    ) -> None:
        margin = 50

        # 1. Ground loot items
        for item in self.ground_items:
            sx = item.x - cam_x
            sy = item.y - cam_y
            if sx < -margin or sx > view_w + margin or sy < -margin or sy > view_h + margin:
                continue
            self._draw_loot_icon(surface, item, int(sx), int(sy), small_font)

        # 2. Death crates
        for crate in self.death_crates:
            sx = crate.x - cam_x
            sy = crate.y - cam_y
            if sx < -margin or sx > view_w + margin or sy < -margin or sy > view_h + margin:
                continue
            ix, iy = int(sx), int(sy)
            box = pygame.Rect(ix - 13, iy - 10, 26, 20)
            pygame.draw.rect(surface, (42, 32, 22), box.move(2, 3))
            fill = (134, 96, 56) if not crate.is_empty else (86, 76, 66)
            pygame.draw.rect(surface, fill, box, border_radius=3)
            pygame.draw.rect(surface, (48, 34, 20), box, 2, border_radius=3)
            pygame.draw.line(surface, (70, 50, 30), (box.left + 3, box.centery), (box.right - 3, box.centery), 2)
            if not crate.is_empty:
                pygame.draw.circle(surface, (245, 205, 70), (ix, iy - 13), 3)

        # 3. Supply Air Drops
        for drop in self.supply_drops:
            sx = drop.x - cam_x
            sy = drop.y - cam_y
            if sx < -120 or sx > view_w + 120 or sy < -160 or sy > view_h + 120:
                continue
            ix, iy = int(sx), int(sy)
            if not drop.landed:
                # Parachute descent visual
                ratio = drop.fall_timer / config.AIRDROP_FALL_TIME
                drop_y = int(iy - ratio * 150)
                # Landing shadow
                shadow_r = max(10, int(24 * (1.0 - ratio * 0.5)))
                pygame.draw.circle(surface, (40, 52, 34), (ix, iy), shadow_r)
                # Canopy & cords
                pygame.draw.line(surface, (220, 220, 220), (ix - 20, drop_y - 34), (ix - 10, drop_y - 8), 1)
                pygame.draw.line(surface, (220, 220, 220), (ix + 20, drop_y - 34), (ix + 10, drop_y - 8), 1)
                pygame.draw.ellipse(surface, (238, 238, 242), pygame.Rect(ix - 26, drop_y - 48, 52, 22))
                crate_rect = pygame.Rect(ix - 15, drop_y - 12, 30, 24)
            else:
                crate_rect = pygame.Rect(ix - 17, iy - 15, 34, 30)
                pygame.draw.rect(surface, (36, 46, 30), crate_rect.move(4, 5))

            pygame.draw.rect(surface, config.COLOR_AIRDROP_CRATE, crate_rect, border_radius=4)
            tarp = pygame.Rect(crate_rect.x, crate_rect.y, crate_rect.w, crate_rect.h // 2)
            pygame.draw.rect(surface, config.COLOR_AIRDROP_TARP, tarp, border_radius=3)
            pygame.draw.rect(surface, (240, 240, 240), crate_rect, 2, border_radius=4)

    def _draw_loot_icon(
        self,
        surface: pygame.Surface,
        item: LootItem,
        ix: int,
        iy: int,
        small_font: pygame.font.Font,
    ) -> None:
        # Subtle ground glow ring for readability
        pygame.draw.circle(surface, (22, 28, 22), (ix, iy), 13, 1)

        if item.kind == "weapon":
            spec = config.WEAPON_SPECS[item.name]
            col = spec["color"]
            pygame.draw.rect(surface, (25, 25, 25), (ix - 14, iy - 5, 28, 10), border_radius=3)
            pygame.draw.rect(surface, col, (ix - 12, iy - 3, 24, 6), border_radius=2)
            pygame.draw.rect(surface, (230, 200, 90), (ix - 2, iy + 2, 5, 5))
            txt = small_font.render(item.name, True, (245, 235, 190))
            surface.blit(txt, (ix - txt.get_width() // 2, iy - 22))

        elif item.kind == "ammo":
            col = config.AMMO_COLORS.get(item.name, (220, 200, 90))
            pygame.draw.rect(surface, (30, 30, 30), (ix - 8, iy - 6, 16, 12), border_radius=2)
            pygame.draw.rect(surface, col, (ix - 6, iy - 4, 12, 8), border_radius=1)

        elif item.kind == "vest":
            lvl_col = {1: (130, 155, 130), 2: (95, 145, 205), 3: (230, 180, 55)}.get(item.level, (160, 160, 160))
            pts = [(ix - 8, iy - 8), (ix + 8, iy - 8), (ix + 10, iy + 8), (ix - 10, iy + 8)]
            pygame.draw.polygon(surface, lvl_col, pts)
            pygame.draw.polygon(surface, (25, 30, 35), pts, 2)
            txt = small_font.render(f"V{item.level}", True, (255, 255, 255))
            surface.blit(txt, (ix - txt.get_width() // 2, iy - 6))

        elif item.kind == "helmet":
            lvl_col = {1: (130, 155, 130), 2: (95, 145, 205), 3: (230, 180, 55)}.get(item.level, (160, 160, 160))
            pygame.draw.circle(surface, lvl_col, (ix, iy), 9)
            pygame.draw.circle(surface, (25, 30, 35), (ix, iy), 9, 2)
            txt = small_font.render(f"H{item.level}", True, (255, 255, 255))
            surface.blit(txt, (ix - txt.get_width() // 2, iy - 6))

        elif item.kind == "first_aid":
            pygame.draw.rect(surface, (238, 240, 244), (ix - 9, iy - 7, 18, 14), border_radius=3)
            pygame.draw.rect(surface, (215, 48, 48), (ix - 2, iy - 5, 4, 10))
            pygame.draw.rect(surface, (215, 48, 48), (ix - 5, iy - 2, 10, 4))
            pygame.draw.rect(surface, (45, 45, 45), (ix - 9, iy - 7, 18, 14), 1, border_radius=3)

        elif item.kind == "bandage":
            pygame.draw.circle(surface, (232, 224, 210), (ix, iy), 7)
            pygame.draw.circle(surface, (185, 65, 65), (ix, iy), 3)
            pygame.draw.circle(surface, (70, 65, 60), (ix, iy), 7, 1)

        elif item.kind == "energy_drink":
            pygame.draw.rect(surface, (46, 158, 232), (ix - 5, iy - 8, 10, 16), border_radius=3)
            pygame.draw.rect(surface, (240, 205, 60), (ix - 4, iy - 3, 8, 5))
            pygame.draw.rect(surface, (22, 35, 50), (ix - 5, iy - 8, 10, 16), 1, border_radius=3)
