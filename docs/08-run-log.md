# 08 — Run log (one change per run)

Columns: date | map | model | prompt version | strategy | score | lives left | tokens | notes

| date | map | model | prompt ver | strategy | score | lives | tokens | notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-16 | live test map (finance theme) | Haiku (sup + 3 subs) | Run-1 | sweep | 13620 practice / 14480 judged | 1 | 2342 / 2215 judged | Path perfect (all coins, 0 spikes, treasure, 148s). Lost: both keys (didn't say Thanks), both c1 (no guardrail block), c18 (wrong schema), c2 (wrong number). |
| 2026-10-16 | live test map (same) | Haiku (sup + 3 subs) + guardrail | Run-2 | sweep | 8619 | 0 (dead at 100s) | 1629 | Keys won (Thanks). c1 won (guardrail). c5 'stages of money laundering' blocked by guardrail (-1). c18 guessed loan keys, lost (-1). Green door answered plain code 'abcde' instead of numbers -> -5, game over. |

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
- Run 2: doors cost 5 lives when answered wrong, not just when locked. Never let the LLM transform codes; Run 3 sends doors to Coder.
- Run 2: guardrail over-blocked an educational c5 (Misconduct HIGH and/or 'money laundering' in the topic definition).
- c18 is 0/2 (patient schema all-null, then guessed loan keys). The expected schema is unknown -> SKIP_TILES=c18 until it's known.
- Potential from fixes: +2000 challenge pts + up to +1000 lives (4 lost).
