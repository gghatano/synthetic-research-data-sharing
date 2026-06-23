"""E2E: 分析プログラム＋結果のアップロード提出(#41, N2)。

ワークベンチ(ブラウザ内 3 分析実行)は廃止され、提出は「合成データを手元に持ち帰り
外部で開発 → プログラム＋結果(画像/テキスト)をアップロード」へ変更された。
ここでは提出フォームの存在・バリデーション・提出反映・XSS 非実行を検証する。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import ANALYST, goto_app, open_dataset, open_dataset_as, open_register

pytestmark = pytest.mark.e2e

# 1x1 PNG(最小)。dataURL プレビュー確認用。
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f9f0000000049454e44ae426082"
)

_PY_PROGRAM = b"import pandas as pd\n# cluster PSA trajectories\nprint('ok')\n"


def _set_program(page: Page, name: str = "analysis.py", buf: bytes = _PY_PROGRAM) -> None:
    page.get_by_test_id("submit-program-file").set_input_files(
        {"name": name, "mimeType": "text/x-python", "buffer": buf}
    )
    expect(page.get_by_test_id("program-status")).to_be_visible()


def test_workbench_is_removed(page: Page, base_url: str) -> None:
    """個別ページから分析ワークベンチ(3 分析の htmx 実行 UI)が無くなっている。"""
    open_dataset(page, base_url, "prostate-psa")
    assert page.get_by_test_id("workbench").count() == 0
    assert page.get_by_test_id("open-workbench").count() == 0
    # 代わりに提出フォームが出る。
    expect(page.get_by_test_id("submit-form")).to_be_visible()


def test_submit_program_and_text_result(page: Page, base_url: str) -> None:
    """ログイン済みでプログラム＋結果テキストをアップロードし提出 → 一覧に反映。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])

    _set_program(page)
    page.get_by_test_id("submit-result-text").fill("responder 比率 0.62 / p=0.03")
    page.get_by_test_id("submit-report").fill("生データでの再現性を確認したい。")
    page.get_by_test_id("submit-to-dataset").click()

    expect(page.get_by_test_id("submit-success")).to_be_visible()

    # プリセット(#53)が初期配置されるため、ユーザー提出分(sub-<n>)に絞って検証する。
    card = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']").last
    expect(card).to_be_visible()
    expect(card.get_by_test_id("submission-program")).to_have_text("analysis.py")
    expect(card.get_by_test_id("submission-status")).to_have_text("submitted")
    expect(card.get_by_test_id("submission-results-count")).to_contain_text("結果 1 件")
    expect(card.get_by_test_id("submission-report")).to_contain_text("再現性")


def test_submit_program_and_image_result(page: Page, base_url: str) -> None:
    """結果に画像(PNG)を添えるとプレビューが出て、提出すると結果件数に反映される。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])

    _set_program(page)
    page.get_by_test_id("submit-result-image").set_input_files(
        {"name": "plot.png", "mimeType": "image/png", "buffer": _PNG_1X1}
    )
    preview = page.get_by_test_id("result-image-preview")
    expect(preview).to_be_visible()
    # dataURL でプレビューしている(サーバー URL ではない)。
    assert (preview.locator("img").get_attribute("src") or "").startswith("data:image/")

    page.get_by_test_id("submit-to-dataset").click()
    # プリセット(#53)と混在するため、ユーザー提出分(sub-<n>)の最新を見る。
    card = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']").last
    expect(card.get_by_test_id("submission-results-count")).to_contain_text("結果 1 件")


def test_submit_requires_login(page: Page, base_url: str) -> None:
    """未ログインでは提出ボタンが無効で、ログイン導線が出る。"""
    # ログインせずにカタログ経由で個別ページへ。
    goto_app(page, base_url)
    page.get_by_test_id("login-to-catalog").click()
    page.wait_for_selector("[data-testid='explore-view']", state="visible")
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator(
        "[data-testid='catalog-card'][data-dataset-id='prostate-psa'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")

    expect(page.get_by_test_id("submit-to-dataset")).to_be_disabled()
    expect(page.get_by_test_id("submit-need-login")).to_be_visible()


def test_submit_validation_missing_program(page: Page, base_url: str) -> None:
    """プログラム未アップロードで提出するとエラー、提出物は増えない。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])
    page.get_by_test_id("submit-result-text").fill("結果のみ")
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submit-error")).to_be_visible()
    # プリセット(#53)は残るが、ユーザー提出分(sub-<n>)は 1 件も増えない。
    assert page.locator("[data-testid='submission-card'][data-submission-id^='sub-']").count() == 0


def test_result_image_rejects_svg(page: Page, base_url: str) -> None:
    """結果画像に SVG(スクリプト混入の恐れ)を選ぶと拒否され、プレビューが出ない。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])
    page.get_by_test_id("submit-result-image").set_input_files(
        {
            "name": "evil.svg",
            "mimeType": "image/svg+xml",
            "buffer": b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>",
        }
    )
    expect(page.get_by_test_id("submit-error")).to_be_visible()
    expect(page.get_by_test_id("result-image-preview")).to_be_hidden()


def test_submit_validation_missing_result(page: Page, base_url: str) -> None:
    """プログラムのみで結果が無いと提出できない(画像かテキストの一方が必須)。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])
    _set_program(page)
    page.get_by_test_id("submit-to-dataset").click()
    expect(page.get_by_test_id("submit-error")).to_be_visible()
    # プリセット(#53)は残るが、ユーザー提出分(sub-<n>)は 1 件も増えない。
    assert page.locator("[data-testid='submission-card'][data-submission-id^='sub-']").count() == 0


def test_uploaded_program_is_not_executed_xss_safe(page: Page, base_url: str) -> None:
    """悪意あるファイル名/プログラム内容は x-text で文字列表示され、実行されない。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])

    payload = b"<script>window.__pwned=1</script>\nprint('x')\n"
    _set_program(page, name="<img src=x onerror=alert(1)>.py", buf=payload)

    # アップロード直後、プログラム内容のプレビューは x-text で文字列表示(タグが実体化しない)。
    preview = page.get_by_test_id("program-preview")
    expect(preview.locator("code")).to_contain_text("<script>window.__pwned=1</script>")
    # 注入された <script> 要素はドキュメントに存在せず、実行もされていない。
    assert page.evaluate("() => window.__pwned") is None
    assert page.locator("script:has-text('window.__pwned')").count() == 0

    # 提出後、一覧カードのプログラム名も x-text 表示(ファイル名のタグが実体化しない)。
    page.get_by_test_id("submit-result-text").fill("<b>not-bold</b>")
    page.get_by_test_id("submit-to-dataset").click()
    # プリセット(#53)と混在するため、ユーザー提出分(sub-<n>)の最新を見る。
    card = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']").last
    expect(card.get_by_test_id("submission-program")).to_contain_text(
        "<img src=x onerror=alert(1)>.py"
    )
    assert page.evaluate("() => window.__pwned") is None


def test_submit_demo_sample(page: Page, base_url: str) -> None:
    """デモ用サンプル提出ボタンで、ファイル準備なしに提出物が一覧に追加される(#52)。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])

    # 提出前、ユーザー提出分(sub-<n>)はゼロ(プリセット #53 は別 id 体系で混ざらない)。
    user_cards = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']")
    assert user_cards.count() == 0

    page.get_by_test_id("submit-demo").click()
    expect(page.get_by_test_id("submit-success")).to_be_visible()

    card = user_cards.last
    expect(card).to_be_visible()
    # 内蔵サンプル(1 件目)が手動提出と同形で表示される。
    expect(card.get_by_test_id("submission-program")).to_have_text("clustering.py")
    expect(card.get_by_test_id("submission-status")).to_have_text("submitted")
    expect(card.get_by_test_id("submission-results-count")).to_contain_text("結果 1 件")


def test_submit_demo_cycles_samples(page: Page, base_url: str) -> None:
    """連続クリックで内蔵サンプルを巡回提出する(#52)。"""
    open_dataset_as(page, base_url, name=ANALYST[0], password=ANALYST[1])

    page.get_by_test_id("submit-demo").click()
    page.get_by_test_id("submit-demo").click()

    # プリセット(#53)と区別するため、ユーザー提出分(sub-<n>)のみを数える。
    cards = page.locator("[data-testid='submission-card'][data-submission-id^='sub-']")
    expect(cards).to_have_count(2)
    # 巡回: 2 クリックで別々のサンプル名が並ぶ(最新が先頭表示でなくても両方存在する)。
    names = cards.locator("[data-testid='submission-program']").all_inner_texts()
    assert "clustering.py" in names
    assert "dose_response.py" in names


def test_submit_demo_requires_login(page: Page, base_url: str) -> None:
    """未ログインではデモ提出ボタンも無効(手動提出と同じ認証ガード)(#52)。"""
    goto_app(page, base_url)
    page.get_by_test_id("login-to-catalog").click()
    page.wait_for_selector("[data-testid='explore-view']", state="visible")
    page.wait_for_selector("[data-testid='catalog-card']", state="visible")
    page.locator(
        "[data-testid='catalog-card'][data-dataset-id='prostate-psa'] [data-testid='catalog-open']"
    ).click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")

    expect(page.get_by_test_id("submit-demo")).to_be_disabled()


def test_user_dataset_has_no_submit_form(page: Page, base_url: str) -> None:
    """ユーザー登録分(user-<n>)は合成データ未生成のため提出フォームを出さない。"""
    open_register(page, base_url)
    page.get_by_test_id("reg-title").fill("提出不可データセット")
    page.get_by_test_id("reg-description").fill("ダミーのみ。")
    page.get_by_test_id("reg-domain").fill("test")
    page.get_by_test_id("reg-sample-select").select_option("renal-egfr")
    page.get_by_test_id("reg-submit").click()
    page.get_by_test_id("reg-open").first.click()
    page.wait_for_selector("[data-testid='dataset-view']", state="visible")

    expect(page.get_by_test_id("dataset-no-submission")).to_be_visible()
    assert page.get_by_test_id("submit-form").count() == 0  # x-if で DOM から除去
    # 合成データのダウンロード導線も出ない(#40 の仮定と整合。x-show で非表示)。
    expect(page.get_by_test_id("download-synthetic")).to_be_hidden()
