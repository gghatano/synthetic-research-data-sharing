---
name: spec-implementation
description: docs/SPEC.md に基づき、実装タスクを小さく切り出して実装・検証する手順。仕様から1単位を実装するとき必ず使う。
---

# Spec Implementation Workflow

docs/SPEC.md を唯一の正とし、1 回につき 1 つの作業単位だけを進める。

1. 対象仕様を特定する（SPEC.md の該当節を引用する）
2. 関連する既存コードを読む（`generator/`, `site/`, テンプレート）
3. 既存の設計パターン・命名・データ契約（dict 形状）を確認する
4. 実装方針を 3〜5 行で提示する（変更対象ファイルと完了条件を含む）
5. 最小単位で実装する
6. 必要なテストを `tests/` に追加・更新する
7. 検証を実行する: `uv run pytest -q` → `uv run ruff check .` →
   `uv run ruff format --check .` → `uv run mypy generator`
8. 再現性スモーク: `make build` が site/data/*.json と
   site/fragments/**/*.html を再生成できることを確認する
9. 失敗したら原因を分析して修正する（test-fix-loop SKILL を使う）
10. code-reviewer サブエージェントにレビューさせる
11. 認証/認可/入力/秘密情報/依存に関わる変更なら security-reviewer も使う
12. 変更内容・検証コマンド出力・未対応事項を報告する

## 禁止事項

- 仕様にない機能を追加しない
- 生成物（site/data, site/fragments）を手編集しない（ジェネレータを直す）
- シード／RANDOM_STATE を変えて再現性を壊さない
- `analyses.py` を純関数でなくしない（外部状態に依存させない）
- テスト失敗・エラーを握りつぶさない
- 大規模リファクタリングを実装タスクに混ぜない（refactor-safely を別途使う）
