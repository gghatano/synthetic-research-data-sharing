# CLAUDE.md

合成データで研究データを安全に共有する **code-to-data / TRE 型ワークフロー** のデモ。
詳細仕様は [docs/SPEC.md](docs/SPEC.md) が**唯一の正**。本ファイルは毎セッションの最小コンテキスト。

## このリポジトリの形

- **Python ジェネレータ**（`generator/`）: 生/合成データ生成・3分析・HTML フラグメント事前生成
- **静的フロント**（`site/`）: 素 HTML + htmx + Alpine.js + Chart.js（CDN, **ビルド工程なし**）
- 本番は FastAPI + htmx を想定するが**このリポジトリには存在しない**。`generator/analyses.py` と
  `generator/templates/` を将来そのまま移植する設計、という制約だけ守る。

## 開発コマンド

| 目的 | コマンド |
|------|----------|
| データ生成 | `make generate PY=python` |
| フラグメント生成 | `make analyze PY=python` |
| 全ビルド | `make build PY=python` |
| ローカル配信 | `make serve PY=python`（http://localhost:8000/） |
| 生成物削除 | `make clean` |
| アプリ依存 | `python -m pip install -r requirements.txt` |
| 開発依存 | `python -m pip install -r requirements-dev.txt` |

> **重要（環境差）**: この環境の Python は `python` で起動する（`python3` は存在しない）。
> Makefile の既定は `python3` なので、ローカルでは必ず **`PY=python`** を付ける。CI(ubuntu)は素の `make build`。

## 検証コマンド（変更完了時に必ず実行）

| 種別 | コマンド |
|------|----------|
| テスト | `python -m pytest -q` |
| lint | `python -m ruff check .` |
| format（確認） | `python -m ruff format --check .` |
| format（適用） | `python -m ruff format .` |
| 型チェック | `python -m mypy generator` |
| 再現性スモーク | `make build PY=python` が site/data/*.json と site/fragments/**/*.html を生成 |

## ブランチ・コミット・PR 方針

- 既定ブランチで直接作業しない。`feature/<topic>` を切る。
- 1 PR = 1 つの完結したタスク（implementation-plan の 1 項目）。差分は小さく。
- コミット前に上記「検証コマンド」を通す。落ちたまま完了報告しない。
- コミットメッセージ末尾に `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

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

- 手順（SKILL）: `.claude/skills/`（spec-implementation, code-review, test-fix-loop, refactor-safely, pr-prep）
- サブエージェント: `.claude/agents/`（reviewer 系は読み取り中心、実装系のみ編集可）
- 計画: [docs/implementation-plan.md](docs/implementation-plan.md)
- レビュー観点: [docs/review-checklist.md](docs/review-checklist.md)
- 完了条件: [docs/acceptance-criteria.md](docs/acceptance-criteria.md)
