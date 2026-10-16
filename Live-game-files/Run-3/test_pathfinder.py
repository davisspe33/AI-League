"""Checks pathfinder-2.py against the real CE game engine (all answers assumed correct).
Run:  python3 Live-game-files/test_pathfinder.py [n_random_maps]
Pass = treasure reached, 5 lives left, every reachable coin/challenge/key/door collected."""
import importlib.util
import json
import os
import random
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CE = os.path.join(HERE, "..", "practice", "ai-league-community-edition", "lambda", "agentic-api")
sys.path.insert(0, CE)
for _m in ("boto3", "botocore", "botocore.exceptions", "botocore.config"):
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.modules["boto3"].client = lambda *a, **k: None
sys.modules["botocore.exceptions"].ClientError = Exception
sys.modules["botocore.config"].Config = lambda *a, **k: None
import game_runner  # noqa: E402

spec = importlib.util.spec_from_file_location("pf", os.path.join(HERE, "pathfinder-2.py"))
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)

TEST_MAP = """n c7 c7 n n n n n c7 c7
w w w w w c7 w w w w
c40 w n c7 c7 c5 c7 c7 w c41
c4 w c8 w n c7 w c8 w c5
c7 n n c7 c7 c7 c7 c7 c7 n
c8 n w w w w w w w c18
c7 n c1 n c8 c7 c8 n c7 n
w w w c7 c7 c7 c7 c7 w n
c7 c7 w c8 w c8 w c8 w c31
treasure c7 c30 c2 c7 c1 c7 c5 c7 c7"""


def parse(text):
    return [["wall" if x == "w" else "normal" if x == "n" else x for x in r.split()] for r in text.split("\n")]


def engine(grid, start, moves):
    challenges = {}
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if pf.kind(cell) in ("challenge", "door"):
                challenges[f"{r},{c}"] = {"question": "q", "expectedAnswer": "CORRECT",
                                         "gradingStrategy": "contains_match"}
    coords = [start]
    for m in moves:
        dr, dc = pf._DELTA[m]
        coords.append((coords[-1][0] + dr, coords[-1][1] + dc))
    md = {"grid": grid, "challenges": challenges, "defaults": {}, "tileOverrides": {},
          "playerStart": {"row": start[0], "col": start[1]}}
    return game_runner.run_game_session("t", md, coords, 0)


def run_case(grid, start, label, verbose=False):
    t = time.time()
    ev = {"game_map": json.dumps(grid), "start_pos": json.dumps(list(start)), "strategy": "sweep"}
    out = pf.lambda_handler(ev, None)
    dt = time.time() - t
    moves = json.loads(out["body"])["path"]
    res = engine(grid, start, moves)
    board = pf.Board(grid)
    items, _ = pf._reachable_items(board, tuple(start))
    consumed = set(tuple(map(int, k.split(","))) for k in res["consumedTiles"])
    missed = [p for p in items if p not in consumed]
    ok = res["reachedTreasure"] and res["livesRemaining"] == 5 and not missed
    if verbose or not ok:
        print(f"{label}: ok={ok} steps={len(moves)} score={res['finalScore']} lives={res['livesRemaining']} "
              f"treasure={res['reachedTreasure']} items={len(items)} missed={missed} time={dt:.1f}s")
    return ok, len(moves), dt


def random_map(rng):
    n = rng.randint(8, 12)
    m = rng.randint(8, 12)
    pool = ["normal"] * 40 + ["wall"] * 18 + ["c7"] * 10 + ["c8"] * 6 + \
           ["c1", "c2", "c4", "c5", "c5", "c18"]
    g = [[rng.choice(pool) for _ in range(m)] for _ in range(n)]
    cells = [(r, c) for r in range(n) for c in range(m)]
    rng.shuffle(cells)
    start, treasure = cells[0], cells[1]
    g[start[0]][start[1]] = "normal"
    g[treasure[0]][treasure[1]] = "treasure"
    for i, d in enumerate(("0", "1")[: rng.randint(0, 2)]):
        g[cells[2 + 2 * i][0]][cells[2 + 2 * i][1]] = "c4" + d
        g[cells[3 + 2 * i][0]][cells[3 + 2 * i][1]] = "c3" + d
    return g, start


if __name__ == "__main__":
    os.environ.setdefault("TIME_BUDGET", "3")
    run_case(parse(TEST_MAP), (0, 0), "test map", verbose=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    rng = random.Random(1)
    done = fails = 0
    times = []
    while done < n:
        g, s = random_map(rng)
        b = pf.Board(g)
        if s not in b.bfs(s, frozenset())[0] or b.treasure not in pf._reachable_items(b, s)[1]:
            continue  # treasure not reachable without spikes; not a fair case
        ok, steps, dt = run_case(g, s, f"random {done}")
        fails += not ok
        times.append(dt)
        done += 1
    print(f"random maps: {done - fails}/{done} perfect, max solve time {max(times):.1f}s")
