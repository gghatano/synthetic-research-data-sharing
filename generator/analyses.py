"""3つの分析。生データ・合成データの双方に **同一コード** を適用する。

各関数は「データセット dict -> 結果 dict」の純関数として実装する。
本番(FastAPI + scikit-learn)へそのまま移植できるよう、外部状態に依存しない。

  1. clustering : PSA 軌跡の時系列クラスタリング (KMeans, k=3)
  2. association: 投薬(用量) と PSA 低下量の関連分析 (単回帰)
  3. survival  : 進行イベントまでの Kaplan-Meier 生存時間分析
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

PROGRESSION_DELTA = 2.0
N_CLUSTERS = 3
RANDOM_STATE = 42


# --------------------------------------------------------------------------- #
# 共通の前処理
# --------------------------------------------------------------------------- #
def _frames(data: dict):
    patients = pd.DataFrame(data["patients"])
    psa = pd.DataFrame(data["psa_measurements"])
    meds = pd.DataFrame(data["medications"])
    psa["date"] = pd.to_datetime(psa["date"])
    psa = psa.sort_values(["patient_id", "date"])
    # 各患者の最初の観測日からの経過月数
    first = psa.groupby("patient_id")["date"].transform("min")
    psa["t_months"] = (psa["date"] - first).dt.days / 30.4
    return patients, psa, meds


def _per_patient_features(psa: pd.DataFrame) -> pd.DataFrame:
    """患者ごとに軌跡特徴量を抽出する。"""
    rows = []
    for pid, g in psa.groupby("patient_id"):
        g = g.sort_values("t_months")
        psa_vals = g["psa"].to_numpy()
        t = g["t_months"].to_numpy()
        baseline = float(psa_vals[0])
        nadir = float(psa_vals.min())
        nadir_idx = int(psa_vals.argmin())
        time_to_nadir = float(t[nadir_idx])
        # nadir 以降の傾き(再上昇の強さ)
        if nadir_idx < len(t) - 1:
            late_slope = float(np.polyfit(t[nadir_idx:], psa_vals[nadir_idx:], 1)[0])
        else:
            late_slope = 0.0
        variability = float(np.std(psa_vals))
        rows.append(
            dict(patient_id=pid, baseline=baseline, nadir=nadir,
                 time_to_nadir=time_to_nadir, late_slope=late_slope,
                 variability=variability)
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 1) クラスタリング
# --------------------------------------------------------------------------- #
def clustering(data: dict) -> dict:
    patients, psa, _ = _frames(data)
    feats = _per_patient_features(psa)

    feature_cols = ["baseline", "nadir", "time_to_nadir", "late_slope", "variability"]
    X = StandardScaler().fit_transform(feats[feature_cols].to_numpy())
    km = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    labels = km.fit_predict(X)
    feats["cluster"] = labels

    # late_slope の平均で responder / partial / progressor を解釈付けする
    order = (feats.groupby("cluster")["late_slope"].mean()
             .sort_values().index.tolist())
    names = {order[0]: "responder", order[1]: "partial", order[2]: "progressor"}
    feats["label"] = feats["cluster"].map(names)

    # クラスタ別の平均 PSA 軌跡(共通の月グリッドに補間)
    grid = np.arange(0, 37, 3)
    psa = psa.merge(feats[["patient_id", "label"]], on="patient_id")
    trajectories = {}
    for label, g in psa.groupby("label"):
        means = []
        for m in grid:
            window = g[(g["t_months"] >= m - 1.5) & (g["t_months"] < m + 1.5)]
            means.append(round(float(window["psa"].mean()), 2) if len(window) else None)
        trajectories[label] = means

    sizes = feats["label"].value_counts().to_dict()
    centroids = {
        names[c]: {col: round(float(v), 2)
                   for col, v in zip(feature_cols, km.cluster_centers_[c])}
        for c in range(N_CLUSTERS)
    }
    return dict(
        analysis="clustering",
        n_patients=int(len(feats)),
        grid_months=grid.tolist(),
        cluster_sizes={k: int(v) for k, v in sizes.items()},
        trajectories=trajectories,
        centroids_standardized=centroids,
        feature_cols=feature_cols,
    )


# --------------------------------------------------------------------------- #
# 2) 投薬–PSA反応の関連分析
# --------------------------------------------------------------------------- #
def association(data: dict) -> dict:
    patients, psa, meds = _frames(data)
    feats = _per_patient_features(psa)
    feats["reduction"] = feats["baseline"] - feats["nadir"]
    feats["reduction_pct"] = 100.0 * feats["reduction"] / feats["baseline"]

    merged = feats.merge(meds[["patient_id", "drug", "dose_mg"]], on="patient_id")

    # 薬剤別の PSA 低下率サマリ
    by_drug = []
    for drug, g in merged.groupby("drug"):
        by_drug.append(dict(
            drug=drug, n=int(len(g)),
            mean_reduction_pct=round(float(g["reduction_pct"].mean()), 1),
            sd_reduction_pct=round(float(g["reduction_pct"].std(ddof=0)), 1),
            mean_dose_mg=round(float(g["dose_mg"].mean()), 1),
        ))
    by_drug.sort(key=lambda r: -r["mean_reduction_pct"])

    # 用量 vs 低下率 の単回帰
    x = merged["dose_mg"].to_numpy(dtype=float)
    y = merged["reduction_pct"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0

    # 散布図用に間引いたサンプル点(最大120点)
    rng = np.random.default_rng(0)
    idx = np.arange(len(x))
    if len(idx) > 120:
        idx = np.sort(rng.choice(idx, 120, replace=False))
    points = [dict(dose=round(float(x[i]), 1), reduction=round(float(y[i]), 1))
              for i in idx]

    xs = [float(x.min()), float(x.max())]
    return dict(
        analysis="association",
        n_patients=int(len(merged)),
        by_drug=by_drug,
        regression=dict(
            slope=round(float(slope), 4),
            intercept=round(float(intercept), 2),
            r2=round(float(r2), 3),
            line=[dict(dose=round(xv, 1), reduction=round(slope * xv + intercept, 1))
                  for xv in xs],
        ),
        points=points,
    )


# --------------------------------------------------------------------------- #
# 3) 生存時間分析(Kaplan-Meier)
# --------------------------------------------------------------------------- #
def _time_to_event(psa: pd.DataFrame):
    """各患者の進行イベント時刻(月)と打ち切りフラグを求める。"""
    records = []
    for pid, g in psa.groupby("patient_id"):
        g = g.sort_values("t_months")
        vals = g["psa"].to_numpy()
        t = g["t_months"].to_numpy()
        running_nadir = np.minimum.accumulate(vals)
        event_t, observed = float(t[-1]), 0
        for i in range(len(vals)):
            if vals[i] >= running_nadir[i] + PROGRESSION_DELTA:
                event_t, observed = float(t[i]), 1
                break
        records.append(dict(patient_id=pid, time=event_t, observed=observed))
    return pd.DataFrame(records)


def _km_curve(times: np.ndarray, observed: np.ndarray):
    """Kaplan-Meier 推定(手実装)。階段状の (t, survival) を返す。"""
    order = np.argsort(times)
    times, observed = times[order], observed[order]
    n = len(times)
    curve = [dict(t=0.0, s=1.0)]
    s = 1.0
    at_risk = n
    for ut in np.unique(times):
        mask = times == ut
        d = int(observed[mask].sum())  # そのtime点でのイベント数
        if at_risk > 0 and d > 0:
            s *= (1.0 - d / at_risk)
            curve.append(dict(t=round(float(ut), 1), s=round(float(s), 4)))
        at_risk -= int(mask.sum())
    return curve


def survival(data: dict) -> dict:
    patients, psa, _ = _frames(data)
    tte = _time_to_event(psa).merge(patients[["patient_id", "risk_group"]],
                                    on="patient_id")

    curves, summary = {}, []
    for risk in ["low", "intermediate", "high"]:
        g = tte[tte["risk_group"] == risk]
        if len(g) == 0:
            continue
        curve = _km_curve(g["time"].to_numpy(), g["observed"].to_numpy())
        curves[risk] = curve
        n_events = int(g["observed"].sum())
        # イベントを起こした患者の進行までの月数中央値
        ev = g[g["observed"] == 1]["time"]
        summary.append(dict(
            risk_group=risk, n=int(len(g)), n_events=n_events,
            event_rate_pct=round(100.0 * n_events / len(g), 1),
            median_months_to_event=(round(float(ev.median()), 1)
                                    if len(ev) else None),
        ))

    return dict(
        analysis="survival",
        n_patients=int(len(tte)),
        progression_delta=PROGRESSION_DELTA,
        curves=curves,
        summary=summary,
    )


ANALYSES = {
    "clustering": clustering,
    "association": association,
    "survival": survival,
}
