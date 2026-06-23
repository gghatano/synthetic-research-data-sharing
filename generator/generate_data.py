"""生データ・合成データを生成する（シード固定で再現可能）。

前立腺がん患者の PSA(前立腺特異抗原) 時系列と ADT(アンドロゲン除去療法) 投薬を
シミュレートする。臨床的な素性:

  - ADT 開始後、PSA は nadir(最低値) まで指数的に低下する
  - 一部の患者で nadir 後に再上昇 = 生化学的再発(進行イベント)
  - Phoenix 基準: PSA >= nadir + 2.0 ng/mL を進行イベントとみなす

生データ(raw)と合成データ(synthetic)は別シード + わずかな分布シフトで生成する。
統計的には類似するが、個々の値・クラスタ境界・KM 曲線は完全には一致しない。
これがデモの核となるメッセージ(「合成データで開発したコードを生データに適用する
ステップに価値がある」)を成立させる。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).resolve().parent.parent / "site" / "data"

RISK_GROUPS = ["low", "intermediate", "high"]
DRUGS = ["leuprolide", "goserelin", "bicalutamide"]

# 約3ヶ月ごとに最大36ヶ月(=13回)観測する
VISIT_INTERVAL_DAYS = 91
MAX_VISITS = 13
PROGRESSION_DELTA = 2.0  # Phoenix 基準 nadir + 2.0 ng/mL


@dataclass
class Profile:
    """生成パラメータ。raw と synthetic で shift を変えて分布をずらす。"""

    name: str
    seed: int
    n_patients: int
    shift: float  # 分布シフト量(0.0 = 生データ基準)


def _risk_params(risk: str, shift: float) -> dict:
    """リスク群ごとの臨床パラメータ。shift で synthetic を僅かにずらす。"""
    base = {
        "low": dict(baseline=8.0, baseline_sd=2.0, nadir_frac=0.18,
                    decay_months=6.0, progression_p=0.10, rise_rate=0.30),
        "intermediate": dict(baseline=20.0, baseline_sd=6.0, nadir_frac=0.26,
                             decay_months=7.5, progression_p=0.30, rise_rate=0.55),
        "high": dict(baseline=45.0, baseline_sd=15.0, nadir_frac=0.34,
                     decay_months=9.0, progression_p=0.60, rise_rate=0.90),
    }[risk]
    p = dict(base)
    # shift: baseline をやや上げ、進行確率と再上昇速度をやや上げる
    p["baseline"] *= (1.0 + 0.06 * shift)
    p["progression_p"] = min(0.95, p["progression_p"] + 0.05 * shift)
    p["rise_rate"] *= (1.0 + 0.10 * shift)
    p["decay_months"] *= (1.0 - 0.04 * shift)
    return p


def _generate(profile: Profile) -> dict:
    rng = np.random.default_rng(profile.seed)
    patients, psa_rows, med_rows = [], [], []

    risk_probs = np.array([0.35, 0.40, 0.25])
    study_start = date(2021, 1, 1)

    for i in range(profile.n_patients):
        pid = f"{profile.name[:3].upper()}-{i + 1:04d}"
        risk = RISK_GROUPS[rng.choice(3, p=risk_probs)]
        rp = _risk_params(risk, profile.shift)

        age = int(np.clip(rng.normal(68, 8), 45, 90))
        enroll = study_start + timedelta(days=int(rng.integers(0, 540)))

        patients.append(
            dict(patient_id=pid, age=age, risk_group=risk,
                 enrollment_date=enroll.isoformat())
        )

        # ADT 開始(登録から数日〜数週間後)
        drug = DRUGS[rng.choice(3, p=[0.45, 0.30, 0.25])]
        dose = {"leuprolide": 22.5, "goserelin": 10.8, "bicalutamide": 50.0}[drug]
        # 用量に個体差(±1段階)を持たせ、関連分析を意味あるものにする
        dose = round(float(dose * rng.choice([0.5, 1.0, 1.5], p=[0.2, 0.6, 0.2])), 1)
        adt_start = enroll + timedelta(days=int(rng.integers(3, 21)))
        med_rows.append(
            dict(patient_id=pid, datetime=adt_start.isoformat() + "T09:00:00",
                 drug=drug, dose_mg=dose)
        )

        baseline = max(1.0, rng.normal(rp["baseline"], rp["baseline_sd"]))
        # 用量が多いほど nadir が深くなる(= PSA 低下率が大きい)。
        # これが関連分析(用量 vs 低下率)のシグナル源になる。
        dose_ratio = dose / 22.5  # 1.0 を基準
        nadir_frac = rp["nadir_frac"] * max(0.35, 1.0 - 0.50 * (dose_ratio - 1.0))
        nadir = max(0.05, baseline * nadir_frac * rng.uniform(0.9, 1.1))
        decay_days = rp["decay_months"] * 30.4 * max(0.6, 1.0 - 0.04 * (dose_ratio - 1.0))

        progresses = rng.random() < rp["progression_p"]
        rise_rate = rp["rise_rate"] * rng.uniform(0.6, 1.4)  # ng/mL per month
        # nadir 到達後、再上昇開始までのラグ(月)
        rise_lag_days = rng.uniform(2.0, 8.0) * 30.4

        noise_sd = 0.06 * baseline + 0.2

        for v in range(MAX_VISITS):
            t_days = v * VISIT_INTERVAL_DAYS
            obs_date = adt_start + timedelta(days=t_days)
            # 指数減衰で nadir に近づく
            decline = nadir + (baseline - nadir) * np.exp(-t_days / decay_days)
            value = decline
            if progresses and t_days > decay_days + rise_lag_days:
                months_rising = (t_days - decay_days - rise_lag_days) / 30.4
                value = nadir + rise_rate * months_rising
            value = max(0.01, value + rng.normal(0, noise_sd))
            psa_rows.append(
                dict(patient_id=pid, date=obs_date.isoformat(),
                     psa=round(float(value), 2))
            )

    return dict(
        meta=dict(
            dataset=profile.name,
            n_patients=profile.n_patients,
            seed=profile.seed,
            shift=profile.shift,
            progression_delta=PROGRESSION_DELTA,
            generated_by="generator.generate_data",
        ),
        patients=patients,
        psa_measurements=psa_rows,
        medications=med_rows,
    )


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profiles = [
        Profile(name="raw", seed=20210101, n_patients=180, shift=0.0),
        Profile(name="synthetic", seed=99999, n_patients=180, shift=1.0),
    ]
    for prof in profiles:
        data = _generate(prof)
        out = OUT_DIR / f"{prof.name}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        n_psa = len(data["psa_measurements"])
        print(f"  wrote {out.relative_to(OUT_DIR.parent.parent)}  "
              f"({prof.n_patients} patients, {n_psa} PSA rows)")


if __name__ == "__main__":
    print("Generating datasets ...")
    build()
    print("done.")
