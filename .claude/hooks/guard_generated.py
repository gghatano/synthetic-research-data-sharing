#!/usr/bin/env python
"""PreToolUse フック: 生成物の手編集をブロックする。

site/data/ と site/fragments/ は `make build` の出力。手編集せず
ジェネレータ（generator/）を直して再生成する方針を強制する。
ブロック時は exit 2 で stderr にメッセージを返す（Claude に伝わる）。
"""

from __future__ import annotations

import json
import sys

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

GUARDED = ("site/data/", "site/fragments/")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    norm = path.replace("\\", "/")
    if any(seg in norm for seg in GUARDED):
        sys.stderr.write(
            "ブロック: " + path + " は make build の生成物です。手編集せず、"
            "generator/（generate_data.py / render.py / templates/）を直して "
            "`make build` で再生成してください。\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
