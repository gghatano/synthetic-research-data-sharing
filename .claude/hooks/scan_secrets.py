#!/usr/bin/env python
"""PostToolUse フック: 編集ファイルに秘密情報らしき文字列が無いか検査する。

検出時は exit 2 で警告（Claude に伝わる）。誤検知を避けるためパターンは限定的。
本デモのデータはすべて架空のため、鍵・トークン類の混入は原則あってはならない。
"""

from __future__ import annotations

import json
import re
import sys

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PATTERNS = {
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic secret assignment": re.compile(
        r"(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    ),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return 0
    hits = [name for name, pat in PATTERNS.items() if pat.search(text)]
    if hits:
        sys.stderr.write(
            "警告: "
            + path
            + " に秘密情報らしき文字列を検出しました ("
            + ", ".join(hits)
            + ")。コミット前に確認・除去してください。\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
