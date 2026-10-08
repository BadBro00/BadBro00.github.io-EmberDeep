# EMBERDEEP — agent handoff

> Last updated: 2026-10-08. Read this first in any new session.
> Working directory: `/home/eugm/Scrivania/OC/emberdeep`
> Run from source: `./run.sh` (venv auto-setup) · Standalone: `./dist/emberdeep` (14 MB onefile)
> Tests: `.venv/bin/python -m unittest discover -s tests` (23 green, headless)

## 1. What this is (and why)

User called the previous single-file arcade game "shitty" and asked for a **whole standalone
game, pixel art acceptable**. Chose: desktop exe (user-confirmed) + genre free choice →
**EMBERDEEP: The Hollow Crown**, a 6-level pixel-art action-platformer (pygame, exe via
PyInstaller). Full loop: title → story intro → 5 zones + boss → victory, with save/continue,
level select, pause, secrets, abilities, mute. Distinct from `neural-path` (puzzle) and
`voidharvest` (arcade); its own folder so old projects are untouched.

## 2. Layout

```text
game.py            # thin entry (imports ed, runs Game)
ed/
  engine.py        # ~1000 lines: states, step_play, foes, boss FSM, camera, HUD, render
  levels.py        # 6 ASCII maps + story cards/signs/gifts; validate() for tests
  art.py           # string-map sprites, procedural tiles, 5x7 bitmap font + draw_text
  physics.py       # pure AABB move_body (no pygame)
  audio.py         # PCM synth (pcm_tone/music_loop_bytes testable); mixer optional
  saveio.py        # save.json; frozen-aware (next to exe)
tests/             # test_physics/levels/art/saveio/engine/fontaudio — 23 tests
emberdeep.spec     # onefile build (console=False, excludes tkinter/numpy/PIL)
requirements.txt run.sh run.bat .gitignore README.md
dist/emberdeep     # built 2026-10-08, smoke-tested (rebuilt after saveio fix)
save.json          # runtime player save, gitignored, absent on fresh checkout
```

## 3. Verification done (all green 2026-10-08)

- **23 unittests OK**: physics (landing/walls/no-tunnel), levels (validate all, beacon grounded,
  boss only L6, gifts), art (all sprites/tiles build), save roundtrip + corrupt fallback,
  engine headless (load all 6, 600-step sims, walk/jump/coin/boss-damage/clear-unlock),
  font renders + PCM/WAV bytes valid.
- **Headless screenshots** (`/tmp/opencode/shots/*.png`, ephemeral): title + L1/L2/L6 inspected —
  title menu, HUD, coins, platforms, sign, torch, heart, boss bar all render. Fixed from shots:
  level-name/boss-bar overlap (name drops to y=34 when boss active).
- **Exe**: PyInstaller onefile 14 MB; `timeout 8 dist/emberdeep` under dummy SDL → still running
  (exit 124), no import errors.

## 4. Environment gotchas (important)

- **pygame 2.6.1 on Python 3.14 here is half-broken**: `pygame.font` and `pygame.mixer` C
  extensions fail to import; `pygame.image` can't save PNG. Workarounds IN the code (do not
  revert without checking): built-in 5x7 font (`ed/art.py`), mixer-optional audio
  (`ed/audio.py`, silent fallback), BMP screenshots + ImageMagick convert for checks.
  Only system Python 3.14 exists (`/usr/bin/python3.14`), so the venv pins to it.
- `saveio.path()` is frozen-aware; **rebuild the exe after touching saveio/engine**.
- Spec sets `console=False`: exe logs nothing; for debugging build once with `console=True`.
- `.venv/`, `dist/`, `build/`, `save.json` are gitignored. Engine tests monkeypatch
  `saveio.path` to temp so the suite never dirties the repo.

## 5. Known issues / what to fix

1. **No real playthrough yet** (biggest risk): sims walk right and pick coins, but nobody has
   completed L1→L6 by actually playing. Jump reach is ~3.2 tiles; some optional coin platforms
   (e.g. LV0 y7 row) may be unreachable — verify on a real run and tune `JUMP_V`/maps.
2. **Level-up-style edge**: `openLevelUp` analog — `say()` dialog during `die()` fade can stack
   (e.g. key pickup text while dying). Rare; guard `say()` when `p["dead"]>0`.
3. **Movers**: one-way + carry works, but standing under a descending mover clips into tiles
   (no crush handling — player gets pushed into floor and `move_body` clamps; acceptable).
4. **No gamepad/touch** (keyboard only) and no key remapping.
5. **Silent on this machine** (mixer missing): melodies unheard — verify SFX/music on a Windows
   build or older-Python Linux before calling audio "done".
6. **Windows/macOS exes not built** (Linux only). `run.bat` exists but untested; build on Windows
   via `pyinstaller emberdeep.spec` there.
7. Exe **UPX** enabled in spec — if corporate AV flags it, set `upx=False` and rebuild.

## 6. Suggested next steps (pick one)

1. **Human playtest pass** (highest value): full L1→boss run, fix jump tuning, enemy density,
   boss difficulty, then bump `best_time`/par display.
2. **Juice**: dash ghosts, slash particles per enemy type, coin magnet, boss intro card + HP
   smooth-drain, pause-screen controls recap.
3. **Content**: L7 endless shaft / time-trial mode + `?seed=`-style daily — needs harness first.
4. **CI**: GH Action (pinned Python ≤3.12 where pygame wheels are whole) running unittest +
   PyInstaller build artifact.

## 7. Working conventions

- Keep art/procgen code-only unless assets earn their weight (single-file exe story).
- Verify by execution: unittest + headless sim/screenshots + real 5-min playtest for balance.
- Reference code as `path:line_number`. Short factual replies; no emojis unless asked.
- **Always rewrite this `handoff.md` when stopping.**
