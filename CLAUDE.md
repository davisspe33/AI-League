# AI League — Working Context (read this first)

Personal prep hub for the **AWS AI League** (agentic "dungeon maze" challenge + model fine-tuning track).
Open the sub-file you need; don't load them all. Last updated: 2026-10-04.

## Where things are
- `practice/ai-league-community-edition/` — cloned open-source Community Edition (CE): practice app, real scoring/pathfinder code.
- `docs/` — distilled notes (index below). Prefer these over re-reading the repo.

## Status snapshot
- Company event is ~1 week out (player said on 2026-10-03 "I play in a week"). It includes the **fine-tuning** track. Leaderboard scores are already high, so small optimizations matter.
- Built (2026-10-04): `training/` has a hazard/coin/challenge-aware `balanced` route tool, 500+100 RLVR dataset and reward function, validated against the real CE engine (`docs/10-strategy-dataset.md`). Next: deploy tool in CE, calibrate P_SCALE from real runs, smoke-test fine-tune.
- Not yet done: deploy CE, baseline runs, quota request, organizer questions (see `docs/09-todo-and-questions.md`).
- Player does NOT want to pay for fine-tuning yet. Free prep first; one paid run in the last ~2 days.

## Index — what to open for which task
| Task | File |
|---|---|
| What the game/event is, dates, formats | `docs/01-overview.md` |
| Score formula, token bonus math, what to optimize | `docs/02-scoring.md` |
| Tile codes (c1–c8…), points, damage | `docs/03-tiles-and-map.md` |
| Supervisor/sub-agent/Pathfinder flow, tool schema, prompt assembly | `docs/04-architecture.md` |
| Prompting strategy + experiments to run | `docs/05-prompting-playbook.md` |
| Fine-tuning plan, dataset/reward design, cost control | `docs/06-fine-tuning.md` |
| Deploying/running the practice app, commands, costs | `docs/07-practice-env.md` |
| Run log template (record every experiment here) | `docs/08-run-log.md` |
| Open questions for organizer + checklist | `docs/09-todo-and-questions.md` |
| Built "balanced" strategy tool, RLVR dataset, reward fn, validation, sensitivity | `docs/10-strategy-dataset.md` (code in `training/`) |

## Ground rules for Claude in this folder
1. **Cost safety:** never start SageMaker training, deploy Bedrock custom models, or run `cdk deploy`/`destroy` without explicit approval. Fine-tuning is ~$80/hour. Claude models are not covered by AWS credits.
2. **Confidence labels:** facts tagged `[verified: code]` were read from the CE source; `[web]` came from AWS/community pages; `[unverified]` or `[idea]` must be checked before relying on them. The official event may differ from the CE.
3. **Log experiments** in `docs/08-run-log.md` (one change at a time).
4. **Known trap (still true for the SAMPLE data; `training/` dataset fixes it):** CE sample training data uses tool `pathfinding_lambda` with strategies `quickest`/`coins_first`, but the CE's actual tool is `pathfinding` with `swift`/`get_coins`. Match training data to the real tool schema (`docs/06-fine-tuning.md`).
5. Keep notes short and update the relevant sub-file when something is learned; update the status snapshot above.

## LIVE GAME (2026-10-16) - read first
- docs/11-live-game-rules.md : official rules, DQ list, bonuses, Lambda env dials, checklist
- docs/12-challenges.md : full challenge catalog (c1,c2,c4,c5,c7,c8,c18,c30,c31,c40,c41)
- docs/13-test-map-analysis.md : test map analysis, sweep route, top-5 target
- DQ rules: no hardcoded paths, no map JSON stored in pathfinder, no hardcoded answers, no undefined external sites.
- Custom pathfinder strategies ARE allowed via the Navigation Prompt.
