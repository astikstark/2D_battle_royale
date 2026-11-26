# BGMI 2D: Top-Down Battle Royale

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Pygame](https://img.shields.io/badge/Pygame-2.5%2B-00A86B)
![License](https://img.shields.io/badge/License-MIT-F2B830)
![Assets](https://img.shields.io/badge/External%20Assets-Zero%20Required-4C8BF5)

A complete, playable, BGMI-inspired 2D Top-Down Battle Royale built in Python with `pygame`. Drop into a 3200×3200 tactical island with 27 autonomous AI bots, loot enterable compounds, outrun the shrinking Blue Zone, contest Supply Air Drops for the AWM, and fight for **Winner Winner Chicken Dinner**.

---

## Gameplay Features

- **Large Tactical Map (3200×3200 px):** Named compounds (*Pochinki, School, Rozhk, Mylta, Georgopol, Military Base*, etc.), highways, natural cover (rocks and trees), and enterable buildings with solid walls and doorways.
- **Authentic Weapon Roster:**
  - **P92** (Starting 9mm Pistol)
  - **M416** (5.56mm Assault Rifle — balanced accuracy & fire rate)
  - **AKM** (7.62mm Assault Rifle — heavy hitting with stronger recoil)
  - **UMP45** (.45 ACP SMG — high fire rate for close quarters)
  - **S12K** (12 Gauge Shotgun — 7-pellet spread with heavy knockback)
  - **AWM** (.300 Magnum Sniper — Supply Air Drop exclusive)
- **Loot, Gear & Healing:** Ground loot in buildings and compounds, Level 1–3 Vests & Helmets with durability and percentage damage reduction, First Aid Kits (restores up to 75 HP), Bandages, Energy Drinks (Boost bar for passive HP regeneration + speed bonus), and Death Crates dropped on elimination.
- **Multi-Phase Blue Zone:** White next-safe-zone indicator, shrinking blue playzone ring, countdown timer, and escalating DPS across 6 phases.
- **Supply Air Drops:** Periodic parachuting crates marked on the minimap with a rising red smoke plume, containing an AWM, `.300 Magnum` ammo, and Level 3 armor.
- **Autonomous AI Bots (27 per match):** Finite-state AI that roams compounds, loots weapons/armor/meds, rotates inward ahead of the Blue Zone, strafes during combat, engages both the player and other bots, and heals when low on HP.
- **100% Procedural Graphics & Audio:** Crisp top-down vector visuals with directional shadows, muzzle flashes, bullet tracers, hit markers, and blood/spark particles—plus procedurally synthesized sound effects (`math`/`array` + `pygame.mixer.Sound`) with automatic silent fallback on headless machines.

---

## Controls

| Key / Input | Action |
| :--- | :--- |
| `W` `A` `S` `D` | Move character |
| `Mouse Move` | Aim weapon |
| `Left Click` | Fire active weapon (hold for full-auto AR/SMG) |
| `R` | Reload active weapon |
| `1` / `2` or `Scroll` | Switch weapon slot |
| `F` | Pick up ground loot / loot Death Crate / loot Supply Drop |
| `4` | Use First Aid Kit (auto-falls back to Bandage if out of Medkits) |
| `5` | Drink Energy Drink (+40 Boost) |
| `6` | Apply Bandage (+18 HP up to 75) |
| `M` | Toggle Enlarged Tactical Map |
| `N` | Mute / Unmute procedural SFX |
| `ESC` | Pause Menu / Close Map |

---

## Architecture Overview

```text
.
├── main.py              # Clean entry point
├── config.py            # Screen, world, weapon stats, armor, colors, zone phases
├── requirements.txt     # Single dependency: pygame
├── LICENSE              # MIT License
├── .gitignore           # Python & IDE exclusions
└── src/
    ├── __init__.py
    ├── game.py          # Main 60 FPS dt loop, state machine, camera, combat & collisions
    ├── entities.py      # Combatant base, Player, Bot AI state machine, Bullet, Particle
    ├── weapons.py       # Weapon dataclass, cooldowns, and factory helpers
    ├── loot.py          # Ground loot spawns, DeathCrates, SupplyDrops, loot icons
    ├── world.py         # Procedural map, enterable buildings, spatial-hash collision & LOS
    ├── zone.py          # 6-phase shrinking BlueZone controller
    ├── hud.py           # HUD overlay, cached minimap, enlarged map, kill feed, menus
    └── sound.py         # Procedural SFX synthesizer with graceful hardware fallback
```

---

## Setup & Run Instructions

### 1. Clone the repository
```bash
git clone https://github.com/your-username/bgmi-2d-battle-royale.git
cd bgmi-2d-battle-royale
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```
*(You can also install `pygame-ce` as a drop-in replacement for `pygame`.)*

### 4. Launch the game
```bash
python main.py
```

---

## Roadmap

- [ ] Throwables: Frag Grenades and Smoke Grenades with area-of-effect physics
- [ ] Drivable vehicles (Dacia / Buggy) along highway networks
- [ ] Weapon attachments (Red Dot, Extended Mag, Compensator)
- [ ] Squads mode (4v4v4 AI teammates) and local LAN multiplayer
- [ ] Persistent match history and local leaderboard stats

---

## License

Released under the [MIT License](LICENSE).
