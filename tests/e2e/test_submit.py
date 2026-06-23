"""E2E: 合成データでの分析→レポート入力→提出→個別ページ紐付け(PF-5 #25)。

analyst が個別ページの分析ワークベンチで合成データの 3 分析を実行し、レポートを添えて
提出すると、そのデータセットの「紐づく提出物」一覧に紐づいて表示されることを検証する。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import (
    goto_app,
    open_analyze_tab,
    open_workbench,
    wait_chart_drawn,
)

pytestmark = pytest.mark.e2e

# チップのアクセシブル名(index.html のボタン文言)。
_CHIP_NAME = {
    "clustering": "PSA軌跡クラスタリング",
    "association": "投薬–PSA反応の関連分析",
    "survival": "進行イベントの生存時間分析",
}


def _pick_and_wait(page: Page, analysis: str) -> None:
    """分析チップを選び、合成フラグメント(Chart 描画)まで待つ。"""
    page.get_by_role("button", name=_CHIP_NAME[analysis]).click()
    fragment = page.locator(f"#analyst-result section.fragment[data-analysis='{analysis}']")
    expect(fragment).to_be_visible()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")


def test_submit_block_hidden_before_analysis(page: Page, base_url: str) -> None:
    """分析実行前は提出ブロック(レポート入力)が出ない。"""
    open_workbench(page, base_url, name="分析 太郎", role="analyst")
    open_analyze_tab(page)
    expect(page.get_by_test_id("submit-block")).to_be_hidden()


def test_submit_requires_report(page: Page, base_url: str) -> None:
    """レポート未入力では提出できずエラーになる(提出物は増えない)。"""
    open_workbench(page, base_url, name="分析 太郎", role="analyst")
    open_analyze_tab(page)
    _pick_and_wait(page, "clustering")

    expect(page.get_by_test_id("submit-block")).to_be_visible()
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submit-error")).to_be_visible()
    assert page.get_by_test_id("submission-card").count() == 0


def test_submit_flow_links_to_dataset(page: Page, base_url: str) -> None:
    """分析実行→レポート入力→提出→個別ページの提出物一覧に紐づいて表示される。"""
    open_workbench(page, base_url, name="分析 太郎", role="analyst")
    open_analyze_tab(page)
    _pick_and_wait(page, "clustering")

    report = "responder クラスタが過半数。生データでの再現性を確認したい。"
    page.get_by_test_id("submit-report").fill(report)
    page.get_by_test_id("submit-to-dataset").click()

    # 成功メッセージ。
    expect(page.get_by_test_id("submit-success")).to_be_visible()

    # 紐づく提出物一覧に 1 件追加される。
    cards = page.get_by_test_id("submission-card")
    expect(cards.first).to_be_visible()
    assert cards.count() == 1

    card = cards.first
    expect(card).to_have_attribute("data-analysis", "clustering")
    expect(card.get_by_test_id("submission-status")).to_have_text("submitted")
    expect(card.get_by_test_id("submission-report")).to_have_text(report)
    # 提出者(analyst 名)が出る。
    expect(card.locator(".catalog-owner")).to_contain_text("分析 太郎")
    # 適用コード抜粋がフラグメント由来で記録される。
    expect(card.locator("details.frag-code code")).not_to_be_empty()

    # 提出物一覧の紐付けキーが dataset_id。
    expect(page.get_by_test_id("submission-list")).to_have_attribute(
        "data-dataset-id", "prostate-psa"
    )


def test_submit_multiple_accumulate(page: Page, base_url: str) -> None:
    """同一データセットに複数提出が並ぶ。"""
    open_workbench(page, base_url, name="分析 太郎", role="analyst")
    open_analyze_tab(page)

    _pick_and_wait(page, "clustering")
    page.get_by_test_id("submit-report").fill("1 件目: クラスタリング所見。")
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submission-card")).to_have_count(1)

    _pick_and_wait(page, "association")
    page.get_by_test_id("submit-report").fill("2 件目: 関連分析所見。")
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submission-card")).to_have_count(2)

    analyses = page.locator("[data-testid='submission-card']").evaluate_all(
        "els => els.map(e => e.getAttribute('data-analysis'))"
    )
    assert set(analyses) == {"clustering", "association"}


def test_submit_disabled_when_logged_out(page: Page, base_url: str) -> None:
    """未ログインでは提出ボタンが無効でログイン導線が出る(閲覧は可・提出は要ログイン)。"""
    # ログインせずに(カタログは公開閲覧可)個別ページ→ワークベンチを開く。
    goto_app(page, base_url)
    page.get_by_test_id("login-to-catalog").click()
    page.wait_for_selector("[data-testid='explore-view']", state="visible")
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator(
        "[data-testid='catalog-card'][data-dataset-id='prostate-psa'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    page.wait_for_selector("[data-testid='dataset-title']", state="visible")
    page.get_by_test_id("open-workbench").click()
    page.wait_for_selector(
        "section.panel:has(h2:has-text('合成データを公開する'))", state="visible"
    )
    open_analyze_tab(page)
    _pick_and_wait(page, "clustering")

    expect(page.get_by_test_id("submit-to-dataset")).to_be_disabled()
    expect(page.get_by_test_id("submit-need-login")).to_be_visible()
    assert page.get_by_test_id("submission-card").count() == 0


def test_submit_keyed_per_dataset(page: Page, base_url: str) -> None:
    """提出は dataset_id 単位。別データセットには紐づかない。"""
    open_workbench(page, base_url, name="分析 太郎", role="analyst", dataset_id="renal-marker")
    open_analyze_tab(page)
    _pick_and_wait(page, "survival")
    page.get_by_test_id("submit-report").fill("renal-marker への提出。")
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submission-card")).to_have_count(1)
    expect(page.get_by_test_id("submission-list")).to_have_attribute(
        "data-dataset-id", "renal-marker"
    )

    # prostate-psa へ移動すると提出物は紐づかない(空状態)。
    page.get_by_test_id("dataset-back").click()
    page.locator(
        "[data-testid='catalog-card'][data-dataset-id='prostate-psa'] [data-testid='catalog-open']"
    ).click()
    expect(page.get_by_test_id("dataset-view")).to_be_visible()
    expect(page.get_by_test_id("submission-empty")).to_be_visible()
    assert page.get_by_test_id("submission-card").count() == 0
