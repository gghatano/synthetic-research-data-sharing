"""IC-3: デモの核メッセージ(合成データ vs 生データ)の検証。

raw と synthetic の双方に **同一の分析コード**(`generator.analyses.ANALYSES`)を
適用し、主要指標が「近いが完全には一致しない」ことを確認する。これが本デモの核
(「合成データで開発したコードを生データに適用するステップに価値がある」)を支える。

本番相当の実プロファイル(n=180, シード固定)を使う。小 n だと指標が不安定なため。
すべて決定的(固定シード + ピン留めされた numpy/pandas/sklearn)なので flaky にしない。

--------------------------------------------------------------------------- #
許容レンジ(TOL)について
--------------------------------------------------------------------------- #
「近い」の許容レンジは SPEC では未規定(Issue #4 に論点ありと記録済み)。
本テストでは下記の **dev 観測値** に基づき、余裕を持った暫定 TOL を採用する。
後で基準を見直せるよう、TOL はこのモジュール冒頭の定数にまとめてある。

観測値(seed raw=20210101 / synthetic=99999, n_patients=180):

  指標                         raw        synthetic    |差|
  --------------------------   --------   ----------   -------
  regression.slope            0.3719     0.4482       0.0763
  regression.r2               0.214      0.354        0.140
  progressor 人数比            0.2278     0.1889       0.0389
    (cluster_sizes raw)        responder=81 partial=58 progressor=41
    (cluster_sizes syn)        responder=97 partial=49 progressor=34
  全体イベント率               0.7333     0.6722       0.0611
    (= sum(n_events)/sum(n))   (132/180)  (121/180)
  high群 event_rate_pct        97.7       100.0        2.3

各 TOL は上記 |差| に対して概ね 2〜4 倍の余裕を持たせた仮置きである。
"""

from __future__ import annotations

import pytest

from generator import generate_data
from generator.analyses import ANALYSES
from generator.generate_data import Profile

# 本番相当。generate_data.build() の profiles と**手動同期**している
# （seed/n_patients/shift が build 側で変わったら、ここと下記 TOL の再校正が必要）。
RAW_PROFILE = Profile(name="raw", seed=20210101, n_patients=180, shift=0.0)
SYN_PROFILE = Profile(name="synthetic", seed=99999, n_patients=180, shift=1.0)

# --- 暫定 TOL(SPEC 未規定。上記観測 |差| に余裕を持たせた仮置き) ------------- #
# slope: 観測差 0.0763 -> TOL 0.15(約2倍)
TOL_SLOPE = 0.15
# r2: 観測差 0.140 -> TOL 0.25(約1.8倍)
TOL_R2 = 0.25
# progressor 人数比: 観測差 0.0389 -> TOL 0.10(約2.6倍)
TOL_PROGRESSOR_RATIO = 0.10
# 全体イベント率: 観測差 0.0611 -> TOL 0.15(約2.5倍)
TOL_OVERALL_EVENT_RATE = 0.15


# --------------------------------------------------------------------------- #
# フィクスチャ(module スコープで使い回し、生成を1回に抑える)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def raw_data() -> dict:
    return generate_data._generate(RAW_PROFILE)


@pytest.fixture(scope="module")
def syn_data() -> dict:
    return generate_data._generate(SYN_PROFILE)


# --------------------------------------------------------------------------- #
# 指標抽出ヘルパ(分析結果 dict -> スカラ)
# --------------------------------------------------------------------------- #
def _slope(data: dict) -> float:
    return float(ANALYSES["association"](data)["regression"]["slope"])


def _r2(data: dict) -> float:
    return float(ANALYSES["association"](data)["regression"]["r2"])


def _progressor_ratio(data: dict) -> float:
    res = ANALYSES["clustering"](data)
    return res["cluster_sizes"]["progressor"] / res["n_patients"]


def _overall_event_rate(data: dict) -> float:
    summary = ANALYSES["survival"](data)["summary"]
    n_events = sum(s["n_events"] for s in summary)
    n = sum(s["n"] for s in summary)
    return n_events / n


# --------------------------------------------------------------------------- #
# association: 回帰の傾き / 決定係数
# --------------------------------------------------------------------------- #
def test_regression_slope_close_but_not_identical(raw_data: dict, syn_data: dict) -> None:
    """用量-低下率回帰の傾きが近い(が完全一致しない)こと。"""
    raw_slope = _slope(raw_data)  # 観測: 0.3719
    syn_slope = _slope(syn_data)  # 観測: 0.4482

    # 非同一(浮動小数なので厳密不一致でよい)
    assert raw_slope != syn_slope
    # 近い
    assert abs(raw_slope - syn_slope) <= TOL_SLOPE
    # 方向性: 観測上どちらも正の傾き(= 用量が多いほど低下率が大きい同じ向きのシグナル)。
    assert raw_slope > 0
    assert syn_slope > 0


def test_regression_r2_close_but_not_identical(raw_data: dict, syn_data: dict) -> None:
    """回帰の決定係数 r2 が近い(が完全一致しない)こと。"""
    raw_r2 = _r2(raw_data)  # 観測: 0.214
    syn_r2 = _r2(syn_data)  # 観測: 0.354

    assert raw_r2 != syn_r2
    assert abs(raw_r2 - syn_r2) <= TOL_R2
    # r2 は [0,1] の範囲で、両者とも弱〜中程度の説明力を持つ(観測上 0.2〜0.4 帯)。
    assert 0.0 <= raw_r2 <= 1.0
    assert 0.0 <= syn_r2 <= 1.0


# --------------------------------------------------------------------------- #
# clustering: progressor 群の人数比
# --------------------------------------------------------------------------- #
def test_progressor_ratio_close_but_not_identical(raw_data: dict, syn_data: dict) -> None:
    """progressor ラベルの人数比が近い(が完全一致しない)こと。"""
    raw_ratio = _progressor_ratio(raw_data)  # 観測: 41/180 = 0.2278
    syn_ratio = _progressor_ratio(syn_data)  # 観測: 34/180 = 0.1889

    assert raw_ratio != syn_ratio
    assert abs(raw_ratio - syn_ratio) <= TOL_PROGRESSOR_RATIO
    # 比なので [0,1]。観測上はいずれも 0.15〜0.25 帯。
    assert 0.0 < raw_ratio < 1.0
    assert 0.0 < syn_ratio < 1.0


# --------------------------------------------------------------------------- #
# survival: 全体イベント率
# --------------------------------------------------------------------------- #
def test_overall_event_rate_close_but_not_identical(raw_data: dict, syn_data: dict) -> None:
    """全体の進行イベント率(= sum(n_events)/sum(n))が近い(が完全一致しない)こと。"""
    raw_rate = _overall_event_rate(raw_data)  # 観測: 132/180 = 0.7333
    syn_rate = _overall_event_rate(syn_data)  # 観測: 121/180 = 0.6722

    assert raw_rate != syn_rate
    assert abs(raw_rate - syn_rate) <= TOL_OVERALL_EVENT_RATE
    # 率なので [0,1]。観測上はいずれも 0.6〜0.8 帯の比較的高いイベント率。
    assert 0.0 < raw_rate < 1.0
    assert 0.0 < syn_rate < 1.0


# --------------------------------------------------------------------------- #
# まとめ: 全指標が「近いが完全一致しない」核メッセージを1テストで束ねる
# --------------------------------------------------------------------------- #
def test_metrics_overview_close_but_not_identical(raw_data: dict, syn_data: dict) -> None:
    """4 指標すべてが (非同一) かつ (TOL 内) であることをまとめて確認する。"""
    metrics = {
        "slope": (_slope(raw_data), _slope(syn_data), TOL_SLOPE),
        "r2": (_r2(raw_data), _r2(syn_data), TOL_R2),
        "progressor_ratio": (
            _progressor_ratio(raw_data),
            _progressor_ratio(syn_data),
            TOL_PROGRESSOR_RATIO,
        ),
        "overall_event_rate": (
            _overall_event_rate(raw_data),
            _overall_event_rate(syn_data),
            TOL_OVERALL_EVENT_RATE,
        ),
    }
    for name, (raw_v, syn_v, tol) in metrics.items():
        assert raw_v != syn_v, f"{name}: raw と synthetic が完全一致してしまっている"
        assert abs(raw_v - syn_v) <= tol, (
            f"{name}: |{raw_v} - {syn_v}| = {abs(raw_v - syn_v):.4f} > TOL={tol}"
        )
