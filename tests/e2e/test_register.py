"""E2E: データ登録(PF-4 / #24)。

owner 限定の登録フォーム → カタログ一覧への即時反映 / analyst ガード /
必須項目バリデーション / 同梱サンプル登録 / 削除・リセット導線。

登録は in-memory な共有ストア(Alpine.store('catalog'))で保持する(localStorage 不使用)。
ブラウザ上で合成データ生成は行わない(擬似)。
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .helpers import ANALYST, goto_app, login, open_register

pytestmark = pytest.mark.e2e


def _fill_metadata(page: Page, title: str) -> None:
    """必須メタデータを埋める(タイトルのみ可変)。"""
    page.get_by_test_id("reg-title").fill(title)
    page.get_by_test_id("reg-description").fill("E2E 用の架空データセット概要")
    page.get_by_test_id("reg-domain").fill("e2e-domain")
    page.get_by_test_id("reg-tags").fill("e2e, demo")
    page.get_by_test_id("reg-usage").fill("活用例1\n活用例2")


def test_register_sample_reflects_in_catalog(page: Page, base_url: str) -> None:
    """owner が同梱サンプルで登録すると、カタログ一覧に即時反映される。"""
    open_register(page, base_url)
    expect(page.get_by_test_id("register-disclaimer")).to_be_visible()

    title = "腎機能マーカー(E2E 登録)"
    _fill_metadata(page, title)
    # 同梱サンプルを選ぶ(デフォルトで sample が選択済み)。
    page.get_by_test_id("reg-sample-select").select_option("renal-egfr")
    page.get_by_test_id("reg-submit").click()

    # 成功メッセージと登録済みリストへの反映。
    expect(page.get_by_test_id("reg-success")).to_be_visible()
    item = page.locator("[data-testid='reg-item']", has_text=title)
    expect(item).to_be_visible()

    # カタログ一覧へ遷移すると登録分が出る。
    page.get_by_test_id("nav-explore").click()
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    expect(page.locator("[data-testid='catalog-card']", has_text=title)).to_be_visible()


def test_register_demo_fills_form_without_registering(page: Page, base_url: str) -> None:
    """デモボタンはフォームを記入するだけ。登録も遷移もしない(#62)。"""
    open_register(page, base_url)
    demo = page.get_by_test_id("reg-demo-register")
    expect(demo).to_be_visible()

    # クリック前は未登録(空)状態。
    expect(page.get_by_test_id("reg-registered-empty")).to_be_visible()

    # クリック → フォームが架空デモデータで埋まる(登録・遷移はしない)。
    demo.click()

    # register ビューに留まる(個別ページへ遷移しない)。
    expect(page.get_by_test_id("register-view")).to_be_visible()
    expect(page.get_by_test_id("dataset-view")).to_be_hidden()

    # メタデータ各フィールドが記入されている。
    expect(page.get_by_test_id("reg-title")).not_to_have_value("")
    expect(page.get_by_test_id("reg-title")).to_have_value(re.compile("デモ"))
    expect(page.get_by_test_id("reg-description")).not_to_have_value("")
    expect(page.get_by_test_id("reg-domain")).not_to_have_value("")
    # データ源が submit-ready: source=sample かつ有効なサンプルが選択済み。
    expect(page.get_by_test_id("reg-source-sample")).to_be_checked()
    expect(page.get_by_test_id("reg-sample-select")).not_to_have_value("")

    # まだ登録は発生していない(登録済みリストは空のまま)。
    expect(page.get_by_test_id("reg-registered-empty")).to_be_visible()
    expect(page.locator("[data-testid='reg-item']")).to_have_count(0)

    # ユーザーが reg-submit を押して初めて登録される。
    page.get_by_test_id("reg-submit").click()
    expect(page.get_by_test_id("reg-success")).to_be_visible()
    expect(page.locator("[data-testid='reg-item']")).to_have_count(1)
    expect(page.locator("[data-testid='reg-item']", has_text="デモ")).to_be_visible()
    # 登録後も自動遷移はせず register ビューに留まる(ナビはユーザーに委ねる)。
    expect(page.get_by_test_id("register-view")).to_be_visible()
    expect(page.get_by_test_id("dataset-view")).to_be_hidden()


def test_register_demo_cycles_definitions(page: Page, base_url: str) -> None:
    """デモボタンを連続クリックすると別々の定義でフォームを埋める(巡回, #62)。"""
    open_register(page, base_url)
    demo = page.get_by_test_id("reg-demo-register")

    demo.click()
    first = page.get_by_test_id("reg-title").input_value()
    assert first  # 1 回目で記入される。

    # 2 回目のクリック → 別タイトルでフォームが上書きされる(登録はしない)。
    demo.click()
    second = page.get_by_test_id("reg-title").input_value()
    assert second
    assert first != second
    # 巡回中は一度も登録されない。
    expect(page.get_by_test_id("reg-registered-empty")).to_be_visible()
    expect(page.locator("[data-testid='reg-item']")).to_have_count(0)


def test_register_required_validation(page: Page, base_url: str) -> None:
    """必須項目(タイトル/概要/ドメイン/データ源)が欠けると登録できずエラーが出る。"""
    open_register(page, base_url)

    # 何も入れずに送信 → タイトル必須エラー。
    page.get_by_test_id("reg-submit").click()
    expect(page.get_by_test_id("reg-error")).to_be_visible()

    # メタデータは埋めるがサンプル未選択 → データ源エラー。
    _fill_metadata(page, "サンプル未選択ケース")
    page.get_by_test_id("reg-submit").click()
    expect(page.get_by_test_id("reg-error")).to_be_visible()
    # まだ登録されていない。
    expect(page.get_by_test_id("reg-registered-empty")).to_be_visible()


def test_register_delete_and_reset(page: Page, base_url: str) -> None:
    """登録分を削除/リセットできる(base は不変なのでカタログは空にならない)。"""
    open_register(page, base_url)
    _fill_metadata(page, "削除対象データセット")
    page.get_by_test_id("reg-sample-select").select_option("generic-marker")
    page.get_by_test_id("reg-submit").click()
    expect(page.locator("[data-testid='reg-item']")).to_have_count(1)

    # 削除。
    page.get_by_test_id("reg-delete").first.click()
    expect(page.get_by_test_id("reg-registered-empty")).to_be_visible()

    # 2 件登録 → リセットで全消去。
    for name in ("ds-a", "ds-b"):
        _fill_metadata(page, name)
        page.get_by_test_id("reg-sample-select").select_option("renal-egfr")
        page.get_by_test_id("reg-submit").click()
    expect(page.locator("[data-testid='reg-item']")).to_have_count(2)
    page.get_by_test_id("reg-reset").click()
    expect(page.get_by_test_id("reg-registered-empty")).to_be_visible()


def test_register_user_dataset_detail_has_no_submit_form(page: Page, base_url: str) -> None:
    """ユーザー登録分の個別ページは合成データ未生成のため提出フォームを出さず注記を表示する。"""
    open_register(page, base_url)
    _fill_metadata(page, "提出フォーム無しデータセット")
    page.get_by_test_id("reg-sample-select").select_option("renal-egfr")
    page.get_by_test_id("reg-submit").click()

    # 登録済みリストの「詳細 →」から個別ページへ。
    page.get_by_test_id("reg-open").first.click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    expect(page.get_by_test_id("dataset-title")).to_be_visible()
    # 提出フォーム/合成データ DL は出ず、未生成の注記が出る。
    expect(page.get_by_test_id("dataset-no-submission")).to_be_visible()
    assert page.get_by_test_id("submit-form").count() == 0  # x-if で DOM から除去
    expect(page.get_by_test_id("download-synthetic")).to_be_hidden()  # x-show で非表示
    # メタデータ/活用例は表示される。
    expect(page.locator("[data-testid='dataset-usage'] .usage-list li").first).to_be_visible()


def test_analyst_cannot_reach_register(page: Page, base_url: str) -> None:
    """analyst には登録導線が出ず、ストア API 経由でも register に入れない。"""
    goto_app(page, base_url)
    login(page, *ANALYST)
    expect(page.get_by_test_id("nav-register")).to_be_hidden()
    page.evaluate("() => Alpine.store('session').go('register')")
    expect(page.get_by_test_id("register-view")).to_be_hidden()
    expect(page.get_by_test_id("top-view")).to_be_visible()


def test_register_existing_dataset_still_has_submit_form(page: Page, base_url: str) -> None:
    """登録機能を入れても、同梱データセットの提出フォームは従来どおり出る(回帰)。"""
    open_register(page, base_url)
    # 何も登録せずカタログから既存データセットを開く。
    page.get_by_test_id("nav-explore").click()
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator(
        "[data-testid='catalog-card'][data-dataset-id='prostate-psa'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    # 既存データセットは提出フォームあり / 未生成注記なし。
    expect(page.get_by_test_id("submit-form")).to_be_visible()
    expect(page.get_by_test_id("dataset-no-submission")).to_be_hidden()
