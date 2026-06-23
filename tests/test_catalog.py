"""PF-2(#22): 複数データセットレジストリ・カタログ索引・後方互換のテスト。

プロダクションコードは変更せず、`build()` を tmp 配下で実行して生成物を検証する。
既存 PSA データセットの再現性(seed 固定)・旧パス互換・カタログスキーマを確認する。
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from generator import generate_data
from generator.generate_data import DATASETS, _generate

# カタログ索引エントリの必須メタデータキー
CATALOG_REQUIRED_KEYS = {
    "dataset_id",
    "title",
    "description",
    "owner",
    "domain",
    "tags",
    "usage_examples",
    "n_patients",
    "legacy_paths",
    "paths",
    "dummy_preview",
}
PATHS_KEYS = {"raw", "synthetic", "fragments_analyst", "fragments_owner"}
PREVIEW_TABLES = {"patients", "psa_measurements", "medications"}


@pytest.fixture
def built(tmp_path, monkeypatch):
    """build() を tmp 配下で実行し、site/data 相当を生成する。

    各データセットを小 n(=30) へ縮めて高速化する(seed/パラメータ/接頭辞は不変)。
    """
    out_dir = tmp_path / "data"
    small = [
        replace(
            ds,
            raw=replace(ds.raw, n_patients=30),
            synthetic=replace(ds.synthetic, n_patients=30),
        )
        for ds in DATASETS
    ]
    monkeypatch.setattr(generate_data, "OUT_DIR", out_dir)
    monkeypatch.setattr(generate_data, "DATASETS", small)
    generate_data.build()
    return out_dir, small


# --- レジストリ -------------------------------------------------------------


def test_registry_has_at_least_two_datasets() -> None:
    assert len(DATASETS) >= 2
    ids = [ds.dataset_id for ds in DATASETS]
    assert len(ids) == len(set(ids)), "dataset_id は一意でなければならない"
    assert "prostate-psa" in ids


# --- 各データセットの生成物 --------------------------------------------------


def test_per_dataset_files_written(built) -> None:
    out_dir, small = built
    for ds in small:
        assert (out_dir / ds.dataset_id / "raw.json").exists()
        assert (out_dir / ds.dataset_id / "synthetic.json").exists()


def test_renal_marker_same_schema_as_psa(built) -> None:
    """第2データセットは PSA と同一の 3 テーブルスキーマを保つ(既存3分析が流用可能)。"""
    out_dir, _ = built
    data = json.loads((out_dir / "renal-marker" / "synthetic.json").read_text("utf-8"))
    assert set(data.keys()) == {"meta", "patients", "psa_measurements", "medications"}
    assert set(data["patients"][0].keys()) == {
        "patient_id",
        "age",
        "risk_group",
        "enrollment_date",
    }
    assert set(data["psa_measurements"][0].keys()) == {"patient_id", "date", "psa"}
    assert set(data["medications"][0].keys()) == {
        "patient_id",
        "datetime",
        "drug",
        "dose_mg",
    }
    # 第2データセットは別の患者ID接頭辞を持つ(PSA と衝突しない)
    assert data["patients"][0]["patient_id"].startswith("RNL-S")


# --- 再現性 -----------------------------------------------------------------


def test_dataset_reproducible_full_size() -> None:
    """全データセットの Profile を実 n でそのまま再生成し、2 回の結果が一致する。"""
    for ds in DATASETS:
        for prof in (ds.raw, ds.synthetic):
            assert _generate(prof) == _generate(prof)


def test_distinct_seeds_across_datasets() -> None:
    """データセット間で seed が衝突しない(再現性と独立性の両立)。"""
    seeds = []
    for ds in DATASETS:
        seeds.append(ds.raw.seed)
        seeds.append(ds.synthetic.seed)
    assert len(seeds) == len(set(seeds))


# --- 旧パス後方互換(prostate-psa) ------------------------------------------


def test_legacy_paths_emitted_for_prostate_psa(built) -> None:
    """prostate-psa は旧パス site/data/{raw,synthetic}.json も生成する。"""
    out_dir, _ = built
    assert (out_dir / "raw.json").exists()
    assert (out_dir / "synthetic.json").exists()


def test_legacy_files_byte_identical_to_new(built) -> None:
    """旧パスと新パス(prostate-psa)のバイト一致(同一データの二重出力)。"""
    out_dir, _ = built
    assert (out_dir / "raw.json").read_bytes() == (
        out_dir / "prostate-psa" / "raw.json"
    ).read_bytes()
    assert (out_dir / "synthetic.json").read_bytes() == (
        out_dir / "prostate-psa" / "synthetic.json"
    ).read_bytes()


def test_no_legacy_paths_for_second_dataset(built) -> None:
    """legacy_paths=False のデータセットは旧パスへ書き出さない(衝突防止)。"""
    out_dir, small = built
    non_legacy = [ds for ds in small if not ds.legacy_paths]
    assert non_legacy, "前提: legacy_paths=False のデータセットが存在する"
    # 旧パスのファイルは prostate-psa のもの(=legacy)だけであることを確認
    legacy_raw = json.loads((out_dir / "raw.json").read_text("utf-8"))
    assert legacy_raw["patients"][0]["patient_id"].startswith(("RAW", "SYN"))


# --- カタログ索引 -----------------------------------------------------------


def test_catalog_json_written_and_lists_all_datasets(built) -> None:
    out_dir, small = built
    catalog = json.loads((out_dir / "catalog.json").read_text("utf-8"))
    assert "datasets" in catalog
    ids = [e["dataset_id"] for e in catalog["datasets"]]
    assert ids == [ds.dataset_id for ds in small]


def test_catalog_entries_have_required_keys(built) -> None:
    out_dir, _ = built
    catalog = json.loads((out_dir / "catalog.json").read_text("utf-8"))
    for entry in catalog["datasets"]:
        assert CATALOG_REQUIRED_KEYS <= set(entry.keys())
        assert set(entry["paths"].keys()) == PATHS_KEYS
        assert isinstance(entry["tags"], list) and entry["tags"]
        assert isinstance(entry["usage_examples"], list) and entry["usage_examples"]
        assert set(entry["dummy_preview"].keys()) == PREVIEW_TABLES
        # プレビューは少量サンプル(各テーブル <= 5 行)
        for table in PREVIEW_TABLES:
            assert 0 < len(entry["dummy_preview"][table]) <= 5


def test_catalog_paths_point_to_existing_files(built) -> None:
    """カタログの paths(raw/synthetic)が実ファイルを指す。"""
    out_dir, _ = built
    catalog = json.loads((out_dir / "catalog.json").read_text("utf-8"))
    site_dir = out_dir.parent  # data/ の親(= site 相当)
    for entry in catalog["datasets"]:
        assert (site_dir / entry["paths"]["raw"]).exists()
        assert (site_dir / entry["paths"]["synthetic"]).exists()


def test_preview_comes_from_synthetic_not_raw(built) -> None:
    """dummy_preview は合成データ由来(公開可能)であることを確認する。"""
    out_dir, _ = built
    catalog = json.loads((out_dir / "catalog.json").read_text("utf-8"))
    entry = next(e for e in catalog["datasets"] if e["dataset_id"] == "prostate-psa")
    syn = json.loads((out_dir / "prostate-psa" / "synthetic.json").read_text("utf-8"))
    assert entry["dummy_preview"]["patients"] == syn["patients"][:5]
