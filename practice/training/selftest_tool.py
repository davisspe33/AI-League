#!/usr/bin/env python3
"""Self-test: feed the exact tool-call arguments a model would emit into lambda_handler (CE/Gateway style event)
and check the returned path equals the planner's ground truth for every record in the dataset."""
import json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bp", os.path.join(HERE, "BalancedPathfinder", "index.py"))
bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "strategy-eval.jsonl")
bad = n = 0
for line in open(path):
    rec = json.loads(line); n += 1
    call = json.loads(rec["extra_info"]["expected_response"].split("\n")[1])
    res = bp.lambda_handler(dict(call["arguments"]), None)               # AgentCore Gateway style
    res2 = bp.lambda_handler({"body": json.dumps(call["arguments"])}, None)  # API Gateway style
    gt = json.loads(json.loads(rec["reward_model"]["ground_truth"])["output"]["body"])["path"]
    got = json.loads(res["body"])["path"]
    if res["statusCode"] != 200 or got != gt or json.loads(res2["body"])["path"] != gt:
        bad += 1
print(f"{n} records through lambda_handler: {bad} mismatches")
os.environ["P_SCALE"] = "0.6"
print("P_SCALE env ok:", bp.lambda_handler(dict(call["arguments"]), None)["statusCode"] == 200)
sys.exit(1 if bad else 0)
