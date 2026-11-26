"""Procedural Battle Royale world: terrain, roads, compounds, obstacles, and spatial collision."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pygame

import config


@dataclass
class Building:
    """An enterable compound building with segmented walls and doorways."""

    name: str
    rect: pygame.Rect
    walls: List[pygame.Rect]
    doorways: List[Tuple[float, float]]
    loot_spots: List[Tuple[float, float]]
    floor_color: Tuple[int, int, int]
    roof_color: Tuple[int, int, int]


@dataclass
class Obstacle:
    """Circular natural cover: rock or tree."""

    kind: str  # "rock" or "tree"
    x: float
    y: float
    radius: float  # Collision radius (trunk for trees, full boulder for rocks)
    visual_radius: float  # Canopy radius for trees, boulder radius for rocks
    color_main: Tuple[int, int, int]
    color_accent: Tuple[int, int, int]


@dataclass
class TerrainPatch:
    """Visual ground detail (grass patch, dirt clearing, sand bank)."""

    x: float
    y: float
    rx: float
    ry: float
    color: Tuple[int, int, int]


class World:
    """Stores the 3200x3200 map layout and accelerates collision/LOS via spatial hashing."""

    def __init__(self, rng: random.Random) -> None:
        self.width = config.WORLD_WIDTH
        self.height = config.WORLD_HEIGHT
        self.rng = rng

        self.roads: List[pygame.Rect] = []
        self.terrain_patches: List[TerrainPatch] = []
        self.buildings: List[Building] = []
        self.walls: List[pygame.Rect] = []
        self.obstacles: List[Obstacle] = []
        self.compound_labels: List[Tuple[str, float, float]] = []

        # Spatial hash grids for O(1) nearby queries
        self._cell = config.SPATIAL_CELL_SIZE
        self._wall_grid: Dict[Tuple[int, int], List[pygame.Rect]] = {}
        self._obs_grid: Dict[Tuple[int, int], List[Obstacle]] = {}

        self._generate()
        self._build_spatial_index()

    # ------------------------------------------------------------------
    # Procedural Map Generation
    # ------------------------------------------------------------------
    def _generate(self) -> None:
        # 1. Terrain patches for natural visual variety
        for _ in range(110):
            px = self.rng.uniform(80, self.width - 80)
            py = self.rng.uniform(80, self.height - 80)
            rx = self.rng.uniform(70, 220)
            ry = self.rng.uniform(60, 190)
            col = self.rng.choice([
                config.COLOR_GRASS_PATCH,
                config.COLOR_GRASS_LIGHT,
                config.COLOR_DIRT,
            ])
            self.terrain_patches.append(TerrainPatch(px, py, rx, ry, col))

        # 2. Primary highway cross-roads & secondary avenues
        road_w = 104
        mid_x = self.width // 2
        mid_y = self.height // 2
        self.roads.append(pygame.Rect(mid_x - road_w // 2, 0, road_w, self.height))
        self.roads.append(pygame.Rect(0, mid_y - road_w // 2, self.width, road_w))
        # Secondary loop roads
        self.roads.append(pygame.Rect(720, 720, self.width - 1440, 74))
        self.roads.append(pygame.Rect(720, self.height - 794, self.width - 1440, 74))
        self.roads.append(pygame.Rect(720, 720, 74, self.height - 1440))
        self.roads.append(pygame.Rect(self.width - 794, 720, 74, self.height - 1440))

        # 3. Named BGMI-inspired compounds (clusters of enterable buildings)
        compounds = [
            ("POCHINKI", 1180, 1180, 3),
            ("SCHOOL", 1980, 1160, 2),
            ("ROZHK", 1180, 2020, 3),
            ("MYLTA", 2040, 2040, 3),
            ("GEORGOPOL", 440, 480, 3),
            ("YASNAYA", 2680, 480, 3),
            ("GATKA", 440, 2660, 2),
            ("MILITARY BASE", 2620, 2660, 3),
            ("FARM", 1600, 460, 2),
            ("QUARRY", 460, 1600, 2),
            ("MANSION", 2740, 1600, 2),
            ("NOVO", 1600, 2720, 2),
        ]

        placed_rects: List[pygame.Rect] = []
        for cname, cx, cy, count in compounds:
            self.compound_labels.append((cname, float(cx), float(cy)))
            for i in range(count):
                for _attempt in range(30):
                    bw = self.rng.choice([170, 200, 230, 260])
                    bh = self.rng.choice([150, 180, 210])
                    ox = self.rng.randint(-210, 210)
                    oy = self.rng.randint(-210, 210)
                    bx = max(140, min(self.width - bw - 140, cx + ox - bw // 2))
                    by = max(140, min(self.height - bh - 140, cy + oy - bh // 2))
                    cand = pygame.Rect(bx, by, bw, bh)
                    padded = cand.inflate(56, 56)

                    if any(padded.colliderect(r) for r in self.roads):
                        continue
                    if any(padded.colliderect(r) for r in placed_rects):
                        continue

                    building = self._create_building(f"{cname}_{i + 1}", cand)
                    self.buildings.append(building)
                    self.walls.extend(building.walls)
                    placed_rects.append(cand)
                    break

        # 4. Rocks & Trees (natural cover)
        for _ in range(95):
            for _try in range(15):
                rx = self.rng.uniform(100, self.width - 100)
                ry = self.rng.uniform(100, self.height - 100)
                rad = self.rng.uniform(22, 38)
                test_rect = pygame.Rect(rx - rad - 18, ry - rad - 18, (rad + 18) * 2, (rad + 18) * 2)
                if any(test_rect.colliderect(r) for r in self.roads):
                    continue
                if any(test_rect.colliderect(b.rect.inflate(36, 36)) for b in self.buildings):
                    continue
                if any(math.hypot(rx - o.x, ry - o.y) < rad + o.visual_radius + 20 for o in self.obstacles):
                    continue
                self.obstacles.append(
                    Obstacle(
                        kind="rock",
                        x=rx,
                        y=ry,
                        radius=rad,
                        visual_radius=rad,
                        color_main=config.COLOR_ROCK,
                        color_accent=config.COLOR_ROCK_HIGHLIGHT,
                    )
                )
                break

        for _ in range(170):
            for _try in range(15):
                tx = self.rng.uniform(90, self.width - 90)
                ty = self.rng.uniform(90, self.height - 90)
                canopy = self.rng.uniform(28, 44)
                trunk = max(10.0, canopy * 0.32)
                test_rect = pygame.Rect(tx - canopy - 10, ty - canopy - 10, (canopy + 10) * 2, (canopy + 10) * 2)
                if any(test_rect.colliderect(r) for r in self.roads):
                    continue
                if any(test_rect.colliderect(b.rect.inflate(28, 28)) for b in self.buildings):
                    continue
                if any(math.hypot(tx - o.x, ty - o.y) < canopy + o.visual_radius + 10 for o in self.obstacles):
                    continue
                self.obstacles.append(
                    Obstacle(
                        kind="tree",
                        x=tx,
                        y=ty,
                        radius=trunk,
                        visual_radius=canopy,
                        color_main=config.COLOR_TREE_CANOPY_OUTER,
                        color_accent=config.COLOR_TREE_CANOPY_INNER,
                    )
                )
                break

    def _create_building(self, name: str, rect: pygame.Rect) -> Building:
        """Build 4 perimeter walls with 2 enterable doorways and interior loot spots."""
        t = 14  # Wall thickness
        door_w = 56
        walls: List[pygame.Rect] = []
        doorways: List[Tuple[float, float]] = []

        # Choose 2 distinct sides to have doorways
        door_sides = set(self.rng.sample(["top", "bottom", "left", "right"], 2))

        # Top wall
        if "top" in door_sides:
            mid = rect.centerx
            left_w = max(t, (mid - door_w // 2) - rect.left)
            right_x = mid + door_w // 2
            right_w = max(t, rect.right - right_x)
            walls.append(pygame.Rect(rect.left, rect.top, left_w, t))
            walls.append(pygame.Rect(right_x, rect.top, right_w, t))
            doorways.append((float(mid), float(rect.top + t // 2)))
        else:
            walls.append(pygame.Rect(rect.left, rect.top, rect.width, t))

        # Bottom wall
        if "bottom" in door_sides:
            mid = rect.centerx
            left_w = max(t, (mid - door_w // 2) - rect.left)
            right_x = mid + door_w // 2
            right_w = max(t, rect.right - right_x)
            walls.append(pygame.Rect(rect.left, rect.bottom - t, left_w, t))
            walls.append(pygame.Rect(right_x, rect.bottom - t, right_w, t))
            doorways.append((float(mid), float(rect.bottom - t // 2)))
        else:
            walls.append(pygame.Rect(rect.left, rect.bottom - t, rect.width, t))

        # Left wall
        if "left" in door_sides:
            mid = rect.centery
            top_h = max(t, (mid - door_w // 2) - rect.top)
            bot_y = mid + door_w // 2
            bot_h = max(t, rect.bottom - bot_y)
            walls.append(pygame.Rect(rect.left, rect.top, t, top_h))
            walls.append(pygame.Rect(rect.left, bot_y, t, bot_h))
            doorways.append((float(rect.left + t // 2), float(mid)))
        else:
            walls.append(pygame.Rect(rect.left, rect.top, t, rect.height))

        # Right wall
        if "right" in door_sides:
            mid = rect.centery
            top_h = max(t, (mid - door_w // 2) - rect.top)
            bot_y = mid + door_w // 2
            bot_h = max(t, rect.bottom - bot_y)
            walls.append(pygame.Rect(rect.right - t, rect.top, t, top_h))
            walls.append(pygame.Rect(rect.right - t, bot_y, t, bot_h))
            doorways.append((float(rect.right - t // 2), float(mid)))
        else:
            walls.append(pygame.Rect(rect.right - t, rect.top, t, rect.height))

        # Interior loot spawn points
        pad = 36
        loot_spots = [
            (float(rect.left + pad), float(rect.top + pad)),
            (float(rect.right - pad), float(rect.top + pad)),
            (float(rect.left + pad), float(rect.bottom - pad)),
            (float(rect.right - pad), float(rect.bottom - pad)),
            (float(rect.centerx), float(rect.centery)),
        ]

        floor_col = self.rng.choice([config.COLOR_BUILDING_FLOOR, config.COLOR_BUILDING_FLOOR_ALT])
        roof_col = self.rng.choice([(104, 84, 72), (88, 92, 98), (112, 78, 66)])
        return Building(name, rect, walls, doorways, loot_spots, floor_col, roof_col)

    # ------------------------------------------------------------------
    # Spatial Hashing
    # ------------------------------------------------------------------
    def _cell_range(self, min_x: float, min_y: float, max_x: float, max_y: float) -> Tuple[int, int, int, int]:
        c = self._cell
        return (
            int(min_x // c),
            int(min_y // c),
            int(max_x // c),
            int(max_y // c),
        )

    def _build_spatial_index(self) -> None:
        self._wall_grid.clear()
        self._obs_grid.clear()

        for wall in self.walls:
            x0, y0, x1, y1 = self._cell_range(wall.left, wall.top, wall.right, wall.bottom)
            for gx in range(x0, x1 + 1):
                for gy in range(y0, y1 + 1):
                    self._wall_grid.setdefault((gx, gy), []).append(wall)

        for obs in self.obstacles:
            x0, y0, x1, y1 = self._cell_range(
                obs.x - obs.radius,
                obs.y - obs.radius,
                obs.x + obs.radius,
                obs.y + obs.radius,
            )
            for gx in range(x0, x1 + 1):
                for gy in range(y0, y1 + 1):
                    self._obs_grid.setdefault((gx, gy), []).append(obs)

    def get_nearby_walls(self, x: float, y: float, radius: float) -> List[pygame.Rect]:
        x0, y0, x1, y1 = self._cell_range(x - radius, y - radius, x + radius, y + radius)
        seen: Set[int] = set()
        result: List[pygame.Rect] = []
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                for w in self._wall_grid.get((gx, gy), ()):
                    wid = id(w)
                    if wid not in seen:
                        seen.add(wid)
                        result.append(w)
        return result

    def get_nearby_obstacles(self, x: float, y: float, radius: float) -> List[Obstacle]:
        x0, y0, x1, y1 = self._cell_range(x - radius, y - radius, x + radius, y + radius)
        seen: Set[int] = set()
        result: List[Obstacle] = []
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                for o in self._obs_grid.get((gx, gy), ()):
                    oid = id(o)
                    if oid not in seen:
                        seen.add(oid)
                        result.append(o)
        return result

    # ------------------------------------------------------------------
    # Collision & Line-of-Sight Helpers
    # ------------------------------------------------------------------
    def resolve_circle_collision(self, x: float, y: float, radius: float) -> Tuple[float, float]:
        """Push a moving circle out of walls, obstacles, and world borders smoothly."""
        # Clamp to world borders
        x = max(radius + 8.0, min(self.width - radius - 8.0, x))
        y = max(radius + 8.0, min(self.height - radius - 8.0, y))

        # Two passes handle corner intersections cleanly
        walls = self.get_nearby_walls(x, y, radius + 24.0)
        obstacles = self.get_nearby_obstacles(x, y, radius + 48.0)

        for _ in range(2):
            for w in walls:
                cx = max(w.left, min(x, w.right))
                cy = max(w.top, min(y, w.bottom))
                dx = x - cx
                dy = y - cy
                dist_sq = dx * dx + dy * dy
                if dist_sq < radius * radius:
                    dist = math.sqrt(dist_sq)
                    if dist > 1e-5:
                        overlap = radius - dist
                        x += (dx / dist) * overlap
                        y += (dy / dist) * overlap
                    else:
                        # Circle center inside rect: push out along shortest axis
                        dl = abs(x - w.left)
                        dr = abs(w.right - x)
                        dt = abs(y - w.top)
                        db = abs(w.bottom - y)
                        m = min(dl, dr, dt, db)
                        if m == dl:
                            x = w.left - radius
                        elif m == dr:
                            x = w.right + radius
                        elif m == dt:
                            y = w.top - radius
                        else:
                            y = w.bottom + radius

            for obs in obstacles:
                dx = x - obs.x
                dy = y - obs.y
                min_d = radius + obs.radius
                dist_sq = dx * dx + dy * dy
                if dist_sq < min_d * min_d:
                    dist = math.sqrt(dist_sq)
                    if dist > 1e-5:
                        overlap = min_d - dist
                        x += (dx / dist) * overlap
                        y += (dy / dist) * overlap
                    else:
                        x += min_d

        x = max(radius + 8.0, min(self.width - radius - 8.0, x))
        y = max(radius + 8.0, min(self.height - radius - 8.0, y))
        return x, y

    def segment_hits_world(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> Optional[Tuple[float, float]]:
        """Check if a bullet segment hits a wall or obstacle; return impact point or None."""
        min_x = min(x1, x2) - 8.0
        max_x = max(x1, x2) + 8.0
        min_y = min(y1, y2) - 8.0
        max_y = max(y1, y2) + 8.0
        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        rad = math.hypot(max_x - min_x, max_y - min_y) * 0.5 + 32.0

        best_t = 2.0
        hit_pt: Optional[Tuple[float, float]] = None

        dx = x2 - x1
        dy = y2 - y1
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-6:
            return None

        # Check walls via clipline
        for w in self.get_nearby_walls(cx, cy, rad):
            clipped = w.clipline(x1, y1, x2, y2)
            if clipped:
                hx, hy = clipped[0]
                t = ((hx - x1) * dx + (hy - y1) * dy) / seg_len_sq
                if 0.0 <= t < best_t:
                    best_t = t
                    hit_pt = (float(hx), float(hy))

        # Check circular obstacles (rocks and tree trunks)
        for obs in self.get_nearby_obstacles(cx, cy, rad):
            # Closest point on segment to circle center
            t = ((obs.x - x1) * dx + (obs.y - y1) * dy) / seg_len_sq
            t_clamped = max(0.0, min(1.0, t))
            px = x1 + dx * t_clamped
            py = y1 + dy * t_clamped
            if (px - obs.x) ** 2 + (py - obs.y) ** 2 <= obs.radius * obs.radius:
                if t_clamped < best_t:
                    best_t = t_clamped
                    hit_pt = (px, py)

        return hit_pt

    def has_line_of_sight(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Return True if no wall or rock/trunk blocks sight between two points."""
        return self.segment_hits_world(x1, y1, x2, y2) is None

    def find_open_spawn(self, min_margin: float = 180.0, clearance: float = 28.0) -> Tuple[float, float]:
        """Find a collision-free point on the map for spawning entities or drops."""
        for _ in range(120):
            x = self.rng.uniform(min_margin, self.width - min_margin)
            y = self.rng.uniform(min_margin, self.height - min_margin)
            if self._is_point_clear(x, y, clearance):
                return x, y
        return self.width * 0.5, self.height * 0.5

    def _is_point_clear(self, x: float, y: float, clearance: float) -> bool:
        test = pygame.Rect(x - clearance, y - clearance, clearance * 2, clearance * 2)
        for w in self.get_nearby_walls(x, y, clearance + 16.0):
            if test.colliderect(w):
                return False
        for o in self.get_nearby_obstacles(x, y, clearance + 40.0):
            if math.hypot(x - o.x, y - o.y) < clearance + o.radius:
                return False
        return True

    # ------------------------------------------------------------------
    # Rendering (Camera-Culled)
    # ------------------------------------------------------------------
    def draw_ground_and_structures(
        self,
        surface: pygame.Surface,
        cam_x: float,
        cam_y: float,
        view_w: int,
        view_h: int,
    ) -> None:
        """Render terrain, roads, building floors, walls, and rocks visible in viewport."""
        view_rect = pygame.Rect(int(cam_x) - 60, int(cam_y) - 60, view_w + 120, view_h + 120)

        # Base grass
        surface.fill(config.COLOR_GRASS_BASE)

        # Subtle grid lines for spatial speed sensation
        grid_step = 160
        start_gx = -(int(cam_x) % grid_step)
        start_gy = -(int(cam_y) % grid_step)
        grid_col = (82, 111, 61)
        for gx in range(start_gx, view_w, grid_step):
            pygame.draw.line(surface, grid_col, (gx, 0), (gx, view_h), 1)
        for gy in range(start_gy, view_h, grid_step):
            pygame.draw.line(surface, grid_col, (0, gy), (view_w, gy), 1)

        # Terrain patches
        for p in self.terrain_patches:
            if (
                p.x + p.rx < view_rect.left
                or p.x - p.rx > view_rect.right
                or p.y + p.ry < view_rect.top
                or p.y - p.ry > view_rect.bottom
            ):
                continue
            r = pygame.Rect(
                int(p.x - p.rx - cam_x),
                int(p.y - p.ry - cam_y),
                int(p.rx * 2),
                int(p.ry * 2),
            )
            pygame.draw.ellipse(surface, p.color, r)

        # Roads
        for road in self.roads:
            if not road.colliderect(view_rect):
                continue
            sr = pygame.Rect(road.x - int(cam_x), road.y - int(cam_y), road.w, road.h)
            pygame.draw.rect(surface, config.COLOR_ROAD, sr)
            # Dashed center line
            if road.w > road.h:
                cy = sr.centery
                for dx in range(0, road.w, 48):
                    lx = sr.left + dx
                    if -40 <= lx <= view_w:
                        pygame.draw.line(surface, config.COLOR_ROAD_LINE, (lx, cy), (lx + 24, cy), 3)
            else:
                cx = sr.centerx
                for dy in range(0, road.h, 48):
                    ly = sr.top + dy
                    if -40 <= ly <= view_h:
                        pygame.draw.line(surface, config.COLOR_ROAD_LINE, (cx, ly), (cx, ly + 24), 3)

        # Buildings (floors + drop shadow + walls)
        for b in self.buildings:
            if not b.rect.colliderect(view_rect):
                continue
            sr = pygame.Rect(b.rect.x - int(cam_x), b.rect.y - int(cam_y), b.rect.w, b.rect.h)
            shadow = sr.move(8, 8)
            pygame.draw.rect(surface, (58, 78, 46), shadow)
            pygame.draw.rect(surface, b.floor_color, sr)
            # Subtle interior floor tiling lines
            for tx in range(sr.left + 32, sr.right, 32):
                pygame.draw.line(surface, (124, 117, 106), (tx, sr.top), (tx, sr.bottom), 1)
            for ty in range(sr.top + 32, sr.bottom, 32):
                pygame.draw.line(surface, (124, 117, 106), (sr.left, ty), (sr.right, ty), 1)

            for w in b.walls:
                sw = pygame.Rect(w.x - int(cam_x), w.y - int(cam_y), w.w, w.h)
                pygame.draw.rect(surface, config.COLOR_WALL, sw)
                pygame.draw.rect(surface, config.COLOR_WALL_TOP, sw.inflate(-4, -4))

        # Rocks (drawn below entities)
        for obs in self.obstacles:
            if obs.kind != "rock":
                continue
            if (
                obs.x + obs.visual_radius < view_rect.left
                or obs.x - obs.visual_radius > view_rect.right
                or obs.y + obs.visual_radius < view_rect.top
                or obs.y - obs.visual_radius > view_rect.bottom
            ):
                continue
            sx = int(obs.x - cam_x)
            sy = int(obs.y - cam_y)
            r = int(obs.visual_radius)
            pygame.draw.circle(surface, config.COLOR_ROCK_SHADOW, (sx + 5, sy + 6), r)
            pygame.draw.circle(surface, obs.color_main, (sx, sy), r)
            pygame.draw.circle(surface, obs.color_accent, (sx - r // 4, sy - r // 4), max(4, int(r * 0.52)))
            pygame.draw.circle(surface, (72, 70, 66), (sx, sy), r, 2)

        # World border boundary wall visual
        border_rect = pygame.Rect(-int(cam_x), -int(cam_y), self.width, self.height)
        pygame.draw.rect(surface, (190, 55, 45), border_rect, 6)

    def draw_canopies(
        self,
        surface: pygame.Surface,
        cam_x: float,
        cam_y: float,
        view_w: int,
        view_h: int,
    ) -> None:
        """Render tree trunks and foliage canopies above entities for depth."""
        view_rect = pygame.Rect(int(cam_x) - 60, int(cam_y) - 60, view_w + 120, view_h + 120)
        for obs in self.obstacles:
            if obs.kind != "tree":
                continue
            if (
                obs.x + obs.visual_radius < view_rect.left
                or obs.x - obs.visual_radius > view_rect.right
                or obs.y + obs.visual_radius < view_rect.top
                or obs.y - obs.visual_radius > view_rect.bottom
            ):
                continue
            sx = int(obs.x - cam_x)
            sy = int(obs.y - cam_y)
            r = int(obs.visual_radius)
            # Shadow
            pygame.draw.circle(surface, (52, 76, 40), (sx + 7, sy + 8), r)
            # Trunk
            pygame.draw.circle(surface, config.COLOR_TREE_TRUNK, (sx, sy), int(obs.radius))
            # Outer & inner canopy
            pygame.draw.circle(surface, obs.color_main, (sx, sy), r)
            pygame.draw.circle(surface, obs.color_accent, (sx - r // 5, sy - r // 5), int(r * 0.68))
            pygame.draw.circle(surface, (34, 66, 32), (sx, sy), r, 2)
