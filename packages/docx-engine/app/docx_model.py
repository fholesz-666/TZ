"""
Společné pomůcky pro práci s OOXML.

Klíčová zásada celého enginu: originální .docx se nikdy neskládá znovu.
Vždy se otevře, zmutuje se obsah konkrétních runů a uloží se zpět.
Tím zůstane zachováno záhlaví, zápatí, razítková tabulka, styly,
číslování, stránkování i vše, co v souboru je a o čem nevíme.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

SegmentKind = Literal["fixed", "variable", "generated"]

# Zvýraznění → role. Bod 7 zadání.
YELLOW = {"YELLOW"}
GREEN = {"BRIGHT_GREEN", "GREEN", "TURQUOISE", "TEAL"}


def run_kind(run) -> SegmentKind:
    """Role runu podle barvy zvýraznění."""
    hl = run.font.highlight_color
    if hl is None:
        return "fixed"
    # str(WD_COLOR_INDEX.BRIGHT_GREEN) je "BRIGHT_GREEN (4)", proto
    # porovnáváme podřetězcem, ne rovností.
    name = str(hl).upper()
    if any(n in name for n in YELLOW):
        return "variable"
    if any(n in name for n in GREEN):
        return "generated"
    # Jiná barva zvýraznění není v konvenci definovaná – bereme ji jako
    # proměnnou a označíme ke kontrole (parser to zapíše do `warnings`).
    return "variable"


def iter_block_items(parent) -> Iterator[Paragraph | Table]:
    """Odstavce a tabulky v pořadí, v jakém jsou v dokumentu."""
    if isinstance(parent, DocxDocument):
        el = parent.element.body
    elif isinstance(parent, _Cell):
        el = parent._tc
    else:  # header / footer part
        el = parent._element
    for child in el.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def clear_highlight(run) -> None:
    """Odstraní zvýraznění, ostatní formátování runu nechá být."""
    rPr = run._r.find(qn("w:rPr"))
    if rPr is None:
        return
    for tag in ("w:highlight", "w:shd"):
        node = rPr.find(qn(tag))
        if node is not None:
            rPr.remove(node)


def set_run_text(run, text: str) -> None:
    """
    Nastaví text runu a zachová jeho formátování.
    Prázdný text run nemaže – zůstane prázdný, aby nezmizel jeho rPr
    a nerozpadlo se okolní formátování.
    """
    run.text = text


@dataclass
class Segment:
    """Souvislý úsek textu jedné role uvnitř odstavce."""

    index: int
    kind: SegmentKind
    text: str
    run_indices: list[int]
    # vyplní parser
    key: str | None = None
    label: str | None = None
    suspect_label: bool = False

    @property
    def id(self) -> str:
        return f"s{self.index}"


@dataclass
class ParagraphNode:
    path: str
    style: str | None
    segments: list[Segment]
    text: str

    @property
    def has_role(self) -> bool:
        return any(s.kind != "fixed" for s in self.segments)


@dataclass
class TableNode:
    path: str
    rows: int
    cols: int
    cells: list[ParagraphNode] = field(default_factory=list)
    repeatable_rows: list[int] = field(default_factory=list)
