# training/ — "balanced" strategy tool + RLVR dataset

Goal: a route strategy that scores better than the CE `swift` / `get_coins` (which ignore spikes and
challenges), and a fine-tuning dataset that teaches the sub-agent to call it correctly and cheaply.

| File | What |
|---|---|
| `BalancedPathfinder/index.py` | Self-contained Lambda tool (strategies `balanced`, `swift`, `get_coins`). Deploy as an agent tool. |
| `generate_dataset.py` | Builds `data/strategy-train.jsonl` (500) + `data/strategy-eval.jsonl` (100), `report.json`, `sample_maps.txt`. |
| `reward-function-strategy.py` | Self-contained reward Lambda for the RLVR run (no AWS calls). |
| `agent-config-snippet.yaml` | Config to wire the tool + matching sub-agent system prompt into the CE. |
| `validate_planner.py` | Compares the score model to the REAL CE game engine (must report 0 mismatches). |
| `sensitivity.py` | Monte-Carlo check vs the engine + "what if my agent answers worse than assumed" table. |
| `selftest_reward.py`, `selftest_tool.py` | Reward function + Lambda handler self-tests on the dataset. |

## Run
```
cd training
python3 generate_dataset.py --train 500 --eval 100 --seed 7        # options: --tool-name route --map-format string|array --explicit-frac 0.15 --door-frac 0.25
python3 selftest_tool.py && python3 selftest_reward.py
python3 validate_planner.py ../practice/ai-league-community-edition 200
python3 sensitivity.py ../practice/ai-league-community-edition
```
Everything is local and free (Python 3 only, CE repo needed just for the two validation scripts).

## How the planner works (balanced)
Exact expected score of a path = coins + challenge points + lives*250 + treasure(1000) - 5/step (speed proxy), computed with a
lives-distribution DP so spikes, wrong answers, death risk, consumed tiles, doors/keys and "treasure ends the game" are all modelled.
Search: hazard-aware Dijkstra between waypoints + hill-climbing (insert coin/challenge/key/door waypoints, remove, 2-opt reverse),
keeping only changes that raise the expected score.

## Wiring it in
1. `cp -r BalancedPathfinder ../practice/ai-league-community-edition/agent-config/tools/`
2. Merge `agent-config-snippet.yaml` into `agent-config/config.yaml`, then `npm run seed-config -- --profile <p> --dry-run` and again without `--dry-run`.
3. Dials (Lambda environment variables, no retraining): `P_SCALE` (multiplies assumed challenge accuracy, e.g. 0.6 = cautious), `STEP_COST` (default 5).
4. Fine-tune with `data/strategy-train.jsonl` + `reward-function-strategy.py` (see `docs/06-fine-tuning.md`). The training system prompt, tool name (`route`)
   and string-typed args mirror what the Qwen model receives at game time (CE `bedrock_imported_model.py`).
