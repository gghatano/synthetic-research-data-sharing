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

カタログ型対応(Issue #22):
  複数データセットを DATASETS レジストリで定義し、各データセットの生成物を
  `site/data/<dataset_id>/{raw,synthetic}.json` に書き出す。全データセットの
  メタデータを束ねた `site/data/catalog.json` も生成する。

  後方互換(重要): 既存の前立腺がん PSA データセット(prostate-psa)については、
  旧パス `site/data/{raw,synthetic}.json` も従来どおり生成し続ける。これは PF-1(#21)
  で導入されたログインシェル内の既存 3 ロールデモ・E2E が旧パスを参照しているため。
  旧→新パスへの移行は後続 Issue(#23/#25/#26) で行う前提。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
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


# 前立腺がん PSA データセット(既定)のリスク群ごとの臨床パラメータ。
# 既存挙動を1ビットも変えないため、値はここに固定し _risk_params の既定値に使う。
_PSA_RISK_PARAMS = {
    "low": dict(
        baseline=8.0,
        baseline_sd=2.0,
        nadir_frac=0.18,
        decay_months=6.0,
        progression_p=0.10,
        rise_rate=0.30,
    ),
    "intermediate": dict(
        baseline=20.0,
        baseline_sd=6.0,
        nadir_frac=0.26,
        decay_months=7.5,
        progression_p=0.30,
        rise_rate=0.55,
    ),
    "high": dict(
        baseline=45.0,
        baseline_sd=15.0,
        nadir_frac=0.34,
        decay_months=9.0,
        progression_p=0.60,
        rise_rate=0.90,
    ),
}


@dataclass
class Profile:
    """生成パラメータ。raw と synthetic で shift を変えて分布をずらす。

    Issue #22 で複数データセット対応のため `id_prefix` と `risk_params` を追加した。
    既定値は前立腺がん PSA データセット(既存挙動)と一致するため、既存呼び出しは不変。
    """

    name: str
    seed: int
    n_patients: int
    shift: float  # 分布シフト量(0.0 = 生データ基準)
    # 患者IDの接頭辞(例: "RAW-0001")。None なら name[:3].upper() を使う(既存挙動)。
    id_prefix: str | None = None
    # リスク群ごとの臨床パラメータ。None なら PSA 既定値を使う(既存挙動)。
    risk_params: dict[str, dict[str, float]] | None = field(default=None)


def _risk_params(risk: str, shift: float, table: dict[str, dict[str, float]] | None = None) -> dict:
    """リスク群ごとの臨床パラメータ。shift で synthetic を僅かにずらす。

    table を渡すとデータセット固有のパラメータ表を使う(既定は PSA)。
    """
    source = table if table is not None else _PSA_RISK_PARAMS
    p = dict(source[risk])
    # shift: baseline をやや上げ、進行確率と再上昇速度をやや上げる
    p["baseline"] *= 1.0 + 0.06 * shift
    p["progression_p"] = min(0.95, p["progression_p"] + 0.05 * shift)
    p["rise_rate"] *= 1.0 + 0.10 * shift
    p["decay_months"] *= 1.0 - 0.04 * shift
    return p


def _generate(profile: Profile) -> dict:
    rng = np.random.default_rng(profile.seed)
    patients, psa_rows, med_rows = [], [], []

    risk_probs = np.array([0.35, 0.40, 0.25])
    study_start = date(2021, 1, 1)

    prefix = profile.id_prefix if profile.id_prefix is not None else profile.name[:3].upper()
    for i in range(profile.n_patients):
        pid = f"{prefix}-{i + 1:04d}"
        risk = RISK_GROUPS[rng.choice(3, p=risk_probs)]
        rp = _risk_params(risk, profile.shift, profile.risk_params)

        age = int(np.clip(rng.normal(68, 8), 45, 90))
        enroll = study_start + timedelta(days=int(rng.integers(0, 540)))

        patients.append(
            dict(patient_id=pid, age=age, risk_group=risk, enrollment_date=enroll.isoformat())
        )

        # ADT 開始(登録から数日〜数週間後)
        drug = DRUGS[rng.choice(3, p=[0.45, 0.30, 0.25])]
        dose = {"leuprolide": 22.5, "goserelin": 10.8, "bicalutamide": 50.0}[drug]
        # 用量に個体差(±1段階)を持たせ、関連分析を意味あるものにする
        dose = round(float(dose * rng.choice([0.5, 1.0, 1.5], p=[0.2, 0.6, 0.2])), 1)
        adt_start = enroll + timedelta(days=int(rng.integers(3, 21)))
        med_rows.append(
            dict(
                patient_id=pid,
                datetime=adt_start.isoformat() + "T09:00:00",
                drug=drug,
                dose_mg=dose,
            )
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
                dict(patient_id=pid, date=obs_date.isoformat(), psa=round(float(value), 2))
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


# --------------------------------------------------------------------------- #
# データセットレジストリ (Issue #22)
# --------------------------------------------------------------------------- #
# 第2データセット(腎細胞がんの腫瘍マーカー)のリスク群別パラメータ。
# 仮定: 既存3分析(clustering / association / survival)は PSA スキーマ
#   (patients.risk_group / psa_measurements.psa / medications.drug,dose_mg)に
#   結合しているため、第2データセットも **同一スキーマ** で別ドメインを表現する。
#   PSA 列は腫瘍マーカー値として再利用し、別パラメータ・別 seed で生成する。
#   これにより分析ロジックを一切変えずに「2件以上のデータセット」を満たす。
_MARKER_RISK_PARAMS = {
    "low": dict(
        baseline=5.0,
        baseline_sd=1.5,
        nadir_frac=0.22,
        decay_months=5.0,
        progression_p=0.14,
        rise_rate=0.22,
    ),
    "intermediate": dict(
        baseline=14.0,
        baseline_sd=4.0,
        nadir_frac=0.30,
        decay_months=6.5,
        progression_p=0.34,
        rise_rate=0.45,
    ),
    "high": dict(
        baseline=32.0,
        baseline_sd=10.0,
        nadir_frac=0.38,
        decay_months=8.0,
        progression_p=0.62,
        rise_rate=0.72,
    ),
}


@dataclass
class Dataset:
    """カタログに載るデータセット定義。生成パラメータ + 表示用メタデータ。"""

    dataset_id: str
    title: str
    description: str
    owner: str
    domain: str
    tags: list[str]
    usage_examples: list[str]
    raw: Profile
    synthetic: Profile
    # 旧パス互換: True の場合 site/data/{raw,synthetic}.json も生成する。
    legacy_paths: bool = False


# 既存の前立腺がん PSA データセット。raw/synthetic の Profile は既存値を厳密に維持する
# (id_prefix="RAW"/"SYN" は従来 name[:3].upper() と一致 → 出力バイト不変)。
DATASETS: list[Dataset] = [
    Dataset(
        dataset_id="prostate-psa",
        title="前立腺がん PSA 推移と ADT 投薬",
        description=(
            "前立腺がん患者の PSA(前立腺特異抗原)時系列と ADT(アンドロゲン除去療法)投薬の"
            "合成コホート。ADT 開始後の PSA 低下・nadir・生化学的再発(Phoenix 基準)を含む。"
        ),
        owner="urology-research",
        domain="oncology/urology",
        tags=["prostate-cancer", "psa", "adt", "survival", "longitudinal"],
        usage_examples=[
            "PSA 軌跡の時系列クラスタリングで治療反応サブタイプを同定する",
            "ADT 用量と PSA 低下率の関連を単回帰で評価する",
            "リスク群別の無進行生存(Kaplan-Meier)を比較する",
        ],
        raw=Profile(name="raw", seed=20210101, n_patients=180, shift=0.0),
        synthetic=Profile(name="synthetic", seed=99999, n_patients=180, shift=1.0),
        legacy_paths=True,
    ),
    Dataset(
        dataset_id="renal-marker",
        title="腎細胞がん 腫瘍マーカー推移と分子標的薬",
        description=(
            "腎細胞がん患者の腫瘍マーカー時系列と分子標的薬投与の合成コホート。"
            "PSA データセットと同型(3テーブル)だが別ドメイン・別パラメータ・別 seed で生成し、"
            "同一の3分析をそのまま適用できる。値は架空の腫瘍マーカー(ng/mL)とみなす。"
        ),
        owner="oncology-data-lab",
        domain="oncology/nephrology",
        tags=["renal-cancer", "tumor-marker", "targeted-therapy", "longitudinal"],
        usage_examples=[
            "腫瘍マーカー軌跡のクラスタリングで反応パターンを層別化する",
            "投与量とマーカー低下率の関連を評価する",
            "リスク群別の無進行生存(Kaplan-Meier)を比較する",
        ],
        raw=Profile(
            name="raw",
            seed=20220202,
            n_patients=150,
            shift=0.0,
            id_prefix="RNL-R",
            risk_params=_MARKER_RISK_PARAMS,
        ),
        synthetic=Profile(
            name="synthetic",
            seed=33331,
            n_patients=150,
            shift=1.0,
            id_prefix="RNL-S",
            risk_params=_MARKER_RISK_PARAMS,
        ),
        legacy_paths=False,
    ),
]


def _dummy_preview(data: dict, n: int = 5) -> dict:
    """カタログ表示用の少量サンプル行(各テーブル先頭 n 行)を抜き出す。"""
    return dict(
        patients=data["patients"][:n],
        psa_measurements=data["psa_measurements"][:n],
        medications=data["medications"][:n],
    )


def _catalog_entry(ds: Dataset, syn: dict) -> dict:
    """カタログ索引 1 件分のメタデータ(合成データ由来のプレビュー込み)を組み立てる。"""
    return dict(
        dataset_id=ds.dataset_id,
        title=ds.title,
        description=ds.description,
        owner=ds.owner,
        domain=ds.domain,
        tags=ds.tags,
        usage_examples=ds.usage_examples,
        n_patients=ds.synthetic.n_patients,
        # 旧パス互換のため、フロントが従来パスを参照できるか示す
        legacy_paths=ds.legacy_paths,
        paths=dict(
            raw=f"data/{ds.dataset_id}/raw.json",
            synthetic=f"data/{ds.dataset_id}/synthetic.json",
            fragments_analyst=f"fragments/{ds.dataset_id}/analyst",
            fragments_owner=f"fragments/{ds.dataset_id}/owner",
        ),
        # プレビューはカタログ閲覧用なので、公開可能な合成データ側から抽出する
        dummy_preview=_dummy_preview(syn),
    )


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog: list[dict] = []

    for ds in DATASETS:
        ds_dir = OUT_DIR / ds.dataset_id
        ds_dir.mkdir(parents=True, exist_ok=True)

        generated: dict[str, dict] = {}
        for prof in (ds.raw, ds.synthetic):
            data = _generate(prof)
            generated[prof.name] = data
            out = ds_dir / f"{prof.name}.json"
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            n_psa = len(data["psa_measurements"])
            print(
                f"  wrote {out.relative_to(OUT_DIR.parent.parent)}  "
                f"({prof.n_patients} patients, {n_psa} PSA rows)"
            )
            # 旧パス互換(prostate-psa のみ): site/data/{raw,synthetic}.json も生成する。
            # PF-1(#21) の既存デモ・E2E が旧パスを参照しているため後方互換を保つ。
            if ds.legacy_paths:
                legacy = OUT_DIR / f"{prof.name}.json"
                legacy.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  wrote {legacy.relative_to(OUT_DIR.parent.parent)}  (legacy-compat)")

        catalog.append(_catalog_entry(ds, generated["synthetic"]))

    catalog_path = OUT_DIR / "catalog.json"
    catalog_path.write_text(
        json.dumps(dict(datasets=catalog), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  wrote {catalog_path.relative_to(OUT_DIR.parent.parent)}  ({len(catalog)} datasets)")


if __name__ == "__main__":
    print("Generating datasets ...")
    build()
    print("done.")
