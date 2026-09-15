"""
Testy dokumentového enginu na reálných šablonách.

Nejdůležitější test je `test_structure_preserved`: dokazuje, že generování
nezmění nic, co nemá – počet odstavců, tabulek, sekcí, obrázků, stylů
ani text v záhlaví. To je celé odůvodnění zvoleného postupu (bod 31).

Spuštění:  pytest -q  (vyžaduje šablony v data/templates/)
"""
from __future__ import annotations

import os
from pathlib import Path

import docx
import pytest

from app.parser import parse_template
from app.render import render, values_from_manifest

TEMPLATES = Path(os.environ.get("FVE_TEMPLATES", "data/templates"))
V1_TZ = TEMPLATES / "V1" / "D.2.2-TZ-FVE-MS Tichá.docx"

pytestmark = pytest.mark.skipif(
    not V1_TZ.exists(), reason="šablony nejsou k dispozici"
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return parse_template(V1_TZ)


def _stats(path: Path) -> dict:
    d = docx.Document(str(path))
    styles: set[str] = {p.style.name for p in d.paragraphs if p.text.strip()}
    return {
        "paragraphs": len(d.paragraphs),
        "tables": len(d.tables),
        "sections": len(d.sections),
        "images": len(d.inline_shapes),
        "styles": len(styles),
        "header": d.sections[0].header.paragraphs[0].text.strip(),
    }


def _highlight_count(path: Path) -> int:
    d = docx.Document(str(path))
    n = sum(1 for p in d.paragraphs for r in p.runs if r.font.highlight_color)
    n += sum(
        1
        for t in d.tables
        for row in t.rows
        for c in row.cells
        for p in c.paragraphs
        for r in p.runs
        if r.font.highlight_color
    )
    return n


def test_parser_finds_roles(manifest: dict) -> None:
    assert manifest["stats"]["variables"] > 100
    assert manifest["stats"]["mapped_variables"] >= 30
    # zežloutlé popisky se nesmí stát proměnnou (Q-26)
    texts = [s["text"].strip() for s in manifest["suspect_labels"]]
    assert "ZHOTOVITEL:" in texts


def test_structure_preserved(manifest: dict, tmp_path: Path) -> None:
    out = tmp_path / "out.docx"
    values = values_from_manifest(manifest, {"pv.count": "40 ks"})
    render(V1_TZ, out, values)
    assert _stats(out) == _stats(V1_TZ)


def test_values_replaced(manifest: dict, tmp_path: Path) -> None:
    out = tmp_path / "out.docx"
    data = {"pv.panel.wp": "550 Wp", "pv.count": "40 ks"}
    report = render(V1_TZ, out, values_from_manifest(manifest, data))
    assert report.filled >= 2
    text = "\n".join(
        c.text for t in docx.Document(str(out)).tables for row in t.rows for c in row.cells
    )
    assert "550 Wp" in text
    assert "40 ks" in text


def test_unfilled_stay_highlighted(manifest: dict, tmp_path: Path) -> None:
    """
    Nevyplněná proměnná musí zůstat zvýrazněná. Kdyby se zvýraznění
    smazalo, stará hodnota ze šablony by v dokumentu vypadala jako
    platný údaj konkrétního projektu.
    """
    out = tmp_path / "out.docx"
    values = values_from_manifest(manifest, {"pv.count": "40 ks"})
    report = render(V1_TZ, out, values)
    assert report.unfilled, "test nedává smysl, kdyby bylo vyplněno vše"
    assert _highlight_count(out) == _highlight_count(V1_TZ) - report.cleared


def test_no_invented_values(manifest: dict, tmp_path: Path) -> None:
    """Bez dat se nesmí nic vyplnit (bod 29)."""
    out = tmp_path / "out.docx"
    report = render(V1_TZ, out, {})
    assert report.filled == 0
    assert _highlight_count(out) == _highlight_count(V1_TZ)


# --------------------------------------------------------------- navázání

SAMPLE_PROJECT = {
    "pv.count": "40 ks",
    "pv.panel.wp": "550 Wp",
    "pv.panel.model": "AIKO Comet 3N",
    "pv.panel.vmp": "41,20 V",
    "pv.panel.imp": "13,21 A",
    "energy.p_dc_kwp": "22,0 kWp",
    "pv.inverters.0.model": "SUN-20K-SG01HP3",
    "pv.inverters.0.p_ac_va": "20 000 VA",
    "pv": {
        "panel": {"manufacturer": "AIKO", "wp": 670, "vmp": 41.2, "imp": 13.21},
        "inverters": [{"label": "INV1", "p_ac_kw": 20.0}],
        "optimizers": {"model": "S500B"},
        "orientation": [
            {"azimuth": 95, "count": 20},
            {"azimuth": 275, "count": 20},
        ],
        "strings": [
            {"id": "1.1", "panel_count": 14, "inverter": "INV1"},
            {"id": "1.2", "panel_count": 13, "inverter": "INV1"},
            {"id": "1.3", "panel_count": 13, "inverter": "INV1"},
        ],
    },
    "site": {"building": {"roof_tilt_deg": 3, "roof_covering": "Trapézový plech"}},
}


def _render_sample(manifest: dict, tmp_path: Path) -> Path:
    from app.binder import rewrite_free_text, rewrite_unmarked
    from app.sequences import compute_strings

    out = tmp_path / "sample.docx"
    values = values_from_manifest(manifest, SAMPLE_PROJECT)
    free_text, _ = rewrite_free_text(manifest, SAMPLE_PROJECT)
    values.update(free_text)
    unmarked, _ = rewrite_unmarked(manifest, SAMPLE_PROJECT)
    values.update(unmarked)
    render(
        V1_TZ,
        out,
        values,
        strings=compute_strings(SAMPLE_PROJECT),
        project=SAMPLE_PROJECT,
    )
    return out


def _all_text(path: Path) -> str:
    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs]
    parts += [
        c.text for t in d.tables for row in t.rows for c in row.cells
    ]
    return "\n".join(parts)


def test_strings_follow_project(manifest: dict, tmp_path: Path) -> None:
    """Tři stringy v projektu → tři řádky ve výpisu i v tabulce."""
    text = _all_text(_render_sample(manifest, tmp_path))
    assert text.count("ks FV panelů– string") == 3
    assert "14 ks FV panelů– string 1.1" in text
    assert "1.4" not in text, "string ze šablony zůstal v dokumentu"


def test_string_enumerations_match(manifest: dict, tmp_path: Path) -> None:
    """Výčty označení stringů v textu sedí s konfigurací."""
    text = _all_text(_render_sample(manifest, tmp_path))
    assert "stringu 1.1 až 1.3" in text
    assert "stringů 1.1 až 1.3" in text
    assert "1.1 až 1.4" not in text


def test_orientation_sums_to_count(manifest: dict, tmp_path: Path) -> None:
    """
    Věta o orientaci se skládá z dat, takže součet sedí.
    V šabloně je tenhle údaj chybný (42 + 42 při 100 panelech).
    """
    text = _all_text(_render_sample(manifest, tmp_path))
    assert "20 panelů je orientováno na východ" in text
    assert "20 panelů je orientováno na západ" in text
    assert "42 panelů" not in text


def test_inverter_replaced_everywhere(manifest: dict, tmp_path: Path) -> None:
    """Typ střídače se změní i uvnitř věty, nejen v tabulce."""
    text = _all_text(_render_sample(manifest, tmp_path))
    assert "SUN-20K-SG01HP3" in text
    assert "SE33,3K" not in text
    assert "Solar Edge" not in text


def test_roof_covering_declension(manifest: dict, tmp_path: Path) -> None:
    text = _all_text(_render_sample(manifest, tmp_path))
    assert "s krytinou z trapézového plechu" in text


def test_normative_text_untouched(manifest: dict, tmp_path: Path) -> None:
    """
    Citace normy se nesmí přepsat, i když obsahuje číslo, které se
    v projektu vyskytuje jako parametr (1000 V).
    """
    text = _all_text(_render_sample(manifest, tmp_path))
    assert "do 1000 V na straně AC" in text
    assert "2 DC  1000 V/IT" in text
