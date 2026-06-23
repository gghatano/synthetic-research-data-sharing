# Branch / Worktree 運用ポリシー

**1 worktree = 1 Issue = 1 branch = 原則 1 PR。** 複数 Issue を同一 worktree で扱わない。

## 命名規則
- branch: `issue/<issue-number>-<short-slug>`
  - 例: `issue/12-pytest-foundation`, `issue/15-synthetic-vs-raw-test`
- worktree パス: `../worktrees/<repo-name>-issue-<issue-number>`
  - 例: `../worktrees/synthetic-research-data-sharing-issue-12`

## 禁止
- `develop`（既定ブランチ）/ `main` 直下で実装しない（足場・Issue 整備のような例外は明示する）
- 1 つの worktree で複数 Issue の変更を混ぜない
- 生成物（site/data, site/fragments）を worktree でも手編集しない（PreToolUse フックがブロック）

## 前提確認（実行前に）
```bash
git remote -v          # origin: github.com:gghatano/...
gh auth status         # github.com に gghatano(ADMIN) で認証済み
```
このリポジトリでは gh が自動的に github.com / gghatano を使う（社内 Enterprise の
hatano-takuma とは別ホストで競合しない）。よって以下の「gh を使う場合」が標準。
gh が使えない環境（CI 等で未認証）では「gh を使わない場合」を使う。

## 作成 — gh を使う場合（host 一致時）
```bash
# Issue 確認
gh issue view 12 --comments

# Issue に紐づく開発ブランチを作成
gh issue develop 12 --name issue/12-pytest-foundation --base develop

# ブランチ取得 + worktree 作成
git fetch origin issue/12-pytest-foundation
git worktree add ../worktrees/synthetic-research-data-sharing-issue-12 issue/12-pytest-foundation

cd ../worktrees/synthetic-research-data-sharing-issue-12
uv sync   # worktree ごとに .venv が要る
```

## 作成 — gh を使わない場合（host 不一致・gh 不可）
```bash
# branch と worktree を同時作成
git worktree add -b issue/12-pytest-foundation \
  ../worktrees/synthetic-research-data-sharing-issue-12 develop

cd ../worktrees/synthetic-research-data-sharing-issue-12
uv sync
git push -u origin issue/12-pytest-foundation
```

## 作業中
- `uv run ...` で実行・検証（.python-version=3.12 / uv.lock を共有するため環境は同一に再現）
- issue-driven-development SKILL の検証・レビュー手順に従う

## PR と後始末
```bash
# PR 作成（pr-from-issue SKILL）
gh pr create --base develop --title "<要約> (#12)" --body-file pr-body.md   # host 一致時
#   host 不一致時は GitHub Web UI で PR 作成、または origin host 向けに認証

# merge 後: worktree 削除（未コミット変更があると失敗 = 安全装置）
git worktree remove ../worktrees/synthetic-research-data-sharing-issue-12
git worktree prune
git branch -d issue/12-pytest-foundation     # ローカル
```

## よく使う worktree コマンド
```bash
git worktree list                 # 現在の worktree 一覧
git worktree remove <path>        # 削除
git worktree prune                # 参照切れの掃除
```

## 既知の落とし穴（push / スタック PR）

過去のリリースで実際にハマった repo 固有の注意点。プロンプトに毎回書かず、ここを参照する。

### 1. コミット author email（push 拒否の回避）
実メールでコミットすると GitHub のメールプライバシー設定で
`push declined due to email privacy restrictions` になる。**必ず noreply を使う**。
```bash
git config user.email "5264958+gghatano@users.noreply.github.com"
git config user.name  "gghatano"
# 既にローカルの実メールでコミット済みなら author を貼り直す:
git rebase develop --exec 'git commit --amend --no-edit --reset-author'
```

### 2. スタック PR のマージで `--delete-branch` を使わない
複数 Issue を依存順にスタック（base = 前段ブランチ）した PR 群を develop へ入れるとき、
`gh pr merge <親> --delete-branch` で**親ブランチを消すと、それを base にしていた子 PR が
自動でクローズされ、しかも base ブランチ消失のため reopen できない**（置き換え PR を作り直す羽目になる）。

正しい手順（親を develop に入れてから子の base を develop へ付け替える）:
```bash
gh pr merge <親> --merge                 # --delete-branch は付けない
gh pr edit  <子> --base develop          # 親が develop に入った後で付け替え（差分が Issue 単位で残る）
# CI 緑を待って:
gh pr merge <子> --merge
# 全部 develop に入ってから、不要ブランチをまとめて削除:
#   git push origin --delete issue/<n>-<slug> ...
```

### 3. マージ前に CI（quality / e2e）緑をポーリング確認
`on: [push, pull_request]` の `ci.yml` が走る。緑になる前にマージしない。
```bash
# pass になるまで待つ（quality と e2e の 2 job、各 1 分弱）
gh pr checks <n>                         # pass/pending/fail を確認
gh pr view  <n> --json mergeStateStatus  # CLEAN になればマージ可
```

### 4. リリース（develop → main）
既定ブランチは develop（Issue は develop マージで `Closes #n` により自動 close）。
リリースは develop→main の PR をマージ → `.github/workflows/deploy.yml` が GitHub Pages へデプロイ。
デプロイ成功を `gh run list --workflow=deploy.yml --branch main` で確認する。
公開 URL: https://gghatano.github.io/synthetic-research-data-sharing/
