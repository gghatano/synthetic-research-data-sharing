"""E2E: 提出物(プログラム＋結果)の owner 審査(#42, N3)。

owner が個別ページの「紐づく提出物」から提出物を選び、プログラム(コード)＋結果
(画像/テキスト)＋レポートを閲覧し、承認で status を approved に遷移させる。
生データ並置(合成≈生)は審査では行わない(核メッセージのデモは #43 のデモ面)。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import open_dataset_as

pytestmark = pytest.mark.e2e

_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f9f0000000049454e44ae426082"
)
_PY_PROGRAM = b"import pandas as pd\n# fit KMeans on synthetic PSA\nprint('clusters')\n"


def _submit_one(
    page: Page,
    *,
    program_name: str = "cluster.py",
    result_text: str = "responder 比率 0.62",
    report: str = "生データでの再現性を確認したい。",
    with_image: bool = True,
) -> None:
    """提出フォームからプログラム＋結果を 1 件提出する(要ログイン済み)。"""
    page.get_by_test_id("submit-program-file").set_input_files(
        {"name": program_name, "mimeType": "text/x-python", "buffer": _PY_PROGRAM}
    )
    if with_image:
        page.get_by_test_id("submit-result-image").set_input_files(
            {"name": "plot.png", "mimeType": "image/png", "buffer": _PNG_1X1}
        )
    page.get_by_test_id("submit-result-text").fill(result_text)
    page.get_by_test_id("submit-report").fill(report)
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submission-card").first).to_be_visible()


def test_owner_reviews_program_results_report_and_approves(page: Page, base_url: str) -> None:
    """owner が提出物のプログラム＋結果＋レポートを閲覧し、承認で approved になる。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")
    _submit_one(page)

    # 審査を開く。
    page.get_by_test_id("review-open").first.click()
    review = page.get_by_test_id("review-view")
    expect(review).to_be_visible()

    # プログラム(コード)が x-text で表示される。
    expect(review.get_by_test_id("review-program-code")).to_contain_text("KMeans")
    # レポートが表示される。
    expect(review.get_by_test_id("review-report-shown")).to_contain_text("再現性")
    # 結果: 画像(dataURL)とテキストの両方。
    results = review.get_by_test_id("review-result")
    assert results.count() == 2
    img = review.locator("[data-result-type='image'] img")
    assert (img.get_attribute("src") or "").startswith("data:image/")
    expect(review.locator("[data-result-type='text']")).to_contain_text("responder 比率")

    # 承認 → status が approved に遷移し、一覧へ反映。
    review.get_by_test_id("review-approve").click()
    expect(review.get_by_test_id("review-callout")).to_be_visible()
    card = page.get_by_test_id("submission-card").first
    expect(card.get_by_test_id("submission-status")).to_have_text("approved")
    expect(card).to_have_attribute("data-status", "approved")


def test_review_has_no_raw_data_juxtaposition(page: Page, base_url: str) -> None:
    """審査ビューに生データ並置(合成 vs 生)が存在しない(核メッセージはデモ面へ移設)。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")
    _submit_one(page, with_image=False)
    page.get_by_test_id("review-open").first.click()
    expect(page.get_by_test_id("review-view")).to_be_visible()

    # 旧・生データ並置の痕跡(別 id pane / 合成 vs 生の compare)が無い。
    assert page.locator("#sub-review-raw").count() == 0
    assert page.locator("#sub-review-synthetic").count() == 0
    assert page.get_by_test_id("review-view").locator(".compare").count() == 0


def test_analyst_has_no_review_affordance(page: Page, base_url: str) -> None:
    """analyst には審査導線が出ず、ガード注記が表示される。"""
    open_dataset_as(page, base_url, name="分析 太郎", role="analyst")
    _submit_one(page, with_image=False)

    # 審査ボタンは owner 限定(x-show)で非表示、ガード注記が出る。
    expect(page.get_by_test_id("review-open")).to_be_hidden()
    expect(page.get_by_test_id("review-guard")).to_be_visible()


def test_approved_submission_reopens_with_result(page: Page, base_url: str) -> None:
    """承認済み提出物を再度開くと、プログラム＋結果が復元表示される。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")
    _submit_one(page, with_image=False)
    page.get_by_test_id("review-open").first.click()
    page.get_by_test_id("review-approve").click()
    page.get_by_test_id("review-view-close").click()
    expect(page.get_by_test_id("review-view")).to_be_hidden()

    # 「審査結果を見る」で再オープン。
    expect(page.get_by_test_id("review-open").first).to_have_text("審査結果を見る")
    page.get_by_test_id("review-open").first.click()
    expect(page.get_by_test_id("review-program-code")).to_contain_text("KMeans")
    expect(page.get_by_test_id("review-approve")).to_be_disabled()
