"""EMBERDEEP — the hollow crown. Entry point (kept thin)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

__all__ = ["main"]


def main():
    import pygame
    from ed.engine import Game
    from ed import saveio

    pygame.init()
    try:
        game = Game(saveio.load())
        game.run()
    except SystemExit:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
