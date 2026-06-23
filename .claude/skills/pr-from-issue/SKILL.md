---
name: pr-from-issue
description: Issue に紐づく PR を作成し、Issue へ進捗・検証結果をコメントして相互リンクする手順。作業完了時に使う。
---

# PR from Issue

pr-prep SKILL の検証を通したうえで、Issue と PR を結びつける。

## 前提
- pr-prep の全検証が緑（pytest / ruff / ruff format --check / mypy / build）
- branch は `issue/<n>-<slug>`、作業は Issue スコープ内に収まっている

## PR 作成
```bash
gh pr create \
  --base develop \
  --title "<簡潔な要約> (#<n>)" \
  --body-file <(cat <<'BODY'
## 対応 Issue
Closes #<n>

## 変更内容
- 対応した仕様項目（docs/SPEC.md の §）
- 変更ファイルと要点

## 検証結果
（実行したコマンドと出力の要約。pytest/ruff/mypy/build）

## レビュー観点
- code-reviewer: <結果>
- security-reviewer: <該当時の結果>

## 残課題 / スコープ外の発見
- 

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)
```
> `Closes #<n>` で merge 時に Issue が自動 close される。close したくない場合は `Refs #<n>`。

## マージ（CI 緑を待つ / スタック PR の注意）
- **マージ前に CI（quality / e2e）が pass になるまで待つ**。`gh pr checks <n>` / `gh pr view <n> --json mergeStateStatus`（CLEAN）。
- **複数 Issue を依存順にスタックした PR 群**（base = 前段ブランチ）は、`gh pr merge --delete-branch` を**使わない**。
  親ブランチを消すと子 PR が自動クローズ＆復活不可になる。親を develop にマージ後、`gh pr edit <子> --base develop` で
  付け替えてからマージし、全部入ってからブランチをまとめて削除する。
- 詳細は [branch-worktree-policy.md](../../../docs/branch-worktree-policy.md) 「既知の落とし穴」を参照。

## Issue へコメント（issue-management.md の Progress Update フォーマット）
```bash
gh issue comment <n> --body-file progress.md
```
- Status を「PR作成済み」へ更新し、PR URL を貼る
- 検証結果・スコープ外発見・残課題を記録する

## 完了報告（チャットへ）
対応 Issue / branch / PR URL / 変更ファイル / 実装内容 / 検証コマンドと結果 /
未対応事項 / スコープ外として記録した事項。
