---
name: code-review
description: 実装差分を docs/review-checklist.md に沿ってレビューする手順。実装完了前に必ず使う。
---

# Code Review Workflow

1. レビュー対象の差分を取得する（`git diff` / `git diff --staged`）
2. docs/review-checklist.md の各観点で評価する:
   仕様適合性 / 設計整合性 / 品質 / セキュリティ / 保守性
3. このリポジトリ固有の観点を必ず確認する:
   - `analyses.py` が純関数を保っているか（外部状態・I/O 依存なし）
   - 生成物（site/data, site/fragments）を手編集していないか
   - シード固定が崩れていないか（再現性）
   - フロントに npm/ビルド依存を持ち込んでいないか（CDN のみ）
   - 「合成 ≈ 生だが非同一」という核メッセージを壊していないか
4. 指摘は深刻度（blocker / major / minor / nit）と該当 `file:line` を添えて列挙する
5. 推測でなく根拠（コード引用・再現手順）を示す
6. レビュアーは**コードを直さない**。指摘のみ返す（修正は実装担当の責務）

## 出力フォーマット

```
## サマリ
（承認可否と理由を 1〜2 行）

## 指摘
- [blocker] file:line — 何が問題か / なぜ / 期待される修正
- [minor]   file:line — ...
```
