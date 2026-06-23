"""E2E: カタログ外の原理デモ面(#43, N4)。

「同一コードが合成・生で動き、結果は近いが非同一」という核メッセージは、データカタログ
ではなくカタログ外の専用デモ面に置く。デモ面で合成 vs 生の並置が表示され、カタログ詳細
(個別ページ)には並置が無いことを検証する。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import ANALYSES, goto_app, open_dataset, wait_chart_drawn

pytestmark = pytest.mark.e2e


def _open_demo(page: Page, base_url: str) -> None:
    """ログインせずに(誰でも閲覧可)原理デモ面を開く。"""
    goto_app(page, base_url)
    page.get_by_test_id("nav-demo").click()
    page.wait_for_selector("[data-testid='demo-view']", state="visible")


def test_demo_reachable_without_login(page: Page, base_url: str) -> None:
    """原理デモ面は未ログインでナビから到達でき、デモ成果物である旨の注記が出る。"""
    _open_demo(page, base_url)
    expect(page.get_by_test_id("demo-disclaimer")).to_be_visible()
    # 初期状態では並置はまだ無く、案内のプレースホルダ。
    expect(page.get_by_test_id("demo-empty")).to_be_visible()


@pytest.mark.parametrize("analysis", ANALYSES)
def test_demo_juxtaposes_synthetic_and_raw(page: Page, base_url: str, analysis: str) -> None:
    """分析を選ぶと合成データと生データの結果が並置され、核メッセージが出る。"""
    _open_demo(page, base_url)
    page.locator(f"[data-testid='demo-picker'] [data-analysis='{analysis}']").click()

    # 左=合成(analyst フラグメント), 右=生(owner フラグメント)。
    syn = f"#demo-synthetic section.fragment[data-kind='synthetic'][data-analysis='{analysis}']"
    raw = f"#demo-raw section.fragment[data-kind='raw'][data-analysis='{analysis}']"
    expect(page.locator(syn)).to_be_visible()
    expect(page.locator(raw)).to_be_visible()

    # 合成・生それぞれの Chart が別 canvas id で描画される(衝突しない)。
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")
    wait_chart_drawn(page, f"chart-raw-{analysis}")

    # 核メッセージ(近いが非同一)が表示される。
    expect(page.get_by_test_id("demo-callout")).to_be_visible()


def test_demo_switch_analysis_no_double_draw(page: Page, base_url: str) -> None:
    """分析を切り替え・再選択しても canvas は単一で Chart は健全(二重描画ガード)。"""
    _open_demo(page, base_url)
    picker = page.get_by_test_id("demo-picker")

    picker.locator("[data-analysis='clustering']").click()
    wait_chart_drawn(page, "chart-synthetic-clustering")
    picker.locator("[data-analysis='association']").click()
    wait_chart_drawn(page, "chart-synthetic-association")
    picker.locator("[data-analysis='clustering']").click()
    wait_chart_drawn(page, "chart-synthetic-clustering")

    # 同 id の canvas はドキュメント内に 1 つ(destroy → 再生成で重複しない)。
    assert page.locator("#chart-synthetic-clustering").count() == 1
    assert page.locator("#chart-raw-clustering").count() == 1


def test_catalog_detail_has_no_juxtaposition(page: Page, base_url: str) -> None:
    """カタログ個別ページには合成 vs 生の並置(核メッセージ)が無い。"""
    open_dataset(page, base_url, "prostate-psa")
    detail = page.get_by_test_id("dataset-view")
    # 個別ページに比較並置(.compare)・デモ用 pane・デモ callout は無い。
    assert detail.locator(".compare").count() == 0
    assert page.locator("#demo-synthetic").count() == 1  # デモ面側に 1 つ(SPA 同一DOM)
    assert detail.locator("#demo-synthetic").count() == 0
    assert detail.get_by_test_id("demo-callout").count() == 0
