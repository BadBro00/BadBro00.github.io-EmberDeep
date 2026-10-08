# EMBERDEEP — the hollow crown

A complete pixel-art action-platformer for desktop. 6 hand-built levels, 4 enemy types,
a multi-phase boss, sword combat + stomps, dash & double-jump unlocks, keys/doors,
checkpoints, secrets, story dialog, persistent save, procedural art + music. No asset files.

## Play (standalone, no Python needed)

```bash
./dist/emberdeep        # 14 MB single file, Linux x86-64
```

## Play from source

```bash
./run.sh                # Linux: venv + deps auto-setup, then runs
run.bat                 # Windows: same via `py` launcher
# or manually: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
#              .venv/bin/python game.py
```

## Controls

- Move `A/D` or arrows · Jump `Z`/`Space`/`Up` (hold = higher)
- Slash `X`/`J` (kills, breaks cracked rock, deflects orbs) · Stomp by landing on heads
- Dash `Shift`/`C` (gift in L2) · Double jump (gift in L4)
- Read signs `E` · Pause `Esc`/`P` · Mute `M`

Goal per level: touch the beacon. L6: kill the Hollow King first.

## Project structure

```text
game.py          # thin entry point
ed/
  engine.py      # game states, physics step, combat, boss AI, camera, HUD, dialog
  levels.py      # 6 ASCII maps + story (no deps)
  art.py         # pixel sprites + tiles + 5x7 bitmap font (no SDL_ttf needed)
  physics.py     # pure AABB collision (no pygame)
  audio.py       # PCM-chiptune synth; silent fallback if SDL_mixer missing
  saveio.py      # save.json (next to exe when frozen)
tests/           # 23 stdlib unittests (run headless, dummy SDL drivers)
emberdeep.spec   # PyInstaller onefile build -> dist/emberdeep
requirements.txt run.sh run.bat
```

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v   # 23 tests, no display/sound needed
```

## Notes

- Art is 100% code (sprites as string maps, tiles procedural, built-in pixel font).
- Sound: procedural WAV synth. If `pygame.mixer` is unavailable (e.g. pygame 2.6.1 on
  Python 3.14, where its `mixer`/`font` extensions don't import), the game runs silent;
  mute toggle still works and sound returns on builds with a working mixer.
- Save: `save.json` next to the exe (or repo root from source).
