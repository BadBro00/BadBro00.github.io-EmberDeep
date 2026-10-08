import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import unittest
from ed.physics import AABB, move_body


class TestPhysics(unittest.TestCase):
    def test_fall_lands(self):
        box = AABB(0, 0, 10, 10)
        solids = [AABB(-50, 32, 200, 16)]
        vy = 0.0
        hit = False
        for _ in range(120):
            vy = min(vy + 900 / 60, 420)
            h = move_body(box, 0, vy, 1 / 60, solids, 2)
            if h["bottom"]:
                hit = True
                break
        self.assertTrue(hit)
        self.assertAlmostEqual(box.y, 22)

    def test_wall_blocks(self):
        box = AABB(0, 0, 10, 10)
        solids = [AABB(20, -50, 16, 200)]
        hit = False
        for _ in range(60):
            h = move_body(box, 120, 0, 1 / 60, solids, 2)
            if h["right"]:
                hit = True
                break
        self.assertTrue(hit)
        self.assertAlmostEqual(box.x, 10)

    def test_no_tunnel_fast(self):
        box = AABB(0, 0, 8, 8)
        solids = [AABB(0, 64, 200, 16)]
        hits = move_body(box, 0, 800, 0.1, solids, 4)
        self.assertTrue(hits["bottom"])
        self.assertLessEqual(box.bottom, 64 + 0.01)

    def test_overlaps(self):
        self.assertTrue(AABB(0, 0, 10, 10).overlaps(AABB(5, 5, 10, 10)))
        self.assertFalse(AABB(0, 0, 10, 10).overlaps(AABB(10, 0, 10, 10)))


if __name__ == "__main__":
    unittest.main()
