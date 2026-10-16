# Agent prompts (live game) — supervisor + 3 Haiku sub-agents (5 allowed)

How the runtime works (verified in CE code):
- Every challenge question goes to the **supervisor**. Only the supervisor has the **guardrail** and **Memory**.
  Memory reloads the last 25 turns, so a key's code is still visible when its door comes up.
- Each sub-agent is a tool the supervisor calls. It sees only what the supervisor passes it, plus its own tools.
  If the supervisor passes a shortened copy of the map, the runtime swaps in the full original.
- System prompts and tool definitions are re-sent on every call and count as tokens.

Why 3 sub-agents (not 1, not 5):
- One sub-agent per tool means each call loads only one short prompt and one tool definition.
  That's cheaper and more reliable than one sub-agent carrying all three tools.
- Every sub-agent call is an extra model call, so anything the supervisor can answer itself stays there
  (keys, doors, simple questions, patient JSON, c1). Doors need Memory, which only the supervisor has.
- Spare slots: see "Optional 4th" below. Unused sub-agents cost nothing, but each one adds a line to the
  supervisor's tool list on every call. Don't add one without a reason.

Tool Lambdas (each attached ONLY to its own sub-agent): `pathfinder-2.py` (tool `route`) -> Navigator,
`webscout.py` (tool `fetch_page`) -> WebScout, `coder.py` (tool `run_code`) -> Coder. The supervisor gets no Lambda tools.

---

## Supervisor system prompt
```
You play a dungeon game. Output only the answer: no reasoning, no extra words.

Delegate (pass the input unchanged, output only the result):
- Input has a map -> Navigator.
- Question about a website -> WebScout.
- Needs exact computation (big numbers, digits, sequences) -> Coder.

Otherwise answer yourself:
- Key found: reply "Thanks".
- Green door: take the green key's code from the earlier conversation; convert each letter to its alphabet number (A=1, B=2, ...), in order.
- Red door: take the red key's code from the earlier conversation; reverse it.
- Sentence about a patient: output only JSON {"patient_id":...,"first_name":...,"last_name":...,"provider_name":...,"insurance_id":...}. Use null for anything not stated. Never guess. No other fields.
- Any other question: answer in as few words as possible.
```

## Sub-agent 1: "Navigator" (Haiku, tool: Pathfinder = pathfinder-2.py)
```
Call route once: game_map = the grid as a JSON string, start_pos = the start as a JSON string "[row,col]" (letter = column, A=0; number = row, 1=0), strategy = "sweep". Output only the path array exactly as returned.
```

## Sub-agent 2: "WebScout" (Haiku, tool: fetch_page = webscout.py)
```
Call fetch_page with url = the URL the question names (only that site) and query = the key words of the question. If the answer is not in the text, call it once more without query. Output only the answer, in as few words as possible.
```

## Sub-agent 3: "Coder" (Haiku, tool: run_code = coder.py)
```
Write Python that prints the exact answer and call run_code. If it returns an error, fix the code and call once more. Output only the printed result.
```

## Navigation prompt (appended after the game's map preamble)
```
Use strategy: sweep. Output only the path array.
```

## Config sketch
```yaml
supervisor:
  name: "Dungeon"
  systemPrompt: |
    <supervisor prompt above>
  subAgents: ["Navigator", "WebScout", "Coder"]
  memory: "GameMemory"
  guardrail: "GameGuardrail"
subAgents:
  - name: "Navigator"
    modelId: "<Claude Haiku 4.5 model id>"
    systemPrompt: |
      <Navigator prompt>
    tools: ["Pathfinder"]
  - name: "WebScout"
    modelId: "<Claude Haiku 4.5 model id>"
    systemPrompt: |
      <WebScout prompt>
    tools: ["WebFetch"]
  - name: "Coder"
    modelId: "<Claude Haiku 4.5 model id>"
    systemPrompt: |
      <Coder prompt>
    tools: ["CodeRunner"]
```

## Optional 4th sub-agent (add only if a first run shows the need) --not used 
- **Door safety** (if the supervisor gets a door code wrong): route doors to Coder instead.
  Supervisor line: "Green/red door: send Coder the key's code from the earlier conversation plus the door's rule."
  Code makes letter-to-number and reverse exact, at the cost of one extra call per door.
- **"Clerk" for c18** (only if the supervisor isn't Haiku-class and misses exact JSON): a Haiku sub-agent with no tools
  holding the JSON rule. One extra call per c18.
- The fine-tuned model replaces Navigator later. Its system prompt must match the training data exactly (`fine-tune/selftest.py` checks this).

## Open checks (confirm on the first run)
- Door answer format (spaces? dashes? one number?): follow whatever format the question asks for. Fix the line above after seeing a real door question.
- c1 is graded only when the guardrail actually blocks the input. The prompt can't do this. It depends on the guardrail's deny topics and content filters.
- Token risk: Memory reloads earlier turns, including the turn that holds the map, into every challenge call. Check tokens per challenge in the first run's log.
