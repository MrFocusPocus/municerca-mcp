#!/usr/bin/env python3
"""PreToolUse hook: block edits to the checks unless ALLOW_TEST_EDITS=1.

An agent asked to fix code must not be able to pass by weakening the tests or the eval set.
Exit code 2 blocks the tool call and shows stderr to the agent.
"""

import json
import os
import sys
from pathlib import Path

payload = json.load(sys.stdin)
file_path = payload.get("tool_input", {}).get("file_path") or ""
root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
try:
    relative = Path(file_path).resolve().relative_to(root).as_posix()
except ValueError:
    sys.exit(0)

protected = relative == "evals/dataset.jsonl" or relative.startswith("tests/")
if protected and os.environ.get("ALLOW_TEST_EDITS") != "1":
    print(
        f"Blocked: {relative} is a check, not code under repair. Fix the implementation. "
        "A human can allow this edit by starting the session with ALLOW_TEST_EDITS=1.",
        file=sys.stderr,
    )
    sys.exit(2)
