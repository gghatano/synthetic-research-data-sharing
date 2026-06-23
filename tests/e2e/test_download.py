"""E2E: 合成データのダウンロード(#40, N1)。

個別ページに合成データ(synthetic.json)のダウンロード導線があり、クリックで
ダウンロードが発火する。生データ(raw)へのダウンロード導線は存在しない。
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .helpers import open_dataset

pytestmark = pytest.mark.e2e


def test_synthetic_download_button_present(page: Page, base_url: str) -> None:
    """個別ページに合成データのダウンロードボタンがあり、href/属性が synthetic を指す。"""
    open_dataset(page, base_url, "prostate-psa")

    section = page.get_by_test_id("dataset-download")
    expect(section).to_be_visible()

    link = page.get_by_test_id("download-synthetic")
    expect(link).to_be_visible()
    # 配布対象は data/<id>/synthetic.json、ファイル名は <id>-synthetic.json。
    assert link.get_attribute("href") == "data/prostate-psa/synthetic.json"
    assert link.get_attribute("download") == "prostate-psa-synthetic.json"


def test_synthetic_download_fires(page: Page, base_url: str) -> None:
    """ダウンロードボタンのクリックで download イベントが発火し、合成データを取得する。"""
    open_dataset(page, base_url, "prostate-psa")

    with page.expect_download() as dl_info:
        page.get_by_test_id("download-synthetic").click()
    download = dl_info.value
    # 提案ファイル名が <dataset_id>-synthetic.json であること。
    assert download.suggested_filename == "prostate-psa-synthetic.json"


def test_synthetic_csv_download_buttons_present(page: Page, base_url: str) -> None:
    """個別ページにテーブル単位の合成データ CSV ダウンロードボタンがある(#51)。"""
    open_dataset(page, base_url, "prostate-psa")

    section = page.get_by_test_id("download-synthetic-csv")
    expect(section).to_be_visible()
    # meta を除く各テーブル(patients / psa_measurements / medications)のボタンがある。
    expect(page.get_by_test_id("download-synthetic-csv-patients")).to_be_visible()
    expect(page.get_by_test_id("download-synthetic-csv-psa_measurements")).to_be_visible()
    expect(page.get_by_test_id("download-synthetic-csv-medications")).to_be_visible()


def test_synthetic_csv_download_fires(page: Page, base_url: str) -> None:
    """CSV ボタンのクリックで download が発火し、ファイル名が .csv で終わる(#51)。"""
    open_dataset(page, base_url, "prostate-psa")

    with page.expect_download() as dl_info:
        page.get_by_test_id("download-synthetic-csv-patients").click()
    download = dl_info.value
    # ファイル名は <dataset_id>-<table>-synthetic.csv。
    assert download.suggested_filename == "prostate-psa-patients-synthetic.csv"
    assert download.suggested_filename.endswith(".csv")


def test_raw_has_no_download_affordance(page: Page, base_url: str) -> None:
    """生データ(raw)をダウンロードさせる導線が UI に存在しない。"""
    open_dataset(page, base_url, "prostate-psa")

    # 個別ページ内で download 属性つきのアンカーは合成データの 1 本のみ。
    download_links = page.get_by_test_id("dataset-view").locator("a[download]")
    expect(download_links).to_have_count(1)
    assert download_links.first.get_attribute("download") == "prostate-psa-synthetic.json"

    # raw.json を指すリンク(href/download)はどこにも無い。
    assert page.locator("a[href*='raw.json']").count() == 0
    assert page.locator("a[download*='raw']").count() == 0
