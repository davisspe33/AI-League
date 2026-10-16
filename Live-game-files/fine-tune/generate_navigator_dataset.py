#!/usr/bin/env python3
"""Build the Navigator RLVR dataset (JSONL) for the live game.

Task taught: read the navigation input, call the `route` tool ONCE with
  game_map  = the grid as a JSON string (copied exactly)
  start_pos = "[row,col]" from the start label (letter = column A=0, number = row 1=0)
  strategy  = "sweep" (always; the live game only uses sweep and the system prompt says so)
and output nothing else.

System prompt and tool definition are identical to the live config
(Live-game-files/agent-prompts.md, Navigator; Live-game-files/pathfinder-2.py docstring).
If you change either there, change it here and regenerate.

Usage:  python3 generate_navigator_dataset.py [--train 500] [--eval 100] [--seed 11] [--budget 0.2]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.dirname(HERE)
ROOT = os.path.dirname(LIVE)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = _load("pf", os.path.join(LIVE, "pathfinder-2.py"))
gd = _load("gd", os.path.join(ROOT, "practice", "training", "generate_dataset.py"))

# Live-game challenge mix (docs/12-challenges.md); a few CE-only types keep the model general.
gd.CH_TYPES = ["c1", "c2", "c4", "c5", "c18", "c3", "c6", "c17"]
gd.CH_W = [3, 3, 3, 4, 3, 1, 1, 1]

TOOL_NAME = "route"
SYSTEM_PROMPT = (
    'Call route once: game_map = the grid as a JSON string, start_pos = the start as a JSON string "[row,col]" '
    '(letter = column, A=0; number = row, 1=0), strategy = "sweep". Output only the path array exactly as returned.'
)
TOOL_DESC = ("Route planner for the dungeon map. Returns the move list from start to treasure. Strategy sweep visits "
             "every coin, challenge, key and door (keys first) with no spikes; swift is the safe shortest path.")

LIVE_SUFFIX = " Use strategy: sweep. Output only the path array."
SWEEP_VARIANTS = [" Use strategy: sweep.", " Strategy: sweep.", " Collect everything and avoid spikes.",
                  " Use the sweep strategy. Return only the path."]


def tool_def():
    return {"type": "function", "function": {"name": TOOL_NAME, "description": TOOL_DESC, "parameters": {
        "type": "object",
        "properties": {
            "game_map": {"type": "string", "description": "the 2D grid array as JSON string or list"},
            "start_pos": {"type": "string",
                          "description": 'start position as [row, col] zero indexed, or a label like "A1"'},
            "strategy": {"type": "string", "description": "sweep (default) or swift"},
        },
        "required": ["game_map"]}}}


def pick_suffix(rng):
    x = rng.random()
    if x < 0.60:
        return LIVE_SUFFIX, "sweep"
    if x < 0.80:
        return "", "sweep"
    return rng.choice(SWEEP_VARIANTS), "sweep"


def make_record(rng, index, split, budget):
    size = rng.choices(gd.SIZES, gd.SIZE_W)[0]
    grid, start = gd.gen_map(rng, size)
    # Live maps may give the start only as a label (playerStart), not as a "start" tile.
    if rng.random() < 0.5:
        grid[start[0]][start[1]] = "normal"
    suffix, label = pick_suffix(rng)
    user = gd.nav_prompt(grid, start) + suffix
    gm = json.dumps(grid, separators=(",", ":"))
    sp = json.dumps(list(start), separators=(",", ":"))
    args = {"game_map": gm, "start_pos": sp, "strategy": label}
    expected = "<tool_call>\n" + json.dumps({"name": TOOL_NAME, "arguments": args}, separators=(",", ":")) + "\n</tool_call>"
    path, info = pf.plan(grid, tuple(start), label, budget)
    sim = pf.simulate(grid, tuple(start), path)
    gt = {
        "function": {"name": TOOL_NAME,
                     "arguments": json.dumps({"game_map": grid, "start_pos": list(start), "strategy": label},
                                             separators=(",", ":"))},
        "output": {"statusCode": 200, "body": json.dumps({"path": path})},
        "strategy": label,
    }
    extra = {
        "index": index, "split": split, "tool": TOOL_NAME, "map_size": size, "strategy": label,
        "position": gd.coords_to_label(*start), "has_start_tile": any("start" in r for r in grid),
        "suffix": suffix.strip(), "n_items": info.get("items"), "steps": len(path),
        "lives_lost": sim["lost"], "treasure": sim.get("treasure", False), "planner_mode": info.get("mode"),
        "expected_response": expected,
    }
    rec = {
        "prompt": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        "tools": [tool_def()],
        "reward_model": {"ground_truth": json.dumps(gt, separators=(",", ":")), "style": "rule"},
        "extra_info": extra,
        "ability": "tool_use",
    }
    return rec, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=500)
    ap.add_argument("--eval", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--budget", type=float, default=0.2, help="pathfinder seconds per map (ground-truth path only)")
    ap.add_argument("--out", default=os.path.join(HERE, "data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    seen, report = set(), {}
    for split, count, off in (("eval", a.eval, 1000), ("train", a.train, 0)):  # eval first: train never repeats an eval map
        rng = random.Random(a.seed + off)
        recs = []
        while len(recs) < count:
            rec, grid = make_record(rng, len(recs), split, a.budget)
            h = hashlib.md5(json.dumps(grid).encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            recs.append(rec)
        with open(os.path.join(a.out, f"navigator-{split}.jsonl"), "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        ex = [r["extra_info"] for r in recs]
        sweeps = [e for e in ex if e["strategy"] == "sweep"]
        report[split] = {
            "records": len(recs),
            "strategy_counts": {s: sum(e["strategy"] == s for e in ex) for s in ("sweep", "swift")},
            "live_suffix_pct": round(100 * sum(e["suffix"] == LIVE_SUFFIX.strip() for e in ex) / len(ex), 1),
            "start_tile_pct": round(100 * sum(e["has_start_tile"] for e in ex) / len(ex), 1),
            "map_sizes": dict(sorted({s: sum(e["map_size"] == s for e in ex) for s in gd.SIZES}.items())),
            "sweep_mean_steps": round(statistics.mean(e["steps"] for e in sweeps), 1),
            "sweep_treasure_pct": round(100 * sum(e["treasure"] for e in sweeps) / len(sweeps), 1),
            "sweep_zero_lives_lost_pct": round(100 * sum(e["lives_lost"] == 0 for e in sweeps) / len(sweeps), 1),
            "planner_modes": {m: sum(e["planner_mode"] == m for e in ex) for m in sorted({e["planner_mode"] for e in ex})},
            "mean_prompt_chars": round(statistics.mean(len(r["prompt"][1]["content"]) for r in recs)),
        }
        print(split, len(recs))
    with open(os.path.join(a.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
