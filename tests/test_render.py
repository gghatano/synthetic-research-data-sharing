"""IC-4: HTML フラグメントのレンダリング(generator/render.py)のスモークテスト。

プロダクションコード(generator/)は変更しない。テストの新規追加のみ。

実 site/ を汚さないため、`render.DATA_DIR` と `render.FRAG_DIR` を monkeypatch で
`tmp_path` 配下へ差し替えてから `render_all()` を呼ぶ。入力 JSON は小 n の生成データ
(`generate_data._generate`)を tmp に書き出して用意する。
"""

from __future__ import annotations

import json

import pytest

from generator import render
from generator.analyses import ANALYSES
from generator.generate_data import Profile, _generate

KINDS = {"analyst": "synthetic", "owner": "raw"}
ANALYSIS_NAMES = list(ANALYSES)  # clustering / association / survival
CHART_TYPES = {"clustering": "line", "association": "scatter", "survival": "line"}


@pytest.fixture
def render_dirs(tmp_path, monkeypatch):
    """DATA_DIR/FRAG_DIR を tmp に差し替え、小 n の入力 JSON を書き出す。

    raw=shift0.0 / synthetic=shift1.0、それぞれ n=30。
    """
    data_dir = tmp_path / "data"
    frag_dir = tmp_path / "fragments"
    data_dir.mkdir()
    frag_dir.mkdir()

    monkeypatch.setattr(render, "DATA_DIR", data_dir)
    monkeypatch.setattr(render, "FRAG_DIR", frag_dir)
    # render_all() の進捗 print が `relative_to(ROOT)` を使うため、ROOT も tmp に揃える
    # (出力先は FRAG_DIR から導出されるので、ROOT の差し替えは print 表示のみに影響する)
    monkeypatch.setattr(render, "ROOT", tmp_path)

    profiles = {
        "raw": Profile(name="raw", seed=20210101, n_patients=30, shift=0.0),
        "synthetic": Profile(name="synthetic", seed=99999, n_patients=30, shift=1.0),
    }
    for name, prof in profiles.items():
        data = _generate(prof)
        (data_dir / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    return data_dir, frag_dir


# --- end-to-end (tmp へ) -----------------------------------------------------


def test_render_all_writes_six_fragments(render_dirs) -> None:
    """analyst/owner × 3 分析 = 計 6 ファイルが生成される。"""
    _, frag_dir = render_dirs
    render.render_all()

    for sub in ("analyst", "owner"):
        for name in ANALYSIS_NAMES:
            f = frag_dir / sub / f"{name}.html"
            assert f.exists(), f"missing fragment: {sub}/{name}.html"

    written = sorted(p.relative_to(frag_dir).as_posix() for p in frag_dir.rglob("*.html"))
    assert len(written) == 6


@pytest.mark.parametrize("sub,kind", list(KINDS.items()))
@pytest.mark.parametrize("name", ANALYSIS_NAMES)
def test_fragment_contains_required_elements(render_dirs, sub: str, kind: str, name: str) -> None:
    """各フラグメントが必須要素(canvas/cfg/table/data 属性)を uid 付きで含む。"""
    _, frag_dir = render_dirs
    render.render_all()

    html = (frag_dir / sub / f"{name}.html").read_text(encoding="utf-8")
    uid = f"{kind}-{name}"

    assert f'id="chart-{uid}"' in html
    assert f'id="cfg-{uid}"' in html
    assert '<table class="frag-table">' in html
    assert f'data-kind="{kind}"' in html
    assert f'data-analysis="{name}"' in html


@pytest.mark.parametrize("sub,kind", list(KINDS.items()))
@pytest.mark.parametrize("name", ANALYSIS_NAMES)
def test_embedded_cfg_is_valid_chart_json(render_dirs, sub: str, kind: str, name: str) -> None:
    """埋め込み cfg JSON が json.loads 可能で、想定の type を持つ chart config。"""
    _, frag_dir = render_dirs
    render.render_all()

    html = (frag_dir / sub / f"{name}.html").read_text(encoding="utf-8")
    uid = f"{kind}-{name}"

    # <script ... id="cfg-{uid}">{JSON}</script> から JSON 本文を取り出す
    marker = f'id="cfg-{uid}">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    cfg = json.loads(html[start:end])

    assert "type" in cfg
    assert cfg["type"] == CHART_TYPES[name]
    assert "data" in cfg


# --- chart builders ----------------------------------------------------------


@pytest.mark.parametrize("name", ANALYSIS_NAMES)
def test_chart_builder_returns_typed_config(syn_dataset: dict, name: str) -> None:
    """各 CHART_BUILDERS[name](result) が dict を返し、想定の type を持つ。"""
    result = ANALYSES[name](syn_dataset)
    chart = render.CHART_BUILDERS[name](result)

    assert isinstance(chart, dict)
    assert chart["type"] == CHART_TYPES[name]
    assert "data" in chart


# --- autoescape / safe -------------------------------------------------------


def _render_minimal(template, *, title: str, chart_json: str) -> str:
    """fragment.html.j2 を最小コンテキストでレンダリングする。"""
    return template.render(
        uid="t-clustering",
        kind="synthetic",
        kind_label="合成データ",
        analysis="clustering",
        title=title,
        result=dict(
            n_patients=1,
            feature_cols=["baseline"],
            centroids_standardized={"responder": {"baseline": 0.0}},
            cluster_sizes={"responder": 1},
        ),
        chart_config=chart_json,
        code="x = 1",
    )


def test_autoescape_policy_matches_template_name() -> None:
    """`_build_env()` の autoescape ポリシーが select_autoescape(["html","xml"]) と一致。

    実装は `Environment(autoescape=select_autoescape(["html","xml"]))` で、これは
    テンプレ名の拡張子で判定する。`fragment.html.j2` は `.j2` 終端のため autoescape は
    無効、という事実を固定する(本番フローと同じ挙動)。
    """
    env = render._build_env()
    assert env.autoescape("fragment.html.j2") is False
    # `.html` / `.xml` 終端のテンプレ名なら有効になる(ポリシー自体の確認)
    assert env.autoescape("foo.html") is True
    assert env.autoescape("foo.xml") is True


def test_chart_config_rendered_raw_via_safe() -> None:
    """chart_config は `| safe` 指定のため、JSON 文字列がそのまま埋め込まれる。"""
    env = render._build_env()
    template = env.get_template("fragment.html.j2")
    chart_json = json.dumps({"type": "line", "data": {}}, ensure_ascii=False)

    html = _render_minimal(template, title="x", chart_json=chart_json)

    # `| safe` なのでクォート等がエスケープされず生 JSON が残る
    assert chart_json in html
    assert "&quot;" not in chart_json  # 前提: 生 JSON にはエスケープ実体が無い


def test_html_template_name_escapes_title() -> None:
    """同テンプレ内容でも `.html` 名で読み込めば autoescape が効き title がエスケープされる。

    autoescape ポリシーが実際に文字列をエスケープすることを、ポリシーに沿う名前で確認する
    (fragment.html.j2 をそのままコピーした一時テンプレを `.html` 名でロードする)。
    """
    from jinja2 import DictLoader

    src = (render.TEMPLATES / "fragment.html.j2").read_text(encoding="utf-8")
    escaping_env = render._build_env()
    escaping_env.loader = DictLoader({"fragment.html": src})
    template = escaping_env.get_template("fragment.html")

    chart_json = json.dumps({"type": "line", "data": {}}, ensure_ascii=False)
    html = _render_minimal(template, title="<b>x</b>", chart_json=chart_json)

    # `.html` 名なので autoescape が有効: title の HTML タグはエスケープされる
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html
    # chart_config は `| safe` のため、autoescape 有効下でも生 JSON のまま
    assert chart_json in html
