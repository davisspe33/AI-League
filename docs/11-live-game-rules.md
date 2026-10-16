# 11 - Live Game Rules (official, pasted on game day 2026-10-16)

Confidence: [verified: organizer rules]. Supersedes guesses in older docs.

## Objective
Agent navigates the grid maze to the treasure, answering challenge tiles, avoiding spikes, collecting coins.

## DISQUALIFICATION (never do these)
1. Hardcoding navigation paths.
2. Storing the map JSON inside the pathfinder.
3. Hardcoding challenge answers.
4. Calling external sites not defined in the challenge.
`training/BalancedPathfinder` is compliant: it receives the map at call time and stores no maps/paths/answers.

## Game stops when
- Time runs out, OR lives hit 0, OR treasure reached.
(Wall / off-grid step = instant game over in CE engine.)

## Allowed / hinted
- Custom pathfinder strategies are allowed; define them dynamically in the **Navigation Prompt** (e.g. "Use strategy: balanced").
- Tools: Lambda, AgentCore Memory (keys), Guardrails (c1), Code Interpreter (c2).
- Coins (c7) are free points: pass over them.

## Bonuses
| Item | Value |
|---|---|
| Treasure | +1000 |
| Lives left | 5 x 250 max |
| Token bonus | 1000 - (total tokens / challenges visited) (CE: reduced by custom-model count) |
| Challenge / coin points | per tile, see docs/12-challenges.md |

## Implications for today
- Token bonus is per challenge visited: keep prompts tiny, single agent, no map echo in prose.
- Time limit is wall-clock and each challenge answer takes seconds: don't plan a 60-step route with 15 challenges. Use `MAX_CHALLENGES` env on the Pathfinder Lambda and/or `STEP_COST`.
- Lives are worth 250 each: avoid spikes (c8) and doors without key (-5 = death).

## BalancedPathfinder env dials (Lambda environment variables)
| Var | Meaning | Example |
|---|---|---|
| P_SCALE | scales all assumed challenge accuracies | 0.6 = cautious |
| P_SUCCESS | JSON per-tile accuracy override; low value = planner avoids tile | {"c6":0.2,"c4":0.3} |
| MAX_CHALLENGES | cap on challenges visited (protects time limit) | 8 |
| STEP_COST | points per step (speed value) | 5 |
Navigation prompt: `Use strategy: balanced`. Tested: selftest + 480 engine cases, 0 mismatches.

## LIVE pathfinder: `Live-game-files/pathfinder-2.py` (use this, supersedes BalancedPathfinder for game day)
Goal = perfect run: every coin, challenge, key, door; zero spikes; key before its door; end on treasure; fewest steps.
- Strategy `sweep` (default; anything not "swift" maps to it). `swift` = safe shortest (no spikes, no locked doors).
- Fully dynamic: tiles classified by pattern (c7 coin, c8 spike, c3N door <- c4N key, any other cN = challenge), map read at call time. No stored maps/paths/answers.
- Solver: BFS legs per unlocked-door state + greedy + 2-opt/or-opt + iterated local search, seeded by map CRC (deterministic).
- Env: `TIME_BUDGET` seconds (default 2; converges in ~0.2s on 10x10). Keep below the tool Lambda timeout.
- Fallbacks: no spike-free route -> min-damage path to treasure (keys picked up, fewest lives lost) -> plain BFS.
- Items only reachable through spikes are skipped (logged as `skipped=` in CloudWatch RESULT line).
- Returns only `{"path": [...]}` (fewer tokens). CloudWatch logs steps, collected, lives_lost, skipped.
- Test map: 79 steps, all 44 items, 5 lives, treasure. `python3 Live-game-files/test_pathfinder.py 100` -> 100/100 perfect via real CE engine.
- `pathfinder-1.py` = old swift/get_coins version (rollback only; it walks over spikes and locked doors).

## Game-day checklist
1. Deploy `Live-game-files/pathfinder-2.py` as the pathfinder Lambda (handler `lambda_handler`, tool name `route`).
2. Navigation prompt: `Use strategy: sweep`; no map/paths in prompts.
3. Agent must answer every challenge correctly (the route assumes it): c4 scraper, c2 code tool, c18 JSON, c1 guardrail, keys in Memory.
4. Log each run in docs/08-run-log.md.
