"""A fake ``claude`` that exercises the tool-permission control protocol.

Streaming-input mode: it reads the user's turn, asks to use the Write tool via
a ``control_request``, waits for our ``control_response`` on stdin, then either
runs the tool (allow) or reports denial. Lets us test Claude Yoke's permission
plumbing without any API cost.
"""

import json
import sys


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


# 1) Wait for the user's turn.
sys.stdin.readline()

emit({"type": "system", "subtype": "init", "session_id": "perm-1",
      "model": "claude-test", "tools": ["Write"], "permissionMode": "default"})
emit({"type": "assistant", "message": {"model": "claude-test",
      "content": [{"type": "text", "text": "I'll create that file."}]}})
emit({"type": "control_request", "request_id": "req-1", "request": {
    "subtype": "can_use_tool", "tool_name": "Write", "display_name": "Write",
    "input": {"file_path": "/tmp/demo.txt", "content": "hi"},
    "description": "demo.txt", "tool_use_id": "tool-1"}})

# 2) Wait for our decision.
line = sys.stdin.readline()
allowed = False
try:
    resp = json.loads(line)
    inner = (resp.get("response") or {}).get("response") or {}
    allowed = inner.get("behavior") == "allow"
except Exception:
    allowed = False

if allowed:
    emit({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "tool-1", "content": "File created"}]}})
    emit({"type": "assistant", "message": {"model": "claude-test",
          "content": [{"type": "text", "text": "Done — file created."}]}})
    emit({"type": "result", "subtype": "success", "total_cost_usd": 0.0001,
          "session_id": "perm-1", "usage": {"output_tokens": 6}})
else:
    emit({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "tool-1", "is_error": True,
         "content": "Tool denied by user"}]}})
    emit({"type": "result", "subtype": "success", "total_cost_usd": 0.0001,
          "session_id": "perm-1", "usage": {"output_tokens": 2}})
