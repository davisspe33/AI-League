# Navigator fine-tune (live game)

Teaches the Navigator sub-agent to make ONE `route` tool call (grid copied exactly, correct start, `strategy: "sweep"`)
and output nothing else. Replaces `practice/training/data/strategy-*.jsonl`, which used the old `balanced` prompt.

| File | What |
|---|---|
| `generate_navigator_dataset.py` | Builds `data/navigator-train.jsonl` (500) + `navigator-eval.jsonl` (100) + `report.json` |
| `reward-function-navigator.py` | Reward Lambda for the RLVR run (self-contained, no AWS calls) |
| `selftest.py` | Checks prompt/tool match the live config, reward behaviour, and replays calls through pathfinder-2 |

```
python3 Live-game-files/fine-tune/generate_navigator_dataset.py
python3 Live-game-files/fine-tune/selftest.py
```

Rules:
- The system prompt is the Navigator prompt in `../agent-prompts.md` **verbatim**, and the tool description is the
  `pathfinder-2.py` docstring. If either changes, regenerate. `selftest.py` fails if they drift apart.
- The model-facing tool name is `route` (the runtime strips the gateway prefix `Target___route`).
- Maps: 5x5 to 15x15, live challenge mix (c1 c2 c4 c5 c18, a few c3/c6/c17), keys/doors, spikes.
  Half have a `start` tile, half rely on the start label only. About 60% end with the live navigation prompt suffix.
- Reward: tool name 0.10, map exact 0.40, start 0.15, strategy 0.20, concise 0.15.
- Cost: fine-tuning is ~$80/hour. Don't launch a training job without explicit approval.
- CE note: the token bonus may be reduced by the number of custom models used (docs/02-scoring.md). Check that a
  fine-tuned Navigator beats plain Haiku before using it in the game.
