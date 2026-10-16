#!/usr/bin/env python3
"""Validate the planner's score model against the REAL Community Edition game engine.

Runs random maps/paths through CE lambda/agentic-api/game_runner.run_game_session (boto3 stubbed)
with all challenges answered correctly (p=1) and all wrong (p=0) and compares:
  runner (finalScore - givenTokenBonus), lives, treasure   vs   BalancedPathfinder.evaluate().
Usage: python3 validate_planner.py [path/to/ai-league-community-edition] [n_maps]
"""
import importlib.util, os, random, sys, types
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
CE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "practice", "ai-league-community-edition")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 300
api = os.path.join(CE, "lambda", "agentic-api")
sys.path.insert(0, api)
for name in ("boto3", "botocore", "botocore.exceptions"):
    sys.modules.setdefault(name, mock.MagicMock())
stub = types.ModuleType("agentcore_client")
stub.invoke_agent_runtime = lambda *a, **k: None
class AgentCoreTimeoutError(Exception): pass
stub.AgentCoreTimeoutError = AgentCoreTimeoutError
sys.modules["agentcore_client"] = stub
import game_runner  # noqa: E402

spec = importlib.util.spec_from_file_location("gd", os.path.join(HERE, "generate_dataset.py"))
gd = importlib.util.module_from_spec(spec); spec.loader.exec_module(gd)
bp = gd.bp


def run_ce(grid, start, moves, correct):
    challenges = {}
    for r, row in enumerate(grid):
        for c, t in enumerate(row):
            if t in bp.CHALLENGES or t in bp.DOORS:
                challenges[f"{r},{c}"] = {"question": "q", "expectedAnswer": "CORRECT" if correct else "ZZZ", "gradingStrategy": "contains_match"}
    md = {"grid": grid, "challenges": challenges, "playerStart": {"row": start[0], "col": start[1]},
          "defaults": {"lives": 5, "livesBonusMultiplier": 250, "tokenBonus": 1000, "treasureBonus": 1000}, "tileOverrides": {}}
    pos, (r, c) = [], start
    for mv in moves:
        dr, dc = bp._DELTA[mv]; r += dr; c += dc; pos.append((r, c))
    return game_runner.run_game_session("v", md, pos, 0)


def main():
    rng = random.Random(123)
    bad, checked = 0, 0
    for i in range(N):
        grid, start = gd.gen_map(rng, rng.choice([6, 8, 10, 12, 15]), 0.4)
        for strat in gd.STRATEGIES:
            moves = bp.plan_moves(grid, start, strat)
            if rng.random() < 0.3 and moves:           # also test sloppy/garbage-ish paths (random prefix + random walk)
                moves = moves[: rng.randint(1, len(moves))] + [rng.choice(["up", "down", "left", "right"]) for _ in range(rng.randint(0, 6))]
            for correct in (True, False):
                P = bp.make_params({"p_success": {k: (1.0 if correct else 0.0) for k in bp.DEFAULT_PARAMS["p_success"]}})
                mine = bp.evaluate(grid, start, moves, P)
                ce = run_ce(grid, start, moves, correct)
                ce_score = ce["finalScore"] - ce["givenTokenBonus"]
                ok = (abs(mine["score"] - ce_score) < 1e-6 and abs(mine["exp_lives"] - ce["livesRemaining"]) < 1e-6
                      and abs(mine["p_treasure"] - (1.0 if ce["reachedTreasure"] else 0.0)) < 1e-6)
                checked += 1
                if not ok:
                    bad += 1
                    if bad <= 5:
                        print("MISMATCH", strat, "correct=", correct, "mine", round(mine["score"]), round(mine["exp_lives"], 2), mine["p_treasure"],
                              "ce", ce_score, ce["livesRemaining"], ce["reachedTreasure"])
                        print(gd.render(grid, moves, start))
    print(f"checked {checked} (map,strategy,answer-mode) cases against the CE engine: {bad} mismatches")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
