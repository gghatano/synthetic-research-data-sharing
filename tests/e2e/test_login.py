"""E2E: 擬似ログインと画面シェル(PF-1)。

ログイン→トップ遷移 / ログアウト / 未ログインガード / owner・analyst の導線出し分け。
ログイン状態は in-memory な Alpine 共有ストアに保持する(localStorage 不使用)。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import goto_app, login

pytestmark = pytest.mark.e2e


def test_login_owner_to_top(page: Page, base_url: str) -> None:
    """owner でログインするとトップが表示され、ログイン画面は消える。"""
    goto_app(page, base_url)
    expect(page.get_by_test_id("login-view")).to_be_visible()

    login(page, "保田 オーナー", "owner")

    expect(page.get_by_test_id("top-view")).to_be_visible()
    expect(page.get_by_test_id("login-view")).to_be_hidden()
    # owner はデータ登録/データカタログの両方の導線が見える。
    expect(page.get_by_test_id("card-register")).to_be_visible()
    expect(page.get_by_test_id("card-explore")).to_be_visible()
    expect(page.get_by_test_id("nav-register")).to_be_visible()


def test_login_preset_fills_form(page: Page, base_url: str) -> None:
    """プリセット選択で名前/ロールが埋まり、そのままログインできる。"""
    goto_app(page, base_url)
    page.get_by_test_id("preset-analyst").click()
    expect(page.get_by_test_id("login-name")).to_have_value("分析 太郎")
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("top-view")).to_be_visible()


def test_analyst_cannot_see_register(page: Page, base_url: str) -> None:
    """analyst ではデータ登録の導線が出ない(owner 専用の出し分け)。"""
    goto_app(page, base_url)
    login(page, "分析 太郎", "analyst")

    expect(page.get_by_test_id("card-explore")).to_be_visible()
    expect(page.get_by_test_id("card-register")).to_be_hidden()
    expect(page.get_by_test_id("nav-register")).to_be_hidden()


def test_login_validation_errors(page: Page, base_url: str) -> None:
    """名前未入力・ロール未選択ではログインできずエラーが出る。"""
    goto_app(page, base_url)
    # 名前なし
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("login-error")).to_be_visible()
    expect(page.get_by_test_id("top-view")).to_be_hidden()
    # 名前ありロールなし
    page.get_by_test_id("login-name").fill("名無し")
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("login-error")).to_be_visible()
    expect(page.get_by_test_id("top-view")).to_be_hidden()


def test_logout_returns_to_login(page: Page, base_url: str) -> None:
    """ログアウトでストアが破棄され、ログイン画面へ戻る。"""
    goto_app(page, base_url)
    login(page, "保田 オーナー", "owner")
    page.get_by_test_id("logout").click()

    expect(page.get_by_test_id("login-view")).to_be_visible()
    expect(page.get_by_test_id("top-view")).to_be_hidden()
    # ログアウト後はナビ(ログアウト導線含む)が隠れる。
    expect(page.get_by_test_id("logout")).to_be_hidden()


def test_unauthenticated_guard(page: Page, base_url: str) -> None:
    """未ログインで保護ビュー(top / register)へ遷移しようとしてもログイン画面に留まる。

    カタログ(explore / dataset)は「誰でも閲覧可」の公開ビューのためガード対象外
    (別テスト test_catalog_public_without_login で公開閲覧を確認する)。
    """
    goto_app(page, base_url)
    # ストア API 経由で保護ビューへ遷移を試みる(本来 UI 導線は未ログインで非表示)。
    page.evaluate("() => Alpine.store('session').go('top')")
    expect(page.get_by_test_id("login-view")).to_be_visible()
    expect(page.get_by_test_id("top-view")).to_be_hidden()

    page.evaluate("() => Alpine.store('session').go('register')")
    expect(page.get_by_test_id("login-view")).to_be_visible()
    expect(page.get_by_test_id("register-view")).to_be_hidden()


def test_catalog_public_without_login(page: Page, base_url: str) -> None:
    """未ログインでもカタログ一覧は閲覧でき、ログインせず詳細まで到達できる(誰でも閲覧)。"""
    goto_app(page, base_url)
    # ログイン画面から「ログインせずカタログを見る」で一覧へ。
    page.get_by_test_id("login-to-catalog").click()
    expect(page.get_by_test_id("explore-view")).to_be_visible()
    expect(page.get_by_test_id("login-view")).to_be_hidden()
    # 未ログインなのでログアウト導線は出ない。
    expect(page.get_by_test_id("logout")).to_be_hidden()
    # カードが描画され、詳細へ遷移できる。
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator("[data-testid='catalog-open']").first.click()
    expect(page.get_by_test_id("dataset-view")).to_be_visible()
    expect(page.get_by_test_id("dataset-title")).to_be_visible()


def test_analyst_register_guard(page: Page, base_url: str) -> None:
    """analyst が register ビューへ遷移しようとしてもトップへ戻される(ロールガード)。"""
    goto_app(page, base_url)
    login(page, "分析 太郎", "analyst")
    page.evaluate("() => Alpine.store('session').go('register')")
    expect(page.get_by_test_id("top-view")).to_be_visible()
    expect(page.get_by_test_id("register-view")).to_be_hidden()


def test_nav_to_explore_shows_catalog(page: Page, base_url: str) -> None:
    """データカタログビューで catalog.json 由来のカードが表示される。"""
    goto_app(page, base_url)
    login(page, "保田 オーナー", "owner")
    page.get_by_test_id("nav-explore").click()
    expect(page.get_by_test_id("explore-view")).to_be_visible()
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    # 少なくとも 1 件のデータセットカードが表示される。
    expect(page.get_by_test_id("catalog-card").first).to_be_visible()
