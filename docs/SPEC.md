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

各データセットは 3 テーブル（JSON）。カタログ型対応（#22）で複数データセットを扱う。

### 3.0 カタログとパス規約（複数データセット, #22）

generator は **複数データセット**を `DATASETS` レジストリ（`generator/generate_data.py`）で
定義し、以下を生成する。

- 各データセットの生/合成データ: `site/data/<dataset_id>/{raw,synthetic}.json`
- 各データセットの分析フラグメント: `site/fragments/<dataset_id>/{analyst,owner}/<analysis>.html`
  （`analyst` = 合成データ結果、`owner` = 生データ結果）
- カタログ索引: `site/data/catalog.json`（全データセットのメタデータ一覧）

**カタログ索引 `catalog.json`** の形:

```json
{ "datasets": [ { /* メタデータ */ }, ... ] }
```

各エントリの**メタデータスキーマ**（必須キー）:

| キー | 型 | 説明 |
|------|----|------|
| `dataset_id` | str | 一意なデータセット ID（パスにも使う、例 `prostate-psa`） |
| `title` | str | 表示名 |
| `description` | str | 概要 |
| `owner` | str | データオーナ（擬似アカウント） |
| `domain` | str | ドメイン（例 `oncology/urology`） |
| `tags` | list[str] | 検索/分類用タグ |
| `usage_examples` | list[str] | 想定分析の短い活用例 |
| `n_patients` | int | 合成データの患者数 |
| `legacy_paths` | bool | 旧パス互換を出力したか（後方互換, 下記） |
| `paths` | object | `raw`/`synthetic`/`fragments_analyst`/`fragments_owner` の参照パス |
| `dummy_preview` | object | カタログ表示用の少量サンプル（各テーブル先頭数行、**合成データ由来**） |

> `dummy_preview` は公開可能な**合成データ**から抽出する（生データは出さない）。

**後方互換（重要, #22 → #23/#25/#26 で解消予定）**: 既存の前立腺がん PSA
（`dataset_id = prostate-psa`）に限り、旧パス
`site/data/{raw,synthetic}.json` と `site/fragments/{analyst,owner}/<analysis>.html`
も**従来どおり生成し続ける**。PF-1（#21）のログインシェル内の既存 3 ロールデモ・E2E が
旧パスを参照しているため。旧→新パスへの移行は後続 Issue で行う。
`prostate-psa` の新旧ファイルはバイト一致する（同一データの二重出力）。

### 3.1 テーブル（3 テーブル）

`site/data/<dataset_id>/{raw,synthetic}.json`（および `prostate-psa` は旧パス
`site/data/{raw,synthetic}.json` も）。

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
| published → submitted | ② 分析者：ワークベンチ | 分析選択で `htmx.ajax GET fragments/<dataset_id>/analyst/<a>.html`（合成結果）を読込 → 提出 |
| submitted → approved | ③ オーナー：審査 | 承認で `htmx.ajax GET fragments/<dataset_id>/owner/<a>.html`（生結果）を読込、合成 vs 生を並置 |

htmx のフラグメント取得は本物の htmx 挙動（静的 `.html` を GET）。本番ではこの GET 先が
FastAPI のエンドポイントに置き換わるだけで、フロント側のマークアップは変わらない。

このワークフローは**カタログのデータ個別ページ配下に内包**される（#23）。フラグメントの
パス基底は選択中データセット（`fragBase = currentDatasetId`）に追従する。分析者は実行結果に
**レポート（所見・メモ）**を添えて提出でき、提出物はデータ個別ページの「紐づく提出物」へ
紐づく（カタログ連携の提出フロー。詳細は **§7.8**）。

### 最終形（カタログ連携の審査, #26）

上記 3 ロール状態機械はワークベンチ単体の体験デモとして温存しつつ、カタログ型では
**審査を「紐づく提出物」一覧から行う**形に一般化した（最終形）。owner は個別ページの
提出物カードから提出物を選んで審査し、承認で同一分析の生データ結果（`owner/<a>.html`）を
並置する。提出物の `status` は **`submitted → approved`** に遷移し、共有ストア
`Alpine.store('submissions')`（in-memory）上で更新されて一覧へ即時反映される。
詳細は **§7.9**。owner と非 owner で審査導線の出し分け（擬似ガード）を行う。

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

## 7.5 擬似認証・画面シェル・ロール（owner / analyst）

カタログ型プラットフォームへの移行に向けた **最初の画面シェル**。ログインを起点に、
ロールに応じた導線を出し分ける。バックエンドを持たないため認証・状態保持はすべて
**擬似（クライアント側 in-memory）** で行う。

### ロール

| ロール | 識別子 | 想定操作 |
|--------|--------|----------|
| データオーナー | `owner` | 合成データの登録（データ登録）／データ探索 |
| 分析者 | `analyst` | データ探索（合成データで分析を開発・提出） |

### 擬似認証と状態保持

- ログイン画面でユーザー名（自由入力 or プリセット選択）＋ロール（owner / analyst）を選ぶ。
  **パスワード・実認証はしない。**
- ログイン状態は **Alpine の共有ストア `Alpine.store('session')`（in-memory）** に保持する。
  - 単一ページのビュー切替（SPA 的: `login → top → register / explore`）で、ビュー遷移を
    またいでログイン状態・選択ロールを保持する。
  - **`localStorage` は使わない。** ハードリロードで状態はリセットされる（既存 3 ロール
    デモと同じ思想）。これはデモ用途として許容する割り切り。
- ログアウトでストアを破棄し、ログイン画面へ戻る。

### 画面シェルと擬似ガード

- ログイン後トップ（`top`）から **「データ登録」「データ探索」** へ遷移する。
  - **データ登録**は `owner` のみ可視（owner 専用ビュー）。中身は後続タスク（PF-4）で実装。
  - **データ探索**は全ロール可視。当面は既存の 3 ロールデモ（公開/分析/審査）を内包し、
    後続タスクでカタログ型 UI（PF-3）へ段階移設する。
- **擬似ガード**: 未ログインで保護ビュー（top / register / explore）へ遷移しようとしても
  ログイン画面に留める。`analyst` が owner 専用ビュー（register）へ来たらトップへ戻す。

### 本番との対応（重要）

ここでのログイン・ロールガードは **あくまで UI 上の擬似**であり、セキュリティ境界ではない。
本番では **TRE/サーバー側のセッションと認可で隔離**し、生データやエンドポイントへのアクセス
可否はサーバーが判定する。クライアント側のロール出し分けは UX のためのものに過ぎない。

| 関心事 | モック（本リポジトリ） | 本番プロトタイプ |
|--------|------------------------|------------------|
| 認証 | ユーザー名＋ロール選択の擬似ログイン | IdP / サーバーセッション |
| 状態保持 | Alpine 共有ストア（in-memory） | サーバーセッション + DB |
| 認可・ロールガード | クライアント側の出し分け（UX 用） | サーバー側で強制（TRE 隔離） |

## 7.6 データカタログ閲覧（一覧・個別ページ, #23）

カタログ型プラットフォームの**閲覧（読み取り）機能**。誰でも研究用データの
**メタデータ・ダミーデータ・活用例**を確認できる。供給源は PF-2（#22）が事前生成する
`site/data/catalog.json`。ビューは `site/index.html` の Alpine ストア
`Alpine.store('session').view` に追加した `explore`（一覧）/`dataset`（個別）で切り替える。

### 公開閲覧（ログイン不要）

- カタログ一覧（`explore`）・個別ページ（`dataset`）は**誰でも閲覧可**。擬似ガード
  （`isPublicView`）の対象外とし、未ログインでもアプリバーの「ログイン」やログイン画面の
  「ログインせずカタログを見る」から到達できる。
- 保護ビュー（`top` / `register`）は従来どおり擬似ガードの対象（未ログインはログインへ、
  `analyst` の `register` 到達はトップへ戻す）。

### カタログ一覧（`explore`）

- `data/catalog.json` を `fetch` し、`datasets[]` を**カード**で描画
  （title / owner / domain / n_patients / description / tags）。
- 簡易検索（最小実装）: タイトル・概要・オーナー・ドメイン・タグの部分一致で絞り込む。
  件数表示（`<絞込数> / <総数> 件`）を添える。一致 0 件は空状態を表示。
- 各カードの「詳細を見る」で個別ページへ（`openDataset(dataset_id)`）。

### データ個別ページ（`dataset`）

選択中の `currentDatasetId` に対応する `catalog.json` のエントリを描画する。

- **メタデータ**: title / owner / domain / n_patients / description / tags。
- **活用例**: `usage_examples` を箇条書き表示。
- **ダミーデータプレビュー**: `dummy_preview` の各テーブル（patients / psa_measurements /
  medications）を列順固定のテーブルで表示。これは**合成データ由来**であり生データは含まない。
- **合成データ分析の導線**: 「分析ワークベンチを開く」で、既存 3 ロールデモ（§4 の
  `idle→published→submitted→approved`）を**個別ページ配下に内包**して開く。フラグメントの
  パス基底は選択中データセット（`dataset_id`）に追従する
  （`fragments/<dataset_id>/{analyst,owner}/<analysis>.html` を `htmx.ajax` で取得）。
  既存デモのマークアップ・`data-analysis` 属性・canvas id は不変（E2E 互換）。
- **紐づく提出物の枠**: 下記の共有ストアから `dataset_id` で引いた提出物を一覧表示する。
  #23 時点では常に空（空状態プレースホルダのみ）。

### 提出物の共有ストア（枠のみ。#25/#26 への引き継ぎ）

提出物は **Alpine 共有ストア `Alpine.store('submissions')`（in-memory）** で保持する。
**キー設計は `dataset_id` 起点**（`catalog.json` / パス規約と一致）。

```
Alpine.store('submissions') = {
  byDataset: { [dataset_id]: Submission[] },  // dataset_id を起点キーにする
  forDataset(dataset_id) -> Submission[],      // 読み取り(個別ページが使用)
  add(dataset_id, submission)                  // #25 が書き込む想定の足場
}
```

- 個別ページの「紐づく提出物」は `forDataset(dataset_id)` を読むだけ。
- 提出（#25）・審査（#26）は `add()` 経由で `byDataset[dataset_id]` に積む。`Submission`
  スキーマは **§7.8 で確定**（`{ id, datasetId, analysis, analysisTitle, analyst, report,
  codeExcerpt, status, submittedAt }`）。
- `localStorage` 不使用（ハードリロードでリセット = 既存デモと同じ思想）。

### 本番との対応

| 関心事 | モック（本リポジトリ） | 本番プロトタイプ |
|--------|------------------------|------------------|
| カタログ供給 | 事前生成 `catalog.json` を `fetch` | カタログ API（DB 検索） |
| ダミーデータ | `dummy_preview`（合成データ抽出） | 合成データのサンプル応答 |
| 分析フラグメント | `htmx.ajax` で静的 `.html` | FastAPI が同形 HTML を返す |
| 提出物 | Alpine 共有ストア（in-memory） | サーバー側ジョブ状態 + DB |

## 7.7 データ登録（擬似, #24）

カタログ型プラットフォームの**登録（書き込み）機能**（機能1）。データオーナーが研究用データの
**メタデータ＋合成/ダミーデータ**をカタログに新規登録できる。ビューは `register`（owner 専用）。

### 確定仮定（静的モックでの登録の表現）

- **ブラウザ上で合成データ生成は行わない**（Python を動かせないため）。登録は
  **メタデータ＋（事前同梱サンプルから選択 or JSON アップロードした）ダミーデータプレビュー**を
  共有ストアに追加する**擬似**とする。
- 本番では **TRE（Trusted Research Environment）内で生データから合成データを生成・検証**し、
  その結果（メタデータ＋ダミー／合成）をカタログ API に登録する。モックはこの UX のみを再現する。
- 登録分は **in-memory（`Alpine.store('catalog')`）**。`localStorage` 不使用でハードリロードで消える
  （既存デモと同じ思想）。**扱うデータはすべて架空**（フォームにも明記）。

### owner 専用ガード

- ナビ「データ登録」とトップの登録カードは `owner` のみ表示（#21 の出し分け）。
- `register` ビュー自体も擬似ガード（`go('register')` は `owner` 以外をトップ/ログインへ戻す）。

### 入力項目

- **メタデータ**: title（必須）/ description（必須）/ domain（必須）/ n_patients / tags（カンマ区切り）/
  usage_examples（活用例、1 行 1 件）。
- **ダミーデータの指定**（必須・いずれか）:
  1. **事前同梱サンプル**から選択（ブラウザ内蔵の固定ダミー。生成ではない）。
  2. **JSON アップロード**（`FileReader`）。`{ patients, psa_measurements, medications }` の
     いずれかのテーブルを含む JSON。**最低限のスキーマ検証**で許可テーブルのみ抽出し、各テーブル
     先頭数行（オブジェクト行のみ）を `dummy_preview` に整形する。**壊れた JSON でも UI を破綻させない**
     （構文エラー・想定外形は状態メッセージで通知し登録を止める）。

### カタログ共有ストア（基底 + ユーザー登録分のマージ）

カタログの単一ソースを **`Alpine.store('catalog')`** に集約する。一覧（`explore`）・個別ページ
（`dataset`）はこのストアの **`all()`** を唯一の表示元として読む（#23 の直接 `fetch` から切替）。

```
Alpine.store('catalog') = {
  base: Dataset[],                 // 事前生成 catalog.json 由来(読み取り専用の基底)
  user: Dataset[],                 // owner が登録した擬似分(in-memory)
  ensureLoaded(): Promise          // base を一度だけ fetch(複数ビューから二重 fetch しない)
  all() -> [...user, ...base]      // 一覧/個別が読む唯一のソース(登録分を先頭に)
  find(dataset_id) -> Dataset|null
  isUserDataset(dataset_id) -> bool
  register(dataset) -> dataset_id  // "user-<n>" を採番して登録、即時に一覧へ反映
  remove(dataset_id) / reset()     // 登録分の削除・全リセット(base は不変)
}
```

- ユーザー登録分の `dataset_id` は **`user-<n>`** でユニーク採番（base の id と衝突しない）。
- 登録は **即時にカタログ一覧・個別ページへ反映**される（`all()` を共有しているため）。
- 登録済み一覧（`register` ビュー）に**削除/リセット導線**を備える。

### ユーザー登録分の個別ページ

- 個別ページはユーザー登録データセットでも開ける（メタデータ・活用例・ダミープレビューを表示）。
- ただし**分析ワークベンチ（フラグメント）はユーザー登録分には存在しない**。この場合は
  「登録メタデータ＋ダミーデータのみ（分析フラグメント未生成）」の旨を表示し、ワークベンチを出さない。
  既存同梱データセット（`prostate-psa` / `renal-marker`）の分析は従来どおり動く。

### 本番との対応

| 関心事 | モック（本リポジトリ） | 本番プロトタイプ |
|--------|------------------------|------------------|
| 合成データ生成 | 行わない（同梱サンプル/アップロードで代替） | TRE 内で生成・評価 |
| 登録の永続化 | Alpine 共有ストア（in-memory） | カタログ API + DB |
| 認可 | クライアント側の owner 出し分け（UX 用） | サーバー側で強制 |

## 7.8 合成データでの分析・提出（カタログ連携, #25）

カタログ型プラットフォームの**活用（提出）機能**（機能3）。非オーナ（analyst）が公開された
**合成データを触って分析プログラム＋レポートを提出**し、その提出物をデータ個別ページへ紐づける。
既存の単一データセット向け「分析ワークベンチ」を**カタログ個別ページから使える形に一般化**した。

### 分析の実行（合成データ・データセット単位）

- 個別ページの「合成データで分析する」から**分析ワークベンチ**を開き、3 分析
  （`clustering` / `association` / `survival`）をチップで選んで実行・閲覧する。
- フラグメントは**データセット単位**で読む: `fragments/<dataset_id>/analyst/<analysis>.html`
  （`fragBase = currentDatasetId`）。`htmx.ajax` の GET 先がデータセットに追従するだけで、
  本番では `/datasets/<id>/analyses/<a>` 相当の動的 URL に置き換わる同形。
- Chart.js の二重描画防止（`Chart.getChart(el).destroy()`）はフラグメント内に保持され、
  データセット切替・再選択でも保たれる。

### 提出（プログラム＋レポート）

- 分析を実行して結果が読み込まれた状態で、**レポート（所見・メモのテキスト）**を入力して提出する。
- **プログラム本体は「選んだ分析 ＋ 適用コード抜粋」**として記録する（自由記述コードの実行はしない）。
  コード抜粋は読み込み済みフラグメントの `details.frag-code` の `<code>` から抽出する。
- **提出は要ログイン（analyst 想定）**。未ログイン時は提出ボタンを無効化しログイン導線を出す
  （**仮定**: 閲覧は誰でも可・提出のみ要ログインという素直なガード。ロールは owner/analyst
  どちらでも提出できるが、ワークフロー上の主体は analyst）。
- 提出物は `Alpine.store('submissions').add(dataset_id, {...})` で保存し、個別ページの
  **「紐づく提出物」**に即時追加する（1 データセットに複数提出が並ぶ。提出者・対象分析・日時・
  レポート・status='submitted'・コード抜粋を表示）。

### 確定 Submission スキーマ（#26 の審査が読む前提）

```
Submission = {
  id:            string,  // "sub-<seq>"（store が採番）
  datasetId:     string,  // 対象データセット（= catalog.json の dataset_id）
  analysis:      string,  // "clustering" | "association" | "survival"
  analysisTitle: string,  // 分析の表示名
  analyst:       string,  // 提出者（ログイン中ユーザー名）
  report:        string,  // レポート（所見・メモ）
  codeExcerpt:   string,  // 適用コード抜粋（フラグメント由来）
  status:        string,  // "submitted"（初期値。審査での遷移は #26）
  submittedAt:   string,  // ISO8601
}
```

`store.add()` は `id` / `status` / `submittedAt` を未指定なら補完し、保存済みオブジェクトを返す。
**`status` は #26（審査）が後から書き換える**前提で、ここでは常に `"submitted"` を初期値とする。

### ユーザー登録データセットの扱い（仮定）

- **仮定**: 分析フラグメントを持つ**同梱データセット（`prostate-psa` / `renal-marker`）のみ**提出可。
  ユーザー登録分（`user-<n>`）は分析フラグメント未生成のためワークベンチ・提出 UI を出さない
  （§7.7 の「分析未提供」注記のまま）。本番では TRE が登録時に合成データ・フラグメントを用意する。

### 本番との対応

| 関心事 | モック（本リポジトリ） | 本番プロトタイプ |
|--------|------------------------|------------------|
| 分析実行 | `htmx.ajax` で静的 `.html`（事前計算） | FastAPI が scikit-learn でジョブ実行し HTML 返却 |
| プログラム | 既存 3 分析から選択 ＋ コード抜粋を記録 | サンドボックス内でのコード実行（隔離） |
| 提出物保存 | Alpine 共有ストア（in-memory） | サーバー側ジョブ状態 + DB |
| 認可 | 提出のみ要ログイン（UX 用ガード） | サーバー側で強制（ロール・データセット権限） |

## 7.9 オーナーによる審査・生データ差し替え・レポート確認（カタログ連携, #26）

カタログ型プラットフォームの**審査機能**（機能4）。owner が提出物（#25）を審査し、
**手元の合成データを生データに差し替えて実験**してレポートを確認する。既存の単一データセット
向け「審査タブ（合成 vs 生の並置）」を、カタログ＋提出物に紐づく形へ一般化した。

### 審査の起点（提出物一覧から選ぶ）

- 個別ページの「紐づく提出物」一覧で、各提出物カードに **owner 限定の審査導線**を出す。
  非 owner（analyst）には審査導線を出さず、ガード注記を表示する（**擬似ガード**）。
- 審査導線を押すと**審査ビュー**が開き、提出物の**合成データの結果（`analyst/<a>.html`）**と
  **提出レポート（所見・メモ）**を表示する（`htmx.ajax` GET、左カラム）。

### 承認 → 生データ差し替え（合成 vs 生の並置）

- 「承認して生データに適用」で、**同一分析を生データに適用した結果**
  （`fragments/<dataset_id>/owner/<a>.html` = 事前計算した生データ結果）を右カラムに読み込み、
  **合成 vs 生を並置**する。生データは「非公開（TRE 隔離）」のまま、事前生成 raw フラグメントの
  読込に限定する（自由記述コードの実行・任意の生データアクセスはしない）。
- 並置後、**「合成 → 生」が近いが非同一**である核メッセージ（callout）を表示する（既存の
  審査タブの核メッセージを一般化して流用）。Chart の二重描画はフラグメント側の
  `Chart.getChart(el).destroy()` で防ぐ。審査ビューは**ワークベンチの審査タブとは別 id**
  （`#sub-review-synthetic` / `#sub-review-raw`）を使い、両者を共存させても衝突しない。

### 状態遷移（status: submitted → approved）

- 承認で提出物の `status` を **`submitted → approved`** に遷移させる。更新は共有ストア
  `Alpine.store('submissions').approve(dataset_id, submission_id, reviewer)` 経由で、
  対象提出物の実体を直接書き換える（`reviewedBy` / `reviewedAt` も記録）。
- in-memory なので個別ページの提出物一覧の `submission-status` 表示が **approved に即時反映**
  される（カードに `data-status="approved"` も付く）。承認済み提出物を再度開くと合成・生の
  並置が復元される。

### owner 限定ガード（仮定）

- 審査は **owner ロールのみ**可能（`canReview() = role === 'owner'`）。
- **仮定**: catalog の `owner` 名と突き合わせる厳密な所有権一致は擬似のため簡略化し、
  「owner ロールなら（このデータセットの提出物を）審査できる」とした。本番では TRE/サーバーが
  データセット所有権でサーバー側認可を強制する（UI ガードは UX 用）。

### 旧 3 ロールデモとの関係（整理）

- 旧 3 ロールデモ（ワークベンチ内の「③ オーナー：審査」タブ）は**体験デモとして温存**し、
  カタログ連携の審査（本節）を**提出物一覧側に追加**した。両者は別 id・別領域で共存する
  （旧デモの E2E `test_review` / `test_flow` を壊さないため）。最終形のユーザー導線は
  「提出物一覧から審査」である。

### 本番との対応

| 関心事 | モック（本リポジトリ） | 本番プロトタイプ |
|--------|------------------------|------------------|
| 生データ適用 | `htmx.ajax` で `owner/<a>.html`（事前計算） | TRE 内で同一分析を生データへ実行し HTML 返却 |
| 生データ隔離 | 「非公開」表示＋事前生成 raw フラグメントのみ読込 | TRE に隔離、owner も生個票へは直接触れずジョブ経由 |
| 審査状態 | Alpine 共有ストアの `status`（in-memory） | サーバー側ジョブ状態 + DB |
| 審査認可 | owner ロール限定の擬似ガード | サーバー側で所有権により強制 |

## 8. 合成データ生成方針（mockdata-generator の思想）

`gghatano/mockdata-generator` の仕様駆動アプローチ（source → generator → synthetic +
evaluation）を参照しつつ、本デモでは簡易ジェネレータで代替する。

- **source**: 臨床的素性（指数減衰・用量依存 nadir・リスク依存の進行）をパラメータ化
- **generator**: シード固定で再現可能に生成（`generate_data.py`）
- **synthetic**: 別シード + 分布シフトで生成し、生データと近いが非同一にする
- **evaluation**: 3分析を両データに適用し、結果が「近いが一致しない」ことを UI 上で比較

### 8.1 複数データセット（#22）

`DATASETS` レジストリで複数データセットを定義する。各データセットは raw/synthetic の
`Profile`（seed・shift・`id_prefix`・`risk_params`）を持ち、シード固定で再現生成する。

- `prostate-psa`: 既存の前立腺がん PSA データセット（seed/パラメータは不変、出力バイト一致）。
- `renal-marker`: 第 2 データセット（腎細胞がんの腫瘍マーカー）。**PSA と同一スキーマ**
  （`risk_group` / `psa`(=腫瘍マーカー値) / `drug,dose_mg`）を保ち、別ドメイン・別 seed・
  別パラメータで生成する。これにより既存 3 分析（`analyses.py`）を**変更せずそのまま**
  適用できる。

> 仮定（#22）: 3 分析は PSA スキーマに結合しているため、第 2 データセットも同一スキーマで
> 別ドメインを表現する設計とした。分析ロジック・分布シフト方針・既存 seed は変更しない。

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
