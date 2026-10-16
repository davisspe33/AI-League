# 03 — Tiles and maps

## Tile codes [verified: code — pathfinder-tool/index.py docstring, game_runner.py DEFAULT_TILE_CONFIG]
| Code | Meaning | Points | Damage |
|---|---|---|---|
| wall | impassable | – | – |
| start | spawn, acts as normal | – | – |
| normal | walkable | – | – |
| treasure | goal | +treasureBonus (1000) | – |
| c1 | "Violent Violet" guardrail challenge (must be blocked) | 400 | 1 |
| c2 | "Blue Brain" code-execution challenge | 600 | 1 |
| c3 | "Memento" memory challenge | 550 | 1 |
| c4 | "Dark Prophet" web-scraping challenge | 800 | 1 |
| c5 | "Bonehead" simple question | 250 | 1 |
| c6 | Boss challenge, needs most skills | 1000 | 2 |
| c7 | Coin, no challenge | 250 | 0 |
| c8 | Spikes | 0 | 1 |
| c17 / c18 | other challenge/door-type tiles | 750 / 500 | 2 / 1 |
| c30–c33 | doors (heavy) `[unverified]` | 1000 | 5 |
| c40–c43 | keys `[unverified]` | 50 | 0 |

Damage is applied on a wrong answer (challenges) or on stepping on spikes. Doors without the matching key deal damage; with the key the door opens and awards points via challenge.

## Maps
- Grid is a 2D array of tile strings; coordinates in the prompt are `{column letter}{row number}` (A1 = row 0, col 0); the map array uses `[rowIndex, columnIndex]` 0-indexed.
- CE sizes 2x2 to 12x12 in Map Builder; real maps seen up to ~15x15.
- Predefined CE maps: CB/Hero, London R1, London Finales (frontend/src/data/predefinedMaps.ts).
- More real maps: clone `ai-league-competition-data` (London, Bengaluru, NYC, Hero, APJ/EMEA/GCR) into `practice/`; `map.json` imports into Map Builder.
- Sample training data labels c1–c8 all as "coins" — that is wrong vs. the real game.


## Live-game tile facts (see docs/12-challenges.md)
- c18 = Healthcare API. Red door c30 = key c40 + reverse code. Green door c31 = key c41 + letters-to-numbers. Keys need Memory and saying Thanks.
