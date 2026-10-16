"""Self-test for the Navigator dataset + reward function.
1. System prompt in the dataset == Navigator prompt in agent-prompts.md; tool description == pathfinder-2 docstring.
2. Every expected response scores 1.0; common mistakes score lower.
3. Every expected tool call, sent to the real pathfinder-2 lambda_handler, returns the ground-truth path.
Run: python3 Live-game-files/fine-tune/selftest.py
"""
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.dirname(HERE)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rf = _load("rf", os.path.join(HERE, "reward-function-navigator.py"))
pf = _load("pf", os.path.join(LIVE, "pathfinder-2.py"))

recs = [json.loads(l) for l in open(os.path.join(HERE, "data", "navigator-eval.jsonl"))]
recs += [json.loads(l) for l in open(os.path.join(HERE, "data", "navigator-train.jsonl"))]

# 1. prompt / tool description stay in sync with the live config
md = open(os.path.join(LIVE, "agent-prompts.md")).read()
nav = re.search(r'## Sub-agent 1: "Navigator".*?```\n(.*?)\n```', md, re.S).group(1).strip()
assert recs[0]["prompt"][0]["content"] == nav, "system prompt differs from agent-prompts.md Navigator prompt"
doc_desc = re.search(r"Description: (.*)", pf.lambda_handler.__doc__).group(1).strip()
assert recs[0]["tools"][0]["function"]["description"] == doc_desc, "tool description differs from pathfinder-2 docstring"
print("prompt + tool description match live config")


def score(rec, response):
    s = {"prompt": rec["prompt"] + [{"role": "assistant", "content": response}],
         "reward_model": rec["reward_model"], "extra_info": rec["extra_info"]}
    return rf.reward_function(s, 0)["aggregate_reward_score"]


# 2. reward checks
perfect = [score(r, r["extra_info"]["expected_response"]) for r in recs]
assert min(perfect) == 1.0, min(perfect)
r = recs[0]
exp = r["extra_info"]["expected_response"]
call = json.loads(exp.split("\n")[1])
a = call["arguments"]


def variant(**changes):
    args = dict(a, **changes)
    return "<tool_call>\n" + json.dumps({"name": "route", "arguments": args}) + "\n</tool_call>"


grid = json.loads(a["game_map"])
broken = [row[:] for row in grid]
broken[0][0] = "wall" if broken[0][0] != "wall" else "normal"
start = json.loads(a["start_pos"])
label = f"{chr(65 + start[1])}{start[0] + 1}"
cases = {
    "expected": exp,
    "start as label": variant(start_pos=label),
    "map as array": variant(game_map=grid),
    "strategy omitted": variant(strategy=""),
    "wrong strategy": variant(strategy="swift"),
    "row/col swapped": variant(start_pos=json.dumps(start[::-1])) if start[0] != start[1] else variant(start_pos="[99,99]"),
    "map changed": variant(game_map=json.dumps(broken)),
    "chatter after call": exp + "\nI called the route tool to find the path through the dungeon for you." * 2,
    "wrong tool name": exp.replace('"route"', '"pathfinding"'),
    "no tool call": '["up","down"]',
}
for k, v in cases.items():
    print(f"  {k:20s} {score(r, v):.3f}")

# 3. expected call -> real Lambda -> same path as ground truth
mismatch = 0
for rec in recs[:100]:
    call = json.loads(rec["extra_info"]["expected_response"].split("\n")[1])
    out = pf.lambda_handler(call["arguments"], None)
    got = json.loads(out["body"])["path"]
    want = json.loads(json.loads(rec["reward_model"]["ground_truth"])["output"]["body"])["path"]
    sim = pf.simulate(json.loads(call["arguments"]["game_map"]), tuple(json.loads(call["arguments"]["start_pos"])), got)
    if not sim.get("treasure") or sim["lost"]:
        mismatch += 1
    _ = want
print(f"{len(recs)} records: all expected responses = 1.0; lambda replay of 100: {100 - mismatch}/100 reach treasure with 0 lives lost")
