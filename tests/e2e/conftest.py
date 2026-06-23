"""E2E(Playwright)用フィクスチャ。

site/ を標準ライブラリの ThreadingHTTPServer で動的ポート配信し、
pytest-base-url の `base_url` をそのサーバに上書きする。htmx の hx-get は
http が必須なため file:// は使わない。CDN(jsdelivr) 到達不可なら session skip。
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = REPO_ROOT / "site"

# CDN 到達性チェックに使う代表 URL(ライブシェルが実際に読み込む Alpine.js)。
_CDN_PROBE = "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"


@pytest.fixture(scope="session")
def _cdn_reachable() -> bool:
    """jsdelivr(CDN) に到達できるか。不可なら e2e を skip する判断材料。"""
    try:
        req = urllib.request.Request(_CDN_PROBE, method="HEAD")
        with urllib.request.urlopen(req, timeout=10):  # noqa: S310 (固定 https URL)
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@pytest.fixture(scope="session")
def site_server(_cdn_reachable: bool) -> Iterator[str]:
    """site/ を動的ポートで配信し、`http://127.0.0.1:<port>` を返す。"""
    if not _cdn_reachable:
        pytest.skip("CDN(jsdelivr) に到達できないため e2e をスキップ")

    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    # ポート 0 で OS に空きポートを割り当てさせる。
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address[0], server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(site_server: str) -> str:
    """pytest-base-url の base_url をローカル配信サーバに上書きする(session スコープ)。"""
    return site_server
