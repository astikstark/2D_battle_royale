"""Procedural sound effect synthesizer with graceful audio fallback."""

from __future__ import annotations

import array
import math
import random
from typing import Dict, Optional

import pygame


class SoundManager:
    """Synthesizes and plays procedural SFX using Python stdlib + pygame.mixer.

    If audio hardware or pygame.mixer is unavailable, all methods degrade
    gracefully into silent no-ops without raising exceptions.
    """

    SAMPLE_RATE = 22050

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self.muted = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}

        if not enabled:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=self.SAMPLE_RATE,
                    size=-16,
                    channels=1,
                    buffer=512,
                )
            self.enabled = True
            self._build_sound_bank()
        except Exception:
            # Headless environment or missing audio device
            self.enabled = False
            self.sounds.clear()

    def _make_sound(self, samples: array.array) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        try:
            return pygame.mixer.Sound(buffer=samples.tobytes())
        except Exception:
            return None

    def _synthesize_gunshot(
        self,
        duration: float,
        base_freq: float,
        noise_mix: float,
        decay: float,
        volume: float,
    ) -> array.array:
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array("h")
        rng = random.Random(int(base_freq * 100) + n_samples)
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * decay)
            # Pitch-dropping punch transient
            freq = base_freq * math.exp(-t * 14.0) + 45.0
            tone = math.sin(2.0 * math.pi * freq * t)
            noise = rng.uniform(-1.0, 1.0)
            sample = ((1.0 - noise_mix) * tone + noise_mix * noise) * env * volume
            clamped = max(-1.0, min(1.0, sample))
            buf.append(int(clamped * 32767))
        return buf

    def _synthesize_tone_sequence(
        self,
        notes: list[tuple[float, float, float]],
        volume: float = 0.4,
    ) -> array.array:
        buf = array.array("h")
        for freq, dur, decay in notes:
            n_samples = int(self.SAMPLE_RATE * dur)
            for i in range(n_samples):
                t = i / self.SAMPLE_RATE
                env = math.exp(-t * decay)
                # Slight harmonic richness
                wave = (
                    0.75 * math.sin(2.0 * math.pi * freq * t)
                    + 0.25 * math.sin(2.0 * math.pi * freq * 2.0 * t)
                )
                sample = max(-1.0, min(1.0, wave * env * volume))
                buf.append(int(sample * 32767))
        return buf

    def _synthesize_click(self, freq: float, duration: float, volume: float) -> array.array:
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array("h")
        rng = random.Random(int(freq))
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * 48.0)
            sig = 0.65 * math.sin(2.0 * math.pi * freq * t) + 0.35 * rng.uniform(-1.0, 1.0)
            sample = max(-1.0, min(1.0, sig * env * volume))
            buf.append(int(sample * 32767))
        return buf

    def _build_sound_bank(self) -> None:
        raw_bank = {
            "pistol": self._synthesize_gunshot(0.11, 240.0, 0.55, 32.0, 0.42),
            "smg": self._synthesize_gunshot(0.085, 290.0, 0.60, 40.0, 0.36),
            "ar": self._synthesize_gunshot(0.13, 195.0, 0.65, 28.0, 0.48),
            "akm": self._synthesize_gunshot(0.15, 155.0, 0.68, 23.0, 0.54),
            "shotgun": self._synthesize_gunshot(0.24, 115.0, 0.80, 14.0, 0.65),
            "sniper": self._synthesize_gunshot(0.32, 130.0, 0.72, 10.5, 0.72),
            "reload": self._synthesize_tone_sequence(
                [(620.0, 0.055, 25.0), (880.0, 0.075, 22.0)], volume=0.32
            ),
            "empty": self._synthesize_click(980.0, 0.04, 0.30),
            "hit": self._synthesize_click(1450.0, 0.045, 0.38),
            "kill": self._synthesize_tone_sequence(
                [(740.0, 0.06, 18.0), (1110.0, 0.11, 14.0)], volume=0.40
            ),
            "pickup": self._synthesize_tone_sequence(
                [(520.0, 0.045, 24.0), (780.0, 0.065, 22.0)], volume=0.28
            ),
            "heal": self._synthesize_tone_sequence(
                [(440.0, 0.09, 10.0), (554.0, 0.09, 10.0), (659.0, 0.14, 9.0)],
                volume=0.32,
            ),
            "zone_tick": self._synthesize_tone_sequence(
                [(180.0, 0.08, 22.0)], volume=0.25
            ),
            "airdrop": self._synthesize_tone_sequence(
                [(330.0, 0.16, 6.0), (440.0, 0.18, 6.0), (523.0, 0.24, 5.0)],
                volume=0.30,
            ),
            "victory": self._synthesize_tone_sequence(
                [
                    (523.25, 0.13, 6.0),
                    (659.25, 0.13, 6.0),
                    (783.99, 0.15, 5.0),
                    (1046.50, 0.35, 3.5),
                ],
                volume=0.45,
            ),
            "defeat": self._synthesize_tone_sequence(
                [(392.0, 0.18, 6.0), (349.23, 0.18, 6.0), (293.66, 0.32, 4.5)],
                volume=0.38,
            ),
        }

        for name, buf in raw_bank.items():
            snd = self._make_sound(buf)
            if snd is not None:
                self.sounds[name] = snd

    def play(self, name: str, volume_scale: float = 1.0) -> None:
        """Play a named sound effect with optional distance-based attenuation."""
        if not self.enabled or self.muted or volume_scale <= 0.02:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            snd.set_volume(max(0.0, min(1.0, volume_scale)))
            snd.play()
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        """Toggle mute state and return the new muted status."""
        self.muted = not self.muted
        return self.muted
