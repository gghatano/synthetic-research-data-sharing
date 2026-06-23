"""E2E(回帰): 旧ワークベンチ系と新・提出物審査系の結果領域を相互排他にする。

同一データセットページには 2 系統の結果/審査領域が x-show で共存する:
  - 旧ワークベンチ系: #analyst-result / #review-synthetic / #review-raw
  - 新・提出物審査系(#26): #sub-review-synthetic / #sub-review-raw

各フラグメント内の canvas id は chart-{kind}-{analysis}(例 chart-synthetic-clustering)
でデータセット非依存・コンテナ非依存。フラグメントの初期化は
document.getElementById("chart-"+uid) でドキュメント先頭一致のみを掴むため、同一 analysis
を両系統で同時に開くと chart-synthetic-clustering が 2 つ存在し、Chart.js の描画/destroy()
が片方を壊す(核メッセージの「合成 vs 生の並置」が崩れる)。

本テストは、ワークベンチで分析を表示してから提出物審査を開く(およびその逆)を踏み、
  1. 同 id の canvas がドキュメント内に同時に 2 つ存在しないこと
  2. 開いた側のチャートが正しく描画されること
  3. 閉じられた側の結果 pane がクリアされること
を検証する(相互排他)。owner ログインで両系統を同一ページ上で到達可能にする。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import (
    open_analyze_tab,
    open_workbench,
    wait_chart_drawn,
)

pytestmark = pytest.mark.e2e

_CHIP_NAME = {
    "clustering": "PSA軌跡クラスタリング",
    "association": "投薬–PSA反応の関連分析",
    "survival": "進行イベントの生存時間分析",
}


def _count_canvas(page: Page, canvas_id: str) -> int:
    """ドキュメント内に当該 id の canvas が何個あるか(重複検出)。"""
    return page.evaluate(
        '(id) => document.querySelectorAll("canvas[id=\'" + id + "\']").length',
        canvas_id,
    )


def _pane_has_fragment(page: Page, pane_id: str) -> bool:
    """pane 配下に分析フラグメント(section.fragment)が残っているか。"""
    return bool(
        page.evaluate(
            "(pid) => { const p = document.getElementById(pid); "
            "return !!(p && p.querySelector('section.fragment')); }",
            pane_id,
        )
    )


def _workbench_load_analysis(page: Page, analysis: str) -> None:
    """owner ワークベンチで公開→分析タブ→分析チップ選択し、合成フラグメント描画まで待つ。"""
    open_analyze_tab(page)
    page.get_by_role("button", name=_CHIP_NAME[analysis]).click()
    fragment = page.locator(f"#analyst-result section.fragment[data-analysis='{analysis}']")
    expect(fragment).to_be_visible()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")


def _submit_current(page: Page, report: str) -> None:
    """選択中分析をレポートを添えて提出し、提出物カードが 1 件出るまで待つ。"""
    page.get_by_test_id("submit-report").fill(report)
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submit-success")).to_be_visible()
    expect(page.get_by_test_id("submission-card").first).to_be_visible()


def test_opening_sub_review_clears_workbench_result(page: Page, base_url: str) -> None:
    """ワークベンチで分析表示→提出→提出物審査を開く: 旧結果がクリアされ canvas 重複が無い。

    両系統が同一 analysis を同時に開くと chart-synthetic-clustering が 2 つになり
    Chart の描画/破棄が衝突する。審査を開いた側でフラグメントが描画され、ワークベンチ側
    結果 pane はクリア(canvas は 1 個のみ)されることを確認する。
    """
    analysis = "clustering"
    # owner なら審査導線も出るため、同一ページで両系統に到達できる。
    open_workbench(page, base_url, name="保田 オーナー", role="owner")
    _workbench_load_analysis(page, analysis)

    # この時点: #analyst-result に chart-synthetic-clustering が 1 個存在。
    assert _count_canvas(page, f"chart-synthetic-{analysis}") == 1
    assert _pane_has_fragment(page, "analyst-result")

    # 提出 → 提出物カードを作る。
    _submit_current(page, "responder クラスタが過半数。生データでの再現性を確認したい。")

    # 提出物審査を開く(新系統 #sub-review-synthetic に同 analysis を読み込む)。
    card = page.locator(f"[data-testid='submission-card'][data-analysis='{analysis}']")
    card.get_by_test_id("review-open").click()
    expect(page.get_by_test_id("review-view")).to_be_visible()

    # 審査側でフラグメントが描画される。
    syn = page.locator(f"#sub-review-synthetic section.fragment[data-analysis='{analysis}']")
    expect(syn).to_be_visible()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")

    # 相互排他: 旧ワークベンチ結果 pane はクリアされ、canvas は 1 個のみ。
    assert _pane_has_fragment(page, "analyst-result") is False
    assert _count_canvas(page, f"chart-synthetic-{analysis}") == 1

    # 審査側 canvas は実際に審査領域(#sub-review-synthetic)配下にある。
    in_sub = page.evaluate(
        '(id) => { const c = document.querySelector("canvas[id=\'" + id + "\']"); '
        "return !!(c && c.closest('#sub-review-synthetic')); }",
        f"chart-synthetic-{analysis}",
    )
    assert in_sub is True

    # 承認で生データ並置: chart-raw も 1 個だけで正しく描画される。
    page.get_by_test_id("review-approve").click()
    raw = page.locator(f"#sub-review-raw section.fragment[data-analysis='{analysis}']")
    expect(raw).to_be_visible()
    wait_chart_drawn(page, f"chart-raw-{analysis}")
    assert _count_canvas(page, f"chart-synthetic-{analysis}") == 1
    assert _count_canvas(page, f"chart-raw-{analysis}") == 1


def test_reopening_workbench_clears_sub_review(page: Page, base_url: str) -> None:
    """逆方向: 提出物審査を開いた後にワークベンチで分析表示すると審査側がクリアされる。

    審査領域 #sub-review-synthetic に chart-synthetic-clustering がある状態で
    ワークベンチの pick() を踏むと、審査側がクリアされ、ワークベンチ側だけに描画が残る
    (canvas 重複なし)。
    """
    analysis = "clustering"
    open_workbench(page, base_url, name="保田 オーナー", role="owner")
    _workbench_load_analysis(page, analysis)
    _submit_current(page, "1 件目の所見。")

    # まず提出物審査を開く(審査側に chart-synthetic-clustering)。
    card = page.locator(f"[data-testid='submission-card'][data-analysis='{analysis}']")
    card.get_by_test_id("review-open").click()
    syn = page.locator(f"#sub-review-synthetic section.fragment[data-analysis='{analysis}']")
    expect(syn).to_be_visible()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")
    assert _count_canvas(page, f"chart-synthetic-{analysis}") == 1

    # 次にワークベンチへ戻り、同じ分析を再度表示する(逆方向の相互排他)。
    page.get_by_role("tab", name="② 分析者：ワークベンチ").click()
    page.get_by_role("button", name=_CHIP_NAME[analysis]).click()
    wb_frag = page.locator(f"#analyst-result section.fragment[data-analysis='{analysis}']")
    expect(wb_frag).to_be_visible()
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")

    # 審査側がクリアされ、canvas は 1 個のみ(ワークベンチ側)。
    assert _pane_has_fragment(page, "sub-review-synthetic") is False
    assert _count_canvas(page, f"chart-synthetic-{analysis}") == 1
    in_workbench = page.evaluate(
        '(id) => { const c = document.querySelector("canvas[id=\'" + id + "\']"); '
        "return !!(c && c.closest('#analyst-result')); }",
        f"chart-synthetic-{analysis}",
    )
    assert in_workbench is True

    # 審査ビューの reviewingId も解除され、ビューが閉じている。
    expect(page.get_by_test_id("review-view")).to_be_hidden()
