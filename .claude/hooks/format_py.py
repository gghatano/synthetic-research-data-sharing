#!/usr/bin/env python
"""PostToolUse フック: 編集された .py を ruff で format / lint --fix する。

ruff 未インストールや非 .py は黙ってスキップ（非ブロッキング, exit 0）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".py"):
        return 0
    ruff = shutil.which("ruff")
    if not ruff:
        return 0
    for args in (["format", path], ["check", "--fix", "--quiet", path]):
        try:
            subprocess.run([ruff, *args], capture_output=True, timeout=60)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
