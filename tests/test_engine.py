import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
import unittest
import pygame
from ed.engine import Game
from ed import saveio


def fresh():
    pygame.init()
    st = saveio.DEFAULT.copy()
    st["abilities"] = []
    st["beacons"] = []
    # keep tests off the real save file
    saveio.path = lambda: os.path.join(tempfile.gettempdir(), "emberdeep_test_save.json")
    g = Game(st)
    return g


class FakeKeys:
    def __init__(self, down=()):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


class TestEngine(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_load_all_levels(self):
        g = fresh()
        for i in range(6):
            g.load_level(i)
            self.assertIsNotNone(g.p)
            self.assertEqual(g.state, "title")  # load doesn't change state

    def test_sim_no_crash(self):
        g = fresh()
        for i in range(6):
            g.load_level(i)
            g.state = "play"
            for _ in range(600):
                g.step_play(1 / 60, FakeKeys(), set())
                g.update_fx(1 / 60)
            self.assertIsNotNone(g.p)

    def test_walk_moves(self):
        g = fresh()
        g.load_level(0)
        g.state = "play"
        x0 = g.p["box"].x
        for _ in range(120):
            g.step_play(1 / 60, FakeKeys((pygame.K_RIGHT,)), set())
        self.assertGreater(g.p["box"].x, x0)

    def test_jump_rises(self):
        g = fresh()
        g.load_level(0)
        g.state = "play"
        # settle to ground
        for _ in range(120):
            g.step_play(1 / 60, FakeKeys(), set())
        y0 = g.p["box"].y
        g.step_play(1 / 60, FakeKeys(), {pygame.K_SPACE})
        for _ in range(10):
            g.step_play(1 / 60, FakeKeys(), set())
        self.assertLess(g.p["box"].y, y0)

    def test_coin_pickup(self):
        g = fresh()
        g.load_level(0)
        g.state = "play"
        c = next(iter(g.R["coins"]))
        g.p["box"].x = c[0] * 16 + 2
        g.p["box"].y = c[1] * 16 + 2
        g.p["vy"] = 0
        before = g.save["coins"]
        g.touch_tiles()
        self.assertEqual(g.save["coins"], before + 1)

    def test_boss_damage(self):
        g = fresh()
        g.load_level(5)
        g.state = "play"
        b = g.R["boss"]
        hp0 = b["hp"]
        g.damage_boss(3)
        self.assertEqual(b["hp"], hp0 - 3)

    def test_level_clear_unlocks(self):
        g = fresh()
        g.load_level(0)
        g.state = "play"
        g.level_clear()
        self.assertEqual(g.state, "clear")
        self.assertGreaterEqual(g.save["unlocked"], 1)


if __name__ == "__main__":
    unittest.main()
