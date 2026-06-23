# Issue 管理ガイド

このリポジトリは **GitHub Issue を計画管理・進行記録・作業指示の単位**とする。
Issue 本文は Claude Code への作業指示書であり、PR・commit と合わせて開発プロセスの証跡になる。

## フロー

```
仕様(docs/SPEC.md)
  → spec-analyst で実装候補抽出
  → issue-triage / issue-planner で Issue 候補へ分割（docs/implementation-plan.md）
  → 人間が候補を確認
  → gh issue create で Issue 作成
  → Issue ごとに branch / worktree 作成（branch-worktree-policy.md）
  → worktree 内で issue-runner が実装
  → test-engineer / code-reviewer /（必要時）security-reviewer
  → PR 作成（pr-from-issue）
  → Issue へ検証結果コメント・相互リンク
  → merge 後 Issue close → worktree 削除
```

Claude Code に解かせるのは最下層の **Implementation Task / Bugfix / Refactor / Investigation** Issue だけ。
計画の見通しは下記 3 層で持つ（上位 2 層は人間が管理）。

```
Epic Issue        … 目的・全体スコープ・配下 Issue 一覧
  └ Feature Issue … 機能単位・設計論点・依存
      └ Task Issue … Claude Code が 1 PR で解く単位（実装はここだけ）
```

## Issue に入れるもの / 入れないもの

入れる: 背景 / 対象仕様 / 実装スコープ / **非スコープ** / 変更想定箇所 / **完了条件** /
**検証方法** / 関連 Issue / 既知のリスク / Claude Code への作業指示。

入れない: 大きすぎる機能全体 / 未確定の設計論点 / 暗黙の他 Issue 依存 /
「よしなに改善」系 / 検証方法を定義できないもの。

> 特に **非スコープ・完了条件・検証方法** が弱い Issue は、過剰実装・周辺修正・検証不足を招く。

## ラベル運用
- 種別: `type:implementation` / `type:bug` / `type:refactor` / `type:investigation`
- 状態: `status:ready` / `status:in-progress` / `status:blocked`
- 優先度: `priority:high` / `priority:medium` / `priority:low`

## Issue 進捗コメント（Progress Update フォーマット）

作業の節目で Issue にこの形式でコメントし、Issue を「作業証跡」にする。

````markdown
## Progress Update

### Status
- [ ] 調査中
- [ ] 実装中
- [ ] テスト中
- [ ] レビュー中
- [ ] PR作成済み
- [ ] 完了

### Summary
このIssueで対応した内容を簡潔に。

### Changes
-

### Verification
実行したコマンド:
```bash
```
結果:
```text
```

### Review
- code-reviewer:
- security-reviewer:

### Out of Scope Findings
-

### Remaining Work
-
````

## gh コマンド早見（コマンド詳細は branch-worktree-policy.md）
```bash
gh issue list
gh issue view <n> --comments
gh issue create --template implementation-task.yml
gh issue comment <n> --body-file progress.md
gh issue close <n>
```

> 認証メモ: origin は github.com（gghatano 所有）。`gh` は github.com に `gghatano`（ADMIN）で
> 認証済みで、このリポジトリ内では自動的に github.com / gghatano が選ばれる（社内 Enterprise の
> `hatano-takuma` とは別ホストなので競合しない）。よって `gh issue create` 等はそのまま使える。
> 別アカウントへ切替えるときは `gh auth switch`。実行前に念のため
> `git remote -v` と `gh auth status` を確認するとよい。
