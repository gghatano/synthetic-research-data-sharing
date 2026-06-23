"""E2E テスト共通ヘルパ。待機・状態取得を集約しフレークを抑える。"""

from __future__ import annotations

from playwright.sync_api import Page

# 分析の網羅対象。
ANALYSES = ["clustering", "association", "survival"]

# expect / アクションの既定タイムアウト(ミリ秒)。CDN/htmx 待ちに余裕を持たせる。
DEFAULT_TIMEOUT_MS = 15_000


def goto_app(page: Page, base_url: str) -> None:
    """アプリを開き、CDN ライブラリ(Chart/htmx/Alpine)の読込完了を待つ(ログイン画面の状態)。"""
    page.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page.goto(base_url + "/")
    # 3 つの CDN ライブラリが読み込まれるまで待つ(htmx は defer, Alpine も defer)。
    page.wait_for_function("() => typeof Chart !== 'undefined' && !!window.htmx && !!window.Alpine")
    # 擬似ログイン画面が x-cloak 解除されて可視化されるまで待つ。
    page.wait_for_selector("[data-testid='login-view']", state="visible")


def login(page: Page, name: str, role: str) -> None:
    """擬似ログインを実行する(role は owner | analyst)。"""
    page.get_by_test_id("login-name").fill(name)
    page.get_by_test_id(f"role-{role}").check()
    page.get_by_test_id("login-submit").click()
    page.wait_for_selector("[data-testid='top-view']", state="visible")


def open_app(page: Page, base_url: str) -> None:
    """アプリを開き、owner でログイン→データ探索(既存 3 ロールデモ)まで遷移して待つ。

    既存の 3 ロールデモは PF-1 でログイン後の「データ探索」ビューへ移設された。
    既存 E2E はこのワークベンチを前提とするため、ここでログイン+遷移をまとめて行う。
    """
    goto_app(page, base_url)
    login(page, "保田 オーナー", "owner")
    page.get_by_test_id("nav-explore").click()
    # 公開パネルが Alpine の x-show で可視化されるまで待つ。
    page.wait_for_selector(
        "section.panel:has(h2:has-text('合成データを公開する'))", state="visible"
    )


def alpine_state(page: Page) -> dict:
    """探索ビューの x-data(workflow) の状態を取り出す。最終 DOM 反映の補助確認用。"""
    return page.evaluate(
        "() => { const r = document.querySelector('[data-testid=explore-view]'); "
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
