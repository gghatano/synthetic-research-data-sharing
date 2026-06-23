# synthetic-research-data-sharing

機微な研究データ（前立腺がん患者の PSA 時系列＋投薬記録）を **生データを外部に出さずに**
分析してもらうための **code-to-data / TRE（Trusted Research Environment）型** ワークフローの
デモです。

## 核となるアイデア

1. **オーナー**が生データから **合成データ** を作って公開する
2. **分析者**が合成データに対して分析コードを開発・実行し、レポートを提出する
3. **オーナー**が提出物を確認し、良ければ **同じコードを生データに適用** して本物のレポートを作る

> 同一の分析コードが合成データ・生データの両方で動き、**結果は近いが完全には一致しない**。
> だからこそ「合成データで安全に開発 → 最後に生データへ適用」というステップに価値がある。

## デモを動かす

```bash
uv sync         # 依存を取得（pyproject.toml / .python-version に基づく）
make build      # データ生成 + 3分析を適用して HTML フラグメントを生成
make serve      # http://localhost:8000/ で確認
```

> 依存・実行・検証は [uv](https://docs.astral.sh/uv/) 経由（`make` は内部で `uv run python` を使用）。
> `make` が無ければ `uv run python -m generator.generate_data && uv run python -m generator.render`。

`make serve` を開いたら、上部タブで 3 ロールを順に体験できます。

1. **① オーナー：公開** … 生データは「🔒 非公開」のまま、合成データを公開
2. **② 分析者：ワークベンチ** … 分析を選ぶと合成データの結果が htmx で読み込まれる → 提出
3. **③ オーナー：審査** … 承認すると同一コードを生データに適用し、合成 vs 生 を並べて比較

## 技術構成

| 層 | このデモ（モック / GitHub Pages） | 本番プロトタイプ想定 |
|----|-----------------------------------|----------------------|
| フロント | 素の HTML + **htmx** + **Alpine.js** + **Chart.js**（CDN, ビルドなし） | 同じ（htmx + Alpine + Chart.js） |
| フラグメント供給 | 事前生成した静的 `.html` を htmx が `hx-get` | **FastAPI** エンドポイントが Jinja2 で同形の HTML を返す |
| 分析実行 | Python で **事前計算**（pandas / scikit-learn） | サーバー側で **オンデマンド実行**（同じ分析コード） |
| ワークフロー状態 | Alpine.js（`published→submitted→approved`） | サーバー側のジョブ状態 + htmx |
| 生データ保護 | 生データJSONは「非公開」表示で擬似 | TRE 内に隔離、分析者からアクセス不可 |

htmx 用マークアップ（`generator/templates/`）と Python 分析コード（`generator/analyses.py`）は
**そのまま本番 FastAPI + htmx に移植可能** な形にしています。モックで「擬似」なのは
サーバー実行の部分のみ（事前生成フラグメント＋Alpine の状態管理で代替）。

## ディレクトリ構成

```
├── docs/SPEC.md            # 仕様書（データモデル・フロー・分析定義・本番対応表）
├── pyproject.toml          # 依存（[project] / dev グループ）+ ruff/mypy/pytest 設定
├── .python-version         # uv が使う Python（3.12）
├── Makefile                # make build / make serve / make clean（内部で uv run python）
├── generator/
│   ├── generate_data.py    # 生・合成データ生成（シード固定で再現可能）
│   ├── analyses.py         # 3分析（生/合成共通の純関数）
│   ├── render.py           # Jinja2 で HTML フラグメントを事前生成
│   └── templates/          # 本番htmxへ移植可能な Jinja2 テンプレート
├── site/                   # ★ GitHub Pages 公開ルート
│   ├── index.html          # htmx + Alpine.js シェル（3ロールUI）
│   ├── assets/app.css
│   ├── data/{raw,synthetic}.json        # 生成物
│   └── fragments/{analyst,owner}/*.html # 生成物
└── .github/workflows/deploy.yml         # build → Pages デプロイ
```

`site/data/` と `site/fragments/` は `make build` で再生成できる生成物です（プレビュー
容易化のためリポジトリにもコミットしています）。

## 3 つの分析

1. **PSA軌跡クラスタリング** … 患者ごとの軌跡特徴量を抽出し `KMeans(k=3)` で
   responder / partial / progressor に分類
2. **投薬–PSA反応の関連分析** … 用量と PSA 低下率の単回帰
3. **進行イベントの生存時間分析** … Phoenix 基準（PSA ≥ nadir+2.0）で進行を定義し
   リスク群別に Kaplan-Meier 推定

詳細は [docs/SPEC.md](docs/SPEC.md) を参照してください。

## デプロイ

開発は `develop`（統合・既定ブランチ）で行い、**リリース時に `develop` → `main` へマージ**します。
`main` への push で GitHub Actions（`.github/workflows/deploy.yml`）が `make build` を実行し、
`site/` を GitHub Pages に公開します。リポジトリの **Settings → Pages → Source** を
**GitHub Actions** に設定してください。

> 注: ここで扱うデータはすべて合成（架空）であり、実在の患者データではありません。
