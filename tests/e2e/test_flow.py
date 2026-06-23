"""E2E: 負/境界ケースとフルフロー(ハッピーパス)。"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import alpine_state, chart_is_drawn, open_app, wait_chart_drawn

pytestmark = pytest.mark.e2e


def test_analyze_tab_disabled_before_publish(page: Page, base_url: str) -> None:
    """公開前に分析者タブを click(force)しても遷移しない(disabled)。"""
    open_app(page, base_url)
    analyze_tab = page.get_by_role("tab", name="② 分析者：ワークベンチ")
    expect(analyze_tab).to_be_disabled()
    analyze_tab.click(force=True)  # disabled なので @click は発火しない
    assert alpine_state(page)["role"] == "publish"


def test_review_tab_disabled_before_submit(page: Page, base_url: str) -> None:
    """提出前は審査タブ不可。公開しても phaseRank<2 のため disabled。"""
    open_app(page, base_url)
    page.locator("section.panel button.primary").first.click()
    review_tab = page.get_by_role("tab", name="③ オーナー：審査")
    expect(review_tab).to_be_disabled()
    review_tab.click(force=True)
    assert alpine_state(page)["role"] != "review"


def test_chart_no_double_draw_on_reload(page: Page, base_url: str) -> None:
    """clustering→association→clustering と読み直しても canvas 単一・Chart 健全。"""
    open_app(page, base_url)
    page.locator("section.panel button.primary").first.click()
    page.get_by_role("tab", name="② 分析者：ワークベンチ").click()

    page.get_by_role("button", name="PSA軌跡クラスタリング").click()
    wait_chart_drawn(page, "chart-synthetic-clustering")

    page.get_by_role("button", name="投薬–PSA反応の関連分析").click()
    wait_chart_drawn(page, "chart-synthetic-association")

    page.get_by_role("button", name="PSA軌跡クラスタリング").click()
    expect(
        page.locator("#analyst-result section.fragment[data-analysis='clustering']")
    ).to_be_visible()
    wait_chart_drawn(page, "chart-synthetic-clustering")

    # canvas は単一(二重描画ガードで destroy → 再生成されても要素は 1 つ)。
    assert page.locator("#chart-synthetic-clustering").count() == 1
    # Chart.getChart が truthy で例外なし。
    assert chart_is_drawn(page, "chart-synthetic-clustering")


def test_full_happy_path(page: Page, base_url: str) -> None:
    """publish→analyze 選択→提出→審査→承認の通し 1 本。"""
    open_app(page, base_url)

    # publish
    page.locator("section.panel button.primary").first.click()
    assert alpine_state(page)["phase"] == "published"

    # analyze
    page.get_by_role("tab", name="② 分析者：ワークベンチ").click()
    page.get_by_role("button", name="進行イベントの生存時間分析").click()
    expect(
        page.locator("#analyst-result section.fragment[data-analysis='survival']")
    ).to_be_visible()
    wait_chart_drawn(page, "chart-synthetic-survival")

    # 提出
    page.locator("section.panel button.primary:has-text('提出する')").click()
    assert alpine_state(page)["phase"] == "submitted"

    # 審査
    page.get_by_role("tab", name="③ オーナー：審査").click()
    expect(
        page.locator("#review-synthetic section.fragment[data-analysis='survival']")
    ).to_be_visible()
    wait_chart_drawn(page, "chart-synthetic-survival")

    # 承認
    approve_btn = page.locator("section.panel button.primary:has-text('承認')")
    approve_btn.click()
    expect(page.locator("#review-raw section.fragment[data-analysis='survival']")).to_be_visible()
    wait_chart_drawn(page, "chart-raw-survival")
    expect(page.locator(".callout")).to_be_visible()

    assert alpine_state(page)["phase"] == "approved"
