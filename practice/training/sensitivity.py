#!/usr/bin/env python3
"""(1) Monte-Carlo check of the expected-score DP against the real CE engine with random challenge answers.
   (2) Sensitivity: how do strategies score if your agent answers challenges worse (or better) than assumed?
Usage: python3 sensitivity.py [path/to/ai-league-community-edition]"""
import random, statistics, sys, os
import validate_planner as vp
gd, bp, game_runner = vp.gd, vp.bp, vp.game_runner

def run_ce_random(grid, start, moves, P, rng):
    challenges = {}
    for r, row in enumerate(grid):
        for c, t in enumerate(row):
            if t in bp.CHALLENGES or t in bp.DOORS:
                ok = rng.random() < P["p_success"].get(t, 0.7)
                challenges[f"{r},{c}"] = {"question": "q", "expectedAnswer": "CORRECT" if ok else "ZZZ", "gradingStrategy": "contains_match"}
    md = {"grid": grid, "challenges": challenges, "playerStart": {"row": start[0], "col": start[1]},
          "defaults": {"lives": 5, "livesBonusMultiplier": 250, "tokenBonus": 1000, "treasureBonus": 1000}, "tileOverrides": {}}
    pos, (r, c) = [], start
    for mv in moves:
        dr, dc = bp._DELTA[mv]; r += dr; c += dc; pos.append((r, c))
    res = game_runner.run_game_session("v", md, pos, 0)
    return res["finalScore"] - res["givenTokenBonus"]

rng = random.Random(5)
P = bp.make_params()
print("== Monte-Carlo vs real CE engine (2000 random answer draws per map) ==")
worst_z = 0
for i in range(8):
    grid, start = gd.gen_map(rng, rng.choice([8, 10, 12, 15]), 0.4)
    moves = bp.plan_moves(grid, start, "balanced", P)
    exp = bp.evaluate(grid, start, moves, P)["score"]
    xs = [run_ce_random(grid, start, moves, P, rng) for _ in range(2000)]
    m, se = statistics.mean(xs), statistics.stdev(xs) / len(xs) ** 0.5
    z = abs(m - exp) / max(se, 1e-9); worst_z = max(worst_z, z)
    print(f"map {i}: DP expected {exp:8.1f} | engine mean {m:8.1f} +/- {se:5.1f} | z={z:.2f}")
print("worst z-score:", round(worst_z, 2), "(want < ~3.5)")

print("\n== Sensitivity: true answer accuracy = assumed accuracy x multiplier (150 maps) ==")
maps = [gd.gen_map(random.Random(900 + i), random.Random(i).choice([8, 10, 12, 15]), 0.25) for i in range(150)]
def scaled(mult):
    return bp.make_params({"p_success": {k: min(1.0, v * mult) for k, v in bp.DEFAULT_PARAMS["p_success"].items()}})
plans = {s: [bp.plan_moves(g, st, s, P) for g, st in maps] for s in ("swift", "get_coins", "balanced")}
cons = [bp.plan_moves(g, st, "balanced", scaled(0.6)) for g, st in maps]   # planned assuming a weak agent
print(f"{'true accuracy':>14} | {'swift':>7} {'get_coins':>9} {'balanced(default)':>18} {'balanced(plan@0.6x)':>20}")
for mult in (0.4, 0.6, 0.8, 1.0, 1.15):
    T = scaled(mult)
    row = [statistics.mean(bp.evaluate(g, st, mv, T)["objective"] for (g, st), mv in zip(maps, plans[s])) for s in ("swift", "get_coins", "balanced")]
    row.append(statistics.mean(bp.evaluate(g, st, mv, T)["objective"] for (g, st), mv in zip(maps, cons)))
    print(f"{mult:>13.2f}x | {row[0]:7.0f} {row[1]:9.0f} {row[2]:18.0f} {row[3]:20.0f}")
