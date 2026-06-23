---
name: worktree-task-runner
description: Issue ごとに専用 branch と git worktree を作成し、分離した作業ディレクトリで実装する手順。Issue 着手時に使う。
---

# Worktree Task Runner

1 worktree = 1 Issue = 1 branch。複数 Issue を同一 worktree で扱わない。
詳細・コマンド例は docs/branch-worktree-policy.md。

## 命名
- branch: `issue/<issue-number>-<short-slug>`（例 `issue/12-pytest-foundation`）
- worktree パス: `../worktrees/<repo-name>-issue-<issue-number>`

## 作成（gh が repo の host で使える場合）
```bash
gh issue view <n> --comments
gh issue develop <n> --name issue/<n>-<slug> --base develop
git fetch origin issue/<n>-<slug>
git worktree add ../worktrees/<repo>-issue-<n> issue/<n>-<slug>
```

## 作成（gh を使わない / host 不一致の場合）
```bash
git worktree add -b issue/<n>-<slug> ../worktrees/<repo>-issue-<n> develop
git push -u origin issue/<n>-<slug>
```

## 作業
1. worktree へ移動し、そこで初回 `uv sync`（worktree ごとに `.venv` が必要）
2. issue-driven-development SKILL の手順で実装・検証・レビュー
3. develop（既定ブランチ）/ main 直下では実装しない

## 後始末
- PR 作成・マージ後に worktree を削除候補とする:
  `git worktree remove ../worktrees/<repo>-issue-<n>`（未コミット変更があると失敗 = 安全）
- 不要 branch は merge 後に削除

## 注意
- 生成物（site/data, site/fragments）は worktree でも手編集しない（フックがブロック）
- `.python-version` と `uv.lock` は共有されるので、worktree でも同一環境が再現する
