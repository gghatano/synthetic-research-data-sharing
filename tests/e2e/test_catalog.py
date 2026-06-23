"""E2E: データカタログ閲覧(PF-3)。

カタログ一覧表示 → 個別ページ遷移 → メタデータ/活用例/ダミーデータ表示 →
紐づく提出物枠の空状態。閲覧はログイン有無を問わないが、ここでは owner で確認する。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import open_catalog, open_dataset, open_register

pytestmark = pytest.mark.e2e


def test_catalog_lists_multiple_datasets(page: Page, base_url: str) -> None:
    """catalog.json から複数データセットがカード表示され、件数表示が一致する。"""
    open_catalog(page, base_url)

    cards = page.get_by_test_id("catalog-card")
    expect(cards.first).to_be_visible()
    assert cards.count() >= 2  # prostate-psa + renal-marker

    # 各カードに title / owner / tag が出る。
    first = cards.first
    expect(first.locator("h3")).not_to_be_empty()
    expect(first.locator(".catalog-owner")).to_be_visible()
    expect(first.locator(".tag").first).to_be_visible()

    # 件数表示が描画件数と整合する。
    count_text = page.get_by_test_id("catalog-count").inner_text()
    assert f"{cards.count()} /" in count_text


def test_catalog_search_filters(page: Page, base_url: str) -> None:
    """検索ボックスでタグ/タイトル部分一致による絞り込みができる。"""
    open_catalog(page, base_url)
    total = page.get_by_test_id("catalog-card").count()

    page.get_by_test_id("catalog-search").fill("prostate")
    expect(
        page.locator("[data-testid='catalog-card'][data-dataset-id='prostate-psa']")
    ).to_be_visible()
    assert page.get_by_test_id("catalog-card").count() <= total
    assert page.get_by_test_id("catalog-card").count() >= 1

    # 一致なしで空状態。
    page.get_by_test_id("catalog-search").fill("zzz-no-match-zzz")
    expect(page.get_by_test_id("catalog-empty")).to_be_visible()


def test_dataset_detail_shows_metadata_and_preview(page: Page, base_url: str) -> None:
    """個別ページがメタデータ・活用例・ダミーデータプレビューを表示する。"""
    open_dataset(page, base_url, "prostate-psa")

    # メタデータ。
    expect(page.get_by_test_id("dataset-title")).to_be_visible()
    expect(page.locator("[data-testid='dataset-view'] .dataset-desc")).to_be_visible()
    expect(page.locator("[data-testid='dataset-view'] .tag").first).to_be_visible()

    # 活用例(usage_examples)が 1 つ以上。
    usage = page.locator("[data-testid='dataset-usage'] .usage-list li")
    expect(usage.first).to_be_visible()
    assert usage.count() >= 1

    # ダミーデータプレビュー: 各テーブルが table.frag-table を持つ。
    preview = page.get_by_test_id("dataset-preview")
    expect(preview).to_be_visible()
    tables = preview.locator("table.frag-table")
    assert tables.count() >= 1
    # 先頭テーブルにデータ行がある。
    expect(tables.first.locator("tbody tr").first).to_be_visible()


def test_dataset_submission_placeholder_empty(page: Page, base_url: str) -> None:
    """提出物が無いデータセットでは空状態(プレースホルダ)が表示される。

    #53 でバンドル済みデータ(prostate-psa / renal-marker)にはデモ用プリセット
    提出物が初期投入されるため、空状態は新規登録した user データセットで確認する。
    """
    open_register(page, base_url)
    # デモ用データを 1 件登録すると、その個別ページへ自動遷移する(#55)。
    # user-<n> データセットはプリセット対象外なので提出物はまだ無い。
    page.get_by_test_id("reg-demo-register").click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")

    submissions = page.get_by_test_id("dataset-submissions")
    expect(submissions).to_be_visible()
    # 共有ストア submissions.byDataset[dataset_id] は空 → 空状態メッセージ。
    expect(page.get_by_test_id("submission-empty")).to_be_visible()
    assert page.get_by_test_id("submission-card").count() == 0

    # 枠は dataset_id を data 属性に持つ(#25 の書き込み先キー設計の確認)。
    # 登録した user データセットの id(user-<n>)が入る。
    dataset_id = page.get_by_test_id("submission-list").get_attribute("data-dataset-id")
    assert dataset_id is not None and dataset_id.startswith("user-")


def test_dataset_back_to_catalog(page: Page, base_url: str) -> None:
    """個別ページからカタログ一覧へ戻れる。"""
    open_dataset(page, base_url, "prostate-psa")
    page.get_by_test_id("dataset-back").click()
    expect(page.get_by_test_id("explore-view")).to_be_visible()
    expect(page.get_by_test_id("dataset-view")).to_be_hidden()


def test_dataset_switch_updates_detail(page: Page, base_url: str) -> None:
    """別データセットを開くと個別ページの内容が切り替わる。"""
    open_dataset(page, base_url, "prostate-psa")
    title_a = page.get_by_test_id("dataset-title").inner_text()

    page.get_by_test_id("dataset-back").click()
    page.locator(
        "[data-testid='catalog-card'][data-dataset-id='renal-marker'] [data-testid='catalog-open']"
    ).click()
    expect(page.get_by_test_id("dataset-view")).to_be_visible()
    title_b = page.get_by_test_id("dataset-title").inner_text()
    assert title_a != title_b
    expect(page.get_by_test_id("submission-list")).to_have_attribute(
        "data-dataset-id", "renal-marker"
    )
