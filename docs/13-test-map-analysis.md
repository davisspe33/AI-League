# 13 - Test map analysis (the one shown on game day; live map is hidden)
Sprite -> tile: flower=c1, hooded blue=c2, green slime=c3, skull=c4, blue ghost=c5, cyan face=c18, goblin=c6, chest-mouth=c17.
Grid (n=normal, w=wall): see training/testmap.py (run `python3 training/testmap.py`).
Game timer: 5:00 (time limit is real). Start A1, treasure A10.

Structure: F2 is the only gap out of row 1 -> F3 (c5) forced. Red key A3 only via A4 (c4 skull, 800). Green key J3 only via J4 (c5).
Treasure pocket A9/B9/A10/B10 sealed by red door C10 -> red key MANDATORY; D10 (c2) also forced before C10.
Down the right side: J6 (c18) then green door J9 (needs green key; else bypass via spikes H9).

Planner results (balanced):
- all challenges correct, STEP_COST 0: 107 steps, 10 challenges, E[score] 15,800 (+ token bonus up to ~1000 => ~16.8k = the top-5 scores)
- skip c2/c4: 13,995 (c4 and c2 are gates here, skipping is bad)
- default accuracies (agent assumed imperfect): 11,868, P(treasure) 0.68
=> Top-5 = perfect sweep + min tokens. Needed: c4 scraper tool, c2 code tool, c18 exact JSON, c1 guardrail, keys via Memory, door code translation.
Env for a sweep: P_SUCCESS all 1.0 (incl. c30,c31), STEP_COST 0, no MAX_CHALLENGES unless time is short.
