# 09 — To-do and questions for organizer

## Ask the organizer (before spending money)
- [ ] Exact event date/time and format (leaderboard week? live finale? 45 s runtime prompt?).
- [ ] Tool name, parameters and strategy names of the Pathfinder in the event (CE: `pathfinding`, `swift`/`get_coins`).
- [ ] Are custom Lambda tools allowed? ("we deploy to a lambda" — what exactly do we deploy?)
- [ ] Fine-tuning track: base model (Qwen 3 0.6B? Nova?), tooling (SageMaker Studio / Forge), time limit, dataset provided or own?
- [ ] Does the number of custom models change the token bonus (CE: 1→50% ... 5→95%)?
- [ ] Lives, points, token bonus base, door/key rules; any DQs.
- [ ] What is "the jail file"? (assumed: guardrail config; confirm whether it is a file or a console setting)
- [ ] Are Claude models allowed/credit-covered? Credit budget?

## Checklist
- [ ] Request SageMaker quota increase (us-east-1)
- [ ] Deploy CE, play baseline on all predefined maps (log in `08-run-log.md`)
- [ ] Clone `ai-league-competition-data` into `practice/`
- [ ] Review faithfulness training set + reward function
- [ ] Prompt experiments (`05-prompting-playbook.md`)
- [x] Build dataset generator + adapted reward function (`training/`, `10-strategy-dataset.md`)
- [ ] Deploy BalancedPathfinder in CE; run baseline vs balanced on predefined maps; calibrate `P_SCALE`
- [ ] Custom hazard-aware pathfinder (optional)
- [ ] Smoke-test fine-tune with hardstop, then one real run in last ~2 days
- [ ] Pre-write 2–3 finale prompt templates


## Resolved (game day)
- Custom pathfinder + strategies in navigation prompt: ALLOWED. DQ list in docs/11.
