# Implementation Plan — Issue 候補一覧

最終更新: 2026-06-23

このファイルは **Issue 化前の候補一覧**（issue-triage / issue-planner の出力）。
人間が確認したのち `gh issue create` で Issue 化する。**まだ Issue は作成しない。**
粒度・運用は [task-granularity-guide.md](task-granularity-guide.md) /
[issue-management.md](issue-management.md) に従う。

## 現状サマリ（棚卸し結果）

SPEC.md の機能（データ生成・3分析・HTMLレンダリング・3ロールUI・CIデプロイ）は
**ひととおり実装済み**。一方で **検証の足場が欠落**しており、自律実装を安全に回すには
まずそこを固めるのが最も依存が少なく価値が高い。

### 確認した主なギャップ / リスク
1. **テストが皆無**。再現性・純関数性・出力スキーマ・核メッセージが回帰検知できない。
2. **ruff / mypy は実行可能だが既存コードに未解消の指摘がある**（`analyses.py` の
   `zip(strict=)`・`by_drug.sort` の型など）。
3. ~~python3 前提のクロスプラットフォーム問題~~ → **uv 採用で解決済み**。
4. **CI は deploy のみ**。テスト・lint の品質ゲートが無い。
5. 「合成 ≈ 生だが非同一」が**どこにも検証されていない**（デモの核心なのに保証なし）。

---

## Issue 候補

各候補のフィールド: 背景 / 実装スコープ / 非スコープ / 依存 / 優先度 / 想定変更箇所 /
検証方法 / 推奨ラベル / 推奨担当 / 想定 PR 粒度。

### IC-1. pytest 基盤と再現性テストの導入
- **背景**: テストが皆無で回帰検知できない（ギャップ1）。SPEC §9 は手動検証のみ規定。
- **実装スコープ**: `tests/` と `tests/conftest.py`（小 n データ生成フィクスチャ）。
  最初のテスト = 同一シードで `generate_data._generate` の出力が完全一致（再現性）。
- **非スコープ**: 分析や render のテスト（IC-2/IC-4）、CI 連携（IC-5）、既存コードの lint 修正（IC-6）。
- **依存**: なし（最優先）。
- **優先度**: high
- **想定変更箇所**: `tests/conftest.py`, `tests/test_generate_data.py`
- **検証方法**: `uv run pytest -q` が緑。
- **推奨ラベル**: `type:implementation`, `priority:high`
- **推奨担当**: test-engineer（issue-runner 進行）
- **想定 PR 粒度**: 小（新規 tests のみ、プロダクションコード変更なし）

### IC-2. 分析の純関数性・出力スキーマのテスト
- **背景**: 3分析（SPEC §5）の戻り値契約が未保証。純関数性も未検証。
- **実装スコープ**: 各 `analyses.ANALYSES[*]` について「入力 dict を破壊しない / 同入力同出力 /
  戻り dict のキー・型が仕様どおり / 境界（空グループ等）で落ちない」を検証。
- **非スコープ**: 合成 vs 生の比較（IC-3）、数値ロジックの変更。
- **依存**: IC-1
- **優先度**: high
- **想定変更箇所**: `tests/test_analyses.py`
- **検証方法**: `uv run pytest -q`。
- **推奨ラベル**: `type:implementation`, `priority:high`
- **推奨担当**: test-engineer
- **想定 PR 粒度**: 小〜中

### IC-3. 「合成 ≈ 生だが非同一」性質テスト（核メッセージ）
- **背景**: デモの核心（SPEC §1/§3/§8）が一切検証されていない（ギャップ5）。
- **実装スコープ**: raw/synthetic 双方に同一分析を適用し、主要指標（回帰傾き・KM イベント率・
  クラスタ人数比）が**許容レンジ内で近い**かつ**完全一致でない**ことを検証。
- **非スコープ**: 生成ロジック・分布シフト量の変更。
- **依存**: IC-1, IC-2
- **優先度**: medium
- **想定変更箇所**: `tests/test_synthetic_vs_raw.py`
- **検証方法**: `uv run pytest -q`。許容レンジは dev 観測値に基づき根拠をコメント明記（脆くしない）。
- **推奨ラベル**: `type:implementation`, `priority:medium`
- **推奨担当**: test-engineer
- **想定 PR 粒度**: 小〜中
- **曖昧点**: 「近い」の許容幅は SPEC に数値規定なし → 仮定を Issue に明記。

### IC-4. レンダリングのスモークテスト
- **背景**: render（SPEC §6/§4）の出力 HTML が壊れても気づけない。
- **実装スコープ**: `render_all()` が analyst/owner × 3分析の .html を生成し、必須要素
  （`canvas#chart-*`, cfg JSON, テーブル）を含む / Jinja2 autoescape が有効、を検証。
- **非スコープ**: テンプレの見た目変更、Chart.js 設定の変更。
- **依存**: IC-1
- **優先度**: medium
- **想定変更箇所**: `tests/test_render.py`
- **検証方法**: `uv run pytest -q`。
- **推奨ラベル**: `type:implementation`, `priority:medium`
- **推奨担当**: test-engineer
- **想定 PR 粒度**: 小

### IC-5. CI に品質ゲートを追加（＋ deploy の uv 化確認）
- **背景**: CI が deploy のみ（ギャップ4）。テスト失敗が検知されずデプロイされ得る。
- **実装スコープ**: push/PR で `astral-sh/setup-uv` → `uv sync` → `uv run pytest / ruff / mypy` を
  実行する job を追加。deploy は test 成功を `needs` にする。
- **非スコープ**: テスト自体の追加（IC-1〜4）、デプロイ先設定。
- **依存**: IC-1（最低 1 テストが緑）。IC-6 が未了でも mypy は warning 扱い等で調整可。
- **優先度**: medium
- **想定変更箇所**: `.github/workflows/`（test job 追加、deploy 調整）
- **検証方法**: PR 上で CI が緑。意図的にテストを落とすと deploy がスキップされる。
- **推奨ラベル**: `type:implementation`, `priority:medium`
- **推奨担当**: implementation-agent（issue-runner 進行）
- **想定 PR 粒度**: 小

### IC-6. 既存コードの ruff / mypy 指摘解消（リファクタ）
- **背景**: ギャップ2。`uv run ruff check .` / `uv run mypy generator` に既存指摘。
- **実装スコープ**: `analyses.py` の `zip(..., strict=)`・`by_drug.sort` の型・format 差分・
  import 整列等を解消。**ロジック・数値・スキーマ・シードは変えない**。
- **非スコープ**: 機能追加、出力の変更。
- **依存**: なし（IC-1 と並行可。ゴールデン比較のため IC-1 のフィクスチャがあると安全）
- **優先度**: medium
- **想定変更箇所**: `generator/analyses.py` ほか generator 配下
- **検証方法**: `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy generator` が緑。
  かつ `make build` 後に `git diff --stat site/` が**差分0**（生成物のバイト同一性）。
- **推奨ラベル**: `type:refactor`, `priority:medium`
- **推奨担当**: backend-implementer（refactor-safely SKILL）
- **想定 PR 粒度**: 小〜中

---

## 依存関係

```
IC-1 ──┬─ IC-2 ── IC-3
       ├─ IC-4
       └─ IC-5（IC-1 必須、IC-6 は任意先行）
IC-6（独立。IC-1 のフィクスチャがあると安全）
```

## 進め方
1. 人間が本候補一覧を確認・取捨選択する。
2. 採用分を `gh issue create`（implementation / refactor テンプレ）で Issue 化する。
3. Issue ごとに branch / worktree を作り、issue-runner で 1 件ずつ進める。
4. 各 Issue: 検証 → code-reviewer →（必要時 security-reviewer）→ PR → Issue へ検証結果コメント。

## 実装開始前に確認すべき論点
- ~~gh の host 不一致~~ → **解決済み**。gh は github.com に gghatano(ADMIN) で認証済みで、
  本リポジトリでは自動的に gghatano が使われる。`gh issue create` 等がそのまま使える。
- **IC-3 の許容レンジ**: 「近い」の数値基準は SPEC 未規定。dev 観測で決め、仮定を Issue に明記。
- **IC-5 と IC-6 の順序**: CI で mypy を必須にするなら IC-6 を先行させるか、段階導入するか。
