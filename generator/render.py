"""分析結果を HTML フラグメントへ事前レンダリングする。

生データ・合成データそれぞれに 3 分析を適用し、Jinja2 で HTML フラグメントを
生成して site/fragments/ 配下に書き出す。フラグメントは htmx が hx-get で
読み込むことを想定したマークアップ(本番 FastAPI のエンドポイント応答と同形)。

  site/fragments/analyst/<analysis>.html  <- 合成データ(synthetic)の結果
  site/fragments/owner/<analysis>.html     <- 生データ(raw)の結果

Chart.js の設定は Python 側で組み立てて JSON として埋め込み、フラグメント内の
小さな初期化スクリプトが描画する(テンプレートを薄く保つ)。
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from generator import analyses

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "site" / "data"
FRAG_DIR = ROOT / "site" / "fragments"
TEMPLATES = Path(__file__).resolve().parent / "templates"

PALETTE = {
    "responder": "#2e7d32",
    "partial": "#f9a825",
    "progressor": "#c62828",
    "low": "#2e7d32",
    "intermediate": "#f9a825",
    "high": "#c62828",
    "scatter": "#1565c0",
    "line": "#c62828",
}

KIND_LABEL = {"synthetic": "合成データ", "raw": "生データ"}


# --------------------------------------------------------------------------- #
# Chart.js 設定の組み立て
# --------------------------------------------------------------------------- #
def _clustering_chart(res: dict) -> dict:
    grid = res["grid_months"]
    datasets = []
    for label, series in res["trajectories"].items():
        datasets.append(
            dict(
                label=f"{label} (n={res['cluster_sizes'].get(label, 0)})",
                data=series,
                borderColor=PALETTE[label],
                backgroundColor=PALETTE[label],
                spanGaps=True,
                tension=0.3,
                fill=False,
            )
        )
    return dict(
        type="line",
        data=dict(labels=grid, datasets=datasets),
        options=dict(
            responsive=True,
            maintainAspectRatio=False,
            plugins=dict(
                legend=dict(position="bottom"),
                title=dict(display=True, text="クラスタ別 平均PSA軌跡"),
            ),
            scales=dict(
                x=dict(title=dict(display=True, text="治療開始からの月数")),
                y=dict(title=dict(display=True, text="PSA (ng/mL)")),
            ),
        ),
    )


def _association_chart(res: dict) -> dict:
    pts = [dict(x=p["dose"], y=p["reduction"]) for p in res["points"]]
    line = [dict(x=p["dose"], y=p["reduction"]) for p in res["regression"]["line"]]
    return dict(
        type="scatter",
        data=dict(
            datasets=[
                dict(label="患者", data=pts, backgroundColor=PALETTE["scatter"], pointRadius=3),
                dict(
                    label=f"回帰直線 (R²={res['regression']['r2']})",
                    data=line,
                    type="line",
                    borderColor=PALETTE["line"],
                    borderWidth=2,
                    pointRadius=0,
                    fill=False,
                ),
            ]
        ),
        options=dict(
            responsive=True,
            maintainAspectRatio=False,
            plugins=dict(
                legend=dict(position="bottom"), title=dict(display=True, text="用量 vs PSA低下率")
            ),
            scales=dict(
                x=dict(title=dict(display=True, text="用量 (mg)")),
                y=dict(title=dict(display=True, text="PSA低下率 (%)")),
            ),
        ),
    )


def _survival_chart(res: dict) -> dict:
    datasets = []
    for risk, curve in res["curves"].items():
        datasets.append(
            dict(
                label=risk,
                data=[dict(x=p["t"], y=round(p["s"] * 100, 1)) for p in curve],
                borderColor=PALETTE[risk],
                backgroundColor=PALETTE[risk],
                stepped=True,
                pointRadius=0,
                fill=False,
            )
        )
    return dict(
        type="line",
        data=dict(datasets=datasets),
        options=dict(
            responsive=True,
            maintainAspectRatio=False,
            plugins=dict(
                legend=dict(position="bottom"),
                title=dict(display=True, text="無進行生存率 (Kaplan-Meier)"),
            ),
            scales=dict(
                x=dict(type="linear", title=dict(display=True, text="月数")),
                y=dict(min=0, max=100, title=dict(display=True, text="無進行生存率 (%)")),
            ),
        ),
    )


CHART_BUILDERS = {
    "clustering": _clustering_chart,
    "association": _association_chart,
    "survival": _survival_chart,
}

TITLES = {
    "clustering": "PSA軌跡クラスタリング",
    "association": "投薬–PSA反応の関連分析",
    "survival": "進行イベントの生存時間分析",
}

CODE_SNIPPETS = {
    "clustering": (
        "feat = per_patient_features(psa)\n"
        "X = StandardScaler().fit_transform(feat[FEATURES])\n"
        "labels = KMeans(n_clusters=3, random_state=42).fit_predict(X)"
    ),
    "association": (
        "feat['reduction_pct'] = 100*(feat.baseline-feat.nadir)/feat.baseline\n"
        "m = feat.merge(meds, on='patient_id')\n"
        "slope, intercept = np.polyfit(m.dose_mg, m.reduction_pct, 1)"
    ),
    "survival": (
        "tte = time_to_event(psa, delta=2.0)  # Phoenix 基準\n"
        "for risk, g in tte.groupby('risk_group'):\n"
        "    curve = kaplan_meier(g.time, g.observed)"
    ),
}


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_all() -> None:
    env = _build_env()
    template = env.get_template("fragment.html.j2")

    datasets = {
        "synthetic": json.loads((DATA_DIR / "synthetic.json").read_text("utf-8")),
        "raw": json.loads((DATA_DIR / "raw.json").read_text("utf-8")),
    }
    # kind -> 出力サブディレクトリ
    kind_dir = {"synthetic": FRAG_DIR / "analyst", "raw": FRAG_DIR / "owner"}

    for kind, data in datasets.items():
        outdir = kind_dir[kind]
        outdir.mkdir(parents=True, exist_ok=True)
        for name, fn in analyses.ANALYSES.items():
            result = fn(data)
            chart = CHART_BUILDERS[name](result)
            uid = f"{kind}-{name}"
            html = template.render(
                uid=uid,
                kind=kind,
                kind_label=KIND_LABEL[kind],
                analysis=name,
                title=TITLES[name],
                result=result,
                chart_config=json.dumps(chart, ensure_ascii=False),
                code=CODE_SNIPPETS[name],
            )
            (outdir / f"{name}.html").write_text(html, encoding="utf-8")
            print(f"  wrote {(outdir / f'{name}.html').relative_to(ROOT)}")


if __name__ == "__main__":
    print("Rendering fragments ...")
    render_all()
    print("done.")
