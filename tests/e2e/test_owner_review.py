"""E2E: オーナーによる提出物審査・生データ差し替え・状態反映(PF-6 #26)。

owner が個別ページの「紐づく提出物」一覧から提出物を選んで審査し、提出された
合成データの結果＋レポートを確認、承認で同一分析を生データに適用した結果(owner/raw
フラグメント)を並置表示する。承認で status が submitted -> approved に遷移し、一覧の
submission-status へ即時反映される。analyst には審査導線が出ないこと(擬似ガード)も検証する。

提出物は共有ストア(in-memory)に直接シードする。これは #25 の提出フローを再実行せず
審査だけを独立に検証するためで、ストアは公開 API(add)経由で積む。ワークベンチを開かない
ことで合成フラグメントの canvas id 衝突も避ける(審査ビュー単体の Chart 描画を確かめる)。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import (
    goto_app,
    login,
    open_dataset,
    wait_chart_drawn,
)

pytestmark = pytest.mark.e2e

ANALYSES = ["clustering", "association", "survival"]
_TITLE = {
    "clustering": "PSA軌跡クラスタリング",
    "association": "投薬–PSA反応の関連分析",
    "survival": "進行イベントの生存時間分析",
}


def _seed_submission(page: Page, dataset_id: str, analysis: str) -> None:
    """共有ストアにこのデータセットの提出物を 1 件積む(審査の入力を用意する)。"""
    page.evaluate(
        "({ datasetId, analysis, title }) => Alpine.store('submissions').add(datasetId, {"
        "  analysis, analysisTitle: title, analyst: '分析 太郎',"
        "  report: 'responder クラスタが過半数。生データでの再現性を確認したい。',"
        "  codeExcerpt: 'analyses.run(analysis)' })",
        {"datasetId": dataset_id, "analysis": analysis, "title": _TITLE[analysis]},
    )


@pytest.mark.parametrize("analysis", ANALYSES)
def test_owner_reviews_and_approves(page: Page, base_url: str, analysis: str) -> None:
    """owner: 提出物を選び審査→合成結果＋レポート確認→承認で生データ並置→approved 反映。"""
    open_dataset(page, base_url, "prostate-psa")  # owner ログイン込み
    _seed_submission(page, "prostate-psa", analysis)

    card = page.locator(f"[data-testid='submission-card'][data-analysis='{analysis}']")
    expect(card).to_be_visible()
    # 初期 status は submitted。
    expect(card.get_by_test_id("submission-status")).to_have_text("submitted")

    # owner には審査導線が出る。
    review_open = card.get_by_test_id("review-open")
    expect(review_open).to_be_visible()
    expect(review_open).to_have_text("審査する →")
    review_open.click()

    # 審査ビューが開き、提出レポートが表示される。
    view = page.get_by_test_id("review-view")
    expect(view).to_be_visible()
    expect(page.get_by_test_id("review-analysis-title")).to_have_text(_TITLE[analysis])
    expect(page.get_by_test_id("review-report-shown")).to_contain_text("再現性")

    # 左カラム: 合成データの結果フラグメント(Chart 描画)。
    syn = page.locator(f"#sub-review-synthetic section.fragment[data-analysis='{analysis}']")
    expect(syn).to_be_visible()
    expect(syn).to_have_attribute("data-kind", "synthetic")
    wait_chart_drawn(page, f"chart-synthetic-{analysis}")

    # 承認前: 右カラムは空(プレースホルダ)、callout 非表示。
    expect(page.get_by_test_id("review-callout")).to_be_hidden()

    approve = page.get_by_test_id("review-approve")
    expect(approve).to_be_enabled()
    approve.click()

    # 右カラム: 生データの結果フラグメント(Chart 描画) = 合成 vs 生 の並置。
    raw = page.locator(f"#sub-review-raw section.fragment[data-analysis='{analysis}']")
    expect(raw).to_be_visible()
    expect(raw).to_have_attribute("data-kind", "raw")
    wait_chart_drawn(page, f"chart-raw-{analysis}")
    expect(syn.locator("table.frag-table")).to_be_visible()
    expect(raw.locator("table.frag-table")).to_be_visible()

    # 承認済み: ボタン文言・disabled、核メッセージ callout 可視。
    expect(approve).to_have_text("承認済み ✓")
    expect(approve).to_be_disabled()
    expect(page.get_by_test_id("review-callout")).to_be_visible()
    expect(page.get_by_test_id("review-callout")).to_contain_text("近いが完全には")

    # 一覧の submission-status が approved に反映される。
    expect(card.get_by_test_id("submission-status")).to_have_text("approved")
    expect(card).to_have_attribute("data-status", "approved")

    # ストア上も status が遷移している。
    status = page.evaluate(
        "(dsid) => Alpine.store('submissions').forDataset(dsid)[0].status", "prostate-psa"
    )
    assert status == "approved"


def test_owner_review_reopen_keeps_juxtaposition(page: Page, base_url: str) -> None:
    """承認済み提出物を再度開くと、合成と生の並置が復元される(status は approved 維持)。"""
    open_dataset(page, base_url, "prostate-psa")
    _seed_submission(page, "prostate-psa", "clustering")

    card = page.locator("[data-testid='submission-card'][data-analysis='clustering']")
    card.get_by_test_id("review-open").click()
    page.get_by_test_id("review-approve").click()
    wait_chart_drawn(page, "chart-raw-clustering")
    expect(card.get_by_test_id("submission-status")).to_have_text("approved")

    # 審査ビューを閉じて、再度「審査結果を見る」で開く。
    page.get_by_test_id("review-view-close").click()
    expect(page.get_by_test_id("review-view")).to_be_hidden()
    reopen = card.get_by_test_id("review-open")
    expect(reopen).to_have_text("審査結果を見る")
    reopen.click()

    # 合成・生の両方が並置で復元され、callout も出る。
    expect(
        page.locator("#sub-review-synthetic section.fragment[data-kind='synthetic']")
    ).to_be_visible()
    expect(page.locator("#sub-review-raw section.fragment[data-kind='raw']")).to_be_visible()
    wait_chart_drawn(page, "chart-synthetic-clustering")
    wait_chart_drawn(page, "chart-raw-clustering")
    expect(page.get_by_test_id("review-callout")).to_be_visible()


def test_analyst_has_no_review_control(page: Page, base_url: str) -> None:
    """analyst には審査導線(review-open)が出ず、ガード注記が出る(擬似ガード)。"""
    goto_app(page, base_url)
    login(page, "分析 太郎", "analyst")
    open_dataset_as_logged_in(page, "prostate-psa")
    _seed_submission(page, "prostate-psa", "clustering")

    card = page.locator("[data-testid='submission-card'][data-analysis='clustering']")
    expect(card).to_be_visible()
    # analyst には審査ボタンが出ない(x-show で非表示。DOM には残るが不可視)。
    expect(card.get_by_test_id("review-open")).to_be_hidden()
    # 非 owner 向けのガード注記が出る。
    expect(page.get_by_test_id("review-guard")).to_be_visible()
    # status は submitted のまま(審査できない)。
    expect(card.get_by_test_id("submission-status")).to_have_text("submitted")


def open_dataset_as_logged_in(page: Page, dataset_id: str) -> None:
    """ログイン済み状態からカタログ→個別ページへ遷移する(ログインは呼び出し側で実施)。"""
    page.get_by_test_id("nav-explore").click()
    page.wait_for_selector("[data-testid='explore-view']", state="visible")
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator(
        f"[data-testid='catalog-card'][data-dataset-id='{dataset_id}'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    page.wait_for_selector("[data-testid='dataset-title']", state="visible")
