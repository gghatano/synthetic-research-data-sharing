---
name: issue-triage
description: 仕様や発見事項から Issue 候補を抽出し、適切な粒度・依存・ラベルに整理する手順。Issue を作る前の計画時に使う。
---

# Issue Triage

仕様（docs/SPEC.md）や作業中の発見を、実装可能な Issue 候補へ整理する。
**この段階では Issue を大量作成しない。** まず docs/implementation-plan.md に候補一覧を書く。

## 手順
1. spec-analyst で仕様を充足マトリクス化し、未実装・乖離・曖昧点を洗い出す
2. 候補を task-granularity-guide.md の粒度（調査/基盤/機能/UI/テスト/リファクタ）で分類する
3. 大きすぎる候補は分割する。1 候補 = 1 PR で完結・検証可能・切り戻し可能に保つ
4. 依存関係を明示する（depends on #）。循環や暗黙依存を排除する
5. 各候補に以下を付ける（implementation-plan.md のフィールド）:
   タイトル / 背景 / 実装スコープ / 非スコープ / 依存 / 優先度 / 想定変更箇所 /
   検証方法 / 推奨ラベル / 推奨担当サブエージェント / 想定 PR 粒度
6. テンプレートの種類を割り当てる:
   実装→implementation-task / バグ→bugfix-task / 改善→refactor-task / 調査→investigation-task

## ラベル指針
- `type:implementation|bug|refactor|investigation`
- `status:ready|blocked|in-progress`
- `priority:high|medium|low`

## Issue 化の禁止対象（task-granularity-guide.md 参照）
- 大きすぎる機能全体 / 未確定の設計論点 / 暗黙の他 Issue 依存 /
  「よしなに改善」系 / 検証方法を定義できないもの

## 出力
docs/implementation-plan.md に追記できる Issue 候補一覧（人間の確認後に gh issue create）。
