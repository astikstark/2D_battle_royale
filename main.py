"""Entry point for BGMI 2D: Top-Down Battle Royale."""

from __future__ import annotations

import sys
import pygame

from src.game import Game


def main() -> int:
    """Initialize Pygame and launch the Battle Royale game."""
    pygame.init()
    try:
        game = Game()
        game.run()
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
