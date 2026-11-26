"""Entities: Combatant, Player, AI Bot state machine, Bullet, and Particle."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame

import config
from src.loot import LootItem
from src.weapons import Weapon, create_weapon, weapon_power_score


@dataclass
class Particle:
    """Short-lived visual particle for muzzle flash, blood, sparks, and smoke."""

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: Tuple[int, int, int]
    life: float
    max_life: float
    grow_rate: float = 0.0

    def update(self, dt: float) -> bool:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= max(0.0, 1.0 - 4.5 * dt)
        self.vy *= max(0.0, 1.0 - 4.5 * dt)
        self.radius = max(0.5, self.radius + self.grow_rate * dt)
        self.life -= dt
        return self.life > 0.0

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float) -> None:
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        ratio = max(0.0, min(1.0, self.life / max(0.001, self.max_life)))
        r = max(1, int(self.radius * (0.45 + 0.55 * ratio)))
        pygame.draw.circle(surface, self.color, (sx, sy), r)


class Bullet:
    """High-speed projectile with tracer tail, range cap, and knockback."""

    def __init__(
        self,
        x: float,
        y: float,
        angle: float,
        weapon: Weapon,
        owner: "Combatant",
    ) -> None:
        self.x = x
        self.y = y
        self.prev_x = x
        self.prev_y = y
        self.angle = angle
        self.speed = weapon.bullet_speed
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed
        self.damage = weapon.damage
        self.knockback = weapon.knockback
        self.max_range = weapon.range
        self.traveled = 0.0
        self.tracer_color = weapon.tracer_color
        self.weapon_name = weapon.name
        self.owner = owner
        self.alive = True

    def update(self, dt: float) -> None:
        self.prev_x = self.x
        self.prev_y = self.y
        step = self.speed * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.traveled += step
        if self.traveled >= self.max_range:
            self.alive = False

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float) -> None:
        # Draw tracer tail proportional to bullet velocity
        tail_len = min(28.0, self.traveled)
        tx = self.x - math.cos(self.angle) * tail_len
        ty = self.y - math.sin(self.angle) * tail_len
        pygame.draw.line(
            surface,
            self.tracer_color,
            (int(tx - cam_x), int(ty - cam_y)),
            (int(self.x - cam_x), int(self.y - cam_y)),
            2,
        )
        pygame.draw.circle(surface, (255, 255, 240), (int(self.x - cam_x), int(self.y - cam_y)), 2)


class Combatant:
    """Shared base class for Player and AI Bots."""

    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        is_player: bool = False,
        base_speed: float = config.PLAYER_SPEED,
        radius: float = config.PLAYER_RADIUS,
    ) -> None:
        self.name = name
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.knock_vx = 0.0
        self.knock_vy = 0.0
        self.angle = 0.0
        self.radius = radius
        self.base_speed = base_speed
        self.is_player = is_player

        self.hp = config.PLAYER_MAX_HP
        self.max_hp = config.PLAYER_MAX_HP
        self.boost = 0.0
        self.alive = True

        # Armor
        self.vest_level = 0
        self.vest_durability = 0.0
        self.helmet_level = 0
        self.helmet_durability = 0.0

        # Inventory: 2 weapon slots, starts with P92 pistol in slot 0
        self.weapons: List[Optional[Weapon]] = [create_weapon("P92", full_mag=True), None]
        self.active_slot = 0
        self.ammo_reserve: Dict[str, int] = {k: 0 for k in config.AMMO_MAX_RESERVE}
        self.ammo_reserve["9mm"] = 30

        # Healing items
        self.first_aids = 1 if is_player else 0
        self.bandages = 2
        self.energy_drinks = 1 if is_player else 0

        # Action timers
        self.reloading = False
        self.reload_timer = 0.0
        self.reload_duration = 0.0

        self.healing_kind: Optional[str] = None  # "first_aid", "bandage", "energy_drink"
        self.heal_timer = 0.0
        self.heal_duration = 0.0

        # Combat visuals & stats
        self.muzzle_flash_timer = 0.0
        self.hurt_flash_timer = 0.0
        self.recoil_offset = 0.0
        self.kills = 0
        self.damage_dealt = 0.0
        self.zone_tick_accum = 0.0

    @property
    def active_weapon(self) -> Weapon:
        w = self.weapons[self.active_slot]
        if w is not None:
            return w
        # Fallback if somehow empty
        other = self.weapons[1 - self.active_slot]
        if other is not None:
            self.active_slot = 1 - self.active_slot
            return other
        pistol = create_weapon("P92", full_mag=True)
        self.weapons[0] = pistol
        self.active_slot = 0
        return pistol

    @property
    def current_speed(self) -> float:
        spd = self.base_speed
        if self.boost >= 60.0:
            spd *= config.BOOST_SPEED_BONUS
        if self.healing_kind is not None:
            spd *= 0.35
        return spd

    def switch_slot(self, slot: int) -> bool:
        if slot not in (0, 1) or slot == self.active_slot:
            return False
        if self.weapons[slot] is None:
            return False
        self.active_slot = slot
        self.cancel_reload()
        self.cancel_heal()
        return True

    def cancel_reload(self) -> None:
        self.reloading = False
        self.reload_timer = 0.0
        self.reload_duration = 0.0

    def cancel_heal(self) -> None:
        self.healing_kind = None
        self.heal_timer = 0.0
        self.heal_duration = 0.0

    def start_reload(self, sound=None) -> bool:
        """Start reloading active weapon if magazine is not full and reserve > 0."""
        w = self.active_weapon
        if self.reloading or not w.needs_reload():
            return False
        if self.ammo_reserve.get(w.ammo_type, 0) <= 0:
            return False
        self.cancel_heal()
        self.reloading = True
        self.reload_duration = w.reload_time
        self.reload_timer = w.reload_time
        if sound is not None and self.is_player:
            sound.play("reload", 0.9)
        return True

    def start_heal(self, kind: str) -> Tuple[bool, str]:
        """Begin a healing or boost cast timer."""
        if self.healing_kind is not None:
            return False, "Already Healing"

        if kind == "first_aid":
            if self.first_aids <= 0:
                # Smart fallback to bandage if player pressed 4 with no First Aid Kits
                if self.bandages > 0:
                    kind = "bandage"
                else:
                    return False, "No Medkits"
            elif self.hp >= config.FIRST_AID_MAX_HP:
                return False, "HP Above 75"

        if kind == "bandage":
            if self.bandages <= 0:
                return False, "No Bandages"
            if self.hp >= config.BANDAGE_MAX_HP:
                return False, "HP Above 75"

        if kind == "energy_drink":
            if self.energy_drinks <= 0:
                return False, "No Energy Drinks"
            if self.boost >= config.PLAYER_MAX_BOOST:
                return False, "Boost Full"

        self.cancel_reload()
        self.healing_kind = kind
        if kind == "first_aid":
            self.heal_duration = config.FIRST_AID_CAST_TIME
        elif kind == "bandage":
            self.heal_duration = config.BANDAGE_CAST_TIME
        else:
            self.heal_duration = config.ENERGY_DRINK_CAST_TIME
        self.heal_timer = self.heal_duration
        return True, ""

    def try_fire(
        self,
        bullets: List[Bullet],
        particles: List[Particle],
        rng: random.Random,
        sound=None,
        listener_pos: Optional[Tuple[float, float]] = None,
    ) -> bool:
        """Attempt to fire the active weapon, spawning bullets & muzzle particles."""
        w = self.active_weapon
        if self.reloading:
            return False
        if w.ammo_in_mag <= 0:
            if w.cooldown <= 0.0:
                if self.ammo_reserve.get(w.ammo_type, 0) > 0:
                    self.start_reload(sound)
                else:
                    w.cooldown = 0.35
                    if sound is not None and self.is_player:
                        sound.play("empty", 0.8)
            return False

        if not w.consume_shot():
            return False

        self.cancel_heal()
        self.muzzle_flash_timer = 0.055
        self.recoil_offset = min(7.0, self.recoil_offset + w.recoil * 0.65)

        muzzle_x = self.x + math.cos(self.angle) * (self.radius + w.barrel_length * 0.55)
        muzzle_y = self.y + math.sin(self.angle) * (self.radius + w.barrel_length * 0.55)

        spread_rad = math.radians(w.spread_deg)
        for _ in range(w.pellets):
            pellet_angle = self.angle + rng.uniform(-spread_rad, spread_rad)
            bullets.append(Bullet(muzzle_x, muzzle_y, pellet_angle, w, self))

        # Muzzle flash & smoke sparks
        for _ in range(3 if w.pellets == 1 else 6):
            sp_ang = self.angle + rng.uniform(-0.45, 0.45)
            sp_spd = rng.uniform(70, 180)
            particles.append(
                Particle(
                    x=muzzle_x,
                    y=muzzle_y,
                    vx=math.cos(sp_ang) * sp_spd,
                    vy=math.sin(sp_ang) * sp_spd,
                    radius=rng.uniform(2.5, 5.0),
                    color=(255, 220, 110),
                    life=0.09,
                    max_life=0.09,
                )
            )

        # Play sound with distance attenuation for non-player shooters
        if sound is not None:
            if self.is_player:
                sound.play(w.sound_key, 0.9)
            elif listener_pos is not None:
                dist = math.hypot(self.x - listener_pos[0], self.y - listener_pos[1])
                if dist < 950.0:
                    vol = max(0.05, (1.0 - dist / 950.0) * 0.55)
                    sound.play(w.sound_key, vol)

        # Auto-reload when mag runs dry and reserve exists
        if w.ammo_in_mag == 0 and self.ammo_reserve.get(w.ammo_type, 0) > 0:
            self.start_reload(sound)
        return True

    def take_damage(
        self,
        raw_damage: float,
        is_zone: bool = False,
        knock_angle: Optional[float] = None,
        knock_force: float = 0.0,
        is_headshot: bool = False,
    ) -> float:
        """Apply damage with vest/helmet mitigation and durability wear; return actual HP lost."""
        if not self.alive:
            return 0.0

        dmg = raw_damage
        if not is_zone:
            if is_headshot and self.helmet_level > 0 and self.helmet_durability > 0:
                red = config.HELMET_DAMAGE_REDUCTION[self.helmet_level]
                absorbed = dmg * red
                dmg -= absorbed
                self.helmet_durability = max(0.0, self.helmet_durability - absorbed * 1.15)
                if self.helmet_durability <= 0.0:
                    self.helmet_level = 0
            elif self.vest_level > 0 and self.vest_durability > 0:
                red = config.VEST_DAMAGE_REDUCTION[self.vest_level]
                absorbed = dmg * red
                dmg -= absorbed
                self.vest_durability = max(0.0, self.vest_durability - absorbed * 1.05)
                if self.vest_durability <= 0.0:
                    self.vest_level = 0

            self.hurt_flash_timer = 0.12
            if knock_angle is not None and knock_force > 0.0:
                self.knock_vx += math.cos(knock_angle) * knock_force
                self.knock_vy += math.sin(knock_angle) * knock_force

        actual = min(self.hp, max(0.0, dmg))
        self.hp -= actual
        if self.hp <= 0.0:
            self.hp = 0.0
            self.alive = False
        return actual

    def pickup_item(self, item: LootItem, loot_manager) -> Tuple[bool, str]:
        """Attempt to pick up a LootItem; returns (consumed_completely, status_message)."""
        if item.kind == "weapon":
            new_w = create_weapon(item.name, full_mag=True)
            if item.weapon_mag >= 0:
                new_w.ammo_in_mag = min(new_w.mag_size, item.weapon_mag)

            # Fill empty secondary slot first, or replace starting pistol
            if self.weapons[1] is None:
                self.weapons[1] = new_w
                # Auto-switch if currently holding starter pistol
                if self.weapons[self.active_slot] and self.weapons[self.active_slot].name == "P92":
                    self.active_slot = 1
                self.cancel_reload()
                return True, f"Equipped {new_w.name}"

            # Replace active weapon and drop old one cleanly
            old_w = self.weapons[self.active_slot]
            self.weapons[self.active_slot] = new_w
            self.cancel_reload()
            if old_w is not None and old_w.name != "P92":
                loot_manager.drop_weapon_on_ground(self.x, self.y, old_w)
            return True, f"Swapped to {new_w.name}"

        if item.kind == "ammo":
            cap = config.AMMO_MAX_RESERVE.get(item.name, 120)
            cur = self.ammo_reserve.get(item.name, 0)
            if cur >= cap:
                return False, f"{item.name} Ammo Full"
            take = min(item.amount, cap - cur)
            self.ammo_reserve[item.name] = cur + take
            item.amount -= take
            if item.amount <= 0:
                return True, f"+{take} {item.name}"
            return False, f"+{take} {item.name} (Max)"

        if item.kind == "vest":
            max_dur = config.VEST_MAX_DURABILITY[item.level]
            if item.level < self.vest_level:
                return False, "Higher Vest Equipped"
            if item.level == self.vest_level and self.vest_durability >= max_dur * 0.95:
                return False, "Vest Already Full"
            self.vest_level = item.level
            self.vest_durability = max_dur
            return True, f"Vest Lv.{item.level}"

        if item.kind == "helmet":
            max_dur = config.HELMET_MAX_DURABILITY[item.level]
            if item.level < self.helmet_level:
                return False, "Higher Helmet Equipped"
            if item.level == self.helmet_level and self.helmet_durability >= max_dur * 0.95:
                return False, "Helmet Already Full"
            self.helmet_level = item.level
            self.helmet_durability = max_dur
            return True, f"Helmet Lv.{item.level}"

        if item.kind == "first_aid":
            if self.first_aids >= 5:
                return False, "Medkits Full"
            take = min(item.amount, 5 - self.first_aids)
            self.first_aids += take
            item.amount -= take
            return item.amount <= 0, f"+{take} First Aid"

        if item.kind == "bandage":
            if self.bandages >= 10:
                return False, "Bandages Full"
            take = min(item.amount, 10 - self.bandages)
            self.bandages += take
            item.amount -= take
            return item.amount <= 0, f"+{take} Bandage"

        if item.kind == "energy_drink":
            if self.energy_drinks >= 6:
                return False, "Drinks Full"
            take = min(item.amount, 6 - self.energy_drinks)
            self.energy_drinks += take
            item.amount -= take
            return item.amount <= 0, f"+{take} Energy Drink"

        return False, ""

    def update_common(self, dt: float, world, sound=None) -> None:
        """Update timers, boost regeneration, recoil, and knockback physics."""
        for w in self.weapons:
            if w is not None:
                w.update(dt)

        if self.muzzle_flash_timer > 0.0:
            self.muzzle_flash_timer = max(0.0, self.muzzle_flash_timer - dt)
        if self.hurt_flash_timer > 0.0:
            self.hurt_flash_timer = max(0.0, self.hurt_flash_timer - dt)
        if self.recoil_offset > 0.0:
            self.recoil_offset = max(0.0, self.recoil_offset - 28.0 * dt)

        # Reload timer
        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0.0:
                w = self.active_weapon
                needed = w.mag_size - w.ammo_in_mag
                avail = self.ammo_reserve.get(w.ammo_type, 0)
                load = min(needed, avail)
                w.ammo_in_mag += load
                self.ammo_reserve[w.ammo_type] = avail - load
                self.reloading = False
                self.reload_timer = 0.0
                self.reload_duration = 0.0

        # Healing timer
        if self.healing_kind is not None:
            self.heal_timer -= dt
            if self.heal_timer <= 0.0:
                if self.healing_kind == "first_aid" and self.first_aids > 0:
                    self.first_aids -= 1
                    self.hp = min(self.max_hp, max(self.hp, config.FIRST_AID_MAX_HP))
                elif self.healing_kind == "bandage" and self.bandages > 0:
                    self.bandages -= 1
                    if self.hp < config.BANDAGE_MAX_HP:
                        self.hp = min(config.BANDAGE_MAX_HP, self.hp + config.BANDAGE_HEAL_AMOUNT)
                elif self.healing_kind == "energy_drink" and self.energy_drinks > 0:
                    self.energy_drinks -= 1
                    self.boost = min(config.PLAYER_MAX_BOOST, self.boost + config.ENERGY_DRINK_BOOST_AMOUNT)
                if sound is not None and self.is_player:
                    sound.play("heal", 0.8)
                self.cancel_heal()

        # Boost regeneration & decay
        if self.boost > 0.0:
            regen = config.BOOST_REGEN_HIGH if self.boost >= 60.0 else config.BOOST_REGEN_LOW
            if self.hp < self.max_hp:
                self.hp = min(self.max_hp, self.hp + regen * dt)
            self.boost = max(0.0, self.boost - config.BOOST_DECAY_RATE * dt)

        # Apply movement + decaying knockback velocity
        total_vx = self.vx + self.knock_vx
        total_vy = self.vy + self.knock_vy
        self.x += total_vx * dt
        self.y += total_vy * dt
        self.knock_vx *= max(0.0, 1.0 - 9.0 * dt)
        self.knock_vy *= max(0.0, 1.0 - 9.0 * dt)

        self.x, self.y = world.resolve_circle_collision(self.x, self.y, self.radius)

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Render top-down silhouette with directional shadow, helmet, hands, and weapon."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        r = int(self.radius)

        # Ground shadow
        pygame.draw.circle(surface, (42, 56, 36), (sx + 4, sy + 5), r)

        body_col = config.COLOR_PLAYER_BODY if self.is_player else config.COLOR_BOT_BODY
        outline_col = config.COLOR_PLAYER_OUTLINE if self.is_player else config.COLOR_BOT_OUTLINE
        if self.hurt_flash_timer > 0.0:
            body_col = (255, 240, 240)

        # Shoulders / torso
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        perp_x = -sin_a
        perp_y = cos_a

        # Vest ring if equipped
        if self.vest_level > 0:
            vest_col = {1: (130, 155, 130), 2: (95, 145, 205), 3: (235, 185, 55)}[self.vest_level]
            pygame.draw.circle(surface, vest_col, (sx, sy), r + 2)

        pygame.draw.circle(surface, body_col, (sx, sy), r)
        pygame.draw.circle(surface, outline_col, (sx, sy), r, 2)

        # Weapon barrel & hands
        w = self.active_weapon
        recoil_pull = self.recoil_offset
        barrel_start_x = sx + cos_a * (r * 0.4 - recoil_pull * 0.4) + perp_x * 5
        barrel_start_y = sy + sin_a * (r * 0.4 - recoil_pull * 0.4) + perp_y * 5
        barrel_end_x = sx + cos_a * (r + w.barrel_length * 0.55 - recoil_pull) + perp_x * 5
        barrel_end_y = sy + sin_a * (r + w.barrel_length * 0.55 - recoil_pull) + perp_y * 5

        pygame.draw.line(
            surface,
            (24, 24, 28),
            (int(barrel_start_x), int(barrel_start_y)),
            (int(barrel_end_x), int(barrel_end_y)),
            6,
        )
        pygame.draw.line(
            surface,
            w.color,
            (int(barrel_start_x), int(barrel_start_y)),
            (int(barrel_end_x), int(barrel_end_y)),
            3,
        )

        # Hands holding weapon
        hand_x = int(sx + cos_a * (r * 0.72) + perp_x * 5)
        hand_y = int(sy + sin_a * (r * 0.72) + perp_y * 5)
        pygame.draw.circle(surface, config.COLOR_SKIN, (hand_x, hand_y), 4)

        # Head / Helmet
        head_r = max(6, int(r * 0.56))
        if self.helmet_level > 0:
            helm_col = {1: (108, 132, 108), 2: (78, 122, 178), 3: (54, 58, 66)}[self.helmet_level]
            pygame.draw.circle(surface, helm_col, (sx, sy), head_r)
            if self.helmet_level == 3:
                # Spetsnaz visor stripe
                vx = int(sx + cos_a * 4)
                vy = int(sy + sin_a * 4)
                pygame.draw.circle(surface, (210, 175, 65), (vx, vy), 3)
            pygame.draw.circle(surface, (20, 24, 28), (sx, sy), head_r, 1)
        else:
            pygame.draw.circle(surface, config.COLOR_SKIN, (sx, sy), head_r)
            pygame.draw.circle(surface, (80, 62, 48), (sx, sy), head_r, 1)

        # Muzzle flash bloom
        if self.muzzle_flash_timer > 0.0:
            pygame.draw.circle(surface, (255, 235, 130), (int(barrel_end_x), int(barrel_end_y)), 7)
            pygame.draw.circle(surface, (255, 255, 230), (int(barrel_end_x), int(barrel_end_y)), 3)

        # Compact overhead HP bar for damaged bots
        if not self.is_player and self.hp < self.max_hp:
            bar_w = 32
            bar_h = 4
            bx = sx - bar_w // 2
            by = sy - r - 12
            pygame.draw.rect(surface, (25, 25, 25), (bx - 1, by - 1, bar_w + 2, bar_h + 2))
            fill_w = int(bar_w * max(0.0, self.hp / self.max_hp))
            pygame.draw.rect(surface, (230, 72, 62), (bx, by, fill_w, bar_h))


class Player(Combatant):
    """Human-controlled Battle Royale survivor."""

    def __init__(self, x: float, y: float) -> None:
        super().__init__(
            name="YOU",
            x=x,
            y=y,
            is_player=True,
            base_speed=config.PLAYER_SPEED,
            radius=config.PLAYER_RADIUS,
        )

    def handle_movement(self, keys, mouse_pos: Tuple[int, int], cam_x: float, cam_y: float) -> None:
        dx = 0.0
        dy = 0.0
        if keys[pygame.K_w]:
            dy -= 1.0
        if keys[pygame.K_s]:
            dy += 1.0
        if keys[pygame.K_a]:
            dx -= 1.0
        if keys[pygame.K_d]:
            dx += 1.0

        mag = math.hypot(dx, dy)
        if mag > 0.0:
            spd = self.current_speed
            self.vx = (dx / mag) * spd
            self.vy = (dy / mag) * spd
        else:
            self.vx = 0.0
            self.vy = 0.0

        world_mx = mouse_pos[0] + cam_x
        world_my = mouse_pos[1] + cam_y
        self.angle = math.atan2(world_my - self.y, world_mx - self.x)


class Bot(Combatant):
    """Autonomous AI survivor with a multi-state tactical state machine."""

    def __init__(self, name: str, x: float, y: float, rng: random.Random) -> None:
        super().__init__(
            name=name,
            x=x,
            y=y,
            is_player=False,
            base_speed=config.BOT_BASE_SPEED * rng.uniform(0.92, 1.06),
            radius=config.BOT_RADIUS,
        )
        self.rng = rng
        self.state = "LOOT"  # "LOOT", "ZONE_MOVE", "COMBAT", "HEAL", "ROAM"
        self.ai_timer = rng.uniform(0.1, 0.5)
        self.strafe_dir = rng.choice([-1, 1])
        self.strafe_timer = rng.uniform(0.6, 1.4)
        self.waypoint: Tuple[float, float] = (x, y)
        self.target: Optional[Combatant] = None
        self.aim_error = rng.uniform(0.06, 0.16)  # Radians of human-like aim inaccuracy
        self.burst_pause = 0.0
        self.stuck_timer = 0.0
        self.last_pos = (x, y)
        # Give bots 1 starter bandage & small reserve
        self.bandages = 2
        self.first_aids = 1 if rng.random() < 0.35 else 0

    def update_ai(
        self,
        dt: float,
        world,
        zone,
        loot_manager,
        combatants: List[Combatant],
        bullets: List[Bullet],
        particles: List[Particle],
        sound,
        listener_pos: Tuple[float, float],
    ) -> None:
        """Run AI state machine: zone safety, healing, combat, looting, and roaming."""
        if not self.alive:
            return

        self.ai_timer -= dt
        self.strafe_timer -= dt
        if self.burst_pause > 0.0:
            self.burst_pause -= dt

        # Detect getting stuck on walls and pick a fresh waypoint
        moved = math.hypot(self.x - self.last_pos[0], self.y - self.last_pos[1])
        if moved < 2.0 and self.healing_kind is None:
            self.stuck_timer += dt
            if self.stuck_timer > 0.9:
                self.stuck_timer = 0.0
                ang = self.rng.uniform(0.0, math.tau)
                self.waypoint = (
                    max(120.0, min(world.width - 120.0, self.x + math.cos(ang) * 180.0)),
                    max(120.0, min(world.height - 120.0, self.y + math.sin(ang) * 180.0)),
                )
        else:
            self.stuck_timer = 0.0
        self.last_pos = (self.x, self.y)

        # Periodic target scanning & state re-evaluation
        if self.ai_timer <= 0.0:
            self.ai_timer = self.rng.uniform(0.22, 0.42)
            self._evaluate_state(world, zone, loot_manager, combatants)

        # Execute current state
        if self.state == "HEAL":
            self._act_heal(zone)
        elif self.state == "ZONE_MOVE":
            self._act_zone_move(zone)
        elif self.state == "COMBAT":
            self._act_combat(dt, world, bullets, particles, sound, listener_pos)
        elif self.state == "LOOT":
            self._act_loot(loot_manager)
        else:
            self._act_roam(world, zone)

        # Always opportunistically pick up useful items right under feet
        self._auto_pickup_nearby(loot_manager)

    def _evaluate_state(self, world, zone, loot_manager, combatants: List[Combatant]) -> None:
        # 1. Check enemy visibility (both player and other bots)
        best_enemy: Optional[Combatant] = None
        best_dist = config.BOT_VISION_RANGE
        for other in combatants:
            if other is self or not other.alive:
                continue
            d = math.hypot(other.x - self.x, other.y - self.y)
            if d < best_dist and world.has_line_of_sight(self.x, self.y, other.x, other.y):
                best_dist = d
                best_enemy = other

        self.target = best_enemy

        # 2. Urgent Blue Zone escape
        outside_blue = zone.is_outside_blue(self.x, self.y)
        outside_safe = not zone.is_inside_safe(self.x, self.y)
        if outside_blue or (outside_safe and zone.is_shrinking and self.rng.random() < 0.75):
            if best_enemy is not None and best_dist < 220.0:
                self.state = "COMBAT"
            else:
                self.state = "ZONE_MOVE"
                self.waypoint = zone.random_point_in_safe_zone(0.65)
            return

        # 3. Heal when low on HP and not in immediate point-blank fight
        if self.hp < 52.0 and (self.first_aids > 0 or self.bandages > 0):
            if best_enemy is None or best_dist > 260.0:
                self.state = "HEAL"
                return

        # 4. Combat if enemy in sight and has usable ammo
        if best_enemy is not None:
            self._select_best_weapon()
            w = self.active_weapon
            if w.ammo_in_mag > 0 or self.ammo_reserve.get(w.ammo_type, 0) > 0:
                self.state = "COMBAT"
                return

        # 5. Loot if under-equipped
        needs_loot = (
            self.active_weapon.name == "P92"
            or self.vest_level < 2
            or self.first_aids == 0
            or self.ammo_reserve.get(self.active_weapon.ammo_type, 0) < 25
        )
        if needs_loot:
            target_loot = self._find_useful_loot(loot_manager, zone)
            if target_loot is not None:
                self.waypoint = target_loot
                self.state = "LOOT"
                return

        # 6. Roam toward safe zone interior or nearby compounds
        if self.state != "ROAM" or math.hypot(self.waypoint[0] - self.x, self.waypoint[1] - self.y) < 48.0:
            self.waypoint = zone.random_point_in_safe_zone(0.85)
        self.state = "ROAM"

    def _select_best_weapon(self) -> None:
        best_slot = self.active_slot
        best_score = -1.0
        for idx, w in enumerate(self.weapons):
            if w is None:
                continue
            has_ammo = w.ammo_in_mag > 0 or self.ammo_reserve.get(w.ammo_type, 0) > 0
            score = weapon_power_score(w.name) + (2.0 if has_ammo else -5.0)
            if score > best_score:
                best_score = score
                best_slot = idx
        if best_slot != self.active_slot:
            self.switch_slot(best_slot)

    def _find_useful_loot(self, loot_manager, zone) -> Optional[Tuple[float, float]]:
        best_pos: Optional[Tuple[float, float]] = None
        best_dist = config.BOT_LOOT_SEARCH_RANGE

        # Check landed air drops first
        for drop in loot_manager.supply_drops:
            if drop.landed and not drop.is_empty and not zone.is_outside_blue(drop.x, drop.y):
                d = math.hypot(drop.x - self.x, drop.y - self.y)
                if d < best_dist * 1.4:
                    return (drop.x, drop.y)

        cur_score = weapon_power_score(self.active_weapon.name)
        for item in loot_manager.ground_items:
            if zone.is_outside_blue(item.x, item.y):
                continue
            d = math.hypot(item.x - self.x, item.y - self.y)
            if d >= best_dist:
                continue
            useful = False
            if item.kind == "weapon" and weapon_power_score(item.name) > cur_score:
                useful = True
            elif item.kind == "vest" and item.level > self.vest_level:
                useful = True
            elif item.kind == "helmet" and item.level > self.helmet_level:
                useful = True
            elif item.kind == "first_aid" and self.first_aids < 2:
                useful = True
            elif item.kind == "ammo" and item.name == self.active_weapon.ammo_type:
                if self.ammo_reserve.get(item.name, 0) < 60:
                    useful = True
            if useful:
                best_dist = d
                best_pos = (item.x, item.y)
        return best_pos

    def _move_toward(self, tx: float, ty: float, speed_mult: float = 1.0) -> None:
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 8.0:
            self.vx = 0.0
            self.vy = 0.0
            return
        spd = self.current_speed * speed_mult
        self.vx = (dx / dist) * spd
        self.vy = (dy / dist) * spd
        self.angle = math.atan2(dy, dx)

    def _act_heal(self, zone) -> None:
        if self.healing_kind is None:
            if self.first_aids > 0 and self.hp < config.FIRST_AID_MAX_HP:
                self.start_heal("first_aid")
            elif self.bandages > 0 and self.hp < config.BANDAGE_MAX_HP:
                self.start_heal("bandage")
            else:
                self.state = "ROAM"
                return
        # Slowly drift toward safe center while healing
        self._move_toward(zone.target_x, zone.target_y, speed_mult=0.6)

    def _act_zone_move(self, zone) -> None:
        self._move_toward(zone.target_x, zone.target_y, speed_mult=1.0)

    def _act_loot(self, loot_manager) -> None:
        self._move_toward(self.waypoint[0], self.waypoint[1], speed_mult=0.95)

    def _act_roam(self, world, zone) -> None:
        self._move_toward(self.waypoint[0], self.waypoint[1], speed_mult=0.82)
        if self.energy_drinks > 0 and self.boost < 40.0 and self.healing_kind is None:
            self.start_heal("energy_drink")

    def _act_combat(
        self,
        dt: float,
        world,
        bullets: List[Bullet],
        particles: List[Particle],
        sound,
        listener_pos: Tuple[float, float],
    ) -> None:
        if self.target is None or not self.target.alive:
            self.state = "ROAM"
            return

        dx = self.target.x - self.x
        dy = self.target.y - self.y
        dist = math.hypot(dx, dy)
        aim_angle = math.atan2(dy, dx)
        self.angle = aim_angle + self.rng.uniform(-self.aim_error, self.aim_error)

        # Strafe / maintain ideal engagement range
        if self.strafe_timer <= 0.0:
            self.strafe_dir = -self.strafe_dir
            self.strafe_timer = self.rng.uniform(0.55, 1.35)

        w = self.active_weapon
        ideal_dist = 140.0 if w.name == "S12K" else (360.0 if w.name == "AWM" else 240.0)
        rad_dir = 0.0
        if dist > ideal_dist + 45.0:
            rad_dir = 0.65
        elif dist < ideal_dist - 55.0:
            rad_dir = -0.65

        strafe_x = -math.sin(aim_angle) * self.strafe_dir
        strafe_y = math.cos(aim_angle) * self.strafe_dir
        move_x = math.cos(aim_angle) * rad_dir + strafe_x * 0.85
        move_y = math.sin(aim_angle) * rad_dir + strafe_y * 0.85
        mag = math.hypot(move_x, move_y)
        if mag > 0.01:
            spd = self.current_speed * 0.88
            self.vx = (move_x / mag) * spd
            self.vy = (move_y / mag) * spd
        else:
            self.vx = 0.0
            self.vy = 0.0

        # Fire in realistic bursts if target is within weapon range and visible
        if dist <= w.range * 0.92 and self.burst_pause <= 0.0:
            if world.has_line_of_sight(self.x, self.y, self.target.x, self.target.y):
                fired = self.try_fire(bullets, particles, self.rng, sound, listener_pos)
                if fired and self.rng.random() < 0.22:
                    self.burst_pause = self.rng.uniform(0.18, 0.45)

    def _auto_pickup_nearby(self, loot_manager) -> None:
        # Ground items
        cur_score = weapon_power_score(self.active_weapon.name)
        for item in list(loot_manager.ground_items):
            if math.hypot(item.x - self.x, item.y - self.y) <= config.LOOT_PICKUP_RADIUS:
                should_take = False
                if item.kind == "weapon" and (
                    self.weapons[1] is None or weapon_power_score(item.name) > cur_score
                ):
                    should_take = True
                elif item.kind == "vest" and item.level > self.vest_level:
                    should_take = True
                elif item.kind == "helmet" and item.level > self.helmet_level:
                    should_take = True
                elif item.kind in ("ammo", "first_aid", "bandage", "energy_drink"):
                    should_take = True

                if should_take:
                    consumed, _ = self.pickup_item(item, loot_manager)
                    if consumed and item in loot_manager.ground_items:
                        loot_manager.ground_items.remove(item)
                    self._select_best_weapon()

        # Supply drops & death crates
        for container in list(loot_manager.supply_drops) + list(loot_manager.death_crates):
            if hasattr(container, "landed") and not container.landed:
                continue
            if container.is_empty:
                continue
            if math.hypot(container.x - self.x, container.y - self.y) <= config.CRATE_INTERACT_RADIUS:
                for item in list(container.items):
                    if item.kind == "weapon" and weapon_power_score(item.name) <= cur_score and self.weapons[1] is not None:
                        continue
                    consumed, _ = self.pickup_item(item, loot_manager)
                    if consumed:
                        container.items.remove(item)
                self._select_best_weapon()
