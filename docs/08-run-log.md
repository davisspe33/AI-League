# 08 — Run log (one change per run)

Columns: date | map | model | prompt version | strategy | score | lives left | tokens | notes

| date | map | model | prompt ver | strategy | score | lives | tokens | notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-16 | live test map (finance theme) | Haiku (sup + 3 subs) | Run-1 | sweep | 13620 practice / 14480 judged | 1 | 2342 / 2215 judged | Path perfect (all coins, 0 spikes, treasure, 148s). Lost: both keys (didn't say Thanks), both c1 (no guardrail block), c18 (wrong schema), c2 (wrong number). |

## Prompt versions
### v0 (default)
```
(paste default / baseline prompt here)
```

## Best so far
- (map): score ___ with prompt vN — why it worked:

## Lessons
- Run 1 (2026-10-16): only OUTPUT tokens count (CE game_runner sums outputTokens). 180 tokens/challenge -> token bonus 820.
- Keys: message "<Color> Key N is: <code>" must get the reply "Thanks". The supervisor applied the door transform instead (-50 each).
- Doors: "What is <color> key N?" -> red = reversed code, green = letters as numbers written together. Both won.
- c1 is graded by ApplyGuardrail(DRAFT) on the question. Model refusals never pass. Needs a real guardrail (Run-2/guardrail.md).
- c18 on this map was a loan application, not a patient: the healthcare-only schema gave all nulls and lost.
- c2: Coder returned $394,780.00; correct daily-compounded value is about $402,737.03. Coder likely didn't run code.
- c5 one-sentence answers won 3/3; c4 WebScout won.
- Potential from fixes: +2000 challenge pts + up to +1000 lives (4 lost).
