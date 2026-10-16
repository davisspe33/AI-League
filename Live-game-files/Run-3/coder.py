import json
import os
import subprocess
import sys
import tempfile

# Coder tool for the c2 (Blue Brain) challenge: runs Python the agent writes and returns what it prints.
# Python 3.12 Lambda, handler = index.lambda_handler. No answers are stored here.
#
# Engines (env ENGINE):
#   auto (default)  - Bedrock AgentCore Code Interpreter; if unavailable (old boto3, missing IAM), run locally
#   agentcore       - Code Interpreter only
#   local           - run in this Lambda with a fresh Python process (no AWS permissions needed)
# Code Interpreter needs these IAM actions on the Lambda role:
#   bedrock-agentcore:StartCodeInterpreterSession, InvokeCodeInterpreter, StopCodeInterpreterSession
# Other env (optional): CODE_INTERPRETER_ID (default aws.codeinterpreter.v1), RUN_TIMEOUT (default 20),
#   MAX_OUTPUT_CHARS (default 2000)

ENGINE = (os.environ.get("ENGINE") or "auto").lower()
CI_ID = os.environ.get("CODE_INTERPRETER_ID") or "aws.codeinterpreter.v1"
RUN_TIMEOUT = float(os.environ.get("RUN_TIMEOUT", "20") or 20)
MAX_OUT = int(os.environ.get("MAX_OUTPUT_CHARS", "2000") or 2000)

# Python 3.11+ refuses to print ints over 4300 digits; huge Fibonacci/factorial answers need this lifted.
PRELUDE = "import sys\ntry:\n    sys.set_int_max_str_digits(0)\nexcept Exception:\n    pass\n"


def _clean(code):
    code = str(code or "").strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1] if "\n" in code else ""
        if code.rstrip().endswith("```"):
            code = code.rstrip()[:-3]
    return code.strip("\n")


def run_agentcore(code):
    import boto3
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    client = boto3.client("bedrock-agentcore", region_name=region)
    sid = client.start_code_interpreter_session(codeInterpreterIdentifier=CI_ID, name="coder",
                                                sessionTimeoutSeconds=300)["sessionId"]
    try:
        resp = client.invoke_code_interpreter(codeInterpreterIdentifier=CI_ID, sessionId=sid, name="executeCode",
                                              arguments={"language": "python", "code": PRELUDE + code})
        stdout, stderr, texts, is_err = "", "", [], False
        for ev in resp.get("stream", []):
            res = ev.get("result") if isinstance(ev, dict) else None
            if not res:
                continue
            is_err = is_err or bool(res.get("isError"))
            sc = res.get("structuredContent") or {}
            stdout += sc.get("stdout") or ""
            stderr += sc.get("stderr") or ""
            for c in res.get("content") or []:
                if c.get("type") == "text" and c.get("text"):
                    texts.append(c["text"])
        if not stdout and not stderr:
            stdout = "\n".join(texts)
        return stdout, stderr, is_err
    finally:
        try:
            client.stop_code_interpreter_session(codeInterpreterIdentifier=CI_ID, sessionId=sid)
        except Exception:
            pass


def run_local(code):
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir="/tmp" if os.path.isdir("/tmp") else None,
                                     delete=False) as f:
        f.write(PRELUDE + code)
        path = f.name
    try:
        p = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True, timeout=RUN_TIMEOUT,
                           cwd=os.path.dirname(path))
        return p.stdout, p.stderr, p.returncode != 0
    except subprocess.TimeoutExpired:
        return "", f"Timed out after {RUN_TIMEOUT:g}s", True
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def lambda_handler(event, context):
    """
    Run Python code and return what it prints. Handles API Gateway and AgentCore Gateway events.

    ---
    Tool: run_code
    Description: Runs Python code (Code Interpreter) and returns its printed output. Use for exact computation such as huge numbers, digits, sequences and counting. The code must print the final answer.
    Parameters:
        code         (required) - complete Python code that prints the answer with print()
    ---
    """
    try:
        body = event
        if isinstance(event, dict) and "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        code = _clean(body.get("code") or body.get("python") or body.get("script"))
        if not code:
            return _err(400, "Missing code")
        engine = ENGINE
        if engine in ("auto", "agentcore"):
            try:
                stdout, stderr, failed = run_agentcore(code)
                engine = "agentcore"
            except Exception as e:
                print(f"Code Interpreter unavailable: {e}")
                if ENGINE == "agentcore":
                    return _err(500, f"Code Interpreter error: {e}")
                stdout, stderr, failed = run_local(code)
                engine = "local"
        else:
            stdout, stderr, failed = run_local(code)
        stdout = stdout.strip()
        print(f"RESULT: engine={engine} failed={failed} stdout_chars={len(stdout)}")
        out = {"output": stdout[-MAX_OUT:]}
        if failed or not stdout:
            out["error"] = (stderr.strip() or "no output; print the answer")[-800:]
        return {"statusCode": 200, "body": json.dumps(out)}
    except Exception as e:
        print(f"ERROR: {e}")
        return _err(500, str(e))


def _err(code, msg):
    return {"statusCode": code, "body": json.dumps({"error": msg})}
