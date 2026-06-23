"""E2E: オーナー審査(合成提出物の確認→承認→生データ適用の並置)。"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .helpers import ANALYSES, alpine_state, open_app, wait_chart_drawn

pytestmark = pytest.mark.e2e

_CHIP_NAME = {
    "clustering": "PSA軌跡クラスタリング",
    "association": "投薬–PSA反応の関連分析",
    "survival": "進行イベントの生存時間分析",
}


def _submit_analysis(page: Page, base_url: str, analysis: str) -> None:
    open_app(page, base_url)
    page.locator("section.panel button.primary").first.click()
    page.get_by_role("tab", name="② 分析者：ワークベンチ").click()
    page.get_by_role("button", name=_CHIP_NAME[analysis]).click()
    expect(
        page.locator(f"#analyst-result section.fragment[data-analysis='{analysis}']")
    ).to_be_visible()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")
    submit_btn = page.locator("section.panel button.primary:has-text('提出する')")
    expect(submit_btn).to_be_enabled()
    submit_btn.click()


@pytest.mark.parametrize("analysis", ANALYSES)
def test_review_flow(page: Page, base_url: str, analysis: str) -> None:
    """審査タブ→合成提出物表示→承認で生データ結果並置・承認済み・callout・ステッパー3 done。"""
    _submit_analysis(page, base_url, analysis)

    page.get_by_role("tab", name="③ オーナー：審査").click()
    expect(page.locator("section.panel:has(h2:has-text('提出物を審査し'))")).to_be_visible()

    # 左カラム(合成)に提出物が読み込まれ Chart 描画。
    syn_fragment = page.locator(f"#review-synthetic section.fragment[data-analysis='{analysis}']")
    expect(syn_fragment).to_be_visible()
    expect(syn_fragment).to_have_attribute("data-kind", "synthetic")
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")

    # 承認前: callout は非表示、ボタン文言は承認前。
    expect(page.locator(".callout")).to_be_hidden()
    approve_btn = page.locator("section.panel button.primary:has-text('承認')")
    expect(approve_btn).to_be_enabled()

    approve_btn.click()

    # 右カラム(生)に raw フラグメントと canvas、Chart 描画。
    raw_fragment = page.locator(f"#review-raw section.fragment[data-analysis='{analysis}']")
    expect(raw_fragment).to_be_visible()
    expect(raw_fragment).to_have_attribute("data-kind", "raw")
    expect(page.locator(f"#chart-raw-{analysis}")).to_be_attached()
    wait_chart_drawn(page, f"chart-raw-{analysis}")

    # 両カラムに table(合成 vs 生の並置)。
    expect(syn_fragment.locator("table.frag-table")).to_be_visible()
    expect(raw_fragment.locator("table.frag-table")).to_be_visible()

    # 承認済み: ボタン文言+disabled、callout 可視、ステッパー3=done。
    expect(approve_btn).to_have_text("承認済み ✓")
    expect(approve_btn).to_be_disabled()
    expect(page.locator(".callout")).to_be_visible()
    expect(page.locator("nav.stepper li").nth(2)).to_have_class(re.compile(r"\bdone\b"))

    assert alpine_state(page)["phase"] == "approved"

    # 再クリック(force)しても承認済みのまま不変。
    approve_btn.click(force=True)
    expect(approve_btn).to_have_text("承認済み ✓")
    assert alpine_state(page)["phase"] == "approved"
