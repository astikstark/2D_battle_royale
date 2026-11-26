"""Main game loop, state management, smooth camera, and combat resolution."""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

import config
from src.entities import Bot, Bullet, Combatant, Particle, Player
from src.hud import HUD, KillFeedEntry
from src.loot import DeathCrate, LootItem, LootManager, SupplyDrop
from src.sound import SoundManager
from src.world import World
from src.zone import BlueZone


class Game:
    """Orchestrates states, world simulation, collisions, camera, and rendering."""

    def __init__(self) -> None:
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.sound = SoundManager(enabled=True)
        self.hud = HUD()
        self.state = "MENU"  # "MENU", "CONTROLS", "PLAYING", "PAUSED", "GAME_OVER"

        # Match state containers (initialized cleanly in reset_match)
        self.rng = random.Random()
        self.world: Optional[World] = None
        self.zone: Optional[BlueZone] = None
        self.loot_manager: Optional[LootManager] = None
        self.player: Optional[Player] = None
        self.bots: List[Bot] = []
        self.bullets: List[Bullet] = []
        self.particles: List[Particle] = []
        self.kill_feed: List[KillFeedEntry] = []

        self.cam_x = 0.0
        self.cam_y = 0.0
        self.shake_timer = 0.0
        self.shake_intensity = 0.0

        self.hit_marker_timer = 0.0
        self.hit_marker_kill = False
        self.toast_text: Optional[str] = None
        self.toast_timer = 0.0
        self.loot_prompt: Optional[str] = None
        self.map_enlarged = False

        self.airdrop_timer = config.AIRDROP_FIRST_DELAY
        self.elapsed_time = 0.0
        self.total_combatants = config.BOT_COUNT + 1
        self.player_rank = 1
        self.eliminated_by = ""
        self._mouse_was_down = False

    # ------------------------------------------------------------------
    # Match Lifecycle (Clean Reset With Zero Stale State)
    # ------------------------------------------------------------------
    def reset_match(self, seed: Optional[int] = None) -> None:
        """Initialize a brand-new match with fresh world, bots, loot, and zone."""
        self.rng = random.Random(seed)
        self.world = World(self.rng)
        self.zone = BlueZone(self.world.width, self.world.height, self.rng)
        self.loot_manager = LootManager(self.rng)
        self.loot_manager.populate_world(self.world)
        self.hud.invalidate_map_cache()

        # Spawn player in an open spot near mid-map
        px, py = self.world.find_open_spawn(min_margin=520.0, clearance=32.0)
        self.player = Player(px, py)

        # Spawn 25-30 AI bots well separated from player and each other
        self.bots = []
        names = list(config.BOT_NAMES)
        self.rng.shuffle(names)
        for i in range(config.BOT_COUNT):
            bx, by = self.world.find_open_spawn(min_margin=180.0, clearance=30.0)
            for _ in range(18):
                if math.hypot(bx - px, by - py) >= 340.0:
                    break
                bx, by = self.world.find_open_spawn(min_margin=180.0, clearance=30.0)
            bname = names[i % len(names)]
            if i >= len(names):
                bname = f"{bname}_{i}"
            self.bots.append(Bot(bname, bx, by, self.rng))

        self.bullets = []
        self.particles = []
        self.kill_feed = []

        self.cam_x = self.player.x - config.SCREEN_WIDTH * 0.5
        self.cam_y = self.player.y - config.SCREEN_HEIGHT * 0.5
        self.shake_timer = 0.0
        self.shake_intensity = 0.0

        self.hit_marker_timer = 0.0
        self.hit_marker_kill = False
        self.toast_text = "Loot compounds, stay in the Safe Zone, be the last one standing!"
        self.toast_timer = 4.2
        self.loot_prompt = None
        self.map_enlarged = False

        self.airdrop_timer = config.AIRDROP_FIRST_DELAY
        self.elapsed_time = 0.0
        self.total_combatants = len(self.bots) + 1
        self.player_rank = self.total_combatants
        self.eliminated_by = ""
        self._mouse_was_down = False

        self.state = "PLAYING"
        pygame.mouse.set_visible(False)

    def _show_toast(self, message: str, duration: float = 2.4) -> None:
        self.toast_text = message
        self.toast_timer = duration

    def _alive_combatants(self) -> List[Combatant]:
        res: List[Combatant] = []
        if self.player is not None and self.player.alive:
            res.append(self.player)
        for b in self.bots:
            if b.alive:
                res.append(b)
        return res

    # ------------------------------------------------------------------
    # Main Loop & Event Handling
    # ------------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            raw_dt = self.clock.tick(config.FPS) / 1000.0
            dt = min(config.MAX_DT, max(0.0, raw_dt))
            self._handle_events()
            if self.state == "PLAYING":
                self.update(dt)
            self.render()

    def _handle_events(self) -> None:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_left_click(mouse_pos)
            elif event.type == pygame.MOUSEWHEEL and self.state == "PLAYING" and self.player:
                self.player.switch_slot(1 - self.player.active_slot)

    def _handle_keydown(self, key: int) -> None:
        if self.state == "MENU":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.reset_match()
            elif key == pygame.K_ESCAPE:
                self.running = False
            return

        if self.state == "CONTROLS":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "MENU"
            return

        if self.state == "PAUSED":
            if key == pygame.K_ESCAPE:
                self.state = "PLAYING"
                pygame.mouse.set_visible(False)
            return

        if self.state == "GAME_OVER":
            if key == pygame.K_RETURN:
                self.reset_match()
            elif key == pygame.K_ESCAPE:
                self.state = "MENU"
                pygame.mouse.set_visible(True)
            return

        # PLAYING state controls
        if key == pygame.K_ESCAPE:
            if self.map_enlarged:
                self.map_enlarged = False
            else:
                self.state = "PAUSED"
                pygame.mouse.set_visible(True)
        elif key == pygame.K_m:
            self.map_enlarged = not self.map_enlarged
        elif key == pygame.K_1 and self.player:
            self.player.switch_slot(0)
        elif key == pygame.K_2 and self.player:
            self.player.switch_slot(1)
        elif key == pygame.K_r and self.player:
            if not self.player.start_reload(self.sound):
                w = self.player.active_weapon
                if w.needs_reload() and self.player.ammo_reserve.get(w.ammo_type, 0) <= 0:
                    self._show_toast(f"No {w.ammo_type} Reserve Ammo", 1.5)
                    self.sound.play("empty", 0.8)
        elif key == pygame.K_f and self.player:
            self._handle_player_loot()
        elif key == pygame.K_4 and self.player:
            ok, msg = self.player.start_heal("first_aid")
            if not ok and msg:
                self._show_toast(msg, 1.5)
        elif key == pygame.K_5 and self.player:
            ok, msg = self.player.start_heal("energy_drink")
            if not ok and msg:
                self._show_toast(msg, 1.5)
        elif key == pygame.K_6 and self.player:
            ok, msg = self.player.start_heal("bandage")
            if not ok and msg:
                self._show_toast(msg, 1.5)
        elif key == pygame.K_n:
            muted = self.sound.toggle_mute()
            self._show_toast("Audio Muted" if muted else "Audio Unmuted", 1.4)

    def _handle_left_click(self, mouse_pos: Tuple[int, int]) -> None:
        if self.state == "MENU":
            if self.hud.menu_buttons.get("play") and self.hud.menu_buttons["play"].collidepoint(mouse_pos):
                self.reset_match()
            elif self.hud.menu_buttons.get("controls") and self.hud.menu_buttons["controls"].collidepoint(mouse_pos):
                self.state = "CONTROLS"
            elif self.hud.menu_buttons.get("quit") and self.hud.menu_buttons["quit"].collidepoint(mouse_pos):
                self.running = False
        elif self.state == "CONTROLS":
            if self.hud.controls_back_btn and self.hud.controls_back_btn.collidepoint(mouse_pos):
                self.state = "MENU"
        elif self.state == "PAUSED":
            if self.hud.pause_buttons.get("resume") and self.hud.pause_buttons["resume"].collidepoint(mouse_pos):
                self.state = "PLAYING"
                pygame.mouse.set_visible(False)
            elif self.hud.pause_buttons.get("restart") and self.hud.pause_buttons["restart"].collidepoint(mouse_pos):
                self.reset_match()
            elif self.hud.pause_buttons.get("menu") and self.hud.pause_buttons["menu"].collidepoint(mouse_pos):
                self.state = "MENU"
                pygame.mouse.set_visible(True)
            elif self.hud.pause_buttons.get("quit") and self.hud.pause_buttons["quit"].collidepoint(mouse_pos):
                self.running = False
        elif self.state == "GAME_OVER":
            if self.hud.end_buttons.get("play_again") and self.hud.end_buttons["play_again"].collidepoint(mouse_pos):
                self.reset_match()
            elif self.hud.end_buttons.get("menu") and self.hud.end_buttons["menu"].collidepoint(mouse_pos):
                self.state = "MENU"
                pygame.mouse.set_visible(True)

    # ------------------------------------------------------------------
    # Looting Interaction (F key)
    # ------------------------------------------------------------------
    def _handle_player_loot(self) -> None:
        assert self.player is not None and self.loot_manager is not None
        kind, obj, _ = self.loot_manager.find_nearest_interactable(self.player.x, self.player.y)
        if kind is None or obj is None:
            return

        if kind == "ground_item":
            assert isinstance(obj, LootItem)
            consumed, msg = self.player.pickup_item(obj, self.loot_manager)
            if consumed and obj in self.loot_manager.ground_items:
                self.loot_manager.ground_items.remove(obj)
            if msg:
                self._show_toast(msg, 1.6)
            if consumed or msg.startswith("+"):
                self.sound.play("pickup", 0.85)
        elif kind in ("death_crate", "supply_drop"):
            assert isinstance(obj, (DeathCrate, SupplyDrop))
            picked_labels: List[str] = []
            for item in list(obj.items):
                # Do not automatically overwrite a high-tier weapon with a lower-tier crate weapon
                # unless the player has an empty slot or is holding P92; Supply Drop AWM always equips!
                if item.kind == "weapon" and kind == "death_crate":
                    if self.player.weapons[1] is not None and self.player.active_weapon.name != "P92":
                        continue
                consumed, msg = self.player.pickup_item(item, self.loot_manager)
                if consumed:
                    obj.items.remove(item)
                if msg and (consumed or msg.startswith("+")):
                    picked_labels.append(msg)
            if picked_labels:
                self.sound.play("pickup", 0.95)
                summary = ", ".join(picked_labels[:3])
                if len(picked_labels) > 3:
                    summary += f" (+{len(picked_labels) - 3} more)"
                self._show_toast(f"Looted: {summary}", 2.2)
            else:
                self._show_toast("Nothing needed in crate (inventory full)", 1.6)

    # ------------------------------------------------------------------
    # Simulation Step
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        assert self.player is not None and self.world is not None
        assert self.zone is not None and self.loot_manager is not None

        self.elapsed_time += dt
        if self.hit_marker_timer > 0.0:
            self.hit_marker_timer = max(0.0, self.hit_marker_timer - dt)
        if self.toast_timer > 0.0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
            if self.toast_timer <= 0.0:
                self.toast_text = None
        if self.shake_timer > 0.0:
            self.shake_timer = max(0.0, self.shake_timer - dt)

        # Update kill feed expiry
        for entry in list(self.kill_feed):
            entry.timer -= dt
            if entry.timer <= 0.0:
                self.kill_feed.remove(entry)

        # 1. Zone update
        self.zone.update(dt)

        # 2. Periodic Supply Air Drop
        self.airdrop_timer -= dt
        if self.airdrop_timer <= 0.0:
            self.airdrop_timer = config.AIRDROP_INTERVAL
            ax, ay = self.zone.random_point_in_safe_zone(0.70)
            ax, ay = self.world.resolve_circle_collision(ax, ay, 24.0)
            self.loot_manager.spawn_supply_drop(ax, ay)
            self.sound.play("airdrop", 0.85)
            self._show_toast("SUPPLY AIR DROP INCOMING! Check Minimap", 3.2)

        # 3. Player input & firing
        keys = pygame.key.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        mouse_down = pygame.mouse.get_pressed()[0]

        if self.player.alive:
            self.player.handle_movement(keys, mouse_pos, self.cam_x, self.cam_y)
            if not self.map_enlarged:
                w = self.player.active_weapon
                wants_shot = mouse_down if w.auto else (mouse_down and not self._mouse_was_down)
                if wants_shot:
                    fired = self.player.try_fire(self.bullets, self.particles, self.rng, self.sound)
                    if fired:
                        self.shake_timer = 0.07
                        self.shake_intensity = min(6.0, w.recoil * 0.75)
            self.player.update_common(dt, self.world, self.sound)
        self._mouse_was_down = mouse_down

        # 4. Update AI Bots
        alive_list = self._alive_combatants()
        listener = (self.player.x, self.player.y)
        for bot in self.bots:
            if not bot.alive:
                continue
            bot.update_ai(
                dt,
                self.world,
                self.zone,
                self.loot_manager,
                alive_list,
                self.bullets,
                self.particles,
                self.sound,
                listener,
            )
            bot.update_common(dt, self.world, self.sound)

        # 5. Blue Zone damage tick
        self._apply_zone_damage(dt)

        # 6. Update Bullets & Resolve Hits
        self._update_bullets(dt)

        # 7. Update Loot (falling air drops, smoke plume) & Particles
        self.loot_manager.update(dt, self.particles)
        self.particles = [p for p in self.particles if p.update(dt)]

        # 8. Update interactive loot prompt
        if self.player.alive:
            kind, obj, _ = self.loot_manager.find_nearest_interactable(self.player.x, self.player.y)
            if kind == "ground_item" and isinstance(obj, LootItem):
                self.loot_prompt = f"[F] Pick up {obj.label}"
            elif kind == "death_crate" and isinstance(obj, DeathCrate):
                self.loot_prompt = f"[F] Loot {obj.owner_name}'s Crate ({len(obj.items)} items)"
            elif kind == "supply_drop" and isinstance(obj, SupplyDrop):
                self.loot_prompt = f"[F] Loot Supply Air Drop ({len(obj.items)} items)"
            else:
                self.loot_prompt = None
        else:
            self.loot_prompt = None

        # 9. Smooth camera follow + screen shake
        target_cx = self.player.x - config.SCREEN_WIDTH * 0.5
        target_cy = self.player.y - config.SCREEN_HEIGHT * 0.5
        lerp = min(1.0, 9.5 * dt)
        self.cam_x += (target_cx - self.cam_x) * lerp
        self.cam_y += (target_cy - self.cam_y) * lerp
        self.cam_x = max(0.0, min(self.world.width - config.SCREEN_WIDTH, self.cam_x))
        self.cam_y = max(0.0, min(self.world.height - config.SCREEN_HEIGHT, self.cam_y))

        # 10. Check Win / Elimination Conditions
        self._check_match_end()

    def _apply_zone_damage(self, dt: float) -> None:
        assert self.zone is not None
        for entity in self._alive_combatants():
            if self.zone.is_outside_blue(entity.x, entity.y):
                dmg = self.zone.dps * dt
                entity.take_damage(dmg, is_zone=True)
                entity.zone_tick_accum += dt
                if entity.is_player and entity.zone_tick_accum >= 1.0:
                    entity.zone_tick_accum = 0.0
                    self.sound.play("zone_tick", 0.65)
                if not entity.alive:
                    self._on_entity_eliminated(entity, killer=None, weapon_name="Blue Zone")

    def _update_bullets(self, dt: float) -> None:
        assert self.world is not None
        alive_combatants = self._alive_combatants()
        remaining: List[Bullet] = []

        for b in self.bullets:
            b.update(dt)
            if not b.alive:
                continue

            # World wall / rock / tree trunk collision
            wall_hit = self.world.segment_hits_world(b.prev_x, b.prev_y, b.x, b.y)
            if wall_hit is not None:
                self._spawn_impact_particles(wall_hit[0], wall_hit[1], is_blood=False)
                continue

            # Combatant hit check (supports Player->Bot, Bot->Player, Bot->Bot)
            hit_target: Optional[Combatant] = None
            for target in alive_combatants:
                if target is b.owner or not target.alive:
                    continue
                if self._segment_hits_circle(b.prev_x, b.prev_y, b.x, b.y, target.x, target.y, target.radius + 2.0):
                    hit_target = target
                    break

            if hit_target is not None:
                is_headshot = self.rng.random() < 0.22
                raw_dmg = b.damage * (1.45 if is_headshot else 1.0)
                dealt = hit_target.take_damage(
                    raw_dmg,
                    is_zone=False,
                    knock_angle=b.angle,
                    knock_force=b.knockback,
                    is_headshot=is_headshot,
                )
                b.owner.damage_dealt += dealt
                self._spawn_impact_particles(b.x, b.y, is_blood=True)

                if b.owner.is_player:
                    self.hit_marker_timer = 0.16
                    self.hit_marker_kill = not hit_target.alive
                    self.sound.play("kill" if not hit_target.alive else "hit", 0.85)

                if not hit_target.alive:
                    self._on_entity_eliminated(hit_target, killer=b.owner, weapon_name=b.weapon_name)
                continue

            remaining.append(b)

        self.bullets = remaining

    def _on_entity_eliminated(
        self,
        victim: Combatant,
        killer: Optional[Combatant],
        weapon_name: str,
    ) -> None:
        assert self.loot_manager is not None
        # Drop victim's gear as a DeathCrate
        self.loot_manager.spawn_death_crate(victim)

        if killer is not None and killer is not victim:
            killer.kills += 1
            killer_name = killer.name
        else:
            killer_name = "Blue Zone"

        self.kill_feed.append(
            KillFeedEntry(
                killer=killer_name,
                victim=victim.name,
                weapon=weapon_name,
                involves_player=(victim.is_player or (killer is not None and killer.is_player)),
            )
        )

        if victim.is_player:
            # Alive count right after player dies + 1 is player's placement rank
            survivors_left = sum(1 for b in self.bots if b.alive)
            self.player_rank = survivors_left + 1
            self.eliminated_by = f"{killer_name} ({weapon_name})" if killer is not None else "Blue Zone"

    def _check_match_end(self) -> None:
        assert self.player is not None
        if not self.player.alive:
            self.state = "GAME_OVER"
            pygame.mouse.set_visible(True)
            self.sound.play("defeat", 0.9)
            return

        bots_alive = sum(1 for b in self.bots if b.alive)
        if bots_alive == 0:
            self.player_rank = 1
            self.state = "GAME_OVER"
            pygame.mouse.set_visible(True)
            self.sound.play("victory", 0.95)

    def _spawn_impact_particles(self, x: float, y: float, is_blood: bool) -> None:
        count = 6 if is_blood else 4
        for _ in range(count):
            ang = self.rng.uniform(0.0, math.tau)
            spd = self.rng.uniform(45.0, 155.0)
            color = (
                self.rng.choice([(200, 32, 32), (165, 22, 22), (235, 60, 50)])
                if is_blood
                else self.rng.choice([(255, 225, 130), (210, 200, 180)])
            )
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(ang) * spd,
                    vy=math.sin(ang) * spd,
                    radius=self.rng.uniform(2.0, 4.5),
                    color=color,
                    life=self.rng.uniform(0.14, 0.30),
                    max_life=0.30,
                )
            )

    @staticmethod
    def _segment_hits_circle(
        x1: float, y1: float, x2: float, y2: float, cx: float, cy: float, r: float
    ) -> bool:
        dx = x2 - x1
        dy = y2 - y1
        seg_sq = dx * dx + dy * dy
        if seg_sq < 1e-6:
            return (cx - x1) ** 2 + (cy - y1) ** 2 <= r * r
        t = ((cx - x1) * dx + (cy - y1) * dy) / seg_sq
        t = max(0.0, min(1.0, t))
        px = x1 + dx * t
        py = y1 + dy * t
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render(self) -> None:
        mouse_pos = pygame.mouse.get_pos()

        if self.state == "MENU":
            self.hud.draw_start_menu(self.screen, mouse_pos)
            pygame.display.flip()
            return

        if self.state == "CONTROLS":
            self.hud.draw_controls_screen(self.screen, mouse_pos)
            pygame.display.flip()
            return

        # Render live world for PLAYING, PAUSED, and GAME_OVER backgrounds
        assert self.world is not None and self.player is not None
        assert self.zone is not None and self.loot_manager is not None

        ox = 0.0
        oy = 0.0
        if self.shake_timer > 0.0 and self.state == "PLAYING":
            ox = self.rng.uniform(-self.shake_intensity, self.shake_intensity)
            oy = self.rng.uniform(-self.shake_intensity, self.shake_intensity)
        rcam_x = self.cam_x + ox
        rcam_y = self.cam_y + oy

        vw, vh = self.screen.get_size()

        # 1. Ground, roads, buildings, walls, rocks
        self.world.draw_ground_and_structures(self.screen, rcam_x, rcam_y, vw, vh)

        # 2. Loot, death crates, air drops
        self.loot_manager.draw(self.screen, rcam_x, rcam_y, vw, vh, self.hud.font_xs)

        # 3. Combatants (camera-culled)
        for bot in self.bots:
            if not bot.alive:
                continue
            if (
                -40 <= bot.x - rcam_x <= vw + 40
                and -40 <= bot.y - rcam_y <= vh + 40
            ):
                bot.draw(self.screen, rcam_x, rcam_y)

        if self.player.alive:
            self.player.draw(self.screen, rcam_x, rcam_y)

        # 4. Bullets & Particles
        for b in self.bullets:
            if -60 <= b.x - rcam_x <= vw + 60 and -60 <= b.y - rcam_y <= vh + 60:
                b.draw(self.screen, rcam_x, rcam_y)

        for p in self.particles:
            if -40 <= p.x - rcam_x <= vw + 40 and -40 <= p.y - rcam_y <= vh + 40:
                p.draw(self.screen, rcam_x, rcam_y)

        # 5. Tree canopies drawn above combatants for tactical cover depth
        self.world.draw_canopies(self.screen, rcam_x, rcam_y, vw, vh)

        # 6. Safe Zone (white) & Blue Zone (shrinking blue ring) overlays
        self._draw_world_zones(rcam_x, rcam_y)

        # 7. HUD / Pause / Game Over overlay
        alive_count = len(self._alive_combatants())
        self.hud.draw_in_game(
            surface=self.screen,
            player=self.player,
            world=self.world,
            zone=self.zone,
            loot_manager=self.loot_manager,
            alive_count=alive_count,
            total_count=self.total_combatants,
            kill_feed=self.kill_feed,
            hit_marker_timer=self.hit_marker_timer,
            hit_marker_kill=self.hit_marker_kill,
            loot_prompt=self.loot_prompt,
            toast_text=self.toast_text,
            map_enlarged=self.map_enlarged,
            mouse_pos=mouse_pos,
            muted=self.sound.muted,
        )

        if self.state == "PAUSED":
            self.hud.draw_pause_menu(self.screen, mouse_pos)
        elif self.state == "GAME_OVER":
            self.hud.draw_end_screen(
                surface=self.screen,
                mouse_pos=mouse_pos,
                rank=self.player_rank,
                total=self.total_combatants,
                kills=self.player.kills,
                damage_dealt=self.player.damage_dealt,
                survival_time=self.elapsed_time,
                eliminated_by=self.eliminated_by,
            )

        pygame.display.flip()

    def _draw_world_zones(self, cam_x: float, cam_y: float) -> None:
        assert self.zone is not None
        if self.zone.target_radius > 2.0:
            pygame.draw.circle(
                self.screen,
                config.COLOR_SAFE_ZONE,
                (int(self.zone.target_x - cam_x), int(self.zone.target_y - cam_y)),
                int(self.zone.target_radius),
                2,
            )

        if self.zone.current_radius > 2.0:
            pygame.draw.circle(
                self.screen,
                config.COLOR_BLUE_ZONE,
                (int(self.zone.current_x - cam_x), int(self.zone.current_y - cam_y)),
                int(self.zone.current_radius),
                5,
            )
