"""IC-1: データ生成の再現性・シード差・スキーマ/件数テスト。

プロダクションコード(generator/)は変更せず、`_generate` を直接呼んで検証する。
数値の脆いアサートは避け、構造・一致・集合メンバシップを中心に確認する。
"""

from __future__ import annotations

from generator import generate_data
from generator.generate_data import Profile

RISK_GROUPS = {"low", "intermediate", "high"}
DRUGS = {"leuprolide", "goserelin", "bicalutamide"}
TOP_KEYS = {"meta", "patients", "psa_measurements", "medications"}
PSA_KEYS = {"patient_id", "date", "psa"}
PATIENT_KEYS = {"patient_id", "age", "risk_group", "enrollment_date"}
MED_KEYS = {"patient_id", "datetime", "drug", "dose_mg"}


# --- 再現性 -----------------------------------------------------------------


def test_reproducible_same_profile() -> None:
    """同一 Profile で2回呼ぶと dict 全体が完全一致する。"""
    profile = Profile(name="test", seed=1234, n_patients=30, shift=0.0)
    a = generate_data._generate(profile)
    b = generate_data._generate(profile)
    assert a == b


def test_reproducible_equivalent_profiles() -> None:
    """同値の別インスタンス Profile でも結果が完全一致する(シードのみが効く)。"""
    a = generate_data._generate(Profile(name="test", seed=777, n_patients=30, shift=0.5))
    b = generate_data._generate(Profile(name="test", seed=777, n_patients=30, shift=0.5))
    assert a == b


# --- シード差 ----------------------------------------------------------------


def test_different_seed_differs() -> None:
    """seed が異なれば結果が変わる(=シードが効いている)。

    meta["seed"] の反映は決定的に確認する。psa_measurements の不一致は確率的命題だが、
    30 患者 × 多数の連続値ノイズを生成するため偶然一致する確率は事実上ゼロ。
    """
    base = Profile(name="test", seed=1234, n_patients=30, shift=0.0)
    other = Profile(name="test", seed=4321, n_patients=30, shift=0.0)
    a = generate_data._generate(base)
    b = generate_data._generate(other)
    assert a["meta"]["seed"] == 1234 and b["meta"]["seed"] == 4321
    assert a["psa_measurements"] != b["psa_measurements"]


# --- スキーマ / 件数 ---------------------------------------------------------


def test_top_level_keys(dataset: dict) -> None:
    assert set(dataset.keys()) == TOP_KEYS


def test_meta_schema(small_profile: Profile, dataset: dict) -> None:
    meta = dataset["meta"]
    assert set(meta.keys()) == {
        "dataset",
        "n_patients",
        "seed",
        "shift",
        "progression_delta",
        "generated_by",
    }
    assert meta["dataset"] == small_profile.name
    assert meta["n_patients"] == small_profile.n_patients
    assert meta["seed"] == small_profile.seed
    assert meta["shift"] == small_profile.shift
    assert meta["progression_delta"] == generate_data.PROGRESSION_DELTA
    assert meta["generated_by"] == "generator.generate_data"


def test_patient_count_matches_n(small_profile: Profile, dataset: dict) -> None:
    assert len(dataset["patients"]) == small_profile.n_patients


def test_one_medication_per_patient(small_profile: Profile, dataset: dict) -> None:
    """各患者に ADT 投薬が1行ずつ。"""
    assert len(dataset["medications"]) == small_profile.n_patients


def test_psa_row_count(small_profile: Profile, dataset: dict) -> None:
    """各患者あたり MAX_VISITS 行の PSA 観測がある。"""
    expected = small_profile.n_patients * generate_data.MAX_VISITS
    assert len(dataset["psa_measurements"]) == expected


def test_patient_schema_and_membership(dataset: dict) -> None:
    for p in dataset["patients"]:
        assert set(p.keys()) == PATIENT_KEYS
        assert p["risk_group"] in RISK_GROUPS
        assert isinstance(p["patient_id"], str)
        assert isinstance(p["age"], int)


def test_psa_row_schema(dataset: dict) -> None:
    for row in dataset["psa_measurements"]:
        assert set(row.keys()) == PSA_KEYS
        assert isinstance(row["patient_id"], str)
        assert isinstance(row["date"], str)
        assert isinstance(row["psa"], float)


def test_medication_schema_and_membership(dataset: dict) -> None:
    for m in dataset["medications"]:
        assert set(m.keys()) == MED_KEYS
        assert m["drug"] in DRUGS
        assert isinstance(m["dose_mg"], float)


def test_patient_ids_consistent_across_tables(dataset: dict) -> None:
    """PSA・投薬の patient_id は患者表の id 集合に含まれる。"""
    patient_ids = {p["patient_id"] for p in dataset["patients"]}
    assert {r["patient_id"] for r in dataset["psa_measurements"]} <= patient_ids
    assert {m["patient_id"] for m in dataset["medications"]} <= patient_ids
