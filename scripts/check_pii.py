"""Fail if a RUT pattern appears in traces/ or in any log file.

Runs as a git pre-commit hook (`make hooks`) and in CI. Prints file and line number only,
never the matched value.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK]\b")


def scan(root: Path) -> list[str]:
    files = [p for p in (root / "traces").rglob("*") if p.is_file()]
    files += [p for p in root.rglob("*.log") if ".venv" not in p.parts]
    hits: list[str] = []
    for path in files:
        for number, line in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
            if RUT.search(line):
                hits.append(f"{path.relative_to(root)}:{number}")
    return hits


def main() -> None:
    hits = scan(ROOT)
    if hits:
        print("RUT pattern found (Ley 19.628). Do not commit:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        sys.exit(1)
    print("check_pii: no RUT pattern in traces/ or logs")


if __name__ == "__main__":
    main()
