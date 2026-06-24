"""E2E: 提出物の審査・コメント・承認(#42 / #64, N3)。

#64 で審査をデータセット個別ページのインラインパネルから、提出物ごとの専用ページ
(submission ビュー = submission-view)へ移設した。owner は提出物カードの導線で専用ページへ
遷移し、プログラム(コード)＋結果(画像/テキスト)＋レポートを閲覧し、コメントで対話し、
承認で status を approved に遷移させる。コメントは owner / analyst 双方が可能(要ログイン)、
承認は owner 限定。生データ並置(合成 vs 生)は審査では行わない(#54)。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import ANALYST, OWNER, open_dataset_as

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


def _open_submission_page(page: Page, card) -> None:
    """カードの導線(review-open)を押し、提出物個別ページ(#64)を開いて待つ。"""
    card.get_by_test_id("review-open").click()
    page.wait_for_selector("[data-testid='submission-view']", state="visible")
    page.wait_for_selector("[data-testid='review-view']", state="visible")


def test_owner_reviews_program_results_report_and_approves(page: Page, base_url: str) -> None:
    """owner が提出物個別ページでプログラム＋結果＋レポートを閲覧し、承認で approved になる。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])
    _submit_one(page)

    # 専用ページへ遷移(プリセット #53 ではなくユーザー提出分を選ぶ)。
    _open_submission_page(page, _user_card(page))
    review = page.get_by_test_id("review-view")

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

    # 承認 → status が approved に遷移し、callout が出る。
    review.get_by_test_id("review-approve").click()
    expect(review.get_by_test_id("review-callout")).to_be_visible()
    expect(review.get_by_test_id("submission-status")).to_have_text("approved")

    # データセット個別ページへ戻ると、一覧カードにも approved が反映される。
    page.get_by_test_id("submission-back").click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    card = _user_card(page)
    expect(card.get_by_test_id("submission-status")).to_have_text("approved")
    expect(card).to_have_attribute("data-status", "approved")


def test_owner_can_comment_on_submission(page: Page, base_url: str) -> None:
    """owner が提出物個別ページでコメントを追加でき、即時に一覧へ表示される(#64)。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])
    _submit_one(page, with_image=False)
    _open_submission_page(page, _user_card(page))

    page.get_by_test_id("comment-input").fill("クラスタ境界の根拠を補足してください。")
    page.get_by_test_id("comment-submit").click()

    items = page.get_by_test_id("comment-item")
    expect(items.last).to_contain_text("クラスタ境界の根拠")
    # 著者はログイン中ユーザー名(owner)。
    expect(items.last).to_contain_text(OWNER[0])
    # 入力欄は送信後にクリアされる。
    expect(page.get_by_test_id("comment-input")).to_have_value("")


def test_analyst_can_comment_but_not_approve(page: Page, base_url: str) -> None:
    """analyst は提出物個別ページを閲覧・コメントできるが、承認導線は出ない(#64)。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])
    _submit_one(page, with_image=False)
    _open_submission_page(page, _user_card(page))

    # 承認ボタンは owner 限定(x-show)で非表示。
    assert page.locator("[data-testid='review-approve']:visible").count() == 0
    # コメントは可能(全ログインユーザー)。
    page.get_by_test_id("comment-input").fill("再現性の検証方法を共有します。")
    page.get_by_test_id("comment-submit").click()
    expect(page.get_by_test_id("comment-item").last).to_contain_text("再現性の検証方法")
    expect(page.get_by_test_id("comment-item").last).to_contain_text(ANALYST[0])


def test_review_has_no_raw_data_juxtaposition(page: Page, base_url: str) -> None:
    """提出物個別ページに生データ並置(合成 vs 生)が存在しない(核メッセージはデモ面へ移設)。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])
    _submit_one(page, with_image=False)
    _open_submission_page(page, _user_card(page))

    # 旧・生データ並置の痕跡(別 id pane / 合成 vs 生の compare)が無い。
    assert page.locator("#sub-review-raw").count() == 0
    assert page.locator("#sub-review-synthetic").count() == 0
    assert page.get_by_test_id("review-view").locator(".compare").count() == 0


def test_analyst_has_no_approve_affordance_in_list(page: Page, base_url: str) -> None:
    """analyst にはデータセット一覧に承認ガード注記が出る(承認は owner 限定, #64)。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])
    _submit_one(page, with_image=False)

    # 一覧の遷移導線(review-open)は出る(閲覧/コメントのため全ロール可)が、文言は「詳細を見る」。
    expect(_user_card(page).get_by_test_id("review-open")).to_have_text("詳細を見る →")
    # 承認は owner 限定の旨のガード注記が出る。
    expect(page.get_by_test_id("review-guard")).to_be_visible()


def test_submission_back_navigation(page: Page, base_url: str) -> None:
    """提出物個別ページから「戻る」でデータセット個別ページへ復帰する(#64)。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])
    _submit_one(page, with_image=False)
    _open_submission_page(page, _user_card(page))

    page.get_by_test_id("submission-back").click()
    expect(page.get_by_test_id("dataset-view")).to_be_visible()
    expect(page.get_by_test_id("submission-view")).to_be_hidden()


def test_approved_submission_reopens_with_result(page: Page, base_url: str) -> None:
    """承認済み提出物を再度開くと、プログラム＋結果が復元表示され承認ボタンが無効(#64)。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])
    _submit_one(page, with_image=False)
    _open_submission_page(page, _user_card(page))
    page.get_by_test_id("review-approve").click()
    expect(page.get_by_test_id("review-callout")).to_be_visible()

    # データセットへ戻る。
    page.get_by_test_id("submission-back").click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")
    card = _user_card(page)
    # 「審査結果を見る →」で再オープン(ユーザー提出分のカード)。
    expect(card.get_by_test_id("review-open")).to_have_text("審査結果を見る →")
    _open_submission_page(page, card)
    expect(page.get_by_test_id("review-program-code")).to_contain_text("KMeans")
    expect(page.get_by_test_id("review-approve")).to_be_disabled()


def _preset_card(page: Page, submission_id: str):
    """指定 id のプリセット(#53)提出物カード。"""
    return page.locator(f"[data-testid='submission-card'][data-submission-id='{submission_id}']")


def test_preset_submissions_seeded_on_dataset(page: Page, base_url: str) -> None:
    """初回表示でプリセット提出物(#53)が一覧に並び、提出ゼロでないこと。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])

    # まだ手動提出していなくても、プリセットがカードとして見える。
    expect(_preset_card(page, "preset-1")).to_be_visible()
    expect(_preset_card(page, "preset-2")).to_be_visible()
    expect(page.get_by_test_id("submission-empty")).to_be_hidden()
    # デモ用バッジが付く(架空成果物であることが分かる)。
    expect(_preset_card(page, "preset-1").get_by_test_id("submission-preset-badge")).to_be_visible()


def test_preset_status_mix_submitted_and_approved(page: Page, base_url: str) -> None:
    """プリセットは submitted と approved を混在し、一覧の status 差が見える(#53)。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])

    submitted = _preset_card(page, "preset-1")
    approved = _preset_card(page, "preset-2")
    expect(submitted.get_by_test_id("submission-status")).to_have_text("submitted")
    expect(submitted).to_have_attribute("data-status", "submitted")
    expect(approved.get_by_test_id("submission-status")).to_have_text("approved")
    expect(approved).to_have_attribute("data-status", "approved")


def test_preset_submission_program_results_report_viewable(page: Page, base_url: str) -> None:
    """プリセット(#53)を専用ページで開くと、プログラム＋結果＋レポートが閲覧できる(#64)。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])

    _open_submission_page(page, _preset_card(page, "preset-1"))
    review = page.get_by_test_id("review-view")
    # プログラム(コード)が x-text 表示される(既存ビューアを再利用)。
    expect(review.get_by_test_id("review-program-code")).to_contain_text("KMeans")
    # 結果(テキスト)が表示される。
    expect(review.get_by_test_id("review-result").first).to_contain_text("responder")
    # レポートにプリセット由来の注記が出る。
    expect(review.get_by_test_id("review-report-shown")).to_contain_text("プリセット")


def test_preset_approved_shows_review_result_button_and_seeded_comment(
    page: Page, base_url: str
) -> None:
    """承認済みプリセットは「審査結果を見る →」で開け、承認ボタンが無効で seed コメントが見える。"""
    open_dataset_as(page, base_url, name=OWNER[0], password=OWNER[1])

    approved = _preset_card(page, "preset-2")
    expect(approved.get_by_test_id("review-open")).to_have_text("審査結果を見る →")
    _open_submission_page(page, approved)
    review = page.get_by_test_id("review-view")
    expect(review.get_by_test_id("review-program-code")).to_contain_text("log_dose")
    expect(review.get_by_test_id("review-approve")).to_be_disabled()
    # デモ用 seed コメント(#64)が一覧に出る。
    expect(page.get_by_test_id("comment-item").first).to_contain_text("用量反応の方向性")


def test_preset_does_not_collide_with_user_submission_ids(page: Page, base_url: str) -> None:
    """プリセット(preset-<n>)が seq を進めず、ユーザー提出は sub-<n> でユニーク採番(#53)。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])

    # デモ提出は「フォーム記入のみ」(#65)。記入→提出 を 2 回行うと、別々の sub-<n> が
    # 付き、プリセットと混ざらない。
    page.get_by_test_id("submit-demo").click()
    page.get_by_test_id("submit-to-dataset").click()
    page.get_by_test_id("submit-demo").click()
    page.get_by_test_id("submit-to-dataset").click()
    user_cards = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']")
    expect(user_cards).to_have_count(2)
    ids = user_cards.evaluate_all("els => els.map(e => e.getAttribute('data-submission-id'))")
    assert len(set(ids)) == 2, f"sub-<n> が重複している: {ids}"
    # プリセット id とも衝突しない。
    assert all(not i.startswith("preset-") for i in ids)
