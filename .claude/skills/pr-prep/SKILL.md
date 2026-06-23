---
name: pr-prep
description: PR 作成前の最終確認手順。コミット／PR を出す直前に必ず使う。
---

# PR Preparation

1. ブランチを確認する（既定ブランチでないこと。`feature/<topic>`）
2. 全検証を通しで実行し、出力を控える:
   - `uv run pytest -q`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run mypy generator`
   - `make build`（再現性スモーク）
3. `git status` / `git diff` で意図しない変更が無いか確認する
   - 生成物（site/data, site/fragments）の差分は **ジェネレータ変更に起因する説明可能なもの** だけか
   - 秘密情報・デバッグ出力・一時ファイルが混入していないか
4. docs/acceptance-criteria.md の該当項目を満たすか確認する
5. コミットメッセージは要点を簡潔に、末尾に
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
6. PR 本文に含める:
   - 対応した仕様項目（SPEC.md の節）
   - 変更内容と変更ファイル
   - 実行した検証コマンドと結果
   - 未対応事項・既知の制約・仕様上の曖昧点
7. PR 本文末尾に `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

## 確認

- 1 PR = 1 タスク（implementation-plan の 1 項目）になっているか
- レビュー（code-reviewer / 必要なら security-reviewer）を通したか
