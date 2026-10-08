import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import unittest
from ed import levels


class TestLevels(unittest.TestCase):
    def test_all_validate(self):
        for i in range(len(levels.LEVELS)):
            self.assertEqual(levels.validate(i), [], f"level {i}")

    def test_spawn_beacon(self):
        for i in range(len(levels.LEVELS)):
            e = levels.parse(i)["ents"]
            self.assertIsNotNone(e["spawn"], f"L{i} spawn")
            self.assertIsNotNone(e["beacon"], f"L{i} beacon")

    def test_reachable_beacon_row(self):
        # beacon sits above solid ground (or arena floor)
        for i in range(len(levels.LEVELS)):
            d = levels.parse(i)
            g, e = d["grid"], d["ents"]
            bx, by = e["beacon"]
            below = [g[yy][bx] for yy in range(by + 1, min(by + 4, d["h"]))]
            self.assertTrue(any(c in "#=B" for c in below), f"L{i} beacon floats")

    def test_boss_only_last(self):
        for i in range(5):
            self.assertIsNone(levels.parse(i)["ents"]["boss"])
        self.assertIsNotNone(levels.parse(5)["ents"]["boss"])

    def test_gifts(self):
        gives = [lv["give"] for lv in levels.LEVELS]
        self.assertIn("dash", gives)
        self.assertIn("double", gives)


if __name__ == "__main__":
    unittest.main()
