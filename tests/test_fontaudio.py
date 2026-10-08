import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import unittest
import pygame
from ed import art
from ed.audio import pcm_tone, music_loop_bytes


class TestFontAudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_font_renders(self):
        s = pygame.Surface((200, 30))
        art.draw_text(s, "EMBERDEEP 123 > E!", 0, 0)
        w, h = art.text_size("ABC")
        self.assertEqual((w, h), ((3 * 6 - 1), 7))
        # something was drawn (non-black pixel)
        self.assertTrue(any(s.get_at((x, y))[:3] != (0, 0, 0)
                            for x in range(200) for y in range(30)))

    def test_font_all_used_chars(self):
        s = pygame.Surface((400, 100))
        art.draw_text(s, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,:;!?'\"+-*/()><=%_ —", 0, 0)

    def test_pcm(self):
        b = pcm_tone(440, 0.1)
        self.assertEqual(len(b), int(22050 * 0.1) * 2)
        w = music_loop_bytes(1)
        self.assertTrue(w[:4] == b"RIFF")


if __name__ == "__main__":
    unittest.main()
