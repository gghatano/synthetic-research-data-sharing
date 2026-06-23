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


def open_catalog(page: Page, base_url: str) -> None:
    """アプリを開き、owner でログイン→データカタログ一覧まで遷移して待つ。"""
    goto_app(page, base_url)
    login(page, "保田 オーナー", "owner")
    page.get_by_test_id("nav-explore").click()
    page.wait_for_selector("[data-testid='explore-view']", state="visible")
    # catalog.json の fetch でカードが描画されるまで待つ。
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")


def open_dataset(page: Page, base_url: str, dataset_id: str = "prostate-psa") -> None:
    """カタログ一覧から指定データセットの個別ページを開いて待つ。"""
    open_catalog(page, base_url)
    page.locator(
        f"[data-testid='catalog-card'][data-dataset-id='{dataset_id}'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    page.wait_for_selector("[data-testid='dataset-title']", state="visible")


def open_app(page: Page, base_url: str) -> None:
    """アプリを開き、owner ログイン→カタログ→個別ページ→分析ワークベンチまで遷移して待つ。

    既存の 3 ロールデモは PF-3 でカタログ個別ページ配下の「分析ワークベンチ」に内包された。
    既存 E2E はこのワークベンチを前提とするため、ここで一連の遷移をまとめて行う
    (マークアップ・data 属性・id は不変なので、これ以降のセレクタは従来どおり)。
    """
    open_dataset(page, base_url, "prostate-psa")
    page.get_by_test_id("open-workbench").click()
    # 公開パネルが Alpine の x-show で可視化されるまで待つ。
    page.wait_for_selector(
        "section.panel:has(h2:has-text('合成データを公開する'))", state="visible"
    )


def alpine_state(page: Page) -> dict:
    """ワークベンチの x-data(workflow) の状態を取り出す。最終 DOM 反映の補助確認用。"""
    return page.evaluate(
        "() => { const r = document.querySelector('[data-testid=workbench]'); "
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
