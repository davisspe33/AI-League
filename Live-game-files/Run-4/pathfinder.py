import json
import os
import random
import re
import time
import zlib
from collections import deque

# Perfect-sweep pathfinder for the AI League dungeon.
# Single file, standard library only. Python 3.12 Lambda, handler = index.lambda_handler.
#
# Everything is computed from the map passed in at call time: no stored maps, paths or answers.
# Goal of strategy "sweep" (default): visit EVERY coin, challenge, key and door, never step on
# spikes, never enter a door before its key, and finish on the treasure, in as few steps as possible.

DIRECTIONS = [(-1, 0, "up"), (1, 0, "down"), (0, -1, "left"), (0, 1, "right")]
_MOVE = {(dr, dc): m for dr, dc, m in DIRECTIONS}
_DELTA = {m: (dr, dc) for dr, dc, m in DIRECTIONS}

DOOR_RE = re.compile(r"^c3\d$")   # c30-c39 doors
KEY_RE = re.compile(r"^c4\d$")    # c40-c49 keys; key c4N opens door c3N
CHAL_RE = re.compile(r"^c\d+$")   # any other cN tile is a challenge
WALL, TREASURE, COIN, SPIKE = "wall", "treasure", "c7", "c8"

# Engine damage per tile, used only to check that a plan loses no lives (CE defaults).
DAMAGE = {"c6": 2, "c17": 2, SPIKE: 1}
DOOR_NO_KEY_DAMAGE = 5


def kind(cell):
    if cell == WALL:
        return "wall"
    if cell == TREASURE:
        return "treasure"
    if cell == COIN:
        return "coin"
    if cell == SPIKE:
        return "spike"
    if DOOR_RE.match(cell):
        return "door"
    if KEY_RE.match(cell):
        return "key"
    if CHAL_RE.match(cell):
        return "challenge"
    return "normal"


def door_for_key(key):
    return "c3" + key[2:]


# --------------------------------------------------------------------------- input parsing

def _parse_start(pos):
    """Parse a start position from any format the model might send."""
    try:
        if isinstance(pos, str):
            s = pos.strip()
            if s.startswith("[") or s.startswith("{"):
                try:
                    return _parse_start(json.loads(s))
                except json.JSONDecodeError:
                    pass
        if isinstance(pos, dict):
            return (int(pos.get("row", 0)), int(pos.get("col", 0)))
        if isinstance(pos, (list, tuple)):
            if len(pos) == 1:
                return _parse_start(pos[0])
            if len(pos) >= 2:
                a = re.sub(r"[^A-Za-z0-9]", "", str(pos[0]))
                b = re.sub(r"[^A-Za-z0-9]", "", str(pos[1]))
                if a.isalpha():
                    return (int(b) - 1, ord(a.upper()) - ord("A"))
                return (int(a), int(b))
        s = re.sub(r"[^A-Za-z0-9]", "", str(pos))
        m = re.match(r"([A-Za-z])(\d+)", s)
        if m:
            return (int(m.group(2)) - 1, ord(m.group(1).upper()) - ord("A"))
        nums = re.findall(r"\d+", s)
        if len(nums) >= 2:
            return (int(nums[0]), int(nums[1]))
    except (ValueError, TypeError, IndexError):
        pass
    return None


def _parse_grid(game_map):
    if isinstance(game_map, str):
        g = game_map.strip()
        a = min([i for i in (g.find("["), g.find("{")) if i >= 0] or [-1])
        b = max(g.rfind("]"), g.rfind("}"))
        if a >= 0 and b > a:
            g = g[a:b + 1]
        game_map = json.loads(g)
    if isinstance(game_map, dict):
        game_map = game_map.get("grid") or game_map.get("game_map") or game_map.get("map")
    if not game_map or not isinstance(game_map, list):
        return None
    grid = [[str(c).strip().lower() for c in row] for row in game_map]
    # Jagged rows (model dropped elements): pad with wall so we never walk into a guessed cell.
    width = max(len(r) for r in grid)
    return [r + [WALL] * (width - len(r)) for r in grid]


def _resolve_start(body, grid):
    rows, cols = len(grid), len(grid[0])

    def ok(p):
        return p is not None and 0 <= p[0] < rows and 0 <= p[1] < cols and grid[p[0]][p[1]] != WALL

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "start":
                return (r, c)
    map_config = body.get("map_config") or {}
    for raw in (map_config.get("playerStart"), body.get("playerStart"),
                body.get("start_pos"), body.get("start"), body.get("position")):
        if raw in (None, "", {}, []):
            continue
        p = _parse_start(raw)
        if ok(p):
            return p
        # model may have swapped [col,row]
        if p is not None and ok((p[1], p[0])):
            return (p[1], p[0])
    return (0, 0)


# --------------------------------------------------------------------------- core search

class Board:
    def __init__(self, grid, avoid_spikes=True):
        self.grid = grid
        self.rows, self.cols = len(grid), len(grid[0])
        self.avoid_spikes = avoid_spikes
        self.kinds = [[kind(c) for c in row] for row in grid]
        self.treasure = self._find_kind("treasure")
        self.cache = {}

    def _find_kind(self, k):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.kinds[r][c] == k:
                    return (r, c)
        return None

    def cells(self, k):
        return [(r, c) for r in range(self.rows) for c in range(self.cols) if self.kinds[r][c] == k]

    def bfs(self, src, opened):
        """Shortest paths from src. Unopened doors and the treasure can be ENTERED as an endpoint but
        never walked through (treasure ends the game; a locked door costs 5 lives)."""
        key = (src, opened)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        dist, prev = {src: 0}, {}
        q = deque([src])
        while q:
            cur = q.popleft()
            r, c = cur
            k = self.kinds[r][c]
            if cur != src and (k == "treasure" or (k == "door" and cur not in opened)):
                continue
            for dr, dc, _ in DIRECTIONS:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols) or (nr, nc) in dist:
                    continue
                nk = self.kinds[nr][nc]
                if nk == "wall" or (nk == "spike" and self.avoid_spikes):
                    continue
                dist[(nr, nc)] = dist[cur] + 1
                prev[(nr, nc)] = cur
                q.append((nr, nc))
        self.cache[key] = (dist, prev)
        return dist, prev

    def path(self, a, b, opened):
        dist, prev = self.bfs(a, opened)
        if b not in dist:
            return None
        seg = [b]
        while seg[-1] != a:
            seg.append(prev[seg[-1]])
        seg.reverse()
        return seg


def _reachable_items(board, start):
    """Items reachable without spikes, opening a door only once its key is reachable."""
    keys = {board.grid[r][c]: (r, c) for r, c in board.cells("key")}
    opened = frozenset()
    while True:
        dist, _ = board.bfs(start, opened)
        new = set(opened)
        for d in board.cells("door"):
            kpos = None
            for kname, p in keys.items():
                if door_for_key(kname) == board.grid[d[0]][d[1]]:
                    kpos = p
            if d in dist and kpos is not None and kpos in dist:
                new.add(d)
        if new == set(opened):
            break
        opened = frozenset(new)
    items = []
    for k in ("coin", "challenge", "key", "door"):
        for p in board.cells(k):
            if p not in dist:
                continue
            if k == "door" and p not in opened:
                continue
            items.append(p)
    return items, dist


class Sweep:
    def __init__(self, board, start, items):
        self.b = board
        self.start = start
        self.items = items
        g = board.grid
        self.door_key = {}
        key_pos = {g[r][c]: (r, c) for r, c in board.cells("key")}
        for d in items:
            if board.kinds[d[0]][d[1]] == "door":
                kname = "c4" + g[d[0]][d[1]][2:]
                self.door_key[d] = key_pos.get(kname)

    def cost(self, order):
        """Total steps of start -> order -> treasure, or None if infeasible."""
        b = self.b
        opened, cur, total, seen = frozenset(), self.start, 0, set()
        for p in order:
            if p in self.door_key:
                if self.door_key[p] not in seen:
                    return None
            dist, _ = b.bfs(cur, opened)
            d = dist.get(p)
            if d is None:
                return None
            total += d
            seen.add(p)
            if p in self.door_key:
                opened = opened | {p}
            cur = p
        dist, _ = b.bfs(cur, opened)
        d = dist.get(b.treasure)
        if d is None:
            return None
        return total + d

    def realize(self, order):
        b = self.b
        opened, cur, cells = frozenset(), self.start, [self.start]
        for p in list(order) + [b.treasure]:
            seg = b.path(cur, p, opened)
            if seg is None:
                return None
            cells.extend(seg[1:])
            if p in self.door_key:
                opened = opened | {p}
            cur = p
        return cells

    def _fix_doors(self, order):
        """Move any door to right after its key."""
        order = list(order)
        for d, k in self.door_key.items():
            if d in order and k in order and order.index(d) < order.index(k):
                order.remove(d)
                order.insert(order.index(k) + 1, d)
        return order

    def greedy(self, rng=None, noise=0.0):
        b = self.b
        left = set(self.items)
        order, cur, opened = [], self.start, frozenset()
        while left:
            dist, _ = b.bfs(cur, opened)
            best, bd = None, None
            for p in left:
                if p in self.door_key and self.door_key[p] not in order:
                    continue
                d = dist.get(p)
                if d is None:
                    continue
                if rng is not None and noise:
                    d = d + rng.random() * noise
                if bd is None or d < bd:
                    best, bd = p, d
            if best is None:
                break
            order.append(best)
            left.discard(best)
            if best in self.door_key:
                opened = opened | {best}
            cur = best
        return order

    def local_search(self, order, deadline):
        best = self.cost(order)
        if best is None:
            return order, None
        n = len(order)
        improved = True
        while improved and time.time() < deadline:
            improved = False
            # 2-opt (reverse a segment)
            for i in range(n - 1):
                for j in range(i + 1, n):
                    cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                    c = self.cost(cand)
                    if c is not None and c < best:
                        order, best, improved = cand, c, True
                if time.time() > deadline:
                    return order, best
            # or-opt (move a run of 1-3 items elsewhere)
            for seg in (1, 2, 3):
                for i in range(n - seg + 1):
                    run = order[i:i + seg]
                    rest = order[:i] + order[i + seg:]
                    for j in range(len(rest) + 1):
                        if j == i:
                            continue
                        cand = rest[:j] + run + rest[j:]
                        c = self.cost(cand)
                        if c is not None and c < best:
                            order, best, improved = cand, c, True
                            break
                    if time.time() > deadline:
                        return order, best
        return order, best

    def solve(self, budget):
        deadline = time.time() + budget
        seed = zlib.crc32(json.dumps(self.b.grid).encode())
        rng = random.Random(seed)
        order = self._fix_doors(self.greedy())
        order, best = self.local_search(order, deadline)
        best_order = order
        stale = 0
        # Iterated local search: perturb (double-bridge / noisy greedy restart) and re-optimise.
        while time.time() < deadline and stale < 60 and len(order) >= 4:
            if rng.random() < 0.3:
                cand = self._fix_doors(self.greedy(rng, noise=3.0))
            else:
                n = len(best_order)
                a, b, c = sorted(rng.sample(range(1, n), 3))
                cand = self._fix_doors(best_order[:a] + best_order[b:c] + best_order[a:b] + best_order[c:])
            cand, cc = self.local_search(cand, deadline)
            if cc is not None and (best is None or cc < best):
                best_order, best, stale = cand, cc, 0
            else:
                stale += 1
        return best_order, best


def simulate(grid, start, moves):
    """Replay moves with engine rules (all answers correct). Returns lives lost, tiles taken, end state."""
    rows, cols = len(grid), len(grid[0])
    r, c = start
    lives, lost, taken, keys, consumed = 5, 0, set(), set(), set()
    for m in moves:
        dr, dc = _DELTA[m]
        r, c = r + dr, c + dc
        if not (0 <= r < rows and 0 <= c < cols) or grid[r][c] == WALL:
            return {"ok": False, "why": "wall", "lost": lost, "taken": taken}
        if (r, c) in consumed:
            continue
        consumed.add((r, c))
        cell = grid[r][c]
        k = kind(cell)
        if k == "treasure":
            return {"ok": True, "lost": lost, "taken": taken, "treasure": True}
        if k == "spike":
            lost += 1
        elif k == "door":
            if cell in keys:
                taken.add((r, c))
            else:
                lost += DOOR_NO_KEY_DAMAGE
        elif k == "key":
            keys.add(door_for_key(cell))
            taken.add((r, c))
        elif k in ("coin", "challenge"):
            taken.add((r, c))
        if lost >= lives:
            return {"ok": False, "why": "dead", "lost": lost, "taken": taken}
    return {"ok": False, "why": "no treasure", "lost": lost, "taken": taken}


def _moves(cells):
    return [_MOVE[(b[0] - a[0], b[1] - a[1])] for a, b in zip(cells, cells[1:])]


def _prune_incidental(sw, order):
    """Drop waypoints already collected by an earlier leg if that shortens the route."""
    changed = True
    while changed:
        changed = False
        cells = sw.realize(order)
        pos_first = {}
        for i, p in enumerate(cells):
            pos_first.setdefault(p, i)
        idx = 0
        for k, p in enumerate(order):
            # find the leg end index for waypoint k
            seg_end = cells.index(p, idx)
            if pos_first[p] < seg_end:
                cand = order[:k] + order[k + 1:]
                c0, c1 = sw.cost(order), sw.cost(cand)
                if c1 is not None and c1 <= c0:
                    order, changed = cand, True
                    break
            idx = seg_end
    return order


def plan_sweep(grid, start, budget=2.0):
    board = Board(grid, avoid_spikes=True)
    if board.treasure is None:
        return None, {"error": "no treasure"}
    items, dist = _reachable_items(board, start)
    sw = Sweep(board, start, items)
    order, steps = sw.solve(budget)
    if steps is None:
        return None, {"error": "no spike-free sweep"}
    order = _prune_incidental(sw, order)
    cells = sw.realize(order)
    all_items = board.cells("coin") + board.cells("challenge") + board.cells("key") + board.cells("door")
    skipped = [p for p in all_items if p not in set(items)]
    return _moves(cells), {"items": len(items), "skipped": skipped}


def plan_safe_swift(grid, start):
    """Shortest path to treasure that avoids spikes and locked doors (collects keys if a door blocks the way)."""
    board = Board(grid, avoid_spikes=True)
    if board.treasure is None:
        return None
    items, _ = _reachable_items(board, start)
    keys_doors = [p for p in items if board.kinds[p[0]][p[1]] in ("key", "door")]
    sw = Sweep(board, start, [])
    if sw.cost([]) is not None:
        return _moves(sw.realize([]))
    sw = Sweep(board, start, keys_doors)
    order, steps = sw.solve(2.0)
    if steps is None:
        return None
    return _moves(sw.realize(_prune_incidental(sw, order)))


def plan_min_damage(grid, start):
    """Used only when no spike-free route to the treasure exists: least lives lost, then fewest steps.
    State = (cell, doors unlocked by keys picked up so far); spikes are free once stepped on."""
    import heapq
    rows, cols = len(grid), len(grid[0])
    start_state = (start, frozenset(), frozenset())
    heap = [(0, 0, 0, start_state)]
    best = {start_state: (0, 0)}
    prev = {start_state: None}
    tie = 0
    while heap:
        dmg, steps, _, st = heapq.heappop(heap)
        if best.get(st) != (dmg, steps):
            continue
        cell, keys, hit = st
        if grid[cell[0]][cell[1]] == TREASURE:
            out = []
            while st is not None:
                out.append(st[0])
                st = prev[st]
            return _moves(out[::-1])
        for dr, dc, _ in DIRECTIONS:
            n = (cell[0] + dr, cell[1] + dc)
            if not (0 <= n[0] < rows and 0 <= n[1] < cols):
                continue
            name = grid[n[0]][n[1]]
            k = kind(name)
            if k == "wall":
                continue
            nd, nkeys, nhit = dmg, keys, hit
            if n not in hit:
                if k == "spike":
                    nd += DAMAGE[SPIKE]
                    nhit = hit | {n}
                elif k == "door" and name not in keys:
                    nd += DOOR_NO_KEY_DAMAGE
                    nhit = hit | {n}
                elif k == "key":
                    nkeys = keys | {door_for_key(name)}
            if nd >= 5:
                continue
            ns = (n, nkeys, nhit)
            cand = (nd, steps + 1)
            if ns not in best or cand < best[ns]:
                best[ns] = cand
                prev[ns] = st
                tie += 1
                heapq.heappush(heap, (nd, steps + 1, tie, ns))
    return None


def plan_bfs_any(grid, start):
    """Last resort: plain shortest path ignoring hazards (never through walls)."""
    rows, cols = len(grid), len(grid[0])
    goal = next(((r, c) for r in range(rows) for c in range(cols) if grid[r][c] == TREASURE), None)
    q, prev = deque([start]), {start: None}
    while q:
        cur = q.popleft()
        if cur == goal:
            out = []
            while prev[cur] is not None:
                out.append(cur)
                cur = prev[cur]
            out.append(start)
            return _moves(out[::-1])
        for dr, dc, _ in DIRECTIONS:
            n = (cur[0] + dr, cur[1] + dc)
            if 0 <= n[0] < rows and 0 <= n[1] < cols and grid[n[0]][n[1]] != WALL and n not in prev:
                prev[n] = cur
                q.append(n)
    return []


def plan(grid, start, strategy="sweep", budget=2.0):
    s = str(strategy or "sweep").lower()
    info = {}
    path = None
    if any(w in s for w in ("swift", "fast", "quick", "short")):
        path = plan_safe_swift(grid, start)
        info["mode"] = "safe_swift"
    else:
        path, info = plan_sweep(grid, start, budget)
        info["mode"] = "sweep"
        if path is None:
            path = plan_safe_swift(grid, start)
            info["mode"] = "safe_swift_fallback"
    if path is None:
        path = plan_min_damage(grid, start)
        info["mode"] = "min_damage_fallback"
    if path is None:
        path = plan_bfs_any(grid, start)
        info["mode"] = "bfs_fallback"
    return path, info


# --------------------------------------------------------------------------- Lambda entry point

def lambda_handler(event, context):
    """
    Route planner for the AI League dungeon map. Handles API Gateway and AgentCore Gateway events.

    ---
    Tool: route
    Description: Route planner for the dungeon map. Returns the move list from start to treasure. Strategy sweep visits every coin, challenge, key and door (keys first) with no spikes; swift is the safe shortest path.
    Parameters:
        game_map     (required) - the 2D grid array as JSON string or list
        start_pos    (optional) - start position as [row, col] zero indexed, or a label like "A1"
        strategy     (optional) - sweep (default) or swift
    ---

    Tiles: wall blocked, treasure goal, c7 coins, c8 spikes, c30-c39 doors (need key c40-c49 with the
    same last digit), every other cN tile is a challenge.
    """
    try:
        body = event
        if isinstance(event, dict) and "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        grid = _parse_grid(body.get("game_map") or body.get("grid") or body.get("map"))
        if not grid:
            return _err(400, "Missing or invalid game_map")
        start = _resolve_start(body, grid)
        budget = float(os.environ.get("TIME_BUDGET", "2") or 2)
        strategy = body.get("strategy") or os.environ.get("DEFAULT_STRATEGY", "sweep")
        # SKIP_TILES: tile TYPES to avoid like spikes (e.g. "c18,c6") when the agent can't answer them reliably.
        # Generic (by type, never by position); still crossed if it's the only way through.
        skip = {t.strip().lower() for t in os.environ.get("SKIP_TILES", "").split(",") if t.strip()}
        plan_grid = [[SPIKE if c in skip else c for c in row] for row in grid] if skip else grid
        path, info = plan(plan_grid, start, strategy, budget)
        check = simulate(grid, start, path)
        print(f"RESULT: strategy={strategy} mode={info.get('mode')} start={list(start)} steps={len(path)} "
              f"collected={len(check['taken'])} lives_lost={check['lost']} treasure={check.get('treasure', False)} "
              f"skipped={info.get('skipped')}")
        return {"statusCode": 200, "body": json.dumps({"path": path})}
    except Exception as e:
        print(f"ERROR: {e}")
        return _err(500, str(e))


def _err(code, msg):
    return {"statusCode": code, "body": json.dumps({"error": msg})}
