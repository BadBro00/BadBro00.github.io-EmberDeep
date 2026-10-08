"""EMBERDEEP engine: states, physics step, combat, boss, camera, HUD, dialog."""
from __future__ import annotations
import math
import random
import pygame

from . import art, audio, levels, saveio
from .levels import TILE, VIEW_W, VIEW_H
from .physics import AABB, move_body

GRAV = 900.0
MOVE = 115.0
JUMP_V = 305.0
COYOTE = 0.10
BUFFER = 0.12
SCALE = 2

SOLID_TILES = set("#=BR")


def solid_here(grid, tx, ty, opened_doors, broken_rocks) -> bool:
    if ty < 0:
        return False
    if tx < 0 or ty >= len(grid) or tx >= len(grid[0]):
        return True  # side/bottom walls
    ch = grid[ty][tx]
    if ch == "D" and (tx, ty) in opened_doors:
        return False
    if ch == "R" and (tx, ty) in broken_rocks:
        return False
    return ch in SOLID_TILES or ch == "D" or ch == "R"


def solids_for(grid, box: AABB, opened_doors, broken_rocks) -> list[AABB]:
    tx0 = max(0, int(box.x // TILE) - 1)
    ty0 = max(0, int(box.y // TILE) - 1)
    tx1 = int((box.x + box.w) // TILE) + 1
    ty1 = int((box.y + box.h) // TILE) + 1
    out = []
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            if solid_here(grid, tx, ty, opened_doors, broken_rocks):
                out.append(AABB(tx * TILE, ty * TILE, TILE, TILE))
    return out


class Game:
    def __init__(self, save: dict):
        self.save = save
        self.screen = None
        self.view = pygame.Surface((VIEW_W, VIEW_H))
        self.clock = pygame.time.Clock()
        self.state = "title"
        self.ti = 0  # title selection
        self.li = 0  # level select index
        self.li_idx = 0
        self.shake = 0.0
        self.time = 0.0
        self.msg: list[str] = []
        self.msg_t = 0.0
        self.card: list[str] = []
        self.card_t = 0.0
        self.dlg: list[tuple[str, str]] = []
        self.fade = 0.0
        self.fade_to = ""
        self.run_t = 0.0
        self.paused_sel = 0
        self.over_sel = 0
        self.embers = [{"x": random.random() * VIEW_W, "y": random.random() * VIEW_H,
                        "s": random.uniform(4, 18)} for _ in range(40)]
        self.level_idx = 0
        self.R = None
        self.p = None
        self.cam = [0.0, 0.0]
        self.deaths_lvl = 0
        self.coins_lvl = 0
        audio.init(save.get("muted", False))

    # ---------- level runtime ----------
    def load_level(self, idx: int):
        self.level_idx = idx
        d = levels.parse(idx)
        grid, ents = d["grid"], d["ents"]
        sx, sy = ents["spawn"]
        self.R = {"grid": grid, "w": d["w"], "h": d["h"], "ents": ents,
                  "coins": set(ents["coins"]), "hearts": set(ents["hearts"]),
                  "keys": set(ents["keys"]), "maxhp": set(ents["maxhp"]),
                  "opened": set(), "broken": set(),
                  "foes": [], "shots": [], "parts": [], "floats": [],
                  "checks": set(), "respawn": (sx * TILE, sy * TILE),
                  "movers": [], "slash_id": 0, "boss": None,
                  "beacon_open": idx != 5, "won": False, "init_foes": True}
        for i, (x, y) in enumerate(ents["mplats_h"]):
            self.R["movers"].append({"x": x * TILE, "y": y * TILE, "w": 32, "h": 8,
                                     "ax": "h", "rng": 48, "t": i * 1.7, "px": x * TILE, "py": y * TILE})
        for i, (x, y) in enumerate(ents["mplats_v"]):
            self.R["movers"].append({"x": x * TILE, "y": y * TILE, "w": 32, "h": 8,
                                     "ax": "v", "rng": 40, "t": i * 2.3, "px": x * TILE, "py": y * TILE})
        self.spawn_foes()
        if ents["boss"]:
            bx, by = ents["boss"]
            self.R["boss"] = {"box": AABB(bx * TILE - 8, by * TILE - 16, 28, 30),
                              "hp": 26, "max": 26, "vx": 0, "vy": 0, "st": "idle",
                              "t": 1.2, "face": -1, "flash": 0, "dead": False}
            audio.play("roar")
        maxhp = 5 + (1 if "hp1" in self.save.get("abilities", []) else 0)
        self.p = {"box": AABB(sx * TILE + 2, sy * TILE + 2, 12, 14),
                  "vx": 0.0, "vy": 0.0, "face": 1, "ground": False,
                  "coy": 0.0, "buf": 0.0, "jumps": 0, "hp": maxhp, "maxhp": maxhp,
                  "inv": 0.0, "slash_t": 0.0, "slash_cd": 0.0, "slash_hit": set(),
                  "dash_t": 0.0, "dash_cd": 0.0, "has_key": False, "_had_key": False,
                  "anim": 0.0, "dead": 0.0, "spring_cd": 0.0}
        self.cam = [self.p["box"].x - VIEW_W / 2, self.p["box"].y - VIEW_H / 2]
        self.run_t = 0.0
        self.deaths_lvl = 0
        self.coins_lvl = 0
        meta = d["meta"]
        self.card = [meta["name"] + " — " + meta["sub"]] + meta["card"]
        self.card_t = 3.0
        audio.music(meta["music"])

    def spawn_foes(self):
        R = self.R
        R["foes"] = []
        e = R["ents"]
        for x, y in e["crawlers"]:
            R["foes"].append({"kind": "crawl", "box": AABB(x * TILE, y * TILE + 4, 12, 10),
                                     "vx": -30, "t": random.random() * 5, "hp": 1, "flash": 0})
        for x, y in e["hoppers"]:
            R["foes"].append({"kind": "hop", "box": AABB(x * TILE + 2, y * TILE, 12, 14),
                                    "vx": 0, "vy": 0, "t": random.random() * 5, "hp": 2,
                                    "flash": 0, "ground": False})
        for x, y in e["bats"]:
            R["foes"].append({"kind": "bat", "box": AABB(x * TILE, y * TILE, 14, 10),
                                   "t": random.random() * 5, "hp": 1, "flash": 0,
                                   "hx": x * TILE, "hy": y * TILE})
        for x, y in e["turrets"]:
            R["foes"].append({"kind": "tur", "box": AABB(x * TILE, y * TILE, 14, 16),
                                    "t": 1.0 + random.random(), "hp": 2, "flash": 0})

    # ---------- player damage/death ----------
    def hurt(self, n: int = 1, kx: float = 0.0):
        p = self.p
        if p["inv"] > 0 or p["dead"] > 0 or self.state != "play":
            return
        p["hp"] -= n
        p["inv"] = 1.0
        p["vx"] = kx
        p["vy"] = min(p["vy"], -160)
        audio.play("hit")
        self.shake = 0.25
        self.burst(p["box"].x + 6, p["box"].y + 7, 8, (230, 60, 70))
        if p["hp"] <= 0:
            p["dead"] = 1.2
            audio.play("roar")

    def die(self, silent=False):
        p = self.p
        self.save["deaths"] = self.save.get("deaths", 0) + 1
        self.deaths_lvl += 1
        sx, sy = self.R["respawn"]
        p["box"].x, p["box"].y = sx + 2, sy + 2
        p["vx"] = p["vy"] = 0
        p["hp"] = p["maxhp"]
        p["inv"] = 1.5
        p["has_key"] = False
        if p.get("_had_key") and not self.R["opened"]:
            self.R["keys"] = set(self.R["ents"]["keys"])
        self.spawn_foes()
        self.R["shots"] = []
        self.cam = [p["box"].x - VIEW_W / 2, p["box"].y - VIEW_H / 2]

    def burst(self, x, y, n, color):
        for _ in range(n):
            self.R["parts"].append({"x": x, "y": y, "vx": random.uniform(-90, 90),
                                    "vy": random.uniform(-140, 20), "life": random.uniform(.25, .6),
                                    "c": color})

    def float(self, x, y, txt, c=(255, 255, 255)):
        self.R["floats"].append({"x": x, "y": y, "txt": txt, "life": 0.9, "c": c})

    # ---------- update ----------
    def step_play(self, dt: float, keys, pressed: set):
        R, p = self.R, self.p
        self.run_t += dt
        if p["dead"] > 0:
            p["dead"] -= dt
            if p["dead"] <= 0:
                self.die()
            self.update_fx(dt)
            return
        # timers
        p["inv"] = max(0, p["inv"] - dt)
        p["slash_cd"] = max(0, p["slash_cd"] - dt)
        p["dash_cd"] = max(0, p["dash_cd"] - dt)
        p["spring_cd"] = max(0, p["spring_cd"] - dt)
        # horizontal
        L = keys[pygame.K_LEFT] or keys[pygame.K_a]
        Rt = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        ax = (1 if Rt else 0) - (1 if L else 0)
        if p["dash_t"] <= 0:
            p["vx"] += ((ax * MOVE) - p["vx"]) * min(1, dt * 14)
            if ax:
                p["face"] = ax
        else:
            p["dash_t"] -= dt
        # jump buffer / coyote
        jump_hit = {pygame.K_z, pygame.K_SPACE, pygame.K_UP, pygame.K_w} & pressed
        if jump_hit:
            p["buf"] = BUFFER
        else:
            p["buf"] = max(0, p["buf"] - dt)
        p["coy"] = max(0, p["coy"] - dt)
        want_jump = p["buf"] > 0 and (p["ground"] or p["coy"] > 0)
        dbl = "double" in self.save.get("abilities", [])
        if p["buf"] > 0 and not want_jump and dbl and p["jumps"] < 1 and not p["ground"]:
            p["vy"] = JUMP_V * 0.92
            p["jumps"] += 1
            p["buf"] = 0
            audio.play("jump")
            self.burst(p["box"].x + 6, p["box"].y + 14, 5, (180, 110, 250))
        if want_jump:
            p["vy"] = -JUMP_V
            p["ground"] = False
            p["coy"] = 0
            p["buf"] = 0
            audio.play("jump")
            self.burst(p["box"].x + 6, p["box"].y + 14, 5, (200, 200, 210))
        # dash
        if "dash" in self.save.get("abilities", []) and p["dash_cd"] <= 0 and \
                ({pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_k} & pressed):
            p["dash_t"] = 0.16
            p["dash_cd"] = 0.7
            p["vx"] = p["face"] * 260
            p["vy"] = 0
            audio.play("slash")
        # slash
        if ({pygame.K_x, pygame.K_j} & pressed) and p["slash_cd"] <= 0:
            p["slash_t"] = 0.16
            p["slash_cd"] = 0.34
            p["slash_hit"] = set()
            R["slash_id"] += 1
            audio.play("slash")
        p["slash_t"] = max(0, p["slash_t"] - dt)
        # gravity
        p["vy"] = min(p["vy"] + GRAV * dt, 420)
        if p["dash_t"] > 0:
            p["vy"] = 0
        # integrate
        solids = solids_for(R["grid"], p["box"], R["opened"], R["broken"])
        # movers as one-way handled after tile move
        hits = move_body(p["box"], p["vx"], p["vy"], dt, solids, 2)
        was_ground = p["ground"]
        p["ground"] = hits["bottom"]
        if hits["bottom"]:
            p["coy"] = COYOTE
            p["jumps"] = 0
            if not was_ground and p["vy"] > 200:
                self.burst(p["box"].x + 6, p["box"].y + 14, 4, (160, 150, 140))
        if hits["top"]:
            p["vy"] = max(p["vy"], 0)
        if hits["left"] or hits["right"]:
            if p["dash_t"] > 0:
                p["dash_t"] = 0
            p["vx"] = 0
        if p["ground"]:
            p["vy"] = 0
        # one-way movers
        for m in R["movers"]:
            m["px"], m["py"] = m["x"], m["y"]
            m["t"] += dt
        self.update_movers(dt)
        # ride movers (carry + land)
        for m in R["movers"]:
            top = AABB(m["x"], m["y"], m["w"], m["h"])
            if p["vy"] >= 0 and p["box"].bottom <= top.top + 8 and \
                    p["box"].bottom + p["vy"] * dt + 8 >= top.top and \
                    p["box"].right > top.left and p["box"].left < top.right:
                p["box"].y = top.top - p["box"].h
                p["vy"] = 0
                p["ground"] = True
                p["coy"] = COYOTE
                p["jumps"] = 0
                p["box"].x += m["x"] - m["px"]
        p["anim"] += dt * (6 if abs(p["vx"]) > 20 and p["ground"] else 2)
        # interactions below
        self.touch_tiles()
        self.update_foes(dt)
        self.update_shots(dt)
        self.slash_hits()
        self.update_boss(dt)
        self.update_fx(dt)
        # fall out
        if p["box"].y > R["h"] * TILE + 40:
            self.hurt(1)
            if p["hp"] > 0:
                sx, sy = R["respawn"]
                p["box"].x, p["box"].y = sx + 2, sy + 2
                p["vx"] = p["vy"] = 0

    def update_movers(self, dt):
        for m in self.R["movers"]:
            # base position stored implicitly: recover by removing oscillation? store base once
            if "bx" not in m:
                m["bx"], m["by"] = m["x"], m["y"]
            if m["ax"] == "h":
                m["x"] = m["bx"] + math.sin(m["t"] * 1.2) * m["rng"]
            else:
                m["y"] = m["by"] + math.sin(m["t"] * 1.4) * m["rng"]

    def tile_at_px(self, x, y):
        R = self.R
        tx, ty = int(x // TILE), int(y // TILE)
        if 0 <= ty < R["h"] and 0 <= tx < R["w"]:
            return R["grid"][ty][tx], (tx, ty)
        return ".", (tx, ty)

    def touch_tiles(self):
        R, p = self.R, self.p
        box = p["box"]
        # sample body tiles
        for ox in (2, 6, 10):
            for oy in (2, 7, 12):
                ch, (tx, ty) = self.tile_at_px(box.x + ox, box.y + oy)
                if ch == "S" and p["spring_cd"] <= 0:
                    self.hurt(1, kx=120 if box.x + 6 < tx * TILE + 8 else -120)
                elif ch == "~":
                    self.hurt(1)
                    if p["hp"] > 0 and self.state == "play":
                        sx, sy = R["respawn"]
                        box.x, box.y = sx + 2, sy + 2
                        p["vx"] = p["vy"] = 0
                    return
                elif ch == "U" and p["spring_cd"] <= 0 and p["vy"] >= 0:
                    p["vy"] = -460
                    p["spring_cd"] = 0.3
                    audio.play("spring")
        # pickups (center-based radius)
        cx, cy = box.x + 6, box.y + 7
        for c in list(R["coins"]):
            if abs(c[0] * TILE + 8 - cx) < 14 and abs(c[1] * TILE + 8 - cy) < 16:
                R["coins"].discard(c)
                self.save["coins"] = self.save.get("coins", 0) + 1
                self.coins_lvl += 1
                audio.play("coin")
                self.float(c[0] * TILE, c[1] * TILE, "+1", (250, 215, 90))
        for h in list(R["hearts"]):
            if abs(h[0] * TILE + 8 - cx) < 14 and abs(h[1] * TILE + 8 - cy) < 16:
                if p["hp"] < p["maxhp"]:
                    R["hearts"].discard(h)
                    p["hp"] += 1
                    audio.play("heart")
        for k in list(R["keys"]):
            if abs(k[0] * TILE + 8 - cx) < 14 and abs(k[1] * TILE + 8 - cy) < 16:
                R["keys"].discard(k)
                p["has_key"] = True
                p["_had_key"] = True
                audio.play("door")
                self.say([("Wren", "A heavy key. A heavy door, somewhere.")])
        for m in list(R["maxhp"]):
            if abs(m[0] * TILE + 8 - cx) < 14 and abs(m[1] * TILE + 8 - cy) < 16:
                R["maxhp"].discard(m)
                p["maxhp"] += 1
                p["hp"] = p["maxhp"]
                abs_ = self.save.setdefault("abilities", [])
                if "hp1" not in abs_:
                    abs_.append("hp1")
                saveio.save(self.save)
                audio.play("heart")
                self.say([("Wren", "Heart of the mountain! Max HP up.")])
        # checkpoint torches
        for (x, y) in R["ents"]["checks"]:
            if abs(x * TILE + 8 - cx) < 12 and abs(y * TILE + 8 - cy) < 20:
                if R["respawn"] != (x * TILE, y * TILE):
                    R["respawn"] = (x * TILE, y * TILE)
                    R["checks"].add((x, y))
                    p["hp"] = min(p["maxhp"], p["hp"] + 2)
                    audio.play("check")
                    self.float(x * TILE, y * TILE - 8, "LIT", (255, 170, 60))
        # giver ghost
        g = R["ents"]["giver"]
        if g and abs(g[0] * TILE + 8 - cx) < 18 and abs(g[1] * TILE + 8 - cy) < 22:
            give = R.get("give_done", False)
            if not give:
                R["give_done"] = True
                ab = levels.LEVELS[self.level_idx]["give"]
                if ab and ab not in self.save.get("abilities", []):
                    self.save["abilities"].append(ab)
                    self.save["unlocked"] = max(self.save.get("unlocked", 0), self.level_idx)
                    saveio.save(self.save)
                audio.play("check")
                if ab == "dash":
                    self.say([("Keeper", "Take my DASH, smith-child. Press SHIFT / C mid-air."),
                              ("Wren", "The air itself pushes back!")])
                elif ab == "double":
                    self.say([("Keeper", "The sky owes you one more. Jump again — mid-air."),
                              ("Wren", "Two jumps. Nobody jumps twice!")])
        # signs
        # (interaction handled in events: E near sign)
        # beacon
        b = R["ents"]["beacon"]
        if b and R["beacon_open"] and abs(b[0] * TILE + 8 - cx) < 14 and abs(b[1] * TILE + 8 - cy) < 20:
            self.level_clear()

    def say(self, pages: list[tuple[str, str]]):
        self.dlg = list(pages)
        self.state = "dialog"

    # ---------- combat ----------
    def slash_rect(self):
        p = self.p
        if p["face"] > 0:
            return AABB(p["box"].x + 6, p["box"].y - 2, 22, 18)
        return AABB(p["box"].x - 16, p["box"].y - 2, 22, 18)

    def slash_hits(self):
        R, p = self.R, self.p
        if p["slash_t"] <= 0:
            return
        sr = self.slash_rect()
        for f in R["foes"][:]:
            if id(f) in p["slash_hit"]:
                continue
            if sr.overlaps(f["box"]):
                p["slash_hit"].add(id(f))
                self.damage_foe(f, 1, p["face"] * 120)
        # rocks
        for (x, y) in list(R["ents"]["rocks"]):
            if (x, y) in R["broken"]:
                continue
            rb = AABB(x * TILE, y * TILE, TILE, TILE)
            if sr.overlaps(rb):
                R["broken"].add((x, y))
                audio.play("stomp")
                self.burst(x * TILE + 8, y * TILE + 8, 10, (150, 150, 170))
                if random.random() < 0.5:
                    R["coins"].add((x, y - 1))
        # turret orbs can be slashed away
        for s in R["shots"][:]:
            sb = AABB(s["x"] - 3, s["y"] - 3, 6, 6)
            if sr.overlaps(sb):
                R["shots"].remove(s)
                audio.play("slash")
        # boss
        b = R["boss"]
        if b and not b["dead"]:
            bb = b["box"]
            if sr.overlaps(bb):
                if id(b) not in p["slash_hit"]:
                    p["slash_hit"].add(id(b))
                    self.damage_boss(1)

    def damage_foe(self, f, n, kx=0):
        f["hp"] -= n
        f["flash"] = 0.12
        if f["kind"] in ("crawl", "hop", "bat"):
            f["vx"] = kx if isinstance(f.get("vx"), (int, float)) else 0
        self.burst(f["box"].x + 6, f["box"].y + 6, 6, (255, 200, 120))
        if f["hp"] <= 0:
            self.R["foes"].remove(f)
            audio.play("stomp")
            self.burst(f["box"].x + 6, f["box"].y + 6, 12, (255, 150, 80))
            if random.random() < 0.35:
                self.R["coins"].add((int(f["box"].x // TILE), int(f["box"].y // TILE)))
        else:
            audio.play("hit")

    def damage_boss(self, n):
        b = self.R["boss"]
        b["hp"] -= n
        b["flash"] = 0.12
        audio.play("hit")
        self.shake = 0.2
        if b["hp"] <= 0 and not b["dead"]:
            b["dead"] = True
            b["t"] = 1.5
            audio.play("roar")
            self.burst(b["box"].x + 14, b["box"].y + 15, 40, (255, 170, 60))
            self.R["beacon_open"] = True
            self.float(b["box"].x, b["box"].y - 10, "THE CROWN DROPS", (250, 215, 90))

    # ---------- foes ----------
    def update_foes(self, dt):
        R, p = self.R, self.p
        solids_cache = {}
        for f in R["foes"][:]:
            f["flash"] = max(0, f.get("flash", 0) - dt)
            fb, k = f["box"], f["kind"]
            if k == "crawl":
                f["t"] += dt
                solids = solids_for(R["grid"], fb, R["opened"], R["broken"])
                # edge probe: turn if no ground ahead or wall hit
                dir_ = 1 if f["vx"] > 0 else -1
                ahead_x = (fb.x + (fb.w + 2 if dir_ > 0 else -2))
                tx, ty = int(ahead_x // TILE), int((fb.y + fb.h + 4) // TILE)
                ground_ahead = solid_here(R["grid"], tx, ty, R["opened"], R["broken"])
                hits = move_body(fb, f["vx"], 200 * dt, dt, solids, 1)
                if hits["left"] or hits["right"] or not ground_ahead:
                    f["vx"] *= -1
                # touch damage + stomp check
                self.foe_touch(f)
            elif k == "hop":
                f["t"] += dt
                solids = solids_for(R["grid"], fb, R["opened"], R["broken"])
                f["vy"] = min(f.get("vy", 0) + GRAV * dt, 400)
                dx = (p["box"].x - fb.x)
                if f.get("ground") and abs(dx) < 160 and f["t"] > 0.9:
                    f["t"] = 0
                    f["vy"] = -280
                    f["vx"] = max(-90, min(90, dx * 1.2))
                hits = move_body(fb, f["vx"], f["vy"], dt, solids, 2)
                f["ground"] = hits["bottom"]
                if hits["bottom"]:
                    f["vy"] = 0
                    f["vx"] *= 0.8
                self.foe_touch(f)
            elif k == "bat":
                f["t"] += dt
                dx, dy = p["box"].x - fb.x, p["box"].y - fb.y
                d = math.hypot(dx, dy) or 1
                sp = 55 if d > 200 else 85
                fb.x += dx / d * sp * dt + math.sin(f["t"] * 6) * 20 * dt
                fb.y += dy / d * sp * 0.7 * dt + math.cos(f["t"] * 5) * 25 * dt
                self.foe_touch(f)
            elif k == "tur":
                f["t"] -= dt
                dx, dy = (p["box"].x - fb.x), (p["box"].y - fb.y)
                if f["t"] <= 0 and math.hypot(dx, dy) < 260:
                    f["t"] = 2.2
                    d = math.hypot(dx, dy) or 1
                    R["shots"].append({"x": fb.x + 7, "y": fb.y + 4,
                                       "vx": dx / d * 130, "vy": dy / d * 130, "life": 3})
                    audio.play("shoot")
                self.foe_touch(f)
        # remove far-fallen
        R["foes"] = [f for f in R["foes"] if f["box"].y < R["h"] * TILE + 80]

    def foe_touch(self, f):
        p = self.p
        fb = f["box"]
        pb = AABB(p["box"].x - 2, p["box"].y - 2, p["box"].w + 4, p["box"].h + 4)
        if not pb.overlaps(fb):
            return
        # stomp: falling and feet above foe mid
        if p["vy"] > 60 and (p["box"].y + p["box"].h) - fb.y < 10:
            p["vy"] = -240
            audio.play("stomp")
            self.damage_foe(f, 1, 0)
            self.float(fb.x, fb.y - 6, "STOMP", (255, 255, 255))
        else:
            self.hurt(1, kx=140 if p["box"].x < fb.x else -140)

    def update_shots(self, dt):
        R, p = self.R, self.p
        for s in R["shots"][:]:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["life"] -= dt
            tx, ty = int(s["x"] // TILE), int(s["y"] // TILE)
            if solid_here(R["grid"], tx, ty, R["opened"], R["broken"]) or s["life"] <= 0:
                R["shots"].remove(s)
                continue
            if abs(s["x"] - (p["box"].x + 6)) < 9 and abs(s["y"] - (p["box"].y + 7)) < 11:
                R["shots"].remove(s)
                self.hurt(1, kx=s["vx"])

    # ---------- boss ----------
    def update_boss(self, dt):
        R, p = self.R, self.p
        b = R["boss"]
        if not b or b["dead"]:
            if b and b["dead"]:
                b["t"] -= dt
            return
        b["flash"] = max(0, b["flash"] - dt)
        bb = b["box"]
        b["t"] -= dt
        dx = p["box"].x - bb.x
        b["face"] = 1 if dx > 0 else -1
        solids = solids_for(R["grid"], bb, R["opened"], R["broken"])
        if b["st"] == "idle":
            b["vx"] += ((b["face"] * 40) - b["vx"]) * min(1, dt * 4)
            b["vy"] = min(b["vy"] + GRAV * dt, 420)
            hits = move_body(bb, b["vx"], b["vy"], dt, solids, 2)
            if hits["bottom"]:
                b["vy"] = 0
            if b["t"] <= 0:
                b["st"] = random.choice(["slam", "volley", "summon"])
                b["t"] = 0.6
                if b["hp"] < b["max"] / 2:
                    b["t"] = 0.35
        elif b["st"] == "slam":
            # leap toward player then shockwave on landing
            if not b.get("air"):
                b["vy"] = -380
                b["vx"] = max(-160, min(160, dx * 2))
                b["air"] = True
                audio.play("jump")
            b["vy"] = min(b["vy"] + GRAV * dt, 500)
            hits = move_body(bb, b["vx"], b["vy"], dt, solids, 2)
            if hits["bottom"]:
                b["vy"] = 0
                b["air"] = False
                b["st"] = "idle"
                b["t"] = 1.4 if b["hp"] > b["max"] / 2 else 0.9
                audio.play("roar")
                self.shake = 0.4
                self.burst(bb.x + 14, bb.y + 28, 16, (200, 120, 80))
                R["shots"].append({"x": bb.x - 4, "y": bb.y + 22, "vx": -140, "vy": 0, "life": 1.6})
                R["shots"].append({"x": bb.x + 32, "y": bb.y + 22, "vx": 140, "vy": 0, "life": 1.6})
        elif b["st"] == "volley":
            if b["t"] <= 0:
                n = 8 if b["hp"] > b["max"] / 2 else 12
                for i in range(n):
                    a = (i / n) * math.pi * 2 + random.random() * 0.3
                    R["shots"].append({"x": bb.x + 14, "y": bb.y + 10,
                                       "vx": math.cos(a) * 120, "vy": math.sin(a) * 120, "life": 2.5})
                audio.play("shoot")
                b["st"] = "idle"
                b["t"] = 1.6 if b["hp"] > b["max"] / 2 else 1.0
        elif b["st"] == "summon":
            if b["t"] <= 0:
                alive = sum(1 for f in R["foes"] if f["kind"] == "crawl")
                for _ in range(min(2, 4 - alive)):
                    R["foes"].append({"kind": "crawl",
                                      "box": AABB(bb.x + random.uniform(-40, 40), bb.y, 12, 10),
                                      "vx": random.choice([-30, 30]), "t": 0, "hp": 1, "flash": 0})
                audio.play("door")
                b["st"] = "idle"
                b["t"] = 1.6
        # touch damage
        pb = AABB(p["box"].x - 2, p["box"].y - 2, p["box"].w + 4, p["box"].h + 4)
        if pb.overlaps(bb):
            if p["vy"] > 60 and (p["box"].y + p["box"].h) - bb.y < 12:
                p["vy"] = -260
                self.damage_boss(1)
            else:
                self.hurt(1, kx=180 if p["box"].x < bb.x else -180)
        b.pop("jumped", None)

    def update_fx(self, dt):
        R = self.R
        for pt in R["parts"][:]:
            pt["x"] += pt["vx"] * dt
            pt["y"] += pt["vy"] * dt
            pt["vy"] += 300 * dt
            pt["life"] -= dt
            if pt["life"] <= 0:
                R["parts"].remove(pt)
        for f in R["floats"][:]:
            f["y"] -= 22 * dt
            f["life"] -= dt
            if f["life"] <= 0:
                R["floats"].remove(f)
        self.shake = max(0, self.shake - dt)

    # ---------- flow ----------
    def level_clear(self):
        R = self.R
        audio.play("check")
        self.save["unlocked"] = max(self.save.get("unlocked", 0), min(5, self.level_idx + 1))
        if self.level_idx not in self.save.get("beacons", []):
            self.save.setdefault("beacons", []).append(self.level_idx)
        saveio.save(self.save)
        if self.level_idx >= 5:
            self.state = "victory"
            self.save["wins"] = self.save.get("wins", 0) + 1
            saveio.save(self.save)
        else:
            self.state = "clear"

    def start_run(self, idx: int):
        self.load_level(idx)
        self.state = "play"

    # ================= RENDER =================
    def draw_text(self, s, x, y, c=(235, 240, 255), big=False, center=False):
        sc = 3 if big else 1
        w, _ = art.text_size(s, sc)
        if center:
            x -= w // 2
        art.draw_text(self.view, s, int(x), int(y), c, sc)

    def render(self):
        v = self.view
        v.fill((8, 8, 18))
        if self.state == "title":
            self.render_title()
        elif self.R is None:
            pass
        else:
            self.render_world()
            if self.state in ("play", "dialog", "pause", "clear"):
                self.render_hud()
            if self.card_t > 0 and self.state == "play":
                self.render_card()
            if self.state == "dialog":
                self.render_dialog()
            if self.state == "pause":
                self.render_pause()
            if self.state == "clear":
                self.render_clear()
            if self.state == "victory":
                self.render_victory()
        # scale up
        w, h = self.screen.get_size()
        pygame.transform.scale(v, (w, h), self.screen)

    def sky(self, variant):
        cols = [(10, 12, 30), (16, 10, 26), (10, 18, 24), (24, 8, 20)]
        self.view.fill(cols[variant % 4])
        # stars
        for i in range(60):
            x = (i * 97) % VIEW_W
            y = (i * 57) % 160
            self.view.set_at((x, y), (120, 130, 180))
        # hills parallax
        cx = self.cam[0] * 0.3 if self.R else 0
        for layer, (col, amp, base) in enumerate([((24, 26, 54), 26, 190), ((36, 34, 70), 18, 215)]):
            pts = []
            for x in range(0, VIEW_W + 8, 8):
                wx = x + cx * (0.5 + layer * 0.3)
                y = base + math.sin(wx * 0.02 + layer * 2) * amp
                pts.append((x, y))
            pts += [(VIEW_W, VIEW_H), (0, VIEW_H)]
            pygame.draw.polygon(self.view, col, [(int(x), int(y)) for x, y in pts])

    def render_world(self):
        R = self.R
        meta = levels.LEVELS[self.level_idx]
        self.sky(meta["music"])
        cx = int(self.cam[0] + (random.uniform(-1, 1) * self.shake * 14 if self.shake else 0))
        cy = int(self.cam[1] + (random.uniform(-1, 1) * self.shake * 14 if self.shake else 0))
        # tiles
        x0, y0 = max(0, cx // TILE), max(0, cy // TILE)
        x1, y1 = min(R["w"] - 1, (cx + VIEW_W) // TILE + 1), min(R["h"] - 1, (cy + VIEW_H) // TILE + 1)
        tick = int(self.run_t * 4)
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                ch = R["grid"][ty][tx]
                if ch == ".":
                    continue
                if ch == "D" and (tx, ty) in R["opened"]:
                    continue
                if ch == "R" and (tx, ty) in R["broken"]:
                    continue
                if ch in ("S", "~"):
                    if ch == "S":
                        self.view.blit(art.sprite("spike"), (tx * TILE - cx, ty * TILE - cy))
                    else:
                        self.view.blit(art.tile("~", tick), (tx * TILE - cx, ty * TILE - cy))
                elif ch in "#=BRD":
                    self.view.blit(art.tile(ch if ch != "D" else "D", tick), (tx * TILE - cx, ty * TILE - cy))
                elif ch == "N":
                    self.view.blit(art.sprite("sign"), (tx * TILE - cx, ty * TILE - cy + 0))
                elif ch == "G":
                    self.view.blit(art.sprite("ghost"), (tx * TILE - cx, ty * TILE - cy))
        # movers / springs
        for m in R["movers"]:
            pygame.draw.rect(self.view, (140, 120, 90),
                             (m["x"] - cx, m["y"] - cy, m["w"], m["h"]))
            pygame.draw.rect(self.view, (90, 70, 50),
                             (m["x"] - cx, m["y"] - cy, m["w"], 2))
        for (x, y) in R["ents"]["springs"]:
            pygame.draw.rect(self.view, (90, 170, 250), (x * TILE - cx + 2, y * TILE - cy + 10, 12, 6))
        # checkpoints
        for (x, y) in R["ents"]["checks"]:
            lit = (x, y) in R["checks"]
            self.view.blit(art.sprite("torch"), (x * TILE - cx, y * TILE - cy))
            if lit:
                pygame.draw.circle(self.view, (255, 190, 80),
                                   (x * TILE - cx + 8, y * TILE - cy - 4), 3)
        # pickups
        for (x, y) in R["coins"]:
            self.view.blit(art.sprite("coin1" if (tick % 2 == 0) else "coin2"),
                           (x * TILE - cx, y * TILE - cy))
        for (x, y) in R["hearts"]:
            self.view.blit(art.sprite("heart"), (x * TILE - cx, y * TILE - cy))
        for (x, y) in R["keys"]:
            self.view.blit(art.sprite("key"), (x * TILE - cx, y * TILE - cy))
        for (x, y) in R["maxhp"]:
            self.view.blit(art.sprite("heart"), (x * TILE - cx, y * TILE - cy))
            pygame.draw.rect(self.view, (250, 215, 90), (x * TILE - cx, y * TILE - cy, 16, 16), 1)
        # beacon
        b = R["ents"]["beacon"]
        if b and (R["beacon_open"] or self.level_idx == 5):
            self.view.blit(art.sprite("beacon"), (b[0] * TILE - cx, b[1] * TILE - cy - 0))
        # foes
        for f in R["foes"]:
            fb = f["box"]
            sx, sy = fb.x - cx, fb.y - cy
            if f["kind"] == "crawl":
                img = art.sprite("cr1" if int(f["t"] * 6) % 2 == 0 else "cr2")
            elif f["kind"] == "hop":
                img = art.sprite("ho")
            elif f["kind"] == "bat":
                img = art.sprite("bat1" if int(f["t"] * 8) % 2 == 0 else "bat2")
            else:
                img = art.sprite("tur")
            self.view.blit(img, (sx - 2, sy - 4))
            if f["flash"] > 0:
                self.view.fill((255, 255, 255), (sx, sy, fb.w, fb.h), special_flags=pygame.BLEND_ADD)
        # boss
        bo = R["boss"]
        if bo and not (bo["dead"] and bo["t"] <= 0):
            alpha = 128 if bo.get("dead") and int(self.run_t * 12) % 2 == 0 else 255
            img = art.sprite("boss").copy()
            if bo["flash"] > 0:
                img.fill((255, 255, 255), special_flags=pygame.BLEND_ADD)
            img.set_alpha(alpha)
            self.view.blit(img, (bo["box"].x - cx - 2, bo["box"].y - cy - 2))
        # shots
        for s in R["shots"]:
            pygame.draw.circle(self.view, (255, 120, 60),
                               (int(s["x"] - cx), int(s["y"] - cy)), 3)
            pygame.draw.circle(self.view, (255, 220, 150),
                               (int(s["x"] - cx), int(s["y"] - cy)), 1)
        # player
        p = self.p
        if not (p["dead"] > 0 and int(self.run_t * 10) % 2 == 0):
            px, py = p["box"].x - cx - 2, p["box"].y - cy - 2
            if not p["ground"]:
                img = art.sprite("pj")
            else:
                img = art.sprite("p1" if int(p["anim"]) % 2 == 0 else "p2")
            if p["face"] < 0:
                img = pygame.transform.flip(img, True, False)
            if p["inv"] > 0 and int(self.run_t * 16) % 2 == 0:
                img = img.copy()
                img.fill((255, 80, 80), special_flags=pygame.BLEND_ADD)
            self.view.blit(img, (px, py))
            if p["slash_t"] > 0:
                off = 12 if p["face"] > 0 else -14
                pygame.draw.ellipse(self.view, (180, 240, 255),
                                    (p["box"].x - cx + off - 4, p["box"].y - cy - 3, 20, 10), 2)
        # particles / floats
        for pt in R["parts"]:
            self.view.set_at((int(pt["x"] - cx), int(pt["y"] - cy)), pt["c"])
            self.view.set_at((int(pt["x"] - cx) + 1, int(pt["y"] - cy)), pt["c"])
        for f in R["floats"]:
            self.draw_text(f["txt"], f["x"] - cx, f["y"] - cy, f["c"])
        # embers foreground
        for e in self.embers:
            e["y"] -= e["s"] * 0.016
            e["x"] += math.sin(self.run_t + e["s"]) * 0.2
            if e["y"] < -4:
                e["y"] = VIEW_H + 4
                e["x"] = random.random() * VIEW_W
            self.view.set_at((int(e["x"]), int(e["y"])), (255, 150, 60))

    def render_hud(self):
        p = self.p
        for i in range(p["maxhp"]):
            c = (230, 60, 70) if i < p["hp"] else (60, 30, 40)
            x = 8 + i * 11
            pygame.draw.rect(self.view, c, (x, 8, 8, 8))
            pygame.draw.rect(self.view, (20, 10, 15), (x, 8, 8, 8), 1)
        self.draw_text(f"x{self.save.get('coins', 0)}", 10, 20, (250, 215, 90))
        if p["has_key"]:
            self.draw_text("KEY", 60, 20, (250, 215, 90))
        meta = levels.LEVELS[self.level_idx]
        b = self.R["boss"]
        ny = 34 if (b and not b["dead"]) else 8
        self.draw_text(meta["name"], VIEW_W - 8 - art.text_size(meta["name"])[0], ny)
        self.draw_text(fmt_time(self.run_t), VIEW_W - 8 - art.text_size(fmt_time(self.run_t))[0], 20,
                       (150, 160, 190))
        b = self.R["boss"]
        if b and not b["dead"]:
            pygame.draw.rect(self.view, (40, 10, 20), (110, 10, 260, 10))
            w = int(260 * max(0, b["hp"] / b["max"]))
            pygame.draw.rect(self.view, (220, 50, 90), (110, 10, w, 10))
            pygame.draw.rect(self.view, (255, 200, 210), (110, 10, 260, 10), 1)
            self.draw_text("HOLLOW KING", 190, 22, (255, 150, 170))

    def render_card(self):
        pygame.draw.rect(self.view, (5, 5, 12), (40, 90, VIEW_W - 80, 60))
        pygame.draw.rect(self.view, (250, 215, 90), (40, 90, VIEW_W - 80, 60), 1)
        for i, line in enumerate(self.card):
            self.draw_text(line, VIEW_W // 2, 100 + i * 14, (235, 240, 255), center=True)

    def render_dialog(self):
        pygame.draw.rect(self.view, (5, 5, 12), (30, VIEW_H - 70, VIEW_W - 60, 56))
        pygame.draw.rect(self.view, (150, 160, 190), (30, VIEW_H - 70, VIEW_W - 60, 56), 1)
        who, txt = self.dlg[0]
        self.draw_text(who + ":", 40, VIEW_H - 62, (250, 215, 90))
        self.draw_text(txt[:52], 40, VIEW_H - 48)
        if len(txt) > 52:
            self.draw_text(txt[52:104], 40, VIEW_H - 36)
        self.draw_text("E >", VIEW_W - 56, VIEW_H - 36, (150, 160, 190))

    def render_pause(self):
        dim = pygame.Surface((VIEW_W, VIEW_H))
        dim.set_alpha(150)
        self.view.blit(dim, (0, 0))
        opts = ["RESUME", "RESTART LEVEL", f"SOUND: {'OFF' if audio.muted() else 'ON'}", "QUIT TO TITLE"]
        self.draw_text("PAUSED", VIEW_W // 2, 90, center=True, big=True)
        for i, o in enumerate(opts):
            c = (250, 215, 90) if i == self.paused_sel else (200, 205, 220)
            self.draw_text(("> " if i == self.paused_sel else "  ") + o, VIEW_W // 2, 130 + i * 18, c,
                           center=True)

    def render_clear(self):
        pygame.draw.rect(self.view, (5, 5, 12), (90, 70, VIEW_W - 180, 130))
        pygame.draw.rect(self.view, (250, 215, 90), (90, 70, VIEW_W - 180, 130), 1)
        self.draw_text("BEACON LIT", VIEW_W // 2, 84, (250, 215, 90), center=True, big=True)
        self.draw_text(f"time {fmt_time(self.run_t)}  deaths {self.deaths_lvl}",
                       VIEW_W // 2, 120, center=True)
        self.draw_text(f"coins this level {self.coins_lvl}", VIEW_W // 2, 134, center=True)
        self.draw_text("> E: descend", VIEW_W // 2, 160, (150, 220, 150), center=True)

    def render_victory(self):
        self.view.fill((12, 10, 8))
        for i, line in enumerate(levels.STORY_OUTRO):
            self.draw_text(line, VIEW_W // 2, 60 + i * 16, (250, 220, 170), center=True)
        self.draw_text("CROWN RESTORED", VIEW_W // 2, 130, (250, 215, 90), center=True, big=True)
        self.draw_text(f"deaths {self.save.get('deaths', 0)}   coins {self.save.get('coins', 0)}",
                       VIEW_W // 2, 165, center=True)
        self.draw_text("> E: title", VIEW_W // 2, 195, center=True)

    def render_title(self):
        self.view.fill((10, 8, 20))
        for e in self.embers:
            e["y"] -= e["s"] * 0.016
            if e["y"] < -4:
                e["y"] = VIEW_H + 4
            self.view.set_at((int(e["x"]), int(e["y"])), (255, 150, 60))
        self.draw_text("EMBERDEEP", VIEW_W // 2, 52, (255, 170, 60), center=True, big=True)
        self.draw_text("— the hollow crown —", VIEW_W // 2, 84, (180, 140, 200), center=True)
        if self.li == 0:
            opts = ["BEGIN THE DESCENT" if self.save.get("unlocked", 0) == 0 and not self.save.get("beacons")
                    else "CONTINUE", "LEVEL SELECT", "HOW TO PLAY",
                    f"SOUND: {'OFF' if audio.muted() else 'ON'}", "QUIT"]
            for i, o in enumerate(opts):
                c = (250, 215, 90) if i == self.ti else (200, 205, 220)
                self.draw_text(("> " if i == self.ti else "  ") + o, VIEW_W // 2, 120 + i * 18, c,
                               center=True)
            self.draw_text(f"beacons {len(self.save.get('beacons', []))}/6   coins {self.save.get('coins', 0)}",
                           VIEW_W // 2, 236, (120, 125, 150), center=True)
        elif self.li == 1:
            self.draw_text("CHOOSE A LIT LEVEL", VIEW_W // 2, 112, center=True)
            un = self.save.get("unlocked", 0)
            for i in range(6):
                open_ = i <= un
                c = (250, 215, 90) if i == self.li_idx else ((200, 205, 220) if open_ else (90, 90, 110))
                mark = "x" if i in self.save.get("beacons", []) else ("·" if open_ else "lock")
                self.draw_text(f"{mark} {levels.LEVELS[i]['name']}", VIEW_W // 2, 130 + i * 15, c,
                               center=True)
        else:
            for i, s in enumerate(["MOVE A/D or arrows", "JUMP Z / Space / Up (hold=higher)",
                                   "SLASH X / J — breaks rock, kills", "DASH Shift / C (after L2 gift)",
                                   "DOUBLE JUMP (after L4 gift)", "READ E near signs · pause Esc"]):
                self.draw_text(s, VIEW_W // 2, 120 + i * 16, center=True)

    # ================= MAIN LOOP =================
    def run(self):
        self.screen = pygame.display.set_mode((VIEW_W * SCALE, VIEW_H * SCALE))
        pygame.display.set_caption("EMBERDEEP — the hollow crown")
        try:
            icon = pygame.transform.scale(art.sprite("beacon"), (32, 32))
            pygame.display.set_icon(icon)
        except pygame.error:
            pass
        pressed: set = set()
        while True:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            pressed.clear()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    saveio.save(self.save)
                    return
                if ev.type == pygame.KEYDOWN:
                    pressed.add(ev.key)
                    if ev.key == pygame.K_m:
                        self.save["muted"] = not audio.muted()
                        audio.set_muted(self.save["muted"])
                        saveio.save(self.save)
            keys = pygame.key.get_pressed()
            self.update(dt, keys, pressed)
            self.render()
            pygame.display.flip()

    def near_sign(self):
        R, p = self.R, self.p
        cx, cy = p["box"].x + 6, p["box"].y + 7
        for (x, y), txt in R["ents"]["signs"].items():
            if abs(x * TILE + 8 - cx) < 20 and abs(y * TILE + 8 - cy) < 24:
                return txt
        return None

    def update(self, dt: float, keys, pressed: set):
        self.time += dt
        if self.card_t > 0:
            self.card_t -= dt
            if pressed:
                self.card_t = 0
        if self.state == "title":
            self.update_title(keys, pressed)
        elif self.state == "play":
            if {pygame.K_ESCAPE, pygame.K_p} & pressed:
                self.state = "pause"
                self.paused_sel = 0
                audio.play("ui")
                return
            if {pygame.K_e, pygame.K_RETURN} & pressed:
                s = self.near_sign()
                if s:
                    self.say([("Sign", s)])
                    return
            # door open with key
            R, p = self.R, self.p
            for (x, y) in R["ents"]["doors"]:
                if (x, y) in R["opened"]:
                    continue
                if abs(x * TILE + 8 - (p["box"].x + 6)) < 20 and abs(y * TILE + 8 - (p["box"].y + 7)) < 24:
                    if p["has_key"]:
                        R["opened"].add((x, y))
                        p["has_key"] = False
                        p["_had_key"] = False
                        audio.play("door")
                        self.float(x * TILE, y * TILE, "OPEN", (150, 220, 150))
                    elif {pygame.K_e, pygame.K_UP} & pressed:
                        self.say([("Wren", "Locked. A key sleeps nearby...")])
                        return
            self.step_play(dt, keys, pressed)
            # camera
            look = p["face"] * 24
            tx = p["box"].x + 6 - VIEW_W / 2 + look
            ty = p["box"].y + 7 - VIEW_H / 2 - 20
            self.cam[0] += (tx - self.cam[0]) * min(1, dt * 5)
            self.cam[1] += (ty - self.cam[1]) * min(1, dt * 5)
            maxx = max(0, R["w"] * TILE - VIEW_W)
            maxy = max(0, R["h"] * TILE - VIEW_H)
            self.cam[0] = max(0, min(maxx, self.cam[0]))
            self.cam[1] = max(-20, min(maxy, self.cam[1]))
        elif self.state == "dialog":
            if {pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_x} & pressed:
                audio.play("ui")
                self.dlg.pop(0)
                if not self.dlg:
                    self.state = "play"
        elif self.state == "pause":
            self.update_pause(pressed)
        elif self.state == "clear":
            if {pygame.K_e, pygame.K_SPACE, pygame.K_RETURN} & pressed:
                self.start_run(self.level_idx + 1)
        elif self.state == "victory":
            if {pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE} & pressed:
                self.state = "title"
                self.li = 0
        if self.fade > 0:
            self.fade -= dt

    def update_title(self, keys, pressed):
        if self.li == 0:
            n = 5
            if {pygame.K_UP, pygame.K_w} & pressed:
                self.ti = (self.ti - 1) % n
                audio.play("ui")
            if {pygame.K_DOWN, pygame.K_s} & pressed:
                self.ti = (self.ti + 1) % n
                audio.play("ui")
            if {pygame.K_RETURN, pygame.K_e, pygame.K_SPACE, pygame.K_z} & pressed:
                audio.play("ui")
                if self.ti == 0:
                    idx = min(5, self.save.get("unlocked", 0))
                    self.start_run(idx)
                    if idx == 0 and not self.save.get("beacons"):
                        self.say([(s, t) for s, t in [("???", l) for l in levels.STORY_INTRO[:2]]] +
                                 [("Wren", l) for l in levels.STORY_INTRO[2:]])
                elif self.ti == 1:
                    self.li = 1
                    self.li_idx = min(5, self.save.get("unlocked", 0))
                elif self.ti == 2:
                    self.li = 2
                elif self.ti == 3:
                    self.save["muted"] = not audio.muted()
                    audio.set_muted(self.save["muted"])
                    saveio.save(self.save)
                else:
                    saveio.save(self.save)
                    raise SystemExit
            if pygame.K_ESCAPE in pressed and self.li != 0:
                self.li = 0
        elif self.li == 1:
            un = self.save.get("unlocked", 0)
            if {pygame.K_UP, pygame.K_w} & pressed:
                self.li_idx = (self.li_idx - 1) % 6
            if {pygame.K_DOWN, pygame.K_s} & pressed:
                self.li_idx = (self.li_idx + 1) % 6
            if pygame.K_ESCAPE in pressed:
                self.li = 0
            if {pygame.K_RETURN, pygame.K_e} & pressed and self.li_idx <= un:
                self.start_run(self.li_idx)
                self.li = 0
        else:
            if pressed:
                self.li = 0

    def update_pause(self, pressed):
        if {pygame.K_UP, pygame.K_w} & pressed:
            self.paused_sel = (self.paused_sel - 1) % 4
        if {pygame.K_DOWN, pygame.K_s} & pressed:
            self.paused_sel = (self.paused_sel + 1) % 4
        if pygame.K_ESCAPE in pressed or pygame.K_p in pressed:
            self.state = "play"
            return
        if {pygame.K_RETURN, pygame.K_e} & pressed:
            if self.paused_sel == 0:
                self.state = "play"
            elif self.paused_sel == 1:
                self.load_level(self.level_idx)
                self.state = "play"
            elif self.paused_sel == 2:
                self.save["muted"] = not audio.muted()
                audio.set_muted(self.save["muted"])
                saveio.save(self.save)
            else:
                saveio.save(self.save)
                self.state = "title"
                self.li = 0


def fmt_time(s: float) -> str:
    m, ss = int(s // 60), int(s % 60)
    return f"{m}:{ss:02d}"
