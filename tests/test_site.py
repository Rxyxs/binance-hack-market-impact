"""The published page is generated: it must equal what site.build makes from the results."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_page_is_regenerated_from_results():
    from bhack import site
    results = json.loads((ROOT / "reports" / "results.json").read_text(encoding="utf-8"))
    committed = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert site.build(results) == committed


def test_page_has_both_languages_for_every_section():
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    for n in range(1, 12):
        assert f'<span class="num">{n:02d}</span>' in page
    assert page.count('lang="es"') > 40 and page.count('lang="en"') > 40
