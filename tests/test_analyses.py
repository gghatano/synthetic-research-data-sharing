"""IC-2: 3分析(clustering / association / survival)の純関数性・スキーマ・堅牢性。

プロダクションコード(generator/)は変更せず、`ANALYSES` の各関数を直接呼んで検証する。
数値の脆い等値比較は避け、型・キー・集合・範囲・合計で確認する。
"""

from __future__ import annotations

import copy

import pytest

from generator.analyses import ANALYSES, PROGRESSION_DELTA

RISK_GROUPS = {"low", "intermediate", "high"}
CLUSTER_LABELS = {"responder", "partial", "progressor"}
FEATURE_COLS = ["baseline", "nadir", "time_to_nadir", "late_slope", "variability"]


# --- 純関数性 ---------------------------------------------------------------


@pytest.mark.parametrize("name", list(ANALYSES))
def test_does_not_mutate_input(name: str, dataset: dict) -> None:
    """各分析は入力 dict を破壊しない。"""
    fn = ANALYSES[name]
    before = copy.deepcopy(dataset)
    fn(dataset)
    assert dataset == before


@pytest.mark.parametrize("name", list(ANALYSES))
def test_deterministic_same_input(name: str, dataset: dict) -> None:
    """同一入力で2回呼ぶと戻り値が完全一致する(KMeans は random_state 固定で決定的)。"""
    fn = ANALYSES[name]
    a = fn(dataset)
    b = fn(dataset)
    assert a == b


# --- 共通スキーマ -----------------------------------------------------------


@pytest.mark.parametrize("name", list(ANALYSES))
def test_analysis_name_and_n_patients(name: str, dataset: dict) -> None:
    result = ANALYSES[name](dataset)
    assert result["analysis"] == name
    assert isinstance(result["n_patients"], int)
    assert result["n_patients"] > 0


# --- clustering -------------------------------------------------------------


def test_clustering_schema(dataset: dict) -> None:
    r = ANALYSES["clustering"](dataset)
    assert set(r.keys()) == {
        "analysis",
        "n_patients",
        "grid_months",
        "cluster_sizes",
        "trajectories",
        "centroids_standardized",
        "feature_cols",
    }
    assert r["feature_cols"] == FEATURE_COLS
    assert isinstance(r["grid_months"], list)
    assert all(isinstance(m, int) for m in r["grid_months"])


def test_clustering_cluster_sizes(dataset: dict) -> None:
    """ラベルは responder/partial/progressor、合計は n_patients。"""
    r = ANALYSES["clustering"](dataset)
    sizes = r["cluster_sizes"]
    # KMeans(k=3) を強制しラベル解釈を付けるため、3 ラベルが揃う契約。
    assert set(sizes) == CLUSTER_LABELS
    assert all(isinstance(v, int) for v in sizes.values())
    assert sum(sizes.values()) == r["n_patients"]


def test_clustering_centroids(dataset: dict) -> None:
    """各 centroid は feature_cols をキーに持つ float の dict。"""
    r = ANALYSES["clustering"](dataset)
    centroids = r["centroids_standardized"]
    assert set(centroids) == CLUSTER_LABELS
    for vals in centroids.values():
        assert set(vals.keys()) == set(FEATURE_COLS)
        assert all(isinstance(v, float) for v in vals.values())


def test_clustering_trajectories(dataset: dict) -> None:
    """trajectories の各値は grid_months と同長の list(float または None)。"""
    r = ANALYSES["clustering"](dataset)
    n = len(r["grid_months"])
    assert set(r["trajectories"]) <= CLUSTER_LABELS
    for series in r["trajectories"].values():
        assert isinstance(series, list)
        assert len(series) == n
        assert all(v is None or isinstance(v, float) for v in series)


# --- association ------------------------------------------------------------


def test_association_schema(dataset: dict) -> None:
    r = ANALYSES["association"](dataset)
    assert set(r.keys()) == {
        "analysis",
        "n_patients",
        "by_drug",
        "regression",
        "points",
    }


def test_association_by_drug(dataset: dict) -> None:
    r = ANALYSES["association"](dataset)
    assert isinstance(r["by_drug"], list)
    assert r["by_drug"]  # 非空（空だと以下の検証が空振りする）
    for row in r["by_drug"]:
        assert set(row.keys()) == {
            "drug",
            "n",
            "mean_reduction_pct",
            "sd_reduction_pct",
            "mean_dose_mg",
        }
        assert isinstance(row["drug"], str)
        assert isinstance(row["n"], int)
        assert isinstance(row["mean_reduction_pct"], float)
        assert isinstance(row["sd_reduction_pct"], float)
        assert isinstance(row["mean_dose_mg"], float)


def test_association_regression(dataset: dict) -> None:
    r = ANALYSES["association"](dataset)
    reg = r["regression"]
    assert set(reg.keys()) == {"slope", "intercept", "r2", "line"}
    assert isinstance(reg["slope"], float)
    assert isinstance(reg["intercept"], float)
    assert isinstance(reg["r2"], float)
    assert isinstance(reg["line"], list)
    for pt in reg["line"]:
        assert set(pt.keys()) == {"dose", "reduction"}
        assert isinstance(pt["dose"], float)
        assert isinstance(pt["reduction"], float)


def test_association_points(dataset: dict) -> None:
    r = ANALYSES["association"](dataset)
    assert isinstance(r["points"], list)
    for pt in r["points"]:
        assert set(pt.keys()) == {"dose", "reduction"}
        assert isinstance(pt["dose"], float)
        assert isinstance(pt["reduction"], float)


# --- survival ---------------------------------------------------------------


def test_survival_schema(dataset: dict) -> None:
    r = ANALYSES["survival"](dataset)
    assert set(r.keys()) == {
        "analysis",
        "n_patients",
        "progression_delta",
        "curves",
        "summary",
    }
    assert r["progression_delta"] == PROGRESSION_DELTA == 2.0


def test_survival_summary_rows(dataset: dict) -> None:
    """summary 各行のキー・型。median は float か None、event_rate_pct は 0..100。"""
    r = ANALYSES["survival"](dataset)
    assert r["summary"]  # 非空（空だと以下の検証が空振りする）
    for row in r["summary"]:
        assert set(row.keys()) == {
            "risk_group",
            "n",
            "n_events",
            "event_rate_pct",
            "median_months_to_event",
        }
        assert row["risk_group"] in RISK_GROUPS
        assert isinstance(row["n"], int)
        assert isinstance(row["n_events"], int)
        assert isinstance(row["event_rate_pct"], float)
        assert 0.0 <= row["event_rate_pct"] <= 100.0
        assert row["median_months_to_event"] is None or isinstance(
            row["median_months_to_event"], float
        )
        assert 0 <= row["n_events"] <= row["n"]


def test_survival_curves_schema(dataset: dict) -> None:
    r = ANALYSES["survival"](dataset)
    for curve in r["curves"].values():
        assert isinstance(curve, list)
        assert curve and curve[0] == {"t": 0.0, "s": 1.0}
        for pt in curve:
            assert set(pt.keys()) == {"t", "s"}
            assert isinstance(pt["t"], float)
            assert isinstance(pt["s"], float)
            assert 0.0 <= pt["s"] <= 1.0


def test_survival_only_present_groups(dataset: dict) -> None:
    """存在するリスク群のみ含み、curves のキー集合 == summary の risk_group 集合。"""
    r = ANALYSES["survival"](dataset)
    summary_groups = {row["risk_group"] for row in r["summary"]}
    assert summary_groups <= RISK_GROUPS
    assert set(r["curves"].keys()) == summary_groups
    # n の合計は n_patients に一致する。
    assert sum(row["n"] for row in r["summary"]) == r["n_patients"]


# --- 境界 / 堅牢性 -----------------------------------------------------------


@pytest.mark.parametrize("name", list(ANALYSES))
def test_runs_on_synthetic_data(name: str, syn_dataset: dict) -> None:
    """shift>0 の合成相当データでも例外なく動き、analysis 名を返す。"""
    r = ANALYSES[name](syn_dataset)
    assert r["analysis"] == name
