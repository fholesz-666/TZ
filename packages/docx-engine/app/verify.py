"""
Kontrola hotového dokumentu.

Pre-flight hlídá data před generováním; tohle hlídá výsledek. Hledá jedinou
věc, ale tu nejzákeřnější: **hodnotu ze šablony, která v dokumentu zůstala**,
přestože projekt má jinou. Přesně takhle vznikl v podkladech panel z jiného
projektu, 44 kWp u Sauny i 28 V ve všech pěti technických zprávách.

Kontrola čte celý text včetně neoznačených částí, záhlaví a tabulek, protože
zapomenutá hodnota se nejčastěji schovává právě ve fixním textu.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import docx

from .binder import FIXED_TEXT_SAFE, _pattern_for, _squash, build_pairs


@dataclass
class Leftover:
    key: str
    value: str
    expected: str
    where: str
    context: str


@dataclass
class VerifyReport:
    leftovers: list[Leftover] = field(default_factory=list)
    highlighted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.leftovers

    def summary(self) -> dict[str, Any]:
        return {
            "leftovers": len(self.leftovers),
            "highlighted_segments": len(self.highlighted),
        }


def _document_texts(path: str | Path) -> list[tuple[str, str]]:
    doc = docx.Document(str(path))
    out: list[tuple[str, str]] = []
    for i, sec in enumerate(doc.sections):
        for name, part in ((f"záhlaví {i}", sec.header), (f"zápatí {i}", sec.footer)):
            for par in part.paragraphs:
                if par.text.strip():
                    out.append((name, par.text))
    for n, par in enumerate(doc.paragraphs):
        if par.text.strip():
            out.append((f"odstavec {n}", par.text))
    for t, table in enumerate(doc.tables):
        for r, row in enumerate(table.rows):
            for c, cell in enumerate(row.cells):
                if cell.text.strip():
                    out.append((f"tabulka {t}, řádek {r}, sloupec {c}", cell.text))
    return out


def _highlighted(path: str | Path) -> list[str]:
    doc = docx.Document(str(path))
    out: list[str] = []
    for par in doc.paragraphs:
        for run in par.runs:
            if run.font.highlight_color is not None and run.text.strip():
                out.append(run.text.strip())
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for par in cell.paragraphs:
                    for run in par.runs:
                        if run.font.highlight_color is not None and run.text.strip():
                            out.append(run.text.strip())
    return out


def verify(
    output_path: str | Path, manifest: dict[str, Any], data: dict[str, str]
) -> VerifyReport:
    """
    Projde vygenerovaný dokument a ohlásí hodnoty, které patří šabloně,
    ne tomuto projektu.
    """
    report = VerifyReport(highlighted=_highlighted(output_path))
    pairs = build_pairs(manifest, data)
    if not pairs:
        return report

    # Co se hlídá:
    #  * krátké tvary ne – „40“ může být v dokumentu legitimně cokoli;
    #  * tvary, které se od nové hodnoty liší jen mezerami, taky ne –
    #    „1 000 V“ a „1 000 V“ je tatáž hodnota;
    #  * čistě číselné údaje jen u klíčů, které jsou jednoznačně projektové.
    #    Věta „ochrana … do 1000 V na straně AC“ cituje normu a nesmí
    #    se hlásit jako zapomenutá hodnota střídače.
    watched: list[tuple[str, str, str]] = []
    for key, old, new in pairs:
        if len(old) < 5 or _squash(old) == _squash(new):
            continue
        if not any(ch.isalpha() for ch in old.replace(" ", "")) and key not in FIXED_TEXT_SAFE:
            continue
        numeric_only = not any(ch.isalpha() for ch in old[:-3])
        if numeric_only and key not in FIXED_TEXT_SAFE:
            continue
        watched.append((key, old, new))

    for where, text in _document_texts(output_path):
        for key, old, new in watched:
            if new and new in text:
                continue  # na tomhle místě už je nová hodnota
            m = _pattern_for(old).search(text)
            if m:
                report.leftovers.append(
                    Leftover(
                        key=key,
                        value=old,
                        expected=new,
                        where=where,
                        context=text[max(0, m.start() - 40) : m.end() + 40].strip(),
                    )
                )
    return report
