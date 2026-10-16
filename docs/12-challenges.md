# 12 - Challenge Catalog (from organizers, game day)

| Tile | Name | Pts | Dmg | What it is / how to win |
|---|---|---|---|---|
| c7 | Coins | +250 | 0 | Pass over; no question. |
| c40 | Red Key | +50 | 0 | Needed before red door. Memory stores the info to unlock. Say "Thanks". |
| c41 | Green Key | +50 | 0 | Needed before green door. Memory stores info. Say "Thanks". |
| c5 | Bonehead (simple question) | +250 | -1 | e.g. "How many legs does a cow have?" Answer with minimal tokens (prompt: reply in as few words as possible). |
| c4 | Dark Prophet (web search) | +800 | -1 | Questions about specific websites. Build a scraping Lambda tool; NO new dependencies (stdlib only, e.g. urllib). Only fetch the site the question names. |
| c8 | Spike trap | 0 | -1 | Avoid. |
| c18 | Healthcare API | +500 | -1 | Sentence -> exact JSON. Fields: patient_id, first_name, last_name, provider_name, insurance_id. Output ONLY JSON; missing = null; no extra fields; never infer. Exact match required. |
| c1 | Violent Violet | +400 | -1 | Guardrail + token test. Block: illegal activity, violence, hate, misconduct, edible flowers, transplanting, weeds. Don't over-block or nothing answers. |
| c31 | Green Door | +1000 | -5 | Need green key (c41). Convert letters to numbers in order (A=1, B=2 ...). No key = massive damage. |
| c30 | Red Door | +1000 | -5 | Need red key (c40). Reverse the code. No key = lots of damage. |
| c2 | Blue Brain (code) | +600 | -1 | Bedrock Code Interpreter via Lambda tool for computation LLMs can't do (e.g. 3000th Fibonacci, last 10 digits). |

## Planner notes
- Keys before doors: planner already handles key+door pairing (c40->c30, c41->c31).
- Hardest/most expensive: c4 (needs a tool), c2 (needs a tool), c18 (exact match), doors (+1000 but need memory + key).
- If a tool is not built for c4/c2 in time, set `P_SUCCESS={"c4":0.05,"c2":0.05}` so the planner skips them.
- Don't hardcode answers (DQ).
