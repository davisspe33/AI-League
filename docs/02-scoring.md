# 02 — Scoring (CE defaults) [verified: code — lambda/agentic-api/score_calculator.py, game_runner.py]

```
finalScore = qaScore + lifeBonusScore + givenTokenBonus + treasureBonus
qaScore         = challengePoints + coinPoints(c7)
lifeBonusScore  = livesRemaining * livesBonusMultiplier        (default 250)
treasureBonus   = treasureBonus if treasure reached else 0     (default 1000)
givenTokenBonus = clamp( tokenBonus - (totalTokens / challengesVisited) * (1 - reduction), 0, tokenBonus )   (tokenBonus default 1000)
```
- Starting lives default **5**; events may override (3 in 2025 finals; "reduced lives" EMEA). Map defaults and per-tile points/damage can be overridden per map/round.
- If `challengesVisited == 0` the full token bonus is awarded.
- `reduction` from number of custom (fine-tuned) models in the agent config: 0→0%, 1→50%, 2→70%, 3→85%, 4→92%, 5+→95%.

## Token bonus examples (tokenBonus=1000, totalTokens=6000, 4 challenges → 1500 tokens/challenge)
| custom models | penalty | bonus |
|---|---|---|
| 0 | 1500 | 0 |
| 1 | 750 | 250 |
| 2 | 450 | 550 |
| 5 | 75 | 925 |

## Implications / levers
1. Tokens are averaged **per challenge visited** → trim fixed overhead (long prompts, map JSON echoes, multi-agent chatter). More challenges visited dilutes fixed overhead, but each wrong answer costs a life (250 + risk). `[idea]` check with data.
2. Each life left = 250 pts; spikes (c8) and wrong answers cost lives → avoid c8 when cheap.
3. Treasure = 1000: always reach it; a path that dies early forfeits it plus life bonus.
4. Custom models are the biggest token-bonus lever (up to +925 here). Event may differ — confirm whether it counts models and how. Each model ≈ $20–$40 to train.
5. Challenge points per tile: see `03-tiles-and-map.md`.
