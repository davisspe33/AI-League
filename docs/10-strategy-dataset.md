# 10 — "balanced" strategy tool + dataset (built 2026-10-04) — files in `training/`

## What exists
- **BalancedPathfinder** Lambda tool: new strategy `balanced` (plus CE-identical `swift`, `get_coins`). Maximises EXPECTED score: coins, challenge points, lives, treasure, speed (steps), avoids spikes, uses keys for doors. Dials via env vars `P_SCALE`, `STEP_COST`.
- **Dataset** `training/data/strategy-{train,eval}.jsonl` (500/100): random maps 5x5–15x15 incl. spikes, challenges (c1–c6), coins, ~25% doors/keys, chokepoint spikes. Prompt = CE navigation preamble; target = ONE `route` tool call (game_map as JSON string, start_pos string, strategy). 15% of prompts name a strategy ("Use strategy: X") so the model also learns to follow instructions.
- **Reward** `training/reward-function-strategy.py` (local, no AWS calls): 0.10 valid call + right tool, 0.35 exact map copy, 0.10 start_pos, 0.30 strategy quality, 0.15 concise (no thinking/chatter = fewer tokens).
- Regenerate/tune: see `training/README.md`.

## Verified [verified: code run on this machine]
- Score model vs the REAL CE game engine: 1,200 cases (maps x strategies x all-correct/all-wrong answers, incl. spikes, doors, keys, garbage paths) → **0 mismatches**.
- Expected-score DP vs engine with random answers (8 maps x 2000 draws): worst z = 2.0 (noise level).
- Lambda handler: 100/100 dataset tool calls return the exact ground-truth path; reward fn gives 1.0 to perfect responses, 0.71 to worst strategy, 0.85 to a wasteful "thinking" response, 0 to no tool call.

## Headline results (100 eval maps, assumed accuracy table in index.py, 5 pts/step)
| strategy | expected objective | steps | exp. lives left | P(death) | coins | challenge pts |
|---|---|---|---|---|---|---|
| swift | 2372 | 11 | 4.03 | 0.06 | 184 | 295 |
| get_coins | 3678 | 37 | 3.05 | 0.12 | 1538 | 684 |
| **balanced** | **5868** | 61 | 3.07 | 0.11 | 1724 | 2796 |
`balanced` beats swift on 99% and get_coins on 98% of maps (under the assumed probabilities).

## Sensitivity — if the agent's real challenge accuracy is X times the assumed one (150 maps)
| true accuracy | swift | get_coins | balanced (default) | balanced (P_SCALE 0.6) |
|---|---|---|---|---|
| 0.4x | 2074 | 2830 | 2593 | 3535 |
| 0.6x | 2165 | 3098 | 3570 | 4118 |
| 0.8x | 2257 | 3369 | 4690 | 4664 |
| 1.0x | 2349 | 3643 | 5806 | 5194 |
| 1.15x | 2408 | 3822 | 6442 | 5552 |
**Calibrate:** measure your real per-challenge accuracy in the practice app, then set `P_SCALE` (e.g. ~0.6–0.8 if you miss many). Below ~0.5x of the assumed accuracy, `get_coins` can beat default `balanced`.

## Caveats / assumptions (check against the real event)
1. Challenge success probabilities are ASSUMED (c5 .95 … c6 .50). Challenge ANSWER quality is not trained here — only the route.
2. Speed bonus unknown → modelled as 5 pts/step. Tile points, damage, lives (5), bonuses = CE defaults; event may override. Doors are assumed to carry challenges (CE only scores them if the map defines one).
3. Token cost of visiting more challenges (each = LLM calls) is not modelled; the CE token bonus is tokens PER challenge visited, so check real token use when running longer routes.
4. The dataset only pays off if the deployed tool implements `balanced` (the CE Pathfinder treats unknown strategies as swift). Confirm custom tools are allowed (`09-todo-and-questions.md`).
5. Labels are ~92% `balanced` by design (it wins almost always); the fine-tune mostly buys reliable format, exact map copying and low token use. Biggest failure mode to watch: copying a 15x15 grid exactly (0.35 of reward).
6. `--map-format array` saves escape-quote tokens but the CE auto-schema types game_map as string — keep `string` unless the gateway schema is changed.
