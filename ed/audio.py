"""Procedural SFX + chiptune (no audio files).

Mixer is optional: where SDL_mixer is unavailable the game runs silent.
Tone synthesis itself is pure PCM math and unit-testable.
"""
from __future__ import annotations
import math
import struct

SR = 22050
_muted = False
_ok = False
_sounds: dict = {}


def set_muted(m: bool):
    global _muted
    _muted = m
    if _ok:
        try:
            import pygame
            pygame.mixer.music.set_volume(0 if m else 0.35)
        except Exception:
            pass


def muted() -> bool:
    return _muted


def pcm_tone(freq: float, dur: float, kind: str = "square", vol: float = 0.35,
             slide: float = 0.0) -> bytes:
    n = max(1, int(SR * dur))
    buf = bytearray()
    ph = 0.0
    for i in range(n):
        t = i / SR
        f = freq * (1 + slide * t / max(dur, 1e-6))
        ph += 2 * math.pi * f / SR
        if kind == "square":
            v = 1.0 if math.sin(ph) > 0 else -1.0
        elif kind == "noise":
            v = (((i * 1103515245 + 12345) >> 16) & 0xFFFF) / 32768.0 - 1.0
        else:  # sine
            v = math.sin(ph)
        env = 1 - i / n
        s = int(max(-1, min(1, v * vol * env)) * 32767)
        buf += struct.pack("<h", s)
    return bytes(buf)


def have_sound() -> bool:
    return _ok


def init(mute: bool = False):
    global _muted, _ok
    _muted = mute
    try:
        import pygame
        pygame.mixer.init(frequency=SR, size=-16, channels=1)
        _ok = True
    except Exception:
        _ok = False
        return
    defs = {
        "jump": (520, 0.12, "square", 0.25, 0.9),
        "slash": (900, 0.08, "noise", 0.22, -0.4),
        "hit": (180, 0.18, "square", 0.35, -0.7),
        "stomp": (300, 0.12, "square", 0.3, -0.5),
        "coin": (1200, 0.09, "sine", 0.3, 0.6),
        "heart": (440, 0.2, "sine", 0.3, 0.8),
        "check": (660, 0.15, "sine", 0.3, 0.3),
        "door": (220, 0.25, "square", 0.3, 0.5),
        "roar": (90, 0.6, "square", 0.4, -0.5),
        "ui": (700, 0.06, "square", 0.2, 0.1),
        "spring": (350, 0.15, "square", 0.3, 1.2),
        "shoot": (750, 0.1, "square", 0.2, -0.6),
    }
    import pygame as _pg
    for k, (f, d, w, v, s) in defs.items():
        try:
            _sounds[k] = _pg.mixer.Sound(buffer=pcm_tone(f, d, w, v, s))
        except Exception:
            pass
    set_muted(mute)


def play(name: str):
    if _muted or not _ok:
        return
    s = _sounds.get(name)
    if s is not None:
        try:
            s.play()
        except Exception:
            pass


def music_loop_bytes(variant: int = 0) -> bytes:
    """One chiptune loop as raw PCM (testable without mixer)."""
    import io
    import wave
    scale = [0, 3, 5, 7, 10, 12]
    base = [110, 98, 87, 82][variant % 4]
    notes = []
    for bar in range(4):
        for st in range(8):
            deg = scale[(st * 2 + bar) % len(scale)]
            notes.append(base * (2 ** (deg / 12)) * (2 if st % 4 == 2 else 1))
    dur = 0.14
    buf = bytearray()
    for f in notes:
        n = int(SR * dur)
        for i in range(n):
            t = i / SR
            v = (1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0) * 0.16
            v += math.sin(2 * math.pi * f / 2 * t) * 0.08
            buf += struct.pack("<h", int(max(-1, min(1, v)) * 32767))
    bio = io.BytesIO()
    w = wave.open(bio, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(bytes(buf))
    w.close()
    return bio.getvalue()


def music(variant: int = 0):
    if not _ok:
        return
    if _muted:
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass
        return
    try:
        import io
        import pygame
        bio = io.BytesIO(music_loop_bytes(variant))
        pygame.mixer.music.load(bio, "wav")
        pygame.mixer.music.play(-1)
        pygame.mixer.music.set_volume(0.35)
    except Exception:
        pass
