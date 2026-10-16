# 06 — Fine-tuning plan

## What CE does [verified: README + estimated-costs.md]
- RLVR training in SageMaker Studio with **Qwen 3 0.6B**; reward function runs as a Lambda; trained model registered -> deployed via Bedrock Custom Model Import -> selectable in Agent Builder.
- Cost: **$80/hour**; ~500 samples/1 epoch ≈ 15–20 min ≈ $20–27; 3 epochs ≈ $60–80; 1000 samples/1 epoch ≈ $33–47. Set `max_runtime_in_seconds` hardstop. Needs quota "Maximum number of concurrent model customization serverless jobs per Region" in us-east-1 (request now).
- Deployed models cost while deployed (Bedrock provisioned units) — undeploy when done. Reset/`cdk destroy` clean up deployments.
- Token benefit: each custom model in the agent config raises token-penalty reduction (1→50% ... 5→95%). See `02-scoring.md`.
- Official event may use SageMaker AI + "Forge" and possibly a Nova model — confirm base model and workflow with organizer.

## Sample artifacts (practice/.../sample-training-artifacts/)
- `tool-call-training.jsonl` (500) / `tool-call-eval.jsonl` (100) + `reward-function-tool-call.py`; `faithfulness-training.jsonl` (403) / `-eval.jsonl` (81) + `reward-function-faithfulness.py` (faithfulness set NOT yet reviewed).
- They are **generic**: random maps 5x5–15x15, random start, strategy `quickest`/`coins_first`, output must be one tool call: `<tool_call>{"name":"pathfinding_lambda","arguments":{"game_map":[...],"start_pos":[r,c],"strategy":"..."}}</tool_call>`.
- No doors/keys/hazard logic; labels c1–c8 as coins.
- **MISMATCH:** real CE tool is `pathfinding` with `swift`/`get_coins`, and `game_map`/`start_pos` are JSON *strings*. Training on the samples as-is may teach the wrong format.
- Reward weights (tool-call): 0.20 correct tool + 0.50 params (map 50%, start 25%, strategy 25%) + 0.10 format + 0.10 lambda success + 0.10 output path match; soft partial credit (<=0.15) when no structured call.

## Custom dataset (BUILT) — see `10-strategy-dataset.md`
`training/data/strategy-train.jsonl` + `training/reward-function-strategy.py` implement steps 3–4 below for the `balanced` tool (matches real tool name/format).

## Plan
1. (Free) Ask organizer: exact tool name/params/strategies, base model, whether model count affects score, training track format.
2. (Free) Request the quota increase.
3. (Free) Build own dataset: random maps that look like the real ones (same sizes/tiles incl. doors, keys, spikes), ground truth from a local copy of the real Pathfinder code; keep the *exact* tool schema and system prompt the agent will use at game time. Hold out an eval split; do NOT overfit to one practice map.
4. (Free) Adapt reward function to the real tool name/params; unit-test it locally.
5. (~$few) Tiny smoke-test training run with a short hardstop to prove the pipeline.
6. (~$20–40) One real run in the last ~2 days; compare against untuned baseline on held-out maps.
7. Consider a second model (e.g. faithfulness/challenge-answering) only if model count affects score in the real event.

## Questions the data should teach
- Tool-call format correctness (biggest, cheapest win), then strategy choice, then short exact challenge answers.
