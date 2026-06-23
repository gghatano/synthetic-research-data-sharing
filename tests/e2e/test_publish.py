"""E2E: 初期表示と公開フェーズ。"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .helpers import alpine_state, open_app

pytestmark = pytest.mark.e2e


def test_initial_display(page: Page, base_url: str) -> None:
    """初期表示: 公開パネル可視・公開タブ選択・ステッパー1 active・他タブ disabled。"""
    open_app(page, base_url)

    # 公開パネルが可視。
    publish_panel = page.locator("section.panel:has(h2:has-text('合成データを公開する'))")
    expect(publish_panel).to_be_visible()

    # 公開タブが選択状態(.sel)。
    publish_tab = page.get_by_role("tab", name="① オーナー：公開")
    expect(publish_tab).to_have_class(re.compile(r"\bsel\b"))

    # ステッパー 1 が active。
    step1 = page.locator("nav.stepper li").nth(0)
    expect(step1).to_have_class(re.compile(r"\bactive\b"))

    # 分析者/審査タブが disabled で title 文言を持つ。
    analyze_tab = page.get_by_role("tab", name="② 分析者：ワークベンチ")
    expect(analyze_tab).to_be_disabled()
    expect(analyze_tab).to_have_attribute("title", "まず合成データを公開してください")

    review_tab = page.get_by_role("tab", name="③ オーナー：審査")
    expect(review_tab).to_be_disabled()
    expect(review_tab).to_have_attribute("title", "まず分析を提出してください")

    # 生データカードは 🔒 非公開 表示。
    expect(page.locator(".card.locked .lock")).to_have_text("🔒 非公開")

    # 公開ボタン文言(idle)。
    publish_btn = page.locator("section.panel button.primary").first
    expect(publish_btn).to_have_text("合成データを公開する")
    expect(publish_btn).to_be_enabled()

    assert alpine_state(page)["phase"] == "idle"


def test_publish_transitions(page: Page, base_url: str) -> None:
    """公開: ボタン disabled+文言変化・合成カード公開・生は施錠維持・タブ/ステッパー更新。"""
    open_app(page, base_url)

    publish_btn = page.locator("section.panel button.primary").first
    publish_btn.click()

    # 公開ボタンが disabled かつ「公開済み ✓」。
    expect(publish_btn).to_be_disabled()
    expect(publish_btn).to_have_text("公開済み ✓")

    # 合成カードに 🔓 公開済み が可視。
    synthetic_card = page.locator(".card:has(h3:has-text('合成データ (synthetic)'))")
    expect(synthetic_card.locator(".lock.open")).to_be_visible()
    expect(synthetic_card.locator(".lock.open")).to_have_text("🔓 公開済み")

    # 生データは 🔒 のまま。
    expect(page.locator(".card.locked .lock")).to_have_text("🔒 非公開")

    # 分析者タブが有効化。
    analyze_tab = page.get_by_role("tab", name="② 分析者：ワークベンチ")
    expect(analyze_tab).to_be_enabled()

    # ステッパー 1=done, 2=active。
    steps = page.locator("nav.stepper li")
    expect(steps.nth(0)).to_have_class(re.compile(r"\bdone\b"))
    expect(steps.nth(1)).to_have_class(re.compile(r"\bactive\b"))

    # 審査タブはまだ disabled(phaseRank<2)。
    review_tab = page.get_by_role("tab", name="③ オーナー：審査")
    expect(review_tab).to_be_disabled()

    assert alpine_state(page)["phase"] == "published"

    # 再クリックしても不変(idle に戻らない)。
    # disabled なので force でクリックを試みても publish() は idle ガードで何もしない。
    publish_btn.click(force=True)
    expect(publish_btn).to_have_text("公開済み ✓")
    assert alpine_state(page)["phase"] == "published"
