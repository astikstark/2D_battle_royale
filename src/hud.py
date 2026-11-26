"""HUD overlay, live minimap, enlarged tactical map, kill feed, and menus."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame

import config


@dataclass
class KillFeedEntry:
    """Single entry in the scrolling top-left kill feed."""

    killer: str
    victim: str
    weapon: str
    timer: float = 6.0
    involves_player: bool = False


class HUD:
    """Draws all in-game UI overlays, tactical maps, and menu screens."""

    def __init__(self) -> None:
        self.font_xs = pygame.font.SysFont("consolas,dejavusans,arial", 12)
        self.font_sm = pygame.font.SysFont("consolas,dejavusans,arial", 15, bold=True)
        self.font_md = pygame.font.SysFont("consolas,dejavusans,arial", 20, bold=True)
        self.font_lg = pygame.font.SysFont("consolas,dejavusans,arial", 34, bold=True)
        self.font_xl = pygame.font.SysFont("consolas,dejavusans,arial", 52, bold=True)

        # Cached button rects for mouse interaction in menus
        self.menu_buttons: Dict[str, pygame.Rect] = {}
        self.pause_buttons: Dict[str, pygame.Rect] = {}
        self.end_buttons: Dict[str, pygame.Rect] = {}
        self.controls_back_btn: Optional[pygame.Rect] = None

        # Pre-rendered minimap static terrain cache (regenerated per match)
        self._minimap_base: Optional[pygame.Surface] = None
        self._bigmap_base: Optional[pygame.Surface] = None
        self._cached_world_id: Optional[int] = None

    def invalidate_map_cache(self) -> None:
        self._minimap_base = None
        self._bigmap_base = None
        self._cached_world_id = None

    def _build_map_surface(self, world, size: int, draw_labels: bool = False) -> pygame.Surface:
        surf = pygame.Surface((size, size))
        surf.fill((66, 92, 52))
        scale_x = size / world.width
        scale_y = size / world.height

        for p in world.terrain_patches:
            r = pygame.Rect(
                int((p.x - p.rx) * scale_x),
                int((p.y - p.ry) * scale_y),
                max(2, int(p.rx * 2 * scale_x)),
                max(2, int(p.ry * 2 * scale_y)),
            )
            pygame.draw.ellipse(surf, p.color, r)

        for road in world.roads:
            r = pygame.Rect(
                int(road.x * scale_x),
                int(road.y * scale_y),
                max(2, int(road.w * scale_x)),
                max(2, int(road.h * scale_y)),
            )
            pygame.draw.rect(surf, config.COLOR_ROAD, r)

        for b in world.buildings:
            r = pygame.Rect(
                int(b.rect.x * scale_x),
                int(b.rect.y * scale_y),
                max(3, int(b.rect.w * scale_x)),
                max(3, int(b.rect.h * scale_y)),
            )
            pygame.draw.rect(surf, (195, 175, 130), r)

        if draw_labels:
            for cname, cx, cy in world.compound_labels:
                lbl = self.font_xs.render(cname, True, (245, 240, 215))
                lx = int(cx * scale_x) - lbl.get_width() // 2
                ly = int(cy * scale_y) - lbl.get_height() // 2
                bg = pygame.Rect(lx - 3, ly - 1, lbl.get_width() + 6, lbl.get_height() + 2)
                pygame.draw.rect(surf, (18, 22, 26), bg)
                surf.blit(lbl, (lx, ly))

        return surf

    def _ensure_map_cache(self, world) -> None:
        wid = id(world)
        if self._cached_world_id != wid or self._minimap_base is None:
            self._minimap_base = self._build_map_surface(world, 184, draw_labels=False)
            self._bigmap_base = self._build_map_surface(world, 560, draw_labels=True)
            self._cached_world_id = wid

    # ------------------------------------------------------------------
    # In-Game HUD
    # ------------------------------------------------------------------
    def draw_in_game(
        self,
        surface: pygame.Surface,
        player,
        world,
        zone,
        loot_manager,
        alive_count: int,
        total_count: int,
        kill_feed: List[KillFeedEntry],
        hit_marker_timer: float,
        hit_marker_kill: bool,
        loot_prompt: Optional[str],
        toast_text: Optional[str],
        map_enlarged: bool,
        mouse_pos: Tuple[int, int],
        muted: bool,
    ) -> None:
        w, h = surface.get_size()
        self._ensure_map_cache(world)

        # Blue Zone edge danger vignette when player is outside
        if player.alive and zone.is_outside_blue(player.x, player.y):
            vignette = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(vignette, (40, 120, 255, 65), (0, 0, w, h), 22)
            surface.blit(vignette, (0, 0))
            warn = self.font_sm.render("OUTSIDE PLAYZONE! MOVE TO SAFE ZONE", True, (130, 195, 255))
            surface.blit(warn, (w // 2 - warn.get_width() // 2, 68))

        # Top-left: Alive & Kills counters
        self._draw_top_counters(surface, alive_count, total_count, player.kills, muted)

        # Top-left below counters: Scrolling Kill Feed
        self._draw_kill_feed(surface, kill_feed)

        # Top-right: Minimap & Zone phase timer
        self._draw_minimap(surface, player, world, zone, loot_manager, w)

        # Bottom-center: Health, Boost, Armor, Progress bar
        self._draw_vitals_panel(surface, player, w, h)

        # Bottom-right: Weapon slots, Ammo, Med quick-slots
        self._draw_loadout_panel(surface, player, w, h)

        # Center-bottom: Loot interaction prompt & toast messages
        if loot_prompt:
            self._draw_banner(surface, loot_prompt, w // 2, h - 162, (24, 32, 42), config.COLOR_UI_ACCENT)
        if toast_text:
            self._draw_banner(surface, toast_text, w // 2, 108, (22, 28, 36), (235, 240, 248))

        # Tactical crosshair + hit marker
        if not map_enlarged:
            self._draw_crosshair(surface, mouse_pos, hit_marker_timer, hit_marker_kill, player.reloading)

        # Enlarged tactical map overlay (M key)
        if map_enlarged:
            self._draw_enlarged_map(surface, player, world, zone, loot_manager, w, h)

    def _draw_top_counters(
        self,
        surface: pygame.Surface,
        alive_count: int,
        total_count: int,
        kills: int,
        muted: bool,
    ) -> None:
        # Alive badge
        alive_rect = pygame.Rect(18, 16, 126, 38)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, alive_rect, border_radius=6)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, alive_rect, 2, border_radius=6)
        lbl = self.font_xs.render("ALIVE", True, config.COLOR_UI_MUTED)
        val = self.font_md.render(f"{alive_count}/{total_count}", True, config.COLOR_UI_TEXT)
        surface.blit(lbl, (alive_rect.x + 10, alive_rect.y + 11))
        surface.blit(val, (alive_rect.right - val.get_width() - 10, alive_rect.y + 8))

        # Kills badge
        kill_rect = pygame.Rect(154, 16, 108, 38)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, kill_rect, border_radius=6)
        pygame.draw.rect(surface, config.COLOR_UI_ACCENT, kill_rect, 2, border_radius=6)
        klbl = self.font_xs.render("KILLS", True, config.COLOR_UI_MUTED)
        kval = self.font_md.render(str(kills), True, config.COLOR_UI_ACCENT)
        surface.blit(klbl, (kill_rect.x + 10, kill_rect.y + 11))
        surface.blit(kval, (kill_rect.right - kval.get_width() - 14, kill_rect.y + 8))

        if muted:
            m_txt = self.font_xs.render("SFX MUTED", True, (235, 110, 100))
            surface.blit(m_txt, (274, 27))

    def _draw_kill_feed(self, surface: pygame.Surface, kill_feed: List[KillFeedEntry]) -> None:
        y = 66
        for entry in kill_feed[-5:]:
            text = f"{entry.killer}  [{entry.weapon}]  {entry.victim}"
            color = config.COLOR_UI_ACCENT if entry.involves_player else config.COLOR_UI_TEXT
            rendered = self.font_xs.render(text, True, color)
            bg = pygame.Rect(18, y, rendered.get_width() + 16, 22)
            panel = pygame.Surface((bg.w, bg.h), pygame.SRCALPHA)
            panel.fill((16, 20, 26, 185))
            surface.blit(panel, bg.topleft)
            pygame.draw.rect(surface, (60, 70, 84), bg, 1)
            surface.blit(rendered, (bg.x + 8, bg.y + 4))
            y += 26

    def _draw_minimap(
        self,
        surface: pygame.Surface,
        player,
        world,
        zone,
        loot_manager,
        screen_w: int,
    ) -> None:
        size = 184
        mx = screen_w - size - 18
        my = 16
        frame = pygame.Rect(mx - 3, my - 3, size + 6, size + 6)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, frame, border_radius=5)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, frame, 2, border_radius=5)

        map_surf = self._minimap_base.copy()
        self._overlay_map_markers(map_surf, player, world, zone, loot_manager, size)
        surface.blit(map_surf, (mx, my))

        # Zone phase & countdown bar below minimap
        bar = pygame.Rect(mx - 3, my + size + 8, size + 6, 30)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, bar, border_radius=5)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, bar, 1, border_radius=5)

        mins = int(max(0.0, zone.timer)) // 60
        secs = int(max(0.0, zone.timer)) % 60
        if zone.state == "SHRINK":
            status = f"PH.{zone.phase_number} SHRINKING {mins}:{secs:02d}"
            col = (115, 190, 255)
        elif zone.state == "CLOSED":
            status = f"FINAL ZONE ({zone.dps:.0f} DPS)"
            col = (245, 95, 85)
        else:
            status = f"PH.{zone.phase_number} SAFE {mins}:{secs:02d}"
            col = config.COLOR_UI_TEXT
        st_surf = self.font_xs.render(status, True, col)
        surface.blit(st_surf, (bar.centerx - st_surf.get_width() // 2, bar.y + 8))

    def _draw_enlarged_map(
        self,
        surface: pygame.Surface,
        player,
        world,
        zone,
        loot_manager,
        screen_w: int,
        screen_h: int,
    ) -> None:
        dim = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        dim.fill((8, 12, 16, 175))
        surface.blit(dim, (0, 0))

        size = 560
        mx = (screen_w - size) // 2
        my = (screen_h - size) // 2
        frame = pygame.Rect(mx - 6, my - 34, size + 12, size + 42)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, frame, border_radius=8)
        pygame.draw.rect(surface, config.COLOR_UI_ACCENT, frame, 2, border_radius=8)

        title = self.font_sm.render("TACTICAL MAP  (Press M to Close)", True, config.COLOR_UI_ACCENT)
        surface.blit(title, (frame.centerx - title.get_width() // 2, frame.y + 8))

        map_surf = self._bigmap_base.copy()
        self._overlay_map_markers(map_surf, player, world, zone, loot_manager, size)
        surface.blit(map_surf, (mx, my))

    def _overlay_map_markers(
        self,
        map_surf: pygame.Surface,
        player,
        world,
        zone,
        loot_manager,
        size: int,
    ) -> None:
        sx = size / world.width
        sy = size / world.height

        # Safe zone (white circle)
        if zone.target_radius > 1.0:
            pygame.draw.circle(
                map_surf,
                config.COLOR_SAFE_ZONE,
                (int(zone.target_x * sx), int(zone.target_y * sy)),
                max(2, int(zone.target_radius * sx)),
                2,
            )

        # Current blue zone (blue circle)
        if zone.current_radius > 1.0:
            pygame.draw.circle(
                map_surf,
                config.COLOR_BLUE_ZONE,
                (int(zone.current_x * sx), int(zone.current_y * sy)),
                max(2, int(zone.current_radius * sx)),
                2,
            )

        # Supply Air Drops (red diamond + beacon ring)
        for drop in loot_manager.supply_drops:
            if not drop.is_empty:
                dx = int(drop.x * sx)
                dy = int(drop.y * sy)
                pygame.draw.circle(map_surf, (255, 70, 70), (dx, dy), 6, 1)
                pygame.draw.rect(map_surf, (235, 50, 50), (dx - 3, dy - 3, 6, 6))

        # Player arrow
        px = int(player.x * sx)
        py = int(player.y * sy)
        tip = (px + int(math.cos(player.angle) * 7), py + int(math.sin(player.angle) * 7))
        left = (
            px + int(math.cos(player.angle + 2.4) * 5),
            py + int(math.sin(player.angle + 2.4) * 5),
        )
        right = (
            px + int(math.cos(player.angle - 2.4) * 5),
            py + int(math.sin(player.angle - 2.4) * 5),
        )
        pygame.draw.polygon(map_surf, (255, 230, 70), [tip, left, right])
        pygame.draw.polygon(map_surf, (20, 20, 20), [tip, left, right], 1)

    def _draw_vitals_panel(self, surface: pygame.Surface, player, screen_w: int, screen_h: int) -> None:
        panel_w = 340
        panel_h = 84
        px = (screen_w - panel_w) // 2
        py = screen_h - panel_h - 16

        # Action cast bar (Reload or Healing) above vitals
        if player.reloading and player.reload_duration > 0.0:
            prog = 1.0 - max(0.0, player.reload_timer / player.reload_duration)
            self._draw_cast_bar(surface, "RELOADING...", prog, screen_w // 2, py - 34, (242, 184, 48))
        elif player.healing_kind is not None and player.heal_duration > 0.0:
            prog = 1.0 - max(0.0, player.heal_timer / player.heal_duration)
            labels = {
                "first_aid": "USING FIRST AID KIT...",
                "bandage": "APPLYING BANDAGE...",
                "energy_drink": "DRINKING ENERGY DRINK...",
            }
            col = (90, 215, 130) if player.healing_kind != "energy_drink" else (245, 165, 55)
            self._draw_cast_bar(surface, labels.get(player.healing_kind, "HEALING..."), prog, screen_w // 2, py - 34, col)

        panel = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, panel, border_radius=8)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, panel, 2, border_radius=8)

        # Armor & Helmet icons on left side of panel
        self._draw_armor_badge(
            surface,
            px + 12,
            py + 12,
            "H",
            player.helmet_level,
            player.helmet_durability,
            config.HELMET_MAX_DURABILITY.get(player.helmet_level, 1.0),
        )
        self._draw_armor_badge(
            surface,
            px + 12,
            py + 46,
            "V",
            player.vest_level,
            player.vest_durability,
            config.VEST_MAX_DURABILITY.get(player.vest_level, 1.0),
        )

        # Boost bar
        bx = px + 66
        by = py + 16
        bw = panel_w - 82
        pygame.draw.rect(surface, (40, 44, 52), (bx, by, bw, 11), border_radius=3)
        if player.boost > 0.0:
            fill = int(bw * (player.boost / config.PLAYER_MAX_BOOST))
            pygame.draw.rect(surface, config.COLOR_BOOST, (bx, by, fill, 11), border_radius=3)
        # Boost segments
        for frac in (0.25, 0.60, 0.85):
            sx = bx + int(bw * frac)
            pygame.draw.line(surface, config.COLOR_UI_PANEL, (sx, by), (sx, by + 11), 2)

        # Health bar
        hy = py + 36
        hh = 24
        pygame.draw.rect(surface, (42, 46, 54), (bx, hy, bw, hh), border_radius=4)
        hp_ratio = max(0.0, min(1.0, player.hp / player.max_hp))
        if hp_ratio > 0.55:
            hp_col = config.COLOR_HP_HIGH
        elif hp_ratio > 0.25:
            hp_col = config.COLOR_HP_MID
        else:
            hp_col = config.COLOR_HP_LOW
        pygame.draw.rect(surface, hp_col, (bx, hy, int(bw * hp_ratio), hh), border_radius=4)

        hp_txt = self.font_sm.render(f"HP  {int(math.ceil(player.hp))}", True, (22, 26, 32) if hp_ratio > 0.35 else (245, 245, 245))
        surface.blit(hp_txt, (bx + 10, hy + 4))

        boost_txt = self.font_xs.render(f"BOOST {int(player.boost)}%", True, config.COLOR_UI_MUTED)
        surface.blit(boost_txt, (bx, py + 64))
        speed_txt = self.font_xs.render("SPEED +" if player.boost >= 60.0 else "", True, config.COLOR_BOOST)
        surface.blit(speed_txt, (bx + bw - speed_txt.get_width(), py + 64))

    def _draw_armor_badge(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        tag: str,
        level: int,
        dur: float,
        max_dur: float,
    ) -> None:
        rect = pygame.Rect(x, y, 42, 26)
        lvl_col = {0: (52, 58, 66), 1: (110, 145, 110), 2: (85, 138, 198), 3: (224, 174, 48)}.get(level, (60, 60, 60))
        pygame.draw.rect(surface, lvl_col, rect, border_radius=4)
        pygame.draw.rect(surface, (20, 24, 28), rect, 1, border_radius=4)
        txt = self.font_xs.render(f"{tag}{level}" if level > 0 else f"{tag}-", True, (255, 255, 255))
        surface.blit(txt, (rect.centerx - txt.get_width() // 2, rect.y + 4))
        if level > 0 and max_dur > 0:
            ratio = max(0.0, min(1.0, dur / max_dur))
            pygame.draw.rect(surface, (25, 25, 25), (rect.x + 3, rect.bottom - 5, rect.w - 6, 3))
            pygame.draw.rect(surface, (240, 240, 240), (rect.x + 3, rect.bottom - 5, int((rect.w - 6) * ratio), 3))

    def _draw_cast_bar(
        self,
        surface: pygame.Surface,
        label: str,
        progress: float,
        cx: int,
        cy: int,
        color: Tuple[int, int, int],
    ) -> None:
        bw = 240
        bh = 24
        rect = pygame.Rect(cx - bw // 2, cy, bw, bh)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, rect, border_radius=5)
        pygame.draw.rect(surface, color, (rect.x + 2, rect.y + 2, int((bw - 4) * max(0.0, min(1.0, progress))), bh - 4), border_radius=4)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, rect, 1, border_radius=5)
        txt = self.font_xs.render(label, True, (250, 250, 250))
        surface.blit(txt, (rect.centerx - txt.get_width() // 2, rect.y + 5))

    def _draw_loadout_panel(self, surface: pygame.Surface, player, screen_w: int, screen_h: int) -> None:
        # Weapon slots
        panel_w = 276
        panel_h = 104
        px = screen_w - panel_w - 18
        py = screen_h - panel_h - 16
        panel = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, panel, border_radius=8)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, panel, 2, border_radius=8)

        for idx in (0, 1):
            w = player.weapons[idx]
            slot_rect = pygame.Rect(px + 10, py + 10 + idx * 44, panel_w - 20, 38)
            active = idx == player.active_slot
            bg_col = (44, 54, 68) if active else (28, 34, 42)
            bd_col = config.COLOR_UI_ACCENT if active else (58, 66, 78)
            pygame.draw.rect(surface, bg_col, slot_rect, border_radius=5)
            pygame.draw.rect(surface, bd_col, slot_rect, 2 if active else 1, border_radius=5)

            key_txt = self.font_xs.render(f"[{idx + 1}]", True, config.COLOR_UI_ACCENT if active else config.COLOR_UI_MUTED)
            surface.blit(key_txt, (slot_rect.x + 8, slot_rect.y + 12))

            if w is not None:
                name_txt = self.font_sm.render(f"{w.name} ({w.category})", True, config.COLOR_UI_TEXT)
                surface.blit(name_txt, (slot_rect.x + 36, slot_rect.y + 10))
                res = player.ammo_reserve.get(w.ammo_type, 0)
                ammo_col = (240, 85, 75) if w.ammo_in_mag == 0 else config.COLOR_UI_TEXT
                ammo_txt = self.font_sm.render(f"{w.ammo_in_mag}/{res}", True, ammo_col)
                surface.blit(ammo_txt, (slot_rect.right - ammo_txt.get_width() - 10, slot_rect.y + 10))
            else:
                empty_txt = self.font_xs.render("Empty Slot", True, config.COLOR_UI_MUTED)
                surface.blit(empty_txt, (slot_rect.x + 38, slot_rect.y + 12))

        # Healing quick-slots on bottom-left
        med_rect = pygame.Rect(18, screen_h - 68, 290, 52)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, med_rect, border_radius=8)
        pygame.draw.rect(surface, config.COLOR_UI_BORDER, med_rect, 2, border_radius=8)
        items = [
            ("[4] Med", player.first_aids, (235, 95, 95)),
            ("[5] Boost", player.energy_drinks, (80, 185, 245)),
            ("[6] Band", player.bandages, (225, 215, 195)),
        ]
        for i, (lbl, qty, col) in enumerate(items):
            ix = med_rect.x + 12 + i * 94
            t1 = self.font_xs.render(lbl, True, config.COLOR_UI_MUTED)
            t2 = self.font_sm.render(f"x{qty}", True, col if qty > 0 else (90, 96, 105))
            surface.blit(t1, (ix, med_rect.y + 8))
            surface.blit(t2, (ix + 14, med_rect.y + 26))

    def _draw_banner(
        self,
        surface: pygame.Surface,
        text: str,
        cx: int,
        cy: int,
        bg_col: Tuple[int, int, int],
        text_col: Tuple[int, int, int],
    ) -> None:
        surf = self.font_sm.render(text, True, text_col)
        rect = pygame.Rect(cx - surf.get_width() // 2 - 14, cy, surf.get_width() + 28, 30)
        pygame.draw.rect(surface, bg_col, rect, border_radius=6)
        pygame.draw.rect(surface, text_col, rect, 1, border_radius=6)
        surface.blit(surf, (rect.x + 14, rect.y + 6))

    def _draw_crosshair(
        self,
        surface: pygame.Surface,
        mouse_pos: Tuple[int, int],
        hit_marker_timer: float,
        hit_marker_kill: bool,
        reloading: bool,
    ) -> None:
        mx, my = mouse_pos
        col = (240, 180, 50) if reloading else (245, 250, 255)
        gap = 6
        arm = 11
        pygame.draw.line(surface, col, (mx - arm, my), (mx - gap, my), 2)
        pygame.draw.line(surface, col, (mx + gap, my), (mx + arm, my), 2)
        pygame.draw.line(surface, col, (mx, my - arm), (mx, my - gap), 2)
        pygame.draw.line(surface, col, (mx, my + gap), (mx, my + arm), 2)
        pygame.draw.circle(surface, col, (mx, my), 2)

        if hit_marker_timer > 0.0:
            hm_col = (245, 60, 60) if hit_marker_kill else (255, 255, 255)
            d1, d2 = 5, 13
            pygame.draw.line(surface, hm_col, (mx - d2, my - d2), (mx - d1, my - d1), 2)
            pygame.draw.line(surface, hm_col, (mx + d1, my - d1), (mx + d2, my - d2), 2)
            pygame.draw.line(surface, hm_col, (mx - d2, my + d2), (mx - d1, my + d1), 2)
            pygame.draw.line(surface, hm_col, (mx + d1, my + d1), (mx + d2, my + d2), 2)

    # ------------------------------------------------------------------
    # Menus & End Screens
    # ------------------------------------------------------------------
    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        mouse_pos: Tuple[int, int],
        accent: bool = False,
    ) -> None:
        hovered = rect.collidepoint(mouse_pos)
        if accent:
            bg = (242, 192, 62) if hovered else config.COLOR_UI_ACCENT
            fg = (18, 22, 28)
            border = (255, 232, 145)
        else:
            bg = (46, 56, 70) if hovered else config.COLOR_UI_PANEL
            fg = config.COLOR_UI_TEXT
            border = config.COLOR_UI_ACCENT if hovered else config.COLOR_UI_BORDER

        pygame.draw.rect(surface, bg, rect, border_radius=8)
        pygame.draw.rect(surface, border, rect, 2, border_radius=8)
        txt = self.font_md.render(label, True, fg)
        surface.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))

    def draw_start_menu(self, surface: pygame.Surface, mouse_pos: Tuple[int, int]) -> None:
        w, h = surface.get_size()
        surface.fill((16, 22, 28))

        # Tactical subtle background grid
        for x in range(0, w, 64):
            pygame.draw.line(surface, (24, 32, 40), (x, 0), (x, h), 1)
        for y in range(0, h, 64):
            pygame.draw.line(surface, (24, 32, 40), (0, y), (w, y), 1)

        title = self.font_xl.render("BGMI 2D: BATTLE ROYALE", True, config.COLOR_UI_ACCENT)
        sub = self.font_md.render("28 Survivors  |  Shrinking Blue Zone  |  Air Drops  |  Tactical AI", True, config.COLOR_UI_MUTED)
        surface.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 200))
        surface.blit(sub, (w // 2 - sub.get_width() // 2, h // 2 - 135))

        bw, bh = 280, 54
        bx = w // 2 - bw // 2
        self.menu_buttons = {
            "play": pygame.Rect(bx, h // 2 - 50, bw, bh),
            "controls": pygame.Rect(bx, h // 2 + 22, bw, bh),
            "quit": pygame.Rect(bx, h // 2 + 94, bw, bh),
        }
        self._draw_button(surface, self.menu_buttons["play"], "PLAY MATCH", mouse_pos, accent=True)
        self._draw_button(surface, self.menu_buttons["controls"], "CONTROLS", mouse_pos)
        self._draw_button(surface, self.menu_buttons["quit"], "QUIT", mouse_pos)

        tip = self.font_xs.render("Press ENTER to drop in immediately  |  Zero external assets required", True, config.COLOR_UI_MUTED)
        surface.blit(tip, (w // 2 - tip.get_width() // 2, h - 42))

    def draw_controls_screen(self, surface: pygame.Surface, mouse_pos: Tuple[int, int]) -> None:
        w, h = surface.get_size()
        surface.fill((16, 22, 28))

        card = pygame.Rect(w // 2 - 340, 70, 680, h - 150)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, card, border_radius=10)
        pygame.draw.rect(surface, config.COLOR_UI_ACCENT, card, 2, border_radius=10)

        title = self.font_lg.render("CONTROLS & MECHANICS", True, config.COLOR_UI_ACCENT)
        surface.blit(title, (card.centerx - title.get_width() // 2, card.y + 24))

        rows = [
            ("W / A / S / D", "Move character smoothly across the map"),
            ("Mouse Aim + Left Click", "Aim and fire active weapon (hold for full-auto)"),
            ("R", "Reload active weapon (requires reserve ammo)"),
            ("1 / 2  (or Mouse Wheel)", "Switch between Primary & Secondary weapon slots"),
            ("F", "Pick up ground loot, death crates, and Supply Drops"),
            ("4", "Use First Aid Kit (restores HP up to 75; falls back to Bandage)"),
            ("5", "Drink Energy Drink (+40 Boost: HP regen & speed boost)"),
            ("6", "Apply Bandage (+18 HP up to 75)"),
            ("M", "Toggle Enlarged Tactical Map"),
            ("ESC", "Pause Match / Return"),
        ]

        y = card.y + 92
        for key_label, desc in rows:
            k_surf = self.font_sm.render(key_label, True, config.COLOR_UI_ACCENT)
            d_surf = self.font_sm.render(desc, True, config.COLOR_UI_TEXT)
            surface.blit(k_surf, (card.x + 36, y))
            surface.blit(d_surf, (card.x + 258, y))
            y += 38

        self.controls_back_btn = pygame.Rect(card.centerx - 120, card.bottom - 72, 240, 48)
        self._draw_button(surface, self.controls_back_btn, "BACK TO MENU", mouse_pos, accent=True)

    def draw_pause_menu(self, surface: pygame.Surface, mouse_pos: Tuple[int, int]) -> None:
        w, h = surface.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((8, 12, 18, 180))
        surface.blit(dim, (0, 0))

        card = pygame.Rect(w // 2 - 190, h // 2 - 185, 380, 370)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, card, border_radius=10)
        pygame.draw.rect(surface, config.COLOR_UI_ACCENT, card, 2, border_radius=10)

        title = self.font_lg.render("PAUSED", True, config.COLOR_UI_ACCENT)
        surface.blit(title, (card.centerx - title.get_width() // 2, card.y + 24))

        bw, bh = 260, 48
        bx = card.centerx - bw // 2
        self.pause_buttons = {
            "resume": pygame.Rect(bx, card.y + 94, bw, bh),
            "restart": pygame.Rect(bx, card.y + 156, bw, bh),
            "menu": pygame.Rect(bx, card.y + 218, bw, bh),
            "quit": pygame.Rect(bx, card.y + 280, bw, bh),
        }
        self._draw_button(surface, self.pause_buttons["resume"], "RESUME (ESC)", mouse_pos, accent=True)
        self._draw_button(surface, self.pause_buttons["restart"], "RESTART MATCH", mouse_pos)
        self._draw_button(surface, self.pause_buttons["menu"], "MAIN MENU", mouse_pos)
        self._draw_button(surface, self.pause_buttons["quit"], "QUIT GAME", mouse_pos)

    def draw_end_screen(
        self,
        surface: pygame.Surface,
        mouse_pos: Tuple[int, int],
        rank: int,
        total: int,
        kills: int,
        damage_dealt: float,
        survival_time: float,
        eliminated_by: str,
    ) -> None:
        w, h = surface.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((10, 14, 20, 210))
        surface.blit(dim, (0, 0))

        victory = rank == 1
        card = pygame.Rect(w // 2 - 340, h // 2 - 220, 680, 440)
        pygame.draw.rect(surface, config.COLOR_UI_PANEL, card, border_radius=12)
        border_col = config.COLOR_UI_ACCENT if victory else (215, 72, 66)
        pygame.draw.rect(surface, border_col, card, 3, border_radius=12)

        if victory:
            headline = self.font_lg.render("WINNER WINNER CHICKEN DINNER!", True, config.COLOR_UI_ACCENT)
            sub_str = "You outlasted every opponent on the battleground."
        else:
            headline = self.font_lg.render(f"ELIMINATED  -  RANK #{rank} / {total}", True, (240, 88, 78))
            sub_str = f"Eliminated by: {eliminated_by}"

        surface.blit(headline, (card.centerx - headline.get_width() // 2, card.y + 34))
        sub = self.font_sm.render(sub_str, True, config.COLOR_UI_MUTED)
        surface.blit(sub, (card.centerx - sub.get_width() // 2, card.y + 84))

        # Match summary stat tiles
        mins = int(survival_time) // 60
        secs = int(survival_time) % 60
        stats = [
            ("RANK", f"#{rank}/{total}"),
            ("KILLS", str(kills)),
            ("DAMAGE", str(int(damage_dealt))),
            ("SURVIVED", f"{mins}:{secs:02d}"),
        ]
        tile_w = 138
        start_x = card.centerx - (tile_w * 4 + 18 * 3) // 2
        for i, (label, val) in enumerate(stats):
            tx = start_x + i * (tile_w + 18)
            tile = pygame.Rect(tx, card.y + 138, tile_w, 94)
            pygame.draw.rect(surface, (32, 40, 50), tile, border_radius=8)
            pygame.draw.rect(surface, config.COLOR_UI_BORDER, tile, 1, border_radius=8)
            l_surf = self.font_xs.render(label, True, config.COLOR_UI_MUTED)
            v_surf = self.font_lg.render(val, True, config.COLOR_UI_ACCENT if victory else config.COLOR_UI_TEXT)
            surface.blit(l_surf, (tile.centerx - l_surf.get_width() // 2, tile.y + 14))
            surface.blit(v_surf, (tile.centerx - v_surf.get_width() // 2, tile.y + 42))

        bw, bh = 240, 52
        self.end_buttons = {
            "play_again": pygame.Rect(card.centerx - bw - 14, card.bottom - 94, bw, bh),
            "menu": pygame.Rect(card.centerx + 14, card.bottom - 94, bw, bh),
        }
        self._draw_button(surface, self.end_buttons["play_again"], "PLAY AGAIN", mouse_pos, accent=True)
        self._draw_button(surface, self.end_buttons["menu"], "MAIN MENU", mouse_pos)
