# Balanced Pathfinder - AI League
# ================================
# Route planner for the AI League dungeon game (Community Edition rules).
# Single file, no dependencies. Python 3.12 Lambda, handler = index.lambda_handler.
# To use it as an agent tool copy this file to:
#   agent-config/tools/BalancedPathfinder/index.py   (and add it to config.yaml)
#
# Strategies:
#   balanced  - (default) maximise EXPECTED score: collect coins, take challenges that are
#               worth it, avoid spikes, protect lives, pick up keys for doors, keep paths short.
#   swift     - plain BFS shortest path (identical to the CE Pathfinder).
#   get_coins - greedy c7 coin collection then BFS to treasure (identical to the CE Pathfinder).
#
# Scoring model (same as CE score_calculator/game_runner, verified by validate_planner.py):
#   score = coins + challenge points + lives_left*250 + treasure(1000)   [token bonus is path independent]
#   Tiles are consumed on first visit, treasure ends the game, spikes/wrong answers cost lives,
#   doors need their key first (otherwise 5 damage). Challenge answers are uncertain, so each
#   challenge tile is modelled with a success probability (P["p_success"]) and the plan maximises
#   the exact expected score via a lives-distribution DP. Speed is modelled as a small cost per step.

import json
import os
import heapq
from collections import deque
from itertools import combinations, permutations

DIRECTIONS = [(-1, 0, "up"), (1, 0, "down"), (0, -1, "left"), (0, 1, "right")]
_DELTA = {m: (dr, dc) for dr, dc, m in DIRECTIONS}
_MOVE = {(dr, dc): m for dr, dc, m in DIRECTIONS}

# (points, damage) - CE defaults (game_runner.DEFAULT_TILE_CONFIG)
TILE_CFG = {
    "c1": (400, 1), "c2": (600, 1), "c3": (550, 1), "c4": (800, 1), "c5": (250, 1),
    "c6": (1000, 2), "c7": (250, 0), "c8": (0, 1), "c17": (750, 2), "c18": (500, 1),
    "c30": (1000, 5), "c31": (1000, 5), "c32": (1000, 5), "c33": (1000, 5),
    "c40": (50, 0), "c41": (50, 0), "c42": (50, 0), "c43": (50, 0),
}
CHALLENGES = {"c1", "c2", "c3", "c4", "c5", "c6", "c17", "c18"}
DOORS = {"c30", "c31", "c32", "c33"}
KEY_TO_DOOR = {"c40": "c30", "c41": "c31", "c42": "c32", "c43": "c33"}

# ASSUMED probability that your agent answers each challenge correctly. Calibrate from your
# run log (docs/08-run-log.md): lower numbers make the planner more cautious.
DEFAULT_PARAMS = {
    "lives": 5,
    "life_value": 250,      # livesBonusMultiplier
    "treasure": 1000,       # treasureBonus
    "step_cost": 5.0,       # speed proxy: points given up per step
    "max_steps": 150,
    "p_success": {"c1": 0.75, "c2": 0.80, "c3": 0.70, "c4": 0.70, "c5": 0.95, "c6": 0.50,
                  "c17": 0.60, "c18": 0.70, "c30": 0.70, "c31": 0.70, "c32": 0.70, "c33": 0.70},
    "tiles": {},            # per-tile overrides {"c5": [250, 1]}
    "max_challenges": None, # cap on challenges visited (time limit is wall-clock; each answer takes seconds)
}


def make_params(over=None):
    P = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_PARAMS.items()}
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(P.get(k), dict):
            P[k].update(v)
        else:
            P[k] = v
    return P


def _cfg(cell, P):
    t = P["tiles"].get(cell)
    return tuple(t) if t else TILE_CFG.get(cell, (0, 0))


def _p(cell, P):
    return P["p_success"].get(cell, 0.7)


def _ev_challenge(cell, P):
    pts, dmg = _cfg(cell, P)
    p = _p(cell, P)
    return p * pts - (1 - p) * dmg * P["life_value"]


# --------------------------------------------------------------------------- evaluation

def _hit(dist, d):
    if d <= 0:
        return dist
    out = {}
    for lives, m in dist.items():
        if lives - d > 0:
            out[lives - d] = out.get(lives - d, 0.0) + m
    return out


def _challenge(dist, pts, dmg, p):
    gain = sum(dist.values()) * p * pts
    out = {}
    for lives, m in dist.items():
        out[lives] = out.get(lives, 0.0) + m * p
        if lives - dmg > 0:
            out[lives - dmg] = out.get(lives - dmg, 0.0) + m * (1 - p)
    return out, gain


def evaluate(grid, start, moves, P=None):
    """Exact expected score of a move list under independent challenge success probabilities.
    Mirrors CE game_runner.run_game_session (token bonus excluded: it is path independent)."""
    P = P or make_params()
    rows, cols = len(grid), len(grid[0])
    r, c = start
    dist = {int(P["lives"]): 1.0}
    pts = coin_pts = chal_pts = 0.0
    n_chal = 0
    consumed, unlocked = set(), set()
    steps, reached, valid = 0, 0.0, True
    for mv in moves:
        dr, dc = _DELTA[mv]
        r, c = r + dr, c + dc
        steps += 1
        if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] == "wall":
            dist, valid = {}, False
            break
        if (r, c) in consumed:
            continue
        cell = grid[r][c]
        if cell == "treasure":
            reached = sum(dist.values())
            consumed.add((r, c))
            break
        if cell == "c7":
            g = sum(dist.values()) * _cfg(cell, P)[0]
            pts += g
            coin_pts += g
        elif cell == "c8":
            dist = _hit(dist, _cfg(cell, P)[1])
        elif cell in DOORS:
            cp, cd = _cfg(cell, P)
            if cell not in unlocked:
                dist = _hit(dist, cd)
            else:
                dist, g = _challenge(dist, cp, cd, _p(cell, P))
                pts += g
                chal_pts += g
                n_chal += 1
        elif cell in KEY_TO_DOOR:
            unlocked.add(KEY_TO_DOOR[cell])
            g = sum(dist.values()) * _cfg(cell, P)[0]
            pts += g
            coin_pts += g
        elif cell in CHALLENGES:
            cp, cd = _cfg(cell, P)
            dist, g = _challenge(dist, cp, cd, _p(cell, P))
            pts += g
            chal_pts += g
            n_chal += 1
        consumed.add((r, c))
        if not dist:
            break
    alive = sum(dist.values())
    exp_lives = sum(l * m for l, m in dist.items())
    total = pts + reached * P["treasure"] + exp_lives * P["life_value"]
    return {
        "valid": valid, "steps": steps, "score": total,
        "objective": total - P["step_cost"] * steps,
        "coin_points": coin_pts, "challenge_points": chal_pts,
        "challenges": n_chal, "p_treasure": reached, "p_death": 1.0 - alive, "exp_lives": exp_lives,
    }


# --------------------------------------------------------------------------- routing

def _enter_cost(cell, unlocked, P):
    if cell == "wall":
        return None
    s = P["step_cost"]
    if cell == "c8":
        return s + _cfg(cell, P)[1] * P["life_value"]
    if cell in DOORS:
        if cell not in unlocked:
            return None
        return s + max(0.0, -_ev_challenge(cell, P))
    if cell in CHALLENGES:
        return s + max(0.0, -_ev_challenge(cell, P))
    return s


def _dijkstra(grid, src, unlocked, P, cache):
    key = (src, unlocked)
    if key in cache:
        return cache[key]
    rows, cols = len(grid), len(grid[0])
    dist, prev, heap = {src: 0.0}, {}, [(0.0, src)]
    while heap:
        d, (r, c) = heapq.heappop(heap)
        if d > dist.get((r, c), 1e18):
            continue
        if grid[r][c] == "treasure" and (r, c) != src:
            continue  # reaching the treasure ends the game; never route through it
        for dr, dc, _m in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            w = _enter_cost(grid[nr][nc], unlocked, P)
            if w is None:
                continue
            nd = d + w
            if nd < dist.get((nr, nc), 1e18) - 1e-9:
                dist[(nr, nc)] = nd
                prev[(nr, nc)] = (r, c)
                heapq.heappush(heap, (nd, (nr, nc)))
    cache[key] = (dist, prev)
    return cache[key]


def _build(grid, wps, P, cache):
    unlocked = frozenset()
    pos = [wps[0]]
    for a, b in zip(wps, wps[1:]):
        dist, prev = _dijkstra(grid, a, unlocked, P, cache)
        if b not in dist:
            return None
        seg, cur = [b], b
        while cur != a:
            cur = prev[cur]
            seg.append(cur)
        seg.reverse()
        pos.extend(seg[1:])
        t = grid[b[0]][b[1]]
        if t in KEY_TO_DOOR:
            unlocked = unlocked | {KEY_TO_DOOR[t]}
    return pos


def _to_moves(pos):
    return [_MOVE[(b[0] - a[0], b[1] - a[1])] for a, b in zip(pos, pos[1:])]


def _score_seq(grid, start, seq, P, cache, enforce_cap=True):
    pos = _build(grid, seq, P, cache)
    if pos is None:
        return None
    moves = _to_moves(pos)
    res = evaluate(grid, start, moves, P)
    if not res["valid"] or res["steps"] > P["max_steps"]:
        return None
    cap = P.get("max_challenges")
    if enforce_cap and cap is not None and res["challenges"] > cap:
        return None
    return res["objective"], moves


def _find(grid, tile):
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell == tile:
                return (r, c)
    return None


def _md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def plan_balanced(grid, start, P=None):
    P = P or make_params()
    start = tuple(start)
    treasure = _find(grid, "treasure")
    if treasure is None:
        return []
    rows, cols = len(grid), len(grid[0])
    cache = {}
    coins, chals, keys, doors = [], [], [], []
    for r in range(rows):
        for c in range(cols):
            t = grid[r][c]
            if t == "c7":
                coins.append((r, c))
            elif t in CHALLENGES and _ev_challenge(t, P) > 0:
                chals.append((r, c))
            elif t in KEY_TO_DOOR:
                keys.append((r, c))
            elif t in DOORS and _ev_challenge(t, P) > 0:
                doors.append((r, c))
    items = coins + chals + keys + doors

    # base route (start -> [keys needed] -> treasure)
    seq = [start, treasure]
    cur = _score_seq(grid, start, seq, P, cache, enforce_cap=False)
    if cur is None:
        best = None
        for k in range(1, len(keys) + 1):
            for subset in combinations(keys, k):
                for perm in permutations(subset):
                    s = [start] + list(perm) + [treasure]
                    res = _score_seq(grid, start, s, P, cache, enforce_cap=False)
                    if res and (best is None or res[0] > best[0]):
                        best = (res[0], s, res)
            if best:
                break
        if best is None:
            return swift_path(grid, rows, cols, start, treasure)
        seq, cur = best[1], best[2]
    cur_obj, cur_moves = cur

    for _ in range(60):
        cands = []
        n = len(seq)
        for it in items:
            if it in seq:
                continue
            ranked = sorted(range(1, n), key=lambda i: _md(seq[i - 1], it) + _md(it, seq[i]) - _md(seq[i - 1], seq[i]))
            for i in ranked[:3]:
                cands.append(seq[:i] + [it] + seq[i:])
        for j in range(1, n - 1):
            cands.append(seq[:j] + seq[j + 1:])
        for i in range(1, n - 1):
            for j in range(i + 1, n - 1):
                cands.append(seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:])
        for d in doors:
            dk = KEY_TO_DOOR_INV.get(grid[d[0]][d[1]])
            for k in keys:
                if grid[k[0]][k[1]] != dk or k in seq or d in seq:
                    continue
                for i in range(1, n):
                    for j in range(i, n):
                        cands.append(seq[:i] + [k] + seq[i:j] + [d] + seq[j:])
        best = None
        for s in cands:
            res = _score_seq(grid, start, s, P, cache)
            if res and res[0] > cur_obj + 1e-6 and (best is None or res[0] > best[0]):
                best = (res[0], s, res[1])
        if best is None:
            break
        cur_obj, seq, cur_moves = best
    return cur_moves


KEY_TO_DOOR_INV = {v: k for k, v in KEY_TO_DOOR.items()}


# --------------------------------------------------------------------------- CE reference strategies (verbatim logic)

def _bfs(game_map, rows, cols, start, goal):
    queue = deque([(start[0], start[1], [])])
    visited = {(start[0], start[1])}
    while queue:
        r, c, path = queue.popleft()
        if (r, c) == goal:
            return path
        for dr, dc, move in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and game_map[nr][nc] != "wall" and (nr, nc) not in visited:
                visited.add((nr, nc))
                queue.append((nr, nc, path + [move]))
    return None


def swift_path(game_map, rows, cols, start, treasure):
    return _bfs(game_map, rows, cols, tuple(start), treasure) or []


def get_coins_path(game_map, rows, cols, start, treasure):
    board = [row[:] for row in game_map]
    r, c = start
    full_path = []
    for _ in range(50):
        queue = deque([(r, c, [])])
        visited = {(r, c)}
        targets = []
        while queue:
            cr, cc, p = queue.popleft()
            if board[cr][cc] == "c7" and (cr, cc) != (r, c):
                targets.append((max(len(p), 1), p, cr, cc))
            for dr, dc, move in DIRECTIONS:
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < rows and 0 <= nc < cols and board[nr][nc] != "wall" and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append((nr, nc, p + [move]))
        if not targets:
            break
        targets.sort()
        _, path_to, r, c = targets[0]
        full_path.extend(path_to)
        board[r][c] = "normal"
    path_end = _bfs(board, rows, cols, (r, c), treasure)
    if path_end is not None:
        full_path.extend(path_end)
        return full_path
    return swift_path(game_map, rows, cols, start, treasure)


ALIASES = {"quickest": "swift", "shortest": "swift", "coins_first": "get_coins", "coins": "get_coins"}


def plan_moves(grid, start, strategy="balanced", P=None):
    rows, cols = len(grid), len(grid[0])
    treasure = _find(grid, "treasure")
    if treasure is None:
        return []
    s = ALIASES.get(str(strategy).lower(), str(strategy).lower())
    if s == "swift":
        return swift_path(grid, rows, cols, start, treasure)
    if s == "get_coins":
        return get_coins_path(grid, rows, cols, tuple(start), treasure)
    return plan_balanced(grid, start, P)


# --------------------------------------------------------------------------- Lambda entry point

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
    return game_map


def lambda_handler(event, context):
    """
    Route planner for the AI League dungeon map. Handles API Gateway and AgentCore Gateway events.

    ---
    Tool: route
    Description: Route planner for the dungeon map. Returns the move list from start to treasure. Strategy balanced collects coins and good challenges while avoiding spikes and keeping lives; swift is the shortest path; get_coins greedily takes coins.
    Parameters:
        game_map     (required) - the 2D grid array as a JSON string
        start_pos    (required) - start position as a JSON string [row, col], zero indexed
        strategy     (required) - balanced, swift or get_coins
    ---

    Tiles: wall blocked, treasure goal, c1-c6 and c17-c18 challenges, c7 coins, c8 spikes,
    c30-c33 doors, c40-c43 keys.
    """
    try:
        body = event
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        grid = _parse_grid(body.get("game_map", []))
        if not grid or not isinstance(grid, list):
            return {"statusCode": 400, "body": json.dumps({"error": "Missing or invalid game_map"})}
        start = body.get("start_pos", [0, 0])
        if isinstance(start, str):
            try:
                start = json.loads(start)
            except json.JSONDecodeError:
                start = [0, 0]
        for r, row in enumerate(grid):
            for c, cell in enumerate(row):
                if cell == "start":
                    start = [r, c]
        strategy = body.get("strategy") or "balanced"
        over = {k: body[k] for k in ("lives", "step_cost", "max_steps") if k in body}
        # Deployment-time dials (Lambda environment variables) - no retraining needed:
        #   P_SCALE   multiplies every assumed challenge success probability (e.g. 0.6 = cautious planner)
        #   P_SUCCESS JSON per-tile accuracy overrides, e.g. {"c6": 0.2}; MAX_CHALLENGES cap on challenges visited
        #   STEP_COST points given up per step (speed pressure)
        scale = float(os.environ.get("P_SCALE", "1") or 1)
        if scale != 1:
            over["p_success"] = {k: min(1.0, v * scale) for k, v in DEFAULT_PARAMS["p_success"].items()}
        if os.environ.get("P_SUCCESS"):   # per-tile accuracy, e.g. {"c6": 0.2, "c4": 0.3}  (low value = planner avoids that tile)
            over.setdefault("p_success", dict(DEFAULT_PARAMS["p_success"]))
            over["p_success"].update({k: float(v) for k, v in json.loads(os.environ["P_SUCCESS"]).items()})
        if os.environ.get("MAX_CHALLENGES"):  # cap on challenges visited (protects the time limit)
            over["max_challenges"] = int(os.environ["MAX_CHALLENGES"])
        if "step_cost" not in over and os.environ.get("STEP_COST"):
            over["step_cost"] = float(os.environ["STEP_COST"])
        P = make_params(over)
        if _find(grid, "treasure") is None:
            return {"statusCode": 400, "body": json.dumps({"error": "No treasure found on map"})}
        path = plan_moves(grid, tuple(start), strategy, P)
        return {"statusCode": 200, "body": json.dumps({"path": path, "steps": len(path), "start_position": list(start), "strategy": strategy})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
