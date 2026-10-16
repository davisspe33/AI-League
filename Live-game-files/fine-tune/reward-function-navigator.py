"""Reward function for the Navigator tool-call dataset (self-contained, no AWS calls).

The model must emit ONE tool call and nothing else:
  <tool_call>{"name": "route", "arguments": {"game_map": ..., "start_pos": ..., "strategy": ...}}</tool_call>

Reward (0..1):
  0.10  parseable tool call with the right tool name
  0.40  game_map copied exactly (parsed equality; JSON string or array both accepted)
  0.15  start_pos correct ([row,col] list, JSON string, or an "A1"-style label)
  0.20  strategy correct ("sweep")
  0.15  concise: nothing but the tool call (extra text costs tokens = costs token bonus)
Works as the Bedrock RFT / SageMaker reward Lambda: lambda_handler(event) -> list of results.
"""
import json
import re
from typing import Any, Dict

W_FORMAT, W_MAP, W_START, W_STRAT, W_CONCISE = 0.10, 0.40, 0.15, 0.20, 0.15
CONCISE_CHARS = 150  # extra characters (outside the tool call) that zero the concise score
ALIASES = {"quickest": "swift", "shortest": "swift", "fast": "swift", "all": "sweep", "everything": "sweep"}

_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def _load(x: Any) -> Any:
    if isinstance(x, str):
        try:
            return json.loads(x.strip())
        except Exception:
            return None
    return x


def _start(x: Any):
    v = _load(x) if isinstance(x, str) and x.strip()[:1] in "[{" else x
    if isinstance(v, list) and len(v) == 2 and all(isinstance(n, (int, float)) for n in v):
        return [int(v[0]), int(v[1])]
    if isinstance(v, dict) and "row" in v and "col" in v:
        return [int(v["row"]), int(v["col"])]
    if isinstance(x, str):
        m = re.fullmatch(r"\s*([A-Za-z])(\d+)\s*", x)
        if m:
            return [int(m.group(2)) - 1, ord(m.group(1).upper()) - ord("A")]
    return None


def parse_calls(response: str):
    calls = []
    for m in _CALL.finditer(response or ""):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        args = d.get("arguments", d.get("parameters", {}))
        if isinstance(args, str):
            args = _load(args) or {}
        calls.append({"name": str(d.get("name", d.get("tool", ""))), "arguments": args if isinstance(args, dict) else {}})
    return calls


def _response_text(sample: Dict[str, Any]) -> str:
    msgs = sample.get("messages", sample.get("prompt", []))
    text = ""
    for msg in msgs:
        if msg.get("role") == "assistant":
            c = msg.get("content", "")
            if isinstance(c, list):
                c = " ".join(str(b.get("text", b)) for b in c)
            if isinstance(c, str):
                text = c
    return text


def reward_function(sample: Dict[str, Any], index: int) -> Dict[str, Any]:
    response = _response_text(sample)
    gt_raw = sample.get("reward_model", {}).get("ground_truth", "{}")
    try:
        gt = json.loads(gt_raw) if isinstance(gt_raw, str) else gt_raw
    except Exception:
        gt = {}
    fn = gt.get("function", {})
    exp_name = str(fn.get("name", "route")).lower()
    exp_args = _load(fn.get("arguments", "{}")) or {}
    exp_map, exp_start = exp_args.get("game_map"), exp_args.get("start_pos")
    exp_strategy = str(gt.get("strategy", exp_args.get("strategy", "sweep"))).lower()

    calls = parse_calls(response)
    m = dict(format=0.0, map=0.0, start=0.0, strategy=0.0, concise=0.0, extra_chars=0.0)
    if not calls:
        lower = (response or "").lower()
        soft = 0.0
        if "<tool_call>" in lower:
            soft += 0.05
        if exp_name in lower:
            soft += 0.03
        if "{" in lower and "}" in lower:
            soft += 0.02
        total = min(soft, 0.10)
    else:
        call = calls[0]
        extra = len(_CALL.sub("", response).strip())
        m["extra_chars"] = float(extra)
        if call["name"].lower() != exp_name:
            total = 0.02
        else:
            args = call["arguments"]
            m["format"] = 1.0
            if _load(args.get("game_map")) == exp_map:
                m["map"] = 1.0
            if _start(args.get("start_pos")) == list(exp_start or []):
                m["start"] = 1.0
            s = str(args.get("strategy", "sweep") or "sweep").strip().lower()
            s = ALIASES.get(s, s)
            m["strategy"] = 1.0 if s == exp_strategy else 0.0
            m["concise"] = 0.0 if len(calls) > 1 else max(0.0, 1.0 - extra / CONCISE_CHARS)
            total = (W_FORMAT * m["format"] + W_MAP * m["map"] + W_START * m["start"]
                     + W_STRAT * m["strategy"] + W_CONCISE * m["concise"])
    total = max(0.0, min(1.0, total))
    sid = sample.get("id", sample.get("extra_info", {}).get("index", f"sample-{index:03d}"))
    return {
        "id": str(sid),
        "aggregate_reward_score": float(total),
        "metrics_list": [
            {"name": "format_valid", "value": m["format"], "type": "Reward"},
            {"name": "game_map_match", "value": m["map"], "type": "Reward"},
            {"name": "start_pos_match", "value": m["start"], "type": "Reward"},
            {"name": "strategy_match", "value": m["strategy"], "type": "Reward"},
            {"name": "concise", "value": m["concise"], "type": "Reward"},
            {"name": "extra_chars", "value": m["extra_chars"], "type": "Metric"},
            {"name": "response_length", "value": float(len(response or "")), "type": "Metric"},
        ],
    }


def lambda_handler(event, context):
    trajectories = event if isinstance(event, list) else event.get("trajectories", [])
    return [reward_function(s, i) for i, s in enumerate(trajectories)]
