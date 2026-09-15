"""
Generování dokumentu: naplnění anotované šablony daty projektu.

Princip (bod 31 zadání): originální .docx se otevře, zmutuje se obsah
konkrétních runů a uloží se pod novým jménem. Dokument se nikdy neskládá
znovu, takže záhlaví, zápatí, razítková tabulka, styly, číslování,
stránkování ani nic dalšího nemůže odejít.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .docx_model import clear_highlight, iter_block_items, run_kind, set_run_text
from .parser import _segments_of


@dataclass
class RenderReport:
    filled: int = 0
    cleared: int = 0
    missing_paths: list[str] = None  # type: ignore[assignment]
    unfilled: list[dict[str, Any]] = None  # type: ignore[assignment]
    string_lines: int = 0
    string_rows: int = 0
    orientation_lines: int = 0
    string_enums: int = 0
    cable_rows: int = 0

    def __post_init__(self) -> None:
        self.missing_paths = self.missing_paths or []
        self.unfilled = self.unfilled or []


def build_path_index(doc) -> dict[str, Paragraph]:
    """
    Mapa cesta → odstavec. Prochází dokument přesně stejně jako parser,
    aby cesty v manifestu ukazovaly na tytéž odstavce.
    """
    index: dict[str, Paragraph] = {}

    def walk(parent, prefix: str) -> None:
        p_i = t_i = 0
        for block in iter_block_items(parent):
            if isinstance(block, Paragraph):
                index[f"{prefix}/p{p_i}"] = block
                p_i += 1
            else:
                table: Table = block
                path = f"{prefix}/tbl{t_i}"
                t_i += 1
                for r, row in enumerate(table.rows):
                    for c, cell in enumerate(row.cells):
                        for k, cp in enumerate(cell.paragraphs):
                            index[f"{path}/r{r}/c{c}/p{k}"] = cp

    for i, sec in enumerate(doc.sections):
        walk(sec.header, f"hdr{i}")
        walk(sec.footer, f"ftr{i}")
    walk(doc, "body")
    return index


def _apply_to_paragraph(par: Paragraph, values: dict[int, str], report: RenderReport) -> None:
    """
    Naplní segmenty odstavce. Text jde do prvního runu segmentu,
    ostatní runy segmentu se vyprázdní – tím zmizí rozsekání hodnoty
    na „5“ + „0“ + „0“ + „ “ + „Wp“, které vzniklo ručním psaním.
    """
    segments = _segments_of(par)
    runs = par.runs
    for seg in segments:
        new = values.get(seg.index)
        if seg.kind == "fixed":
            # Fixní text se přepisuje jen tam, kde se v něm našla hodnota
            # tohoto projektu (zapomenuté zvýraznění, bod 62). Každá taková
            # změna je v soupisu `unmarked_in_fixed`.
            if new is None:
                continue
        new = values.get(seg.index)
        if new is None:
            # Nevyplněný segment zůstane zvýrazněný. Kdyby se zvýraznění
            # smazalo, stará hodnota ze šablony by v dokumentu vypadala
            # jako platný údaj – přesně to bod 50 zakazuje.
            report.unfilled.append(
                {"segment": seg.index, "kind": seg.kind, "text": seg.text[:80]}
            )
            continue
        first = True
        for ri in seg.run_indices:
            if ri >= len(runs):
                continue
            run = runs[ri]
            set_run_text(run, new if first else "")
            first = False
            clear_highlight(run)
            report.cleared += 1
        report.filled += 1


def _mark_fields_dirty(doc) -> None:
    """
    Řekne Wordu, ať při otevření přepočítá pole (obsah, křížové odkazy,
    stránkování). Bez toho by v obsahu zůstala stará čísla stránek.
    """
    settings = doc.settings.element
    tag = qn("w:updateFields")
    node = settings.find(tag)
    if node is None:
        node = settings.makeelement(tag, {qn("w:val"): "true"})
        settings.append(node)
    else:
        node.set(qn("w:val"), "true")


def render(
    template_path: str | Path,
    output_path: str | Path,
    values: dict[str, str],
    strings: list[dict[str, Any]] | None = None,
    project: dict[str, Any] | None = None,
) -> RenderReport:
    """
    `values` je mapa "cesta#segment" → text, například:
        {"body/tbl1/r5/c1/p0#1": "40 ks"}
    Tuhle mapu skládá backend z projektových dat a manifestu šablony.
    """
    doc = docx.Document(str(template_path))
    index = build_path_index(doc)
    report = RenderReport()

    by_path: dict[str, dict[int, str]] = {}
    for ref, text in values.items():
        path, _, seg = ref.partition("#")
        by_path.setdefault(path, {})[int(seg)] = text

    for path, par in index.items():
        if not par.runs:
            continue
        vals = by_path.get(path, {})
        if not vals and not any(run_kind(r) != "fixed" for r in par.runs if r.text):
            continue
        _apply_to_paragraph(par, vals, report)

    for path in by_path:
        if path not in index:
            report.missing_paths.append(path)

    if strings:
        # Opakující se bloky až nakonec – mění počet odstavců a řádků,
        # takže by rozhodily cesty v `index`.
        from .sequences import (
            apply_dc_cable_rows,
            apply_orientation,
            apply_string_enumerations,
            apply_string_list,
            apply_string_table,
        )

        report.string_lines = apply_string_list(doc, strings)
        report.string_rows = apply_string_table(doc, strings)
        report.string_enums = apply_string_enumerations(doc, strings)
        report.cable_rows = apply_dc_cable_rows(doc, strings)
        if project is not None:
            report.orientation_lines = apply_orientation(doc, project, strings)

    _mark_fields_dirty(doc)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return report


def values_from_manifest(manifest: dict[str, Any], data: dict[str, str]) -> dict[str, str]:
    """
    Manifest + hodnoty podle klíčů → mapa pro `render`.
    Klíč, který v `data` není, se nevyplní; segment zůstane s původním
    textem a generátor ho ohlásí v `unfilled`. Nikdy se nedoplňuje
    vymyšlená hodnota (bod 29).
    """
    primary = {v["key"]: v for v in manifest["variables"] if "#" not in v["key"]}
    out: dict[str, str] = {}
    for var in manifest["variables"]:
        base = var["key"].split("#")[0]
        if base not in data:
            continue
        if "#" in var["key"]:
            # Odvozená varianta se vyplní jen tehdy, když v šabloně nesla
            # tutéž hodnotu jako primární pole. Jinak je to jiný údaj,
            # který se omylem chytil na stejný popisek, a musí zůstat
            # nevyřešený (bod 50).
            ref = primary.get(base)
            if not ref or ref["sample_values"][:1] != var["sample_values"][:1]:
                continue
        text = data[base]
        for occ in var["occurrences"]:
            out[f"{occ['path']}#{occ['segment']}"] = text
    return out


def main() -> None:  # pragma: no cover
    import sys

    from .binder import rewrite_free_text, rewrite_unmarked

    template, manifest_file, data_file, output = sys.argv[1:5]
    manifest = json.loads(Path(manifest_file).read_text(encoding="utf-8"))
    data = json.loads(Path(data_file).read_text(encoding="utf-8"))

    from .sequences import compute_strings
    from .validate import preflight
    from .verify import verify

    values = values_from_manifest(manifest, data)
    free_text, bind = rewrite_free_text(manifest, data)
    values.update(free_text)
    unmarked_values, unmarked_hits = rewrite_unmarked(manifest, data)
    values.update(unmarked_values)
    strings = compute_strings(data)

    pf = preflight(data)
    if pf.errors and "--force" not in sys.argv:
        print("PRE-FLIGHT ZASTAVIL GENEROVÁNÍ:")
        for f in pf.findings:
            print("  ", f)
        print("\nOpravte data, nebo spusťte znovu s --force.")
        raise SystemExit(2)

    report = render(template, output, values, strings=strings, project=data)
    vr = verify(output, manifest, data)
    out = {
        "filled_from_keys": len(values) - len(free_text),
        "rewritten_in_text": bind.rewritten,
        "substitutions": len(bind.substitutions),
        "unmarked_in_fixed": len(unmarked_hits),
        "string_lines": report.string_lines,
        "string_rows": report.string_rows,
        "orientation_lines": report.orientation_lines,
        "string_enums": report.string_enums,
        "cable_rows": report.cable_rows,
        "cleared_highlights": report.cleared,
        "still_unresolved": len(report.unfilled),
        "missing_paths": report.missing_paths,
        "preflight_errors": len(pf.errors),
        "preflight_warnings": len(pf.warnings),
        "leftovers": len(vr.leftovers),
    }
    for f in pf.findings:
        print("  ", f)
    for lo in vr.leftovers[:10]:
        print(f"   ZŮSTALO  {lo.key}: {lo.value!r} → mělo být {lo.expected!r} ({lo.where})")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if len(sys.argv) > 5:
        Path(sys.argv[5]).write_text(
            json.dumps(
                {
                    "substitutions": [vars(s) for s in bind.substitutions],
                    "unmarked_in_fixed": unmarked_hits,
                    "preflight": [vars(f) for f in pf.findings],
                    "leftovers": [vars(l) for l in vr.leftovers],
                    "unresolved": report.unfilled,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":  # pragma: no cover
    main()
