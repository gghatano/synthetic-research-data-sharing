#!/usr/bin/env python
"""PostToolUse フック: 編集された .py を ruff で format / lint --fix する。

ruff は uv プロジェクトの dev 依存。`uv run ruff` で起動する（無ければ PATH の ruff に
フォールバック）。uv/ruff いずれも無い、または非 .py は黙ってスキップ（非ブロッキング, exit 0）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def _runner() -> list[str] | None:
    if shutil.which("uv"):
        return ["uv", "run", "--quiet", "ruff"]
    if shutil.which("ruff"):
        return ["ruff"]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".py"):
        return 0
    runner = _runner()
    if not runner:
        return 0
    for args in (["format", path], ["check", "--fix", "--quiet", path]):
        try:
            subprocess.run([*runner, *args], capture_output=True, timeout=120)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
