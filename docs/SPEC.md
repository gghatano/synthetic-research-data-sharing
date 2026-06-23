# 仕様書: synthetic-research-data-sharing

## 1. 背景・目的

医療・研究の現場では、患者データのように機微で再配布できないデータを外部の分析者と
共有したい場面がある。生データをそのまま渡すことはプライバシー・規制の観点で困難な
ため、本デモは **code-to-data / TRE（Trusted Research Environment）型** のワークフローを
提示する。

- 生データは TRE 内に隔離し、外部に出さない
- 分析者にはデータではなく **合成データ** を渡し、分析コードを開発してもらう
- 開発されたコードを **オーナーが生データに適用** して本物のレポートを得る

**核となるメッセージ**: 同一の分析コードが合成データ・生データの両方で動作し、結果は
**統計的に近いが完全には一致しない**。このギャップが「合成データで安全に開発し、最後に
生データへ適用する」というワークフローの価値を示す。

## 2. 用語

| 用語 | 説明 |
|------|------|
| TRE | Trusted Research Environment。生データを隔離し、計算だけを内部で行う環境 |
| code-to-data | データを動かさず、分析コードをデータ側へ持ち込んで実行する方式 |
| 合成データ | 生データの統計的性質を模して生成した架空データ。個票は実在しない |
| nadir | 治療後に PSA が到達する最低値 |
| Phoenix 基準 | 生化学的再発の定義。PSA ≥ nadir + 2.0 ng/mL を進行イベントとする |

## 3. データモデル

3 テーブル（JSON、`site/data/{raw,synthetic}.json`）。

### patients
| 列 | 型 | 説明 |
|----|----|------|
| `patient_id` | str | 患者ID（例: `RAW-0001` / `SYN-0001`） |
| `age` | int | 年齢 |
| `risk_group` | enum | `low` / `intermediate` / `high` |
| `enrollment_date` | date | 登録日 |

### psa_measurements
| 列 | 型 | 説明 |
|----|----|------|
| `patient_id` | str | 患者ID |
| `date` | date | 測定日（約3ヶ月毎、最大13回 ≒ 36ヶ月） |
| `psa` | float | PSA 値 (ng/mL) |

### medications
| 列 | 型 | 説明 |
|----|----|------|
| `patient_id` | str | 患者ID |
| `datetime` | datetime | 投薬日時（ADT 開始） |
| `drug` | enum | `leuprolide` / `goserelin` / `bicalutamide` |
| `dose_mg` | float | 用量 (mg) |

### 生成の素性（`generator/generate_data.py`）

- ADT（アンドロゲン除去療法）開始後、PSA は指数的に nadir まで低下する
- 用量が多いほど nadir が深くなる（= 投薬–反応の関連分析のシグナル源）
- リスク群に応じた確率で nadir 後に PSA が再上昇 → 進行イベント
- リスク群が高いほど baseline PSA が高く、進行確率・再上昇速度が大きい

### 生データ vs 合成データ

合成データは **別シード + 分布シフト**（baseline をやや上げ、進行確率・再上昇速度を
やや上げる）で生成する。両者は統計的に類似するが、個々の値・クラスタ境界・KM 曲線は
完全には一致しない。これにより核メッセージが成立する。

> 本デモのデータは **すべて架空**であり、実在の患者に由来しない。

## 4. ワークフロー（3 ロール状態機械）

`site/index.html` の Alpine.js が状態を管理する。

```
        publish()            submit()            approve()
 idle ───────────► published ───────► submitted ─────────► approved
  │                   │                   │                   │
オーナーが        分析者が合成      分析者が提出       オーナーが承認し
合成データを      データで分析を     （合成結果＋コード）  同一コードを生データへ
公開             開発・実行                            適用 → 比較表示
```

| フェーズ | ロール | UI / htmx 動作 |
|----------|--------|----------------|
| idle → published | ① オーナー：公開 | 生データは🔒非公開のまま、合成データを公開 |
| published → submitted | ② 分析者：ワークベンチ | 分析選択で `hx-get fragments/analyst/<a>.html`（合成結果）を読込 → 提出 |
| submitted → approved | ③ オーナー：審査 | 承認で `hx-get fragments/owner/<a>.html`（生結果）を読込、合成 vs 生を並置 |

htmx のフラグメント取得は本物の htmx 挙動（静的 `.html` を GET）。本番ではこの GET 先が
FastAPI のエンドポイントに置き換わるだけで、フロント側のマークアップは変わらない。

## 5. 3 つの分析（`generator/analyses.py`）

各分析は「データセット dict → 結果 dict」の **純関数** として実装し、raw・synthetic の
双方に同一コードを適用する。

### 5.1 PSA軌跡クラスタリング `clustering`
- 患者ごとに特徴量を抽出: `baseline`, `nadir`, `time_to_nadir`, `late_slope`（nadir後の傾き）, `variability`
- 標準化後 `sklearn.cluster.KMeans(k=3)` で分類
- `late_slope` の平均で responder / partial / progressor を解釈付け
- 出力: クラスタ別人数・標準化重心・クラスタ別平均 PSA 軌跡

### 5.2 投薬–PSA反応の関連分析 `association`
- 患者ごとの PSA 低下率 `100*(baseline-nadir)/baseline` を算出
- 薬剤別サマリ（平均低下率・SD・平均用量）
- 用量 vs 低下率 を `numpy.polyfit` で単回帰（傾き・切片・R²）
- 出力: 薬剤別テーブル・回帰直線・散布図サンプル点

### 5.3 進行イベントの生存時間分析 `survival`
- Phoenix 基準（PSA ≥ 累積nadir + 2.0）で各患者の進行時刻 or 打ち切りを判定
- リスク群別に Kaplan-Meier 推定（手実装の階段曲線）
- 出力: リスク群別 KM 曲線・イベント率・進行までの中央値

## 6. モック実装（htmx + Alpine + Python生成、GitHub Pages）

- フロント: 素の HTML + htmx + Alpine.js + Chart.js（すべて CDN、ビルド工程なし）
- 分析・データ: Python（pandas / numpy / scikit-learn）で生・合成データを生成し、3分析を
  両データに事前計算。結果を Chart.js 設定 JSON ＋ Jinja2 でレンダリングした HTML
  フラグメントとして出力
- 状態遷移: Alpine.js で `idle→published→submitted→approved` を管理。htmx は
  `fragments/{analyst,owner}/<analysis>.html` を `hx-get` で読み込む

## 7. 本番想定アーキテクチャ（FastAPI + htmx）との対応

| 関心事 | モック（本リポジトリ） | 本番プロトタイプ |
|--------|------------------------|------------------|
| フロント | htmx + Alpine + Chart.js（CDN） | 同一 |
| フラグメント | 事前生成した静的 `.html` | FastAPI が Jinja2 で同形 HTML を返す（`generator/templates/` を流用） |
| 分析実行 | ビルド時に事前計算 | リクエスト時にサーバーで実行（`generator/analyses.py` を流用） |
| 認可・隔離 | 生データを「非公開」表示で擬似 | TRE 内に隔離、分析者は生データへアクセス不可 |
| ワークフロー | Alpine のクライアント状態 | サーバー側ジョブ状態 + DB |

移植時に置き換わるのは **「事前生成 → サーバー応答」** の供給経路のみ。htmx マークアップ
（`generator/templates/fragment.html.j2`）と分析コード（`generator/analyses.py`）はそのまま
再利用できる。

## 8. 合成データ生成方針（mockdata-generator の思想）

`gghatano/mockdata-generator` の仕様駆動アプローチ（source → generator → synthetic +
evaluation）を参照しつつ、本デモでは簡易ジェネレータで代替する。

- **source**: 臨床的素性（指数減衰・用量依存 nadir・リスク依存の進行）をパラメータ化
- **generator**: シード固定で再現可能に生成（`generate_data.py`）
- **synthetic**: 別シード + 分布シフトで生成し、生データと近いが非同一にする
- **evaluation**: 3分析を両データに適用し、結果が「近いが一致しない」ことを UI 上で比較

## 9. 検証方法

```bash
uv sync        # 依存を取得（pyproject.toml / .python-version）
make build     # site/data/*.json と site/fragments/**/*.html を生成
make serve     # http://localhost:8000/
```

- ① オーナー公開 → 合成データ公開・生データ非公開（locked）を確認
- ② 分析者 → 3分析それぞれを htmx で読み込み、Chart.js でチャート描画
- ③ オーナー審査 → 承認で生データ結果を読み込み、合成 vs 生 の差を並置確認
- `uv run python -m generator.generate_data` を再実行してデータが再現生成できる（シード固定）
