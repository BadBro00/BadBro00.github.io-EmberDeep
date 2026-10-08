import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import unittest
import pygame
from ed import art


class TestArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_all_sprites(self):
        for name in ["p1", "p2", "pj", "cr1", "cr2", "ho", "bat1", "bat2",
                     "tur", "coin1", "coin2", "heart", "key", "spike",
                     "torch", "beacon", "sign", "ghost", "boss"]:
            s = art.sprite(name)
            self.assertGreater(s.get_width(), 0, name)
            # not fully transparent
            self.assertIsNotNone(s.get_bounding_rect(), name)

    def test_tiles(self):
        for ch in "#=BRD~":
            s = art.tile(ch)
            self.assertEqual((s.get_width(), s.get_height()), (16, 16), ch)


if __name__ == "__main__":
    unittest.main()
