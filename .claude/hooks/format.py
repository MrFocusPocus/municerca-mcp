#!/usr/bin/env python3
"""PostToolUse hook: run ruff format on the Python file that was just edited."""

import json
import subprocess
import sys

file_path = json.load(sys.stdin).get("tool_input", {}).get("file_path") or ""
if file_path.endswith(".py"):
    subprocess.run(["uv", "run", "ruff", "format", "--quiet", file_path], check=False)
