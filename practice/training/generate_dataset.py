#!/usr/bin/env python3
"""Build the AI League 'strategy' RLVR dataset (JSONL) + report.

Task taught to the (fine-tuned) sub-agent: read the navigation prompt, call the route tool ONCE
with game_map / start_pos / strategy. The strategy label is the one whose planned path has the
best expected score (coins, lives, treasure, challenges, speed) according to BalancedPathfinder.

Usage:  python3 generate_dataset.py [--train 500] [--eval 100] [--seed 7] [--tool-name route]
                                    [--map-format string|array] [--explicit-frac 0.15]
                                    [--door-frac 0.25] [--out data]
"""
import argparse, hashlib, importlib.util, json, os, random, statistics
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("bp", os.path.join(HERE, "BalancedPathfinder", "index.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

STRATEGIES = ["balanced", "swift", "get_coins"]
SIZES = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
SIZE_W = [1, 1, 1, 2, 2, 4, 3, 3, 2, 2, 3]
CH_TYPES = ["c1", "c2", "c3", "c4", "c5", "c6"]
CH_W = [2, 2, 2, 2, 3, 1]

SYSTEM_PROMPT = (
    "You are the Pathfinding Specialist. Call the route tool once. game_map: the grid from the input as a "
    "JSON string. start_pos: the start as a JSON string [row,col] (letter = column starting A=0, number = row "
    "starting 1=0). strategy: balanced, unless the input names swift or get_coins. Then reply with only the path array."
)
TOOL_DESC = ("Route planner for the dungeon map. Returns the move list from start to treasure. Strategy balanced collects "
             "coins and good challenges while avoiding spikes and keeping lives; swift is the shortest path; get_coins "
             "greedily takes coins.")


def coords_to_label(r, c):
    return f"{chr(ord('A') + c)}{r + 1}"


def nav_prompt(grid, start):
    """Same text as CE prompt_formatter.format_navigation_prompt."""
    return (
        f"Find a path from position {coords_to_label(*start)}, where the position is "
        f"formatted as {{column}}{{row}}. {{column}} is a letter starting "
        f"with A, and {{row}} is a number starting with 1. The map object's "
        f"coordinates are formatted as [{{rowIndex}},{{columnIndex}}], where "
        f"{{rowIndex}} is the row number starting with 0, and "
        f"{{columnIndex}} is the column number starting with 0. The path "
        f"should find the treasure on this map: {json.dumps(grid)}."
    )


# ----------------------------------------------------------------------------- map generation

def _bfs_path(g, s, t, blocked=()):
    n, m = len(g), len(g[0])
    prev, q = {s: None}, deque([s])
    while q:
        cur = q.popleft()
        if cur == t:
            out = []
            while cur is not None:
                out.append(cur)
                cur = prev[cur]
            return out[::-1]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx = (cur[0] + dr, cur[1] + dc)
            if 0 <= nx[0] < n and 0 <= nx[1] < m and nx not in prev and g[nx[0]][nx[1]] != "wall" and nx not in blocked:
                prev[nx] = cur
                q.append(nx)
    return None


def _reachable(g, s, blocked=()):
    n, m = len(g), len(g[0])
    seen, q = {s}, deque([s])
    while q:
        cur = q.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx = (cur[0] + dr, cur[1] + dc)
            if 0 <= nx[0] < n and 0 <= nx[1] < m and nx not in seen and g[nx[0]][nx[1]] != "wall" and nx not in blocked:
                seen.add(nx)
                q.append(nx)
    return seen


def gen_map(rng, size, door_frac=0.25, spike_gate_frac=0.15):
    for _ in range(500):
        n = size
        wall_p = rng.uniform(0.10, 0.27)
        g = [["wall" if rng.random() < wall_p else "normal" for _ in range(n)] for _ in range(n)]
        cells = [(r, c) for r in range(n) for c in range(n) if g[r][c] != "wall"]
        if len(cells) < n * n * 0.5:
            continue
        s = rng.choice(cells)
        far = [x for x in cells if abs(x[0] - s[0]) + abs(x[1] - s[1]) >= max(3, int(n * 0.8))]
        if not far:
            continue
        t = rng.choice(far)
        path = _bfs_path(g, s, t)
        if path is None:
            continue
        free = [x for x in cells if x not in (s, t)]
        rng.shuffle(free)
        k_coin = round(len(free) * rng.uniform(0.04, 0.10))
        k_spk = round(len(free) * rng.uniform(0.02, 0.07))
        k_ch = round(len(free) * rng.uniform(0.04, 0.10))
        it = iter(free)
        for _i in range(k_coin):
            r, c = next(it); g[r][c] = "c7"
        for _i in range(k_spk):
            r, c = next(it); g[r][c] = "c8"
        for _i in range(k_ch):
            r, c = next(it); g[r][c] = rng.choices(CH_TYPES, CH_W)[0]
        g[s[0]][s[1]] = "start"
        g[t[0]][t[1]] = "treasure"
        # chokepoints on the shortest path (cells whose removal disconnects start/treasure)
        cuts = [p for p in path[1:-1] if _bfs_path(g, s, t, blocked={p}) is None]
        if cuts and rng.random() < spike_gate_frac:
            r, c = rng.choice(cuts); g[r][c] = "c8"
        if rng.random() < door_frac:
            colors = rng.sample([0, 1, 2, 3], rng.choice([1, 1, 2]))
            used = set()
            for col in colors:
                door, key = f"c{30 + col}", f"c{40 + col}"
                path_now = _bfs_path(g, s, t) or path
                cuts = [p for p in path_now[1:-1] if _bfs_path(g, s, t, blocked={p}) is None and p not in used]
                if cuts and rng.random() < 0.6:
                    d = rng.choice(cuts)
                else:
                    pool = [x for x in cells if x not in (s, t) and x not in used and g[x[0]][x[1]] in ("normal", "c7", "c8") or (x in cells and x not in (s, t) and x not in used and g[x[0]][x[1]] in CH_TYPES)]
                    if not pool:
                        continue
                    d = rng.choice(pool)
                saved = g[d[0]][d[1]]
                g[d[0]][d[1]] = "wall"      # key must be reachable without crossing the door
                reach = _reachable(g, s)
                g[d[0]][d[1]] = saved
                kc = [x for x in reach if x not in (s, t, d) and x not in used and g[x[0]][x[1]] not in ("wall", "treasure", "start")]
                if not kc:
                    continue
                k = rng.choice(kc)
                g[d[0]][d[1]], g[k[0]][k[1]] = door, key
                used.update([d, k])
        # sanity: treasure still reachable for plain BFS (doors are passable for BFS)
        if _bfs_path(g, s, t) is None:
            continue
        return g, s
    raise RuntimeError("could not generate map")


def render(grid, moves=None, start=None):
    sym = {"wall": "#", "normal": ".", "start": "S", "treasure": "T", "c7": "$", "c8": "^", "c1": "1", "c2": "2",
           "c3": "3", "c4": "4", "c5": "5", "c6": "6", "c30": "D", "c31": "D", "c32": "D", "c33": "D",
           "c40": "k", "c41": "k", "c42": "k", "c43": "k"}
    rows = [[sym.get(x, "?") for x in row] for row in grid]
    out = [r[:] for r in rows]
    if moves and start:
        r, c = start
        for mv in moves[:-1]:
            dr, dc = bp._DELTA[mv]; r += dr; c += dc
            if out[r][c] == ".":
                out[r][c] = "*"
    return "\n".join("".join(r) for r in out)


# ----------------------------------------------------------------------------- records

def tool_def(tool_name, map_format):
    gm = {"type": "string", "description": "the 2D grid array as a JSON string"} if map_format == "string" else \
        {"type": "array", "description": "the 2D grid array"}
    return {"type": "function", "function": {"name": tool_name, "description": TOOL_DESC, "parameters": {
        "type": "object",
        "properties": {
            "game_map": gm,
            "start_pos": {"type": "string", "description": "start position as a JSON string [row, col], zero indexed"},
            "strategy": {"type": "string", "description": "balanced, swift or get_coins"},
        },
        "required": ["game_map", "start_pos", "strategy"]}}}


def make_record(rng, index, split, tool_name, map_format, explicit_frac, door_frac, P):
    size = rng.choices(SIZES, SIZE_W)[0]
    grid, start = gen_map(rng, size, door_frac)
    scores, plans = {}, {}
    for st in STRATEGIES:
        mv = bp.plan_moves(grid, start, st, P)
        plans[st] = mv
        scores[st] = bp.evaluate(grid, start, mv, P)
    best = max(STRATEGIES, key=lambda s: (round(scores[s]["objective"], 6), s == "balanced"))
    explicit = rng.random() < explicit_frac
    required = None
    user = nav_prompt(grid, start)
    label = best
    if explicit:
        required = rng.choice(STRATEGIES)
        label = required
        user += f" Use strategy: {required}."
    gm = json.dumps(grid, separators=(",", ":"))
    args = {"game_map": gm if map_format == "string" else grid, "start_pos": json.dumps(list(start), separators=(",", ":")), "strategy": label}
    expected_response = "<tool_call>\n" + json.dumps({"name": tool_name, "arguments": args}, separators=(",", ":")) + "\n</tool_call>"
    gt = {
        "function": {"name": tool_name, "arguments": json.dumps({"game_map": grid, "start_pos": list(start), "strategy": label}, separators=(",", ":"))},
        "output": {"statusCode": 200, "body": json.dumps({"path": plans[label], "steps": len(plans[label])})},
        "strategy_scores": {s: round(scores[s]["objective"], 2) for s in STRATEGIES},
        "best_strategy": best,
    }
    if required:
        gt["required_strategy"] = required
    counts = {k: sum(row.count(k) for row in grid) for k in ("c7", "c8")}
    extra = {
        "index": index, "split": split, "tool": tool_name, "map_size": size, "strategy": label,
        "explicit_strategy": explicit, "position": coords_to_label(*start),
        "n_coins": counts["c7"], "n_spikes": counts["c8"],
        "n_challenges": sum(row.count(c) for row in grid for c in CH_TYPES) if False else sum(1 for row in grid for x in row if x in CH_TYPES),
        "n_doors": sum(1 for row in grid for x in row if x in bp.DOORS),
        "expected_response": expected_response,
    }
    rec = {
        "prompt": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        "tools": [tool_def(tool_name, map_format)],
        "reward_model": {"ground_truth": json.dumps(gt, separators=(",", ":")), "style": "rule"},
        "extra_info": extra,
        "ability": "tool_use",
    }
    return rec, grid, start, scores, plans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=500)
    ap.add_argument("--eval", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tool-name", default="route")
    ap.add_argument("--map-format", choices=["string", "array"], default="string")
    ap.add_argument("--explicit-frac", type=float, default=0.15)
    ap.add_argument("--door-frac", type=float, default=0.25)
    ap.add_argument("--out", default=os.path.join(HERE, "data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    P = bp.make_params()
    seen, report, samples = set(), {}, []
    for split, count, seed_off in (("eval", a.eval, 1000), ("train", a.train, 0)):  # eval first -> train maps never duplicate eval
        rng = random.Random(a.seed + seed_off)
        recs, agg = [], {s: [] for s in STRATEGIES}
        label_count = {s: 0 for s in STRATEGIES}
        while len(recs) < count:
            rec, grid, start, scores, plans = make_record(rng, len(recs), split, a.tool_name, a.map_format, a.explicit_frac, a.door_frac, P)
            h = hashlib.md5(json.dumps(grid).encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            recs.append(rec)
            label_count[rec["extra_info"]["strategy"]] += 1
            for s in STRATEGIES:
                agg[s].append(scores[s])
            if split == "eval" and len(samples) < 3 and 8 <= len(grid) <= 11:
                samples.append((grid, start, plans, scores))
        path = os.path.join(a.out, f"strategy-{split}.jsonl")
        with open(path, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        mean = lambda key, s: round(statistics.mean(x[key] for x in agg[s]), 2)
        report[split] = {
            "records": len(recs), "label_counts": label_count,
            "mean_by_strategy": {s: {"objective": mean("objective", s), "score": mean("score", s), "steps": mean("steps", s),
                                     "exp_lives": mean("exp_lives", s), "p_treasure": mean("p_treasure", s),
                                     "p_death": mean("p_death", s), "coin_points": mean("coin_points", s),
                                     "challenge_points": mean("challenge_points", s)} for s in STRATEGIES},
            "balanced_beats_swift_pct": round(100 * sum(b["objective"] > w["objective"] + 1e-6 for b, w in zip(agg["balanced"], agg["swift"])) / len(recs), 1),
            "balanced_beats_get_coins_pct": round(100 * sum(b["objective"] > w["objective"] + 1e-6 for b, w in zip(agg["balanced"], agg["get_coins"])) / len(recs), 1),
            "balanced_worse_than_any_pct": round(100 * sum(b["objective"] < max(w["objective"], x["objective"]) - 1e-6 for b, w, x in zip(agg["balanced"], agg["swift"], agg["get_coins"])) / len(recs), 1),
        }
        print(split, path, len(recs))
    with open(os.path.join(a.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(a.out, "sample_maps.txt"), "w") as f:
        for i, (grid, start, plans, scores) in enumerate(samples):
            f.write(f"=== sample {i + 1}  legend: S start, T treasure, $ coin, ^ spike, 1-6 challenges, D door, k key, # wall, * path\n")
            for s in STRATEGIES:
                f.write(f"--- {s}: steps={scores[s]['steps']} objective={scores[s]['objective']:.0f} p_death={scores[s]['p_death']:.2f} "
                        f"exp_lives={scores[s]['exp_lives']:.2f} coins={scores[s]['coin_points']:.0f} challenges={scores[s]['challenge_points']:.0f}\n")
                f.write(render(grid, plans[s], start) + "\n")
            f.write("\n")
    print(json.dumps(report["eval"]["mean_by_strategy"], indent=1))


if __name__ == "__main__":
    main()
