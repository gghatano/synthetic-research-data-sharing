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
    # owner はデータ登録/データ探索の両方の導線が見える。
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
    """未ログインで保護ビューへ遷移しようとしてもログイン画面に留まる(擬似ガード)。"""
    goto_app(page, base_url)
    # ストア API 経由で保護ビューへ遷移を試みる(本来 UI 導線は未ログインで非表示)。
    page.evaluate("() => Alpine.store('session').go('explore')")
    expect(page.get_by_test_id("login-view")).to_be_visible()
    expect(page.get_by_test_id("explore-view")).to_be_hidden()

    page.evaluate("() => Alpine.store('session').go('register')")
    expect(page.get_by_test_id("login-view")).to_be_visible()
    expect(page.get_by_test_id("register-view")).to_be_hidden()


def test_analyst_register_guard(page: Page, base_url: str) -> None:
    """analyst が register ビューへ遷移しようとしてもトップへ戻される(ロールガード)。"""
    goto_app(page, base_url)
    login(page, "分析 太郎", "analyst")
    page.evaluate("() => Alpine.store('session').go('register')")
    expect(page.get_by_test_id("top-view")).to_be_visible()
    expect(page.get_by_test_id("register-view")).to_be_hidden()


def test_nav_to_explore_shows_demo(page: Page, base_url: str) -> None:
    """データ探索ビューで既存 3 ロールデモ(公開パネル)に到達できる。"""
    goto_app(page, base_url)
    login(page, "保田 オーナー", "owner")
    page.get_by_test_id("nav-explore").click()
    expect(page.get_by_test_id("explore-view")).to_be_visible()
    expect(page.locator("section.panel:has(h2:has-text('合成データを公開する'))")).to_be_visible()
