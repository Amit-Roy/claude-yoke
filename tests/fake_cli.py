"""A stand-in for the ``claude`` CLI that emits a few stream-json events.

Used by ``stream_probe.py`` to exercise the real subprocess + line-reader +
JSON-parsing path without spending any API tokens.
"""

import json
import sys

EVENTS = [
    {"type": "system", "subtype": "init", "session_id": "fake-123",
     "model": "claude-test", "tools": ["Read", "Bash"], "permissionMode": "default"},
    {"type": "assistant", "message": {
        "model": "claude-test",
        "usage": {"input_tokens": 10, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 0, "output_tokens": 3},
        "content": [{"type": "text", "text": "hello from the fake cli"}]}},
    {"type": "result", "subtype": "success", "total_cost_usd": 0.0002,
     "session_id": "fake-123", "usage": {"output_tokens": 3}},
]

for event in EVENTS:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()
