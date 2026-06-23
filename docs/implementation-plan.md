# Implementation Plan

最終更新: 2026-06-23

## 現状サマリ（棚卸し結果）

SPEC.md の機能（データ生成・3分析・HTMLレンダリング・3ロールUI・CIデプロイ）は
**ひととおり実装済み**。一方で **検証の足場が欠落**しており、自律実装を安全に回すには
まずそこを固めるのが最も依存が少なく価値が高い。

### 確認した主なギャップ / リスク
1. **テストが皆無**。再現性・純関数性・出力スキーマ・核メッセージが回帰検知できない。
2. **lint / format / typecheck は設定・実行可能になったが、既存コードに未解消の指摘がある**
   （足場整備で uv プロジェクト化＋ruff/mypy 設定を追加。`uv run ruff check` で B905 等、
   `uv run mypy generator` で `analyses.py` の型指摘が出る。解消は T5）。
3. ~~クロスプラットフォーム（python3 前提）~~ → **uv 採用で解決済み**。`make` は `uv run python`
   を使い、CI もローカルも同一手順。（T7 完了）
4. **CI は deploy のみ**。テスト・lint を通す品質ゲートが無い（deploy も uv 化が必要）。
5. 「合成 ≈ 生だが非同一」が**どこにも検証されていない**（デモの核心なのに保証なし）。

> タスクは「1 PR = 1 完結単位」。各タスクは spec-implementation SKILL の手順で進め、
> 完了条件は docs/acceptance-criteria.md を満たすこと。

---

## タスク（優先順 / 依存少ない順）

### T1. テスト基盤の導入（pytest）  ★最優先・依存なし
- 対象仕様: SPEC §9（検証方法）、§3/§5（データ・分析定義）
- 変更対象: `tests/`（新規）, `tests/conftest.py`
- 内容: 小さな n で生成したデータを供給するフィクスチャ。最初の 1 ケース（generate の再現性）
- 想定テスト: 同一シードで `_generate` の出力が完全一致
- 完了条件: `uv run pytest -q` が緑。CI でなくローカルで実行可能
- リスク: 依存未取得環境 → `uv sync` で解決（pyproject の dev グループに pytest 等が入っている）

### T2. 分析の純関数性・出力スキーマのテスト
- 対象仕様: SPEC §5（3分析の定義）
- 変更対象: `tests/test_analyses.py`
- 想定テスト: 各 `ANALYSES[*]` が入力 dict を変更しない / 同入力で同出力 /
  戻り dict のキー・型（clustering の cluster_sizes・trajectories、association の regression、
  survival の curves/summary）が仕様どおり / 境界（空グループ等）で落ちない
- 完了条件: 共通 DoD（acceptance-criteria）
- 依存: T1

### T3. 「合成 ≈ 生だが非同一」性質テスト（核メッセージ）
- 対象仕様: SPEC §1, §3「生 vs 合成」, §8 evaluation
- 変更対象: `tests/test_synthetic_vs_raw.py`
- 想定テスト: raw/synthetic 双方に同一分析を適用し、主要指標（回帰傾き・KM イベント率・
  クラスタ人数比）が**許容レンジ内で近い**かつ**完全一致でない**ことを確認
- 完了条件: 許容レンジは根拠とともにコメント明記（脆くしない）
- 依存: T1, T2

### T4. レンダリングのスモークテスト
- 対象仕様: SPEC §6, §4（フラグメント）
- 変更対象: `tests/test_render.py`
- 想定テスト: `render_all()` が analyst/owner × 3分析の .html を生成し、必須要素
  （canvas#chart-*, cfg JSON, テーブル）を含む。autoescape が効いている
- 依存: T1

### T5. lint / format / typecheck の指摘解消
- 内容: 既存コードの ruff/mypy 指摘を解消（`analyses.py` の `zip(..., strict=)`、
  `by_drug.sort` の型、format 差分・import 整列等）。**ロジック・数値・スキーマは変えない**
  （refactor-safely）。生成物が変わらないことをゴールデン比較で確認
- 完了条件: `uv run ruff check .`/`uv run ruff format --check .`/`uv run mypy generator` が緑
- 依存: なし（T1 と並行可）

### T6. CI に品質ゲートを追加（＋ deploy の uv 化）
- 対象仕様: SPEC §9、運用方針
- 変更対象: `.github/workflows/`（test job 追加、deploy も uv へ）
- 内容: push/PR で `astral-sh/setup-uv` → `uv sync` → `uv run pytest / ruff / mypy`。
  deploy job も `uv sync` → `make build` に統一し、test 成功を needs にする
- 完了条件: CI が緑。テスト失敗時に deploy されない
- 依存: T1〜T5

### ~~T7. クロスプラットフォーム整合~~ → 足場整備で完了
uv 採用により `python3`/`python` 差を解消。Makefile は `uv run python`、ローカル/CI 同一手順。

---

## 進め方
1. まず **T1**（最も依存が少なく検証可能）から着手する
2. 各タスクで: 対象仕様確認 → 実装 → テスト → pytest/ruff/mypy/build → code-reviewer →
   （必要時 security-reviewer）→ 修正 → 証跡提示
3. 1 回の作業で複数タスクをまとめない

## 仕様上の曖昧点（実装前に仮定を置く / 必要なら確認）
- T3 の「近い」の許容レンジ（相対誤差何 %）は SPEC に数値規定が無い → 実装時に dev で観測して
  根拠つきで設定し、コメントに明記する（勝手な大きな判断はしない）
- KM の median が None になり得るケース（イベント極少）の表示仕様は既存実装（"—"）に合わせる
