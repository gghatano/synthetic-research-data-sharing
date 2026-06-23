# Acceptance Criteria

各タスクが「完了」と言えるための、検証可能な条件。証跡（コマンド出力・差分）で示すこと。

## 全タスク共通（Definition of Done）
- [ ] 対象仕様（SPEC.md の節）を満たし、仮定があれば明記した
- [ ] `python -m pytest -q` が緑
- [ ] `python -m ruff check .` が無警告
- [ ] `python -m ruff format --check .` が差分なし
- [ ] `python -m mypy generator` がエラーなし
- [ ] `make build PY=python` が site/data/*.json と site/fragments/**/*.html を生成
- [ ] code-reviewer のレビューを通した（必要なら security-reviewer も）
- [ ] 変更ファイル・検証出力・残課題・曖昧点を報告した

## プロダクト要件（SPEC 由来）
- [ ] **再現性**: 同一シードで `generate_data` が同一 JSON を生成する（テストで保証）
- [ ] **純関数性**: `analyses` の各関数が入力を破壊せず、同入力で同出力（テストで保証）
- [ ] **出力スキーマ**: 各分析の戻り dict が仕様のキー・型を満たす（テストで保証）
- [ ] **核メッセージ**: 合成と生で主要指標が「近いが完全一致しない」（テストで保証）
- [ ] **3 ロール UI**: 公開→提出→承認→比較 が動作し、htmx でフラグメントを読み込む
- [ ] **生データ非公開表示**: ① で raw は 🔒、合成のみ公開
- [ ] **チャート描画**: 3 分析すべてで Chart.js が描画される（再読込時の二重描画なし）

## 品質ゲート（ツール整備後）
- [ ] CI（deploy.yml もしくは別 workflow）でテスト・lint・型チェックが実行される
- [ ] 開発依存が requirements-dev.txt に固定され、`pyproject.toml` に設定がある
