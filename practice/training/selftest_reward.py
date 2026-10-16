#!/usr/bin/env python3
"""Self-test: reward function against the generated eval set (perfect / degraded responses)."""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rf", os.path.join(HERE, "reward-function-strategy.py"))
rf = importlib.util.module_from_spec(spec); spec.loader.exec_module(rf)
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "strategy-eval.jsonl")
recs = [json.loads(l) for l in open(path)][:60]
def score(rec, resp):
    s = dict(rec); s["messages"] = rec["prompt"] + [{"role": "assistant", "content": resp}]
    return rf.reward_function(s, 0)["aggregate_reward_score"]
def call(rec, **over):
    name = rec["extra_info"]["tool"]
    call = json.loads(rec["extra_info"]["expected_response"].split("\n")[1])
    call["arguments"].update(over)
    return "<tool_call>\n" + json.dumps(call) + "\n</tool_call>"
res = {k: [] for k in ("perfect", "worst_strategy", "bad_map", "think_chatter", "no_call", "wrong_tool")}
for r in recs:
    gt = json.loads(r["reward_model"]["ground_truth"])
    res["perfect"].append(score(r, r["extra_info"]["expected_response"]))
    sc = gt["strategy_scores"]; worst = min(sc, key=sc.get)
    res["worst_strategy"].append(score(r, call(r, strategy=worst)) if "required_strategy" not in gt else None)
    res["bad_map"].append(score(r, call(r, game_map="[[\"wall\"]]")))
    res["think_chatter"].append(score(r, "<think>" + "let me think about the grid. " * 20 + "</think>\n" + r["extra_info"]["expected_response"]))
    res["no_call"].append(score(r, "[\"right\",\"down\"]"))
    res["wrong_tool"].append(score(r, r["extra_info"]["expected_response"].replace(r["extra_info"]["tool"], "other_tool", 1)))
for k, v in res.items():
    v = [x for x in v if x is not None]
    print(f"{k:15s} mean reward {sum(v)/len(v):.3f}  (n={len(v)})")
assert min(res["perfect"]) > 0.999, "perfect responses must score ~1.0"
print("OK")
