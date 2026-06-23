"""E2E テスト共通ヘルパ。待機・状態取得を集約しフレークを抑える。"""

from __future__ import annotations

from playwright.sync_api import Page

# 分析の網羅対象。
ANALYSES = ["clustering", "association", "survival"]

# expect / アクションの既定タイムアウト(ミリ秒)。CDN/htmx 待ちに余裕を持たせる。
DEFAULT_TIMEOUT_MS = 15_000


def open_app(page: Page, base_url: str) -> None:
    """アプリを開き、CDN ライブラリ(Chart/htmx/Alpine)と初期描画の完了を待つ。"""
    page.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page.goto(base_url + "/")
    # 3 つの CDN ライブラリが読み込まれるまで待つ(htmx は defer, Alpine も defer)。
    page.wait_for_function("() => typeof Chart !== 'undefined' && !!window.htmx && !!window.Alpine")
    # 公開パネルが Alpine の x-show で可視化されるまで待つ。
    page.wait_for_selector(
        "section.panel:has(h2:has-text('合成データを公開する'))", state="visible"
    )


def alpine_state(page: Page) -> dict:
    """ルート x-data(workflow) の状態を取り出す。最終 DOM 反映の補助確認用。"""
    return page.evaluate(
        "() => { const r = document.querySelector('[x-data]'); "
        "const d = Alpine.$data(r); "
        "return { role: d.role, phase: d.phase, selected: d.selected, "
        "submitted: d.submitted, loaded: d.loaded }; }"
    )


def chart_is_drawn(page: Page, canvas_id: str) -> bool:
    """canvas に Chart インスタンスが紐づいているか(Chart.getChart が truthy)。"""
    return bool(
        page.evaluate(
            "(id) => { const el = document.getElementById(id); "
            "return !!(el && typeof Chart !== 'undefined' && Chart.getChart(el)); }",
            canvas_id,
        )
    )


def wait_chart_drawn(page: Page, canvas_id: str) -> None:
    """Chart.getChart(canvas) が truthy になるまでポーリング待機する。"""
    page.wait_for_function(
        "(id) => { const el = document.getElementById(id); "
        "return !!(el && typeof Chart !== 'undefined' && Chart.getChart(el)); }",
        arg=canvas_id,
    )
