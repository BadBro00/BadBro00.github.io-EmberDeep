"""Pure platformer collision helpers (no pygame dependency)."""
from __future__ import annotations


class AABB:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: float, y: float, w: float, h: float):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def left(self): return self.x

    @property
    def right(self): return self.x + self.w

    @property
    def top(self): return self.y

    @property
    def bottom(self): return self.y + self.h

    def copy(self): return AABB(self.x, self.y, self.w, self.h)

    def overlaps(self, o: "AABB") -> bool:
        return (self.x < o.x + o.w and self.x + self.w > o.x
                and self.y < o.y + o.h and self.y + self.h > o.y)


def move_axis(box: AABB, delta: float, solids: list[AABB], axis: str):
    """Move along one axis, clamp on contact. Returns (collided_bool, side)."""
    collided, side = False, None
    if axis == "x":
        box.x += delta
        if delta > 0:
            for s in solids:
                if box.overlaps(s):
                    box.x = s.x - box.w
                    collided, side = True, "right"
        elif delta < 0:
            for s in solids:
                if box.overlaps(s):
                    box.x = s.x + s.w
                    collided, side = True, "left"
    else:
        box.y += delta
        if delta > 0:
            for s in solids:
                if box.overlaps(s):
                    box.y = s.y - box.h
                    collided, side = True, "bottom"
        elif delta < 0:
            for s in solids:
                if box.overlaps(s):
                    box.y = s.y + s.h
                    collided, side = True, "top"
    return collided, side


def move_body(box: AABB, vx: float, vy: float, dt: float, solids: list[AABB],
              substeps: int = 2) -> dict:
    """Substepped per-axis move. Returns hit flags dict."""
    hits = {"left": False, "right": False, "top": False, "bottom": False}
    for _ in range(max(1, substeps)):
        c, s = move_axis(box, vx * dt / max(1, substeps), solids, "x")
        if c:
            hits[s] = True
        c, s = move_axis(box, vy * dt / max(1, substeps), solids, "y")
        if c:
            hits[s] = True
    return hits
