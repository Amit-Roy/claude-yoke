"""A fake ``claude`` that exercises the AskUserQuestion control protocol.

Emits an AskUserQuestion ``can_use_tool`` request, then inspects our
``control_response``: if it carried ``updatedInput.answers`` the question was
answered, otherwise it was skipped. Lets us test the question modal plumbing
without API cost.
"""

import json
import sys

QUESTIONS = [{
    "question": "Tabs or spaces?",
    "header": "Indent",
    "options": [
        {"label": "Tabs", "description": "Use tabs"},
        {"label": "Spaces", "description": "Use spaces"},
    ],
    "multiSelect": False,
}]


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


sys.stdin.readline()

emit({"type": "system", "subtype": "init", "session_id": "ask-1",
      "model": "claude-test", "tools": ["AskUserQuestion"], "permissionMode": "default"})
emit({"type": "assistant", "message": {"model": "claude-test", "content": [
    {"type": "tool_use", "id": "tool-1", "name": "AskUserQuestion",
     "input": {"questions": QUESTIONS}}]}})
emit({"type": "control_request", "request_id": "req-1", "request": {
    "subtype": "can_use_tool", "tool_name": "AskUserQuestion",
    "display_name": "AskUserQuestion", "input": {"questions": QUESTIONS},
    "tool_use_id": "tool-1"}})

line = sys.stdin.readline()
answers = None
try:
    resp = json.loads(line)
    inner = (resp.get("response") or {}).get("response") or {}
    answers = (inner.get("updatedInput") or {}).get("answers")
except Exception:
    answers = None

if answers:
    emit({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "tool-1",
         "content": "Your questions have been answered: " + json.dumps(answers)}]}})
    emit({"type": "assistant", "message": {"model": "claude-test",
          "content": [{"type": "text", "text": "Thanks — noted."}]}})
    emit({"type": "result", "subtype": "success", "total_cost_usd": 0.0001,
          "session_id": "ask-1", "usage": {"output_tokens": 4}})
else:
    emit({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "tool-1",
         "content": "The user did not answer the questions."}]}})
    emit({"type": "result", "subtype": "success", "total_cost_usd": 0.0001,
          "session_id": "ask-1", "usage": {"output_tokens": 2}})
