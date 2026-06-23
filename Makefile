# synthetic-research-data-sharing — build pipeline
#
# generate : 生データ・合成データ(JSON)を site/data/ に生成
# analyze  : 3分析を生/合成双方に適用し HTML フラグメントを site/fragments/ に生成
# build    : generate + analyze（CI/ローカルの両方で使う）
# serve    : site/ をローカル配信してブラウザ確認
# clean    : 生成物を削除

# 実行は uv 経由（python3/python の環境差を uv が吸収）。uv 無しなら `make PY=python3` 等で上書き可。
PY ?= uv run python
SITE := site

.PHONY: build generate analyze serve clean

build: generate analyze

generate:
	$(PY) -m generator.generate_data

analyze:
	$(PY) -m generator.render

serve:
	@echo "http://localhost:8000/ で確認できます (Ctrl-C で停止)"
	cd $(SITE) && $(PY) -m http.server 8000

clean:
	# data/ 配下(catalog.json・各データセットの raw/synthetic・旧パス互換 json)を一括削除。
	rm -rf $(SITE)/data
	# fragments/ 配下: 各データセットの <dataset_id>/ と、旧パス互換の analyst/ owner/ を削除。
	[ -d $(SITE)/fragments ] && find $(SITE)/fragments -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + || true
