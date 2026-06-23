# CLAUDE.md

合成データで研究データを安全に共有する **code-to-data / TRE 型ワークフロー** のデモ。
詳細仕様は [docs/SPEC.md](docs/SPEC.md) が**唯一の正**。本ファイルは毎セッションの最小コンテキスト。

## このリポジトリの形

- **Python ジェネレータ**（`generator/`）: 生/合成データ生成・3分析・HTML フラグメント事前生成
- **静的フロント**（`site/`）: 素 HTML + htmx + Alpine.js + Chart.js（CDN, **ビルド工程なし**）
- 本番は FastAPI + htmx を想定するが**このリポジトリには存在しない**。`generator/analyses.py` と
  `generator/templates/` を将来そのまま移植する設計、という制約だけ守る。

## ツール: uv

依存・実行・検証はすべて **uv** 経由（`python3`/`python` の環境差を uv が吸収する）。
依存の単一の真実は `pyproject.toml`（`[project].dependencies` と `[dependency-groups].dev`）。
ランタイムは `.python-version`（3.12）で固定。`requirements*.txt` は使わない。

## 開発コマンド

| 目的 | コマンド |
|------|----------|
| 環境同期（初回/依存変更時） | `uv sync` |
| データ生成 | `uv run python -m generator.generate_data` |
| フラグメント生成 | `uv run python -m generator.render` |
| 全ビルド | `make build`（内部で `uv run python` を使用） |
| ローカル配信 | `make serve`（http://localhost:8000/） |
| 生成物削除 | `make clean` |
| 依存を1つ追加 | `uv add <pkg>` / dev は `uv add --dev <pkg>` |

> `make` が無い環境では `uv run python -m generator.generate_data && uv run python -m generator.render` で代替可。

## 検証コマンド（変更完了時に必ず実行）

| 種別 | コマンド |
|------|----------|
| テスト | `uv run pytest -q` |
| lint | `uv run ruff check .` |
| format（確認） | `uv run ruff format --check .` |
| format（適用） | `uv run ruff format .` |
| 型チェック | `uv run mypy generator` |
| 再現性スモーク | `make build` が site/data/*.json と site/fragments/**/*.html を生成 |

## Issue 駆動開発（最重要の運用ルール）

実装作業は原則 **GitHub Issue 単位**で行う。Issue 本文を作業指示書として扱う。
詳細: [docs/issue-management.md](docs/issue-management.md) /
[docs/branch-worktree-policy.md](docs/branch-worktree-policy.md) /
[docs/task-granularity-guide.md](docs/task-granularity-guide.md)。

- **Issue 未作成の実装に着手しない**（足場整備など明示的な例外を除く）。
- Issue ごとに専用 branch（`issue/<n>-<slug>`）と git worktree
  （`../worktrees/<repo>-issue-<n>`）を作る。1 worktree = 1 Issue = 1 branch。
- 作業開始時に `gh issue view <n> --comments` で**本文とコメントを必ず読む**。
- Issue のスコープを超える変更をしない。**非スコープ**に書かれた内容を実装しない。
- スコープ外の発見事項は実装せず、Issue コメントまたは別 Issue 候補として記録する。
- 仕様の曖昧点は、置いた仮定を Issue に明記する。
- 完了時は **Issue と PR の双方**に検証結果・変更概要・残課題を残し、相互リンクする。
- gh 実行前に `git remote -v` と `gh auth status` の host 一致を確認する（不一致なら docs の代替手順）。

## ブランチ・コミット・PR 方針

- 既定ブランチで直接作業しない。Issue があれば `issue/<n>-<slug>`、足場整備等は `feature/<topic>`。
- 1 PR = 1 Issue（= 1 完結タスク）。差分は小さく。
- コミット前に上記「検証コマンド」を通す。落ちたまま完了報告しない。
- `uv.lock` はコミットする（再現可能な環境のため）。
- コミットメッセージ末尾に `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- PR 本文に Issue 番号・変更内容・検証結果・レビュー観点を記載し、作成後 Issue に PR リンクを残す。

## 実装時の禁止事項

- **仕様書（docs/SPEC.md）に反する実装をしない。** 曖昧なら勝手に大きな設計判断をせず仮定を明記。
- **生成物を手で編集しない**: `site/data/*.json`, `site/fragments/**/*.html` は `make build` の出力。
  内容を変えたいときはジェネレータ（`generator/`）を直す。
- **再現性を壊さない**: 乱数は必ずシード固定（`generate_data.py` の seed、`analyses.py` の `RANDOM_STATE=42`）。
- `analyses.py` を外部状態に依存させない（「データ dict → 結果 dict」の純関数を保つ）。
- フロントにビルド工程・npm 依存を持ち込まない（CDN のみ）。`node_modules/` はテスト用途限定。
- 秘密情報（鍵・トークン・実患者データ）をコミットしない。データはすべて架空。
- テスト失敗・エラーを握りつぶさない。

## 完了時に必ず提示する証跡

実装した内容 / 変更ファイル / 実行した検証コマンドとその**出力** / 未対応事項 /
仕様上の曖昧点 / 次に実装すべきタスク。「成功した」と主張するだけでなく、コマンド出力か差分で示す。

## 運用資産

- 手順（SKILL）: `.claude/skills/`
  - 実装系: spec-implementation, code-review, test-fix-loop, refactor-safely, pr-prep
  - Issue 駆動: issue-driven-development, issue-triage, worktree-task-runner, pr-from-issue
- サブエージェント: `.claude/agents/`（reviewer 系は読み取り中心、実装系のみ編集可）
  - 計画: spec-analyst, issue-planner, implementation-planner
  - 実行: issue-runner（主担当）, implementation-agent, backend-implementer, frontend-implementer, test-engineer
  - レビュー/記録: code-reviewer, security-reviewer, pr-writer
- Issue 運用: [issue-management.md](docs/issue-management.md) / [branch-worktree-policy.md](docs/branch-worktree-policy.md) / [task-granularity-guide.md](docs/task-granularity-guide.md)
- Issue テンプレート: `.github/ISSUE_TEMPLATE/`（implementation / bugfix / refactor / investigation）
- 計画（Issue 候補一覧）: [docs/implementation-plan.md](docs/implementation-plan.md)
- レビュー観点: [docs/review-checklist.md](docs/review-checklist.md) / 完了条件: [docs/acceptance-criteria.md](docs/acceptance-criteria.md)
