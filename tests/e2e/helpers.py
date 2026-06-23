"""E2E テスト共通ヘルパ。待機・状態取得を集約しフレークを抑える。"""

from __future__ import annotations

from playwright.sync_api import Page

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


def open_register(page: Page, base_url: str) -> None:
    """アプリを開き、owner ログイン→データ登録ビューまで遷移して待つ(#24)。"""
    goto_app(page, base_url)
    login(page, "保田 オーナー", "owner")
    page.get_by_test_id("nav-register").click()
    page.wait_for_selector("[data-testid='register-view']", state="visible")


def open_dataset_as(
    page: Page, base_url: str, *, name: str, role: str, dataset_id: str = "prostate-psa"
) -> None:
    """指定ロールでログイン→個別ページまで遷移して待つ(#41 提出フロー)。

    提出(プログラム＋結果アップロード)は要ログインのため、ログインユーザーを
    差し替えられる版を用意する。提出は analyst を主体に検証する。
    """
    goto_app(page, base_url)
    login(page, name, role)
    page.get_by_test_id("nav-explore").click()
    page.wait_for_selector("[data-testid='explore-view']", state="visible")
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator(
        f"[data-testid='catalog-card'][data-dataset-id='{dataset_id}'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    page.wait_for_selector("[data-testid='dataset-title']", state="visible")
