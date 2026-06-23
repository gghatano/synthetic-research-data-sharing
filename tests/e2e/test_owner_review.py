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
    expect(_user_card(page)).to_be_visible()


def _user_card(page: Page):
    """ユーザー提出分(sub-<n>)の最新カード。プリセット(#53, preset-<n>)を除外する。"""
    return page.locator("[data-testid='submission-card'][data-submission-id^='sub-']").last


def test_owner_reviews_program_results_report_and_approves(page: Page, base_url: str) -> None:
    """owner が提出物のプログラム＋結果＋レポートを閲覧し、承認で approved になる。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")
    _submit_one(page)

    # 審査を開く(プリセット #53 ではなくユーザー提出分を選ぶ)。
    _user_card(page).get_by_test_id("review-open").click()
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
    card = _user_card(page)
    expect(card.get_by_test_id("submission-status")).to_have_text("approved")
    expect(card).to_have_attribute("data-status", "approved")


def test_review_has_no_raw_data_juxtaposition(page: Page, base_url: str) -> None:
    """審査ビューに生データ並置(合成 vs 生)が存在しない(核メッセージはデモ面へ移設)。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")
    _submit_one(page, with_image=False)
    _user_card(page).get_by_test_id("review-open").click()
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
    # プリセット(#53)を含め全カードの審査ボタンが出ない(analyst 不可)。
    assert page.locator("[data-testid='review-open']:visible").count() == 0
    expect(page.get_by_test_id("review-guard")).to_be_visible()


def test_approved_submission_reopens_with_result(page: Page, base_url: str) -> None:
    """承認済み提出物を再度開くと、プログラム＋結果が復元表示される。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")
    _submit_one(page, with_image=False)
    card = _user_card(page)
    card.get_by_test_id("review-open").click()
    page.get_by_test_id("review-approve").click()
    page.get_by_test_id("review-view-close").click()
    expect(page.get_by_test_id("review-view")).to_be_hidden()

    # 「審査結果を見る」で再オープン(ユーザー提出分のカード)。
    expect(card.get_by_test_id("review-open")).to_have_text("審査結果を見る")
    card.get_by_test_id("review-open").click()
    expect(page.get_by_test_id("review-program-code")).to_contain_text("KMeans")
    expect(page.get_by_test_id("review-approve")).to_be_disabled()


def _preset_card(page: Page, submission_id: str):
    """指定 id のプリセット(#53)提出物カード。"""
    return page.locator(f"[data-testid='submission-card'][data-submission-id='{submission_id}']")


def test_preset_submissions_seeded_on_dataset(page: Page, base_url: str) -> None:
    """初回表示でプリセット提出物(#53)が一覧に並び、提出ゼロでないこと。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")

    # まだ手動提出していなくても、プリセットがカードとして見える。
    expect(_preset_card(page, "preset-1")).to_be_visible()
    expect(_preset_card(page, "preset-2")).to_be_visible()
    expect(page.get_by_test_id("submission-empty")).to_be_hidden()
    # デモ用バッジが付く(架空成果物であることが分かる)。
    expect(_preset_card(page, "preset-1").get_by_test_id("submission-preset-badge")).to_be_visible()


def test_preset_status_mix_submitted_and_approved(page: Page, base_url: str) -> None:
    """プリセットは submitted と approved を混在し、一覧の status 差が見える(#53)。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")

    submitted = _preset_card(page, "preset-1")
    approved = _preset_card(page, "preset-2")
    expect(submitted.get_by_test_id("submission-status")).to_have_text("submitted")
    expect(submitted).to_have_attribute("data-status", "submitted")
    expect(approved.get_by_test_id("submission-status")).to_have_text("approved")
    expect(approved).to_have_attribute("data-status", "approved")


def test_preset_submission_program_results_report_viewable(page: Page, base_url: str) -> None:
    """プリセット(#53)を審査ビューで開くと、プログラム＋結果＋レポートが閲覧できる。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")

    _preset_card(page, "preset-1").get_by_test_id("review-open").click()
    review = page.get_by_test_id("review-view")
    expect(review).to_be_visible()
    # プログラム(コード)が x-text 表示される(既存ビューアを再利用)。
    expect(review.get_by_test_id("review-program-code")).to_contain_text("KMeans")
    # 結果(テキスト)が表示される。
    expect(review.get_by_test_id("review-result").first).to_contain_text("responder")
    # レポートにプリセット由来の注記が出る。
    expect(review.get_by_test_id("review-report-shown")).to_contain_text("プリセット")


def test_preset_approved_shows_review_result_button(page: Page, base_url: str) -> None:
    """承認済みプリセットは「審査結果を見る」で開け、承認ボタンが無効(#53)。"""
    open_dataset_as(page, base_url, name="保田 オーナー", role="owner")

    approved = _preset_card(page, "preset-2")
    expect(approved.get_by_test_id("review-open")).to_have_text("審査結果を見る")
    approved.get_by_test_id("review-open").click()
    review = page.get_by_test_id("review-view")
    expect(review).to_be_visible()
    expect(review.get_by_test_id("review-program-code")).to_contain_text("log_dose")
    expect(review.get_by_test_id("review-approve")).to_be_disabled()


def test_preset_does_not_collide_with_user_submission_ids(page: Page, base_url: str) -> None:
    """プリセット(preset-<n>)が seq を進めず、ユーザー提出は sub-<n> でユニーク採番(#53)。"""
    open_dataset_as(page, base_url, name="分析 太郎", role="analyst")

    # デモ提出を 2 回 → 別々の sub-<n> が付き、プリセットと混ざらない。
    page.get_by_test_id("submit-demo").click()
    page.get_by_test_id("submit-demo").click()
    user_cards = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']")
    expect(user_cards).to_have_count(2)
    ids = user_cards.evaluate_all("els => els.map(e => e.getAttribute('data-submission-id'))")
    assert len(set(ids)) == 2, f"sub-<n> が重複している: {ids}"
    # プリセット id とも衝突しない。
    assert all(not i.startswith("preset-") for i in ids)
