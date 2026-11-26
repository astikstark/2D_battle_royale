"""Global configuration constants, weapon stats, colors, and zone phases."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Display & Performance
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
WINDOW_TITLE = "BGMI 2D: Top-Down Battle Royale"
MAX_DT = 0.05  # Clamp delta time to avoid tunneling on frame spikes

# ---------------------------------------------------------------------------
# World Dimensions
# ---------------------------------------------------------------------------
WORLD_WIDTH = 3200
WORLD_HEIGHT = 3200
SPATIAL_CELL_SIZE = 256

# ---------------------------------------------------------------------------
# Match Settings
# ---------------------------------------------------------------------------
BOT_COUNT = 27  # 27 bots + 1 player = 28 combatants (25-30 bots range)
AIRDROP_INTERVAL = 48.0  # Seconds between supply air drops
AIRDROP_FIRST_DELAY = 25.0  # First air drop arrives early to drive action
AIRDROP_FALL_TIME = 4.0  # Visual parachute descent duration
LOOT_PICKUP_RADIUS = 56.0
CRATE_INTERACT_RADIUS = 64.0

# ---------------------------------------------------------------------------
# Entity Stats
# ---------------------------------------------------------------------------
PLAYER_RADIUS = 16.0
PLAYER_SPEED = 225.0
PLAYER_MAX_HP = 100.0
PLAYER_MAX_BOOST = 100.0
BOOST_SPEED_BONUS = 1.12  # +12% movement speed when boost >= 60
BOOST_DECAY_RATE = 1.6  # Boost points drained per second
BOOST_REGEN_LOW = 1.5  # HP/s when boost > 0
BOOST_REGEN_HIGH = 3.2  # HP/s when boost >= 60

BOT_RADIUS = 16.0
BOT_BASE_SPEED = 195.0
BOT_VISION_RANGE = 520.0
BOT_LOOT_SEARCH_RANGE = 420.0

# ---------------------------------------------------------------------------
# Armor & Healing
# ---------------------------------------------------------------------------
VEST_DAMAGE_REDUCTION = {
    0: 0.0,
    1: 0.25,
    2: 0.40,
    3: 0.55,
}
VEST_MAX_DURABILITY = {
    0: 0.0,
    1: 120.0,
    2: 180.0,
    3: 250.0,
}

HELMET_DAMAGE_REDUCTION = {
    0: 0.0,
    1: 0.15,
    2: 0.25,
    3: 0.35,
}
HELMET_MAX_DURABILITY = {
    0: 0.0,
    1: 80.0,
    2: 120.0,
    3: 180.0,
}

# Healing definitions
FIRST_AID_CAST_TIME = 3.8
FIRST_AID_MAX_HP = 75.0
BANDAGE_CAST_TIME = 1.8
BANDAGE_HEAL_AMOUNT = 18.0
BANDAGE_MAX_HP = 75.0
ENERGY_DRINK_CAST_TIME = 2.2
ENERGY_DRINK_BOOST_AMOUNT = 40.0

# ---------------------------------------------------------------------------
# Ammo Types & Reserve Caps
# ---------------------------------------------------------------------------
AMMO_MAX_RESERVE = {
    "9mm": 120,
    "5.56mm": 180,
    "7.62mm": 150,
    ".45 ACP": 180,
    "12 Gauge": 48,
    ".300 Magnum": 30,
}

AMMO_PACK_AMOUNT = {
    "9mm": 30,
    "5.56mm": 30,
    "7.62mm": 30,
    ".45 ACP": 30,
    "12 Gauge": 10,
    ".300 Magnum": 10,
}

AMMO_COLORS = {
    "9mm": (235, 195, 75),
    "5.56mm": (95, 200, 110),
    "7.62mm": (215, 145, 75),
    ".45 ACP": (100, 175, 235),
    "12 Gauge": (220, 75, 75),
    ".300 Magnum": (220, 90, 230),
}

# ---------------------------------------------------------------------------
# Weapon Specifications
# ---------------------------------------------------------------------------
WEAPON_SPECS = {
    "P92": {
        "category": "Pistol",
        "ammo_type": "9mm",
        "damage": 24,
        "fire_rate": 4.2,       # Rounds per second
        "mag_size": 15,
        "reload_time": 1.6,
        "bullet_speed": 880.0,
        "spread_deg": 3.5,
        "range": 480.0,
        "pellets": 1,
        "auto": False,
        "recoil": 2.2,
        "knockback": 35.0,
        "barrel_length": 20,
        "color": (160, 165, 175),
        "tracer_color": (255, 230, 150),
        "sound": "pistol",
        "weight": 0.0,  # Starting weapon, not spawned in ground loot pool
    },
    "M416": {
        "category": "AR",
        "ammo_type": "5.56mm",
        "damage": 33,
        "fire_rate": 9.5,
        "mag_size": 30,
        "reload_time": 2.1,
        "bullet_speed": 1150.0,
        "spread_deg": 2.6,
        "range": 740.0,
        "pellets": 1,
        "auto": True,
        "recoil": 3.0,
        "knockback": 55.0,
        "barrel_length": 29,
        "color": (75, 85, 95),
        "tracer_color": (255, 240, 170),
        "sound": "ar",
        "weight": 26.0,
    },
    "AKM": {
        "category": "AR",
        "ammo_type": "7.62mm",
        "damage": 42,
        "fire_rate": 7.6,
        "mag_size": 30,
        "reload_time": 2.4,
        "bullet_speed": 1060.0,
        "spread_deg": 4.2,
        "range": 700.0,
        "pellets": 1,
        "auto": True,
        "recoil": 4.6,
        "knockback": 75.0,
        "barrel_length": 30,
        "color": (130, 82, 52),
        "tracer_color": (255, 200, 110),
        "sound": "akm",
        "weight": 24.0,
    },
    "UMP45": {
        "category": "SMG",
        "ammo_type": ".45 ACP",
        "damage": 28,
        "fire_rate": 10.8,
        "mag_size": 25,
        "reload_time": 1.8,
        "bullet_speed": 920.0,
        "spread_deg": 3.8,
        "range": 520.0,
        "pellets": 1,
        "auto": True,
        "recoil": 2.0,
        "knockback": 40.0,
        "barrel_length": 24,
        "color": (60, 68, 78),
        "tracer_color": (210, 235, 255),
        "sound": "smg",
        "weight": 28.0,
    },
    "S12K": {
        "category": "Shotgun",
        "ammo_type": "12 Gauge",
        "damage": 17,           # Per pellet (7 pellets = up to 119 point-blank)
        "fire_rate": 2.3,
        "mag_size": 5,
        "reload_time": 2.3,
        "bullet_speed": 840.0,
        "spread_deg": 13.0,
        "range": 310.0,
        "pellets": 7,
        "auto": False,
        "recoil": 7.5,
        "knockback": 120.0,
        "barrel_length": 27,
        "color": (92, 65, 55),
        "tracer_color": (255, 175, 95),
        "sound": "shotgun",
        "weight": 22.0,
    },
    "AWM": {
        "category": "Sniper",
        "ammo_type": ".300 Magnum",
        "damage": 105,
        "fire_rate": 0.78,
        "mag_size": 5,
        "reload_time": 3.1,
        "bullet_speed": 1650.0,
        "spread_deg": 0.4,
        "range": 1150.0,
        "pellets": 1,
        "auto": False,
        "recoil": 9.0,
        "knockback": 150.0,
        "barrel_length": 36,
        "color": (72, 108, 72),
        "tracer_color": (255, 255, 220),
        "sound": "sniper",
        "weight": 0.0,  # Exclusive to Supply Air Drops
    },
}

# ---------------------------------------------------------------------------
# Blue Zone Phases: (wait_seconds, shrink_seconds, target_radius_ratio, dps)
# ---------------------------------------------------------------------------
ZONE_PHASES = [
    {"phase": 1, "wait": 24.0, "shrink": 28.0, "radius_ratio": 0.52, "dps": 1.8},
    {"phase": 2, "wait": 20.0, "shrink": 24.0, "radius_ratio": 0.32, "dps": 3.5},
    {"phase": 3, "wait": 16.0, "shrink": 22.0, "radius_ratio": 0.18, "dps": 6.5},
    {"phase": 4, "wait": 14.0, "shrink": 18.0, "radius_ratio": 0.09, "dps": 11.0},
    {"phase": 5, "wait": 10.0, "shrink": 16.0, "radius_ratio": 0.03, "dps": 18.0},
    {"phase": 6, "wait": 8.0,  "shrink": 14.0, "radius_ratio": 0.0,  "dps": 28.0},
]

# ---------------------------------------------------------------------------
# Color Palette (Tactical Erangel-Inspired)
# ---------------------------------------------------------------------------
COLOR_GRASS_BASE = (88, 118, 66)
COLOR_GRASS_PATCH = (78, 108, 58)
COLOR_GRASS_LIGHT = (98, 128, 74)
COLOR_DIRT = (138, 118, 86)
COLOR_ROAD = (82, 84, 88)
COLOR_ROAD_LINE = (210, 195, 130)
COLOR_WATER = (56, 106, 138)
COLOR_SAND = (176, 160, 116)

COLOR_BUILDING_FLOOR = (146, 138, 124)
COLOR_BUILDING_FLOOR_ALT = (132, 125, 114)
COLOR_WALL = (78, 74, 70)
COLOR_WALL_TOP = (102, 96, 90)
COLOR_ROOF = (98, 82, 72)

COLOR_ROCK = (118, 116, 112)
COLOR_ROCK_HIGHLIGHT = (144, 142, 138)
COLOR_ROCK_SHADOW = (64, 68, 58)

COLOR_TREE_TRUNK = (92, 66, 44)
COLOR_TREE_CANOPY_OUTER = (46, 86, 44)
COLOR_TREE_CANOPY_INNER = (64, 110, 56)

COLOR_PLAYER_BODY = (52, 148, 226)
COLOR_PLAYER_OUTLINE = (20, 42, 68)
COLOR_BOT_BODY = (210, 74, 64)
COLOR_BOT_OUTLINE = (68, 24, 22)
COLOR_SKIN = (224, 186, 152)

COLOR_BLUE_ZONE = (48, 140, 255)
COLOR_SAFE_ZONE = (245, 248, 255)
COLOR_AIRDROP_CRATE = (195, 42, 42)
COLOR_AIRDROP_TARP = (45, 102, 188)

COLOR_UI_BG = (16, 20, 26)
COLOR_UI_PANEL = (24, 30, 38)
COLOR_UI_BORDER = (68, 78, 92)
COLOR_UI_TEXT = (240, 244, 248)
COLOR_UI_MUTED = (162, 172, 186)
COLOR_UI_ACCENT = (242, 184, 48)
COLOR_HP_HIGH = (232, 238, 244)
COLOR_HP_MID = (242, 184, 48)
COLOR_HP_LOW = (232, 68, 62)
COLOR_BOOST = (245, 158, 42)
COLOR_KILL_FEED_BG = (18, 22, 28)

# ---------------------------------------------------------------------------
# Bot Names
# ---------------------------------------------------------------------------
BOT_NAMES = [
    "ViperX", "GhostOps", "Shadow99", "KobraIN", "DeltaZero",
    "MortalBot", "SniperRaj", "AceVikram", "NovaStrike", "Blaze77",
    "IronWolf", "PhantomK", "ReaperIND", "TitanOne", "HawkEye",
    "FuryMax", "StormZ", "VenomPro", "RogueSix", "BlitzK",
    "ApexHunter", "Raven07", "CobraKai", "PulseX", "Dagger9",
    "SpectreV", "Valkyrie", "Nomad42", "StrikerX", "Outlaw88",
]
