"""E2E: 分析者ワークベンチ(チップ選択→フラグメント描画→提出)。"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .helpers import ANALYSES, alpine_state, open_app, wait_chart_drawn

pytestmark = pytest.mark.e2e

# チップのアクセシブル名(index.html のボタン文言)。
_CHIP_NAME = {
    "clustering": "PSA軌跡クラスタリング",
    "association": "投薬–PSA反応の関連分析",
    "survival": "進行イベントの生存時間分析",
}


def _publish_and_open_analyze(page: Page, base_url: str) -> None:
    open_app(page, base_url)
    page.locator("section.panel button.primary").first.click()
    page.get_by_role("tab", name="② 分析者：ワークベンチ").click()
    expect(
        page.locator("section.panel:has(h2:has-text('合成データで分析を開発する'))")
    ).to_be_visible()


def test_submit_disabled_before_selection(page: Page, base_url: str) -> None:
    """未選択時は提出ボタンが disabled。"""
    _publish_and_open_analyze(page, base_url)
    submit_btn = page.locator("section.panel button.primary:has-text('提出する')")
    expect(submit_btn).to_be_disabled()


@pytest.mark.parametrize("analysis", ANALYSES)
def test_analyze_flow(page: Page, base_url: str, analysis: str) -> None:
    """チップ選択→合成フラグメント描画(Chart/table/details)→提出で phase=submitted。"""
    _publish_and_open_analyze(page, base_url)

    page.get_by_role("button", name=_CHIP_NAME[analysis]).click()

    # htmx swap: 対象フラグメントの出現を待つ。
    fragment = page.locator(f"#analyst-result section.fragment[data-analysis='{analysis}']")
    expect(fragment).to_be_visible()
    expect(fragment).to_have_attribute("data-kind", "synthetic")

    # canvas 存在 + Chart 描画。
    canvas = page.locator(f"#chart-synthetic-{analysis}")
    expect(canvas).to_be_attached()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")

    # table と details を持つ。
    expect(fragment.locator("table.frag-table")).to_be_visible()
    expect(fragment.locator("details.frag-code")).to_be_attached()

    # チップが選択状態。
    chip = page.get_by_role("button", name=_CHIP_NAME[analysis])
    expect(chip).to_have_class(re.compile(r"\bsel\b"))

    # 提出ボタンが有効。
    submit_btn = page.locator("section.panel button.primary:has-text('提出する')")
    expect(submit_btn).to_be_enabled()

    submit_btn.click()

    # phase=submitted: ステッパー 3 が active、ヒントが可視。
    expect(page.locator("nav.stepper li").nth(2)).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator(".hint")).to_be_visible()

    st = alpine_state(page)
    assert st["phase"] == "submitted"
    assert st["submitted"] == analysis
