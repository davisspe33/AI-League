# 04 — Agent architecture and Pathfinder

## Flow [verified: code + README]
```
Your navigation prompt
  -> game runner builds: FIXED preamble (start label, coordinate-format explanation, grid JSON, "find the treasure") + YOUR prompt appended
  -> AgentCore Runtime (container) -> Supervisor agent (Strands)
       -> Sub-agent ("Pathfinding Specialist") via tool_use
            -> AgentCore Gateway (MCP) -> Pathfinder Lambda (BFS)
  -> response must be a path array e.g. ["right","down","left"]  (path_parser.py parses it)
```
- Direct MCP tool call fallback exists in the sub-agent to avoid LLM truncation of long paths; empty responses retried up to 3x (cold start).
- Challenges are asked/answered as the path is walked; graded by exact_match / contains_match / json_exact_match / guardrail_block (`any_of:<strategy>` allows alternatives separated by `|||`). Guardrail challenges only pass if the guardrail actually intervenes (empty response = fail).
- Models in CE: Nova 2 Lite (default, covered by credits), Claude Haiku 4.5 (not covered), plus Nova Micro/Pro, DeepSeek, Llama, Mistral options in config page, and deployed custom models.

## Fixed preamble text (prompt_formatter.py)
"Find a path from position {A1}, where the position is formatted as {column}{row}. {column} is a letter starting with A, and {row} is a number starting with 1. The map object's coordinates are formatted as [{rowIndex},{columnIndex}] ... The path should find the treasure on this map: {grid_json}."
Your prompt text is appended after this (e.g. strategy instruction).

## Default config (agent-config/config.yaml)
- Supervisor: delegates all pathfinding to the specialist, passes the **entire input verbatim**, returns ONLY the path array.
- Sub-agent: calls `pathfinding` tool; start_pos from label ("A1" -> [0,0]); strategy from prompt ("swift" or "get_coins") default swift; returns ONLY the array.
- Config is YAML; add tools under `agent-config/tools/<Name>/index.py`; apply with `npm run seed-config -- --profile <aws-profile>` (use `--dry-run` first). Examples: `agent-config/examples/default` and `full-config` (2 sub-agents, 2 tools, memory, guardrail).

## Pathfinder tool [verified: code — lambda/pathfinder-tool/index.py + pathfinding_schema.json]
- Name `pathfinding`; params: `game_map` (JSON **string** of 2D array), `start_pos` (JSON **string** "[row,col]"), `strategy` enum `swift` | `get_coins` (default swift).
- It also auto-detects the `start` cell and overrides start_pos; tolerant of messy LLM-formatted map strings.
- `swift` = plain BFS shortest path; `get_coins` = greedy coins-per-step to c7 coins then BFS to treasure (max 50 iterations).
- **BFS treats every non-wall tile as walkable: it does NOT avoid spikes (c8) or challenge tiles.** So the default path may bleed lives. `[idea]` Write a custom Lambda/tool (Dijkstra with tile costs: spikes high cost, challenges weighted by points vs. risk, coins bonus) and register it as the agent's tool — CE supports custom Lambda tools. Confirm the event allows custom tools ("we deploy to a lambda" suggests yes).
