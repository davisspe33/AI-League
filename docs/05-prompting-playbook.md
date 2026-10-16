# 05 — Prompting playbook (free; start now)

Goal: maximize score with the fewest tokens and zero lost lives. Change ONE thing per run and log it in `08-run-log.md`.

## Baseline first
1. Deploy CE (`07-practice-env.md`), run each known map 3–5x with the default prompt. Record score, lives lost, tokens, strategy chosen.
2. Note variance: if the same prompt scores differently, reliability is the first thing to fix.

## Experiments (ordered by expected payoff) `[idea]` — verify each with runs
1. **Pin the strategy** in the user prompt (e.g. "Use strategy swift." / "Use strategy get_coins.") so the agent never improvises. Compare swift vs get_coins per map: coins are 250 each, but extra steps cross more hazards.
2. **Shrink every prompt**: user prompt, supervisor prompt, sub-agent prompt. Tokens/challenge is penalized; delete anything that doesn't change behavior. The default supervisor already says "return ONLY the path array" — keep it.
3. **Skip the supervisor chatter**: test whether a single-agent or minimal config scores equal with fewer tokens.
4. **Hazard-aware path**: custom pathfinder that avoids c8 and risky challenges (`04-architecture.md`). Compare lives remaining.
5. **Challenge answering**: give a short rule per challenge type (c1 guardrail, c2 code, c3 memory, c4 web, c5 simple, c6 boss). Make answers exact and terse (graders are mostly exact/contains match). Add a guardrail + topic deny-list for c1 and test that it truly intervenes.
6. **Model choice**: Nova 2 Lite (cheap) vs Haiku 4.5 (better but costs money, not covered by credits). Only pay if it clearly wins.
7. **Finale mode** (if the event has a 45-second runtime prompt): pre-write 2–3 tested prompt templates in a notes file and practice swapping in the strategy/map details in under 45 s.

## Rules of thumb
- Reliability > cleverness: one lost life (250 + a possible death) outweighs most token savings.
- Always re-run a promising prompt 3x before trusting it.
- Keep the winning prompt text saved in `08-run-log.md` with its score.


## Live-game additions
- Navigation prompt may define strategies dynamically (e.g. "Use strategy: balanced").
- Token bonus is per challenge visited: shortest possible prompts, answer-only outputs.
- c18: output ONLY the JSON, nulls for missing, no extra fields. c1: block listed topics only.
