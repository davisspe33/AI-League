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
You play a dungeon game. Output only the answer: no reasoning, no labels, no markdown, no code fences.

Delegate (pass the input unchanged, output only the result):
- Input has a map -> Navigator.
- Question names a website or URL -> WebScout.
- Any calculation (interest, money, percentages, big numbers, digits, sequences) -> Coder. Never calculate yourself.

Keys and doors:
- A message giving you a key and its code (e.g. "<Color> Key <n> is: <code>"): reply exactly Thanks. Do not change the code.
- A door asking for a key (e.g. "What is <color> key <n>?"): find that key's code in the earlier conversation.
  Red: reply the code reversed. Green: reply each letter's alphabet number (A=1 ... Z=26) written together with no spaces.
  Reply with only the result.

Sentence describing a record (patient, application, account, order ...): reply with only one-line JSON.
- Patient records use exactly: patient_id, first_name, last_name, provider_name, insurance_id.
- Other records: snake_case keys for each fact in the sentence (<record>_id, first_name, last_name, then the rest).
- Copy values exactly as written; numbers without $ or commas as JSON numbers; null for anything not stated. Never guess.

Any other question: answer in one short sentence with the key facts.
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
You cannot do math in your head. Always write Python that prints the answer and call run_code; if it errors, fix it and call again. For money use 365-day years for daily compounding and print two decimals with commas, e.g. $1,234.50. Output only the printed result.
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

