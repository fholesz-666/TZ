"""
Import .docx šablony → anotovaná mapa (manifest).

Vstup:  originální .docx se žlutým a zeleným zvýrazněním.
Výstup: JSON manifest se seznamem bloků, segmentů a kandidátů na proměnné.

Originální soubor se NEMĚNÍ. Manifest odkazuje do dokumentu stabilními
cestami (`body/12`, `body/3/tbl/r2/c1/p0`), takže generátor umí najít
přesně ten run, který má naplnit.

Body zadání 7, 56–67: barva je primární indikace, ne jediný zdroj pravdy.
Parser proto u každého kandidáta vrací i `evidence` a `confidence`,
které doplní křížová analýza referenčních projektů (analyzer.py).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Any

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from .docx_model import ParagraphNode, Segment, iter_block_items, run_kind

# --------------------------------------------------------------------------
# Slovník známých popisků → klíč v datovém modelu projektu.
# Vychází z analýzy sad V1 / V2 / V3 (viz docs/01-analyza-podkladu.md).
# Neznámý popisek není chyba – vytvoří se kandidát s návrhem klíče
# a uživatel ho v průvodci importem potvrdí nebo přejmenuje.
# --------------------------------------------------------------------------
LABEL_TO_KEY: dict[str, str | None] = {
    # identifikace stavby
    "nazev": "meta.name",
    "nazev stavby": "meta.building_name",
    "nazev objektu": "meta.building_name",
    "nazev vyrobny": "meta.plant_name",
    "misto stavby": "site.address.full",
    "adresa vyrobny": "site.address.full",
    "umisteni vyrobny": "site.address.full",
    "katastralni uzemi": "site.cadastre.area",
    "obec": "site.address.municipality",
    "souradnice": "site.gps",
    "parcelni cisla instalace fv panelu a technologie fve": "site.cadastre.parcels",
    "predmet pd": "meta.subject",
    "predmet dokumentace": "meta.subject",
    "kraj": "site.address.region",
    "cislo zakazky": "meta.order_number",
    "datum": "meta.date",
    "stupen": "meta.stage",
    "format": "meta.sheet_format",
    "cast dokumentace": "meta.doc_code",
    "revize dok": "meta.revision",
    # účastníci
    "investor": "investor.name",
    "zhotovitel": "contractor.name",
    "vypracoval": "people.author",
    "kontroloval": "people.checker",
    "autorizoval": "people.authorizer",
    "projektant fve": "people.author",
    "autorizovana osoba": "people.authorizer",
    "zpracovatel": "company.name",
    "ico": "investor.ico",
    "cislo pare": "meta.copy_number",
    "dotacni fond": "subsidy.fund",
    "registracni cislo dotace": "subsidy.registration_number",
    "meritko": "meta.scale",
    "oznaceni dokumentu": "meta.doc_marking",
    "nazev vykresu dokumentu": "meta.doc_title",
    "podpis": None,  # podpisový řádek – nikdy proměnná
    "revize": "meta.revision",
    "predmet revize": "meta.revision_subject",
    "datum revize": "meta.revision_date",
    "revizi provedl": "meta.revision_author",
    # klima
    "snehova oblast": "site.climate.snow_zone",
    "vetrna oblast": "site.climate.wind_zone",
    # FV pole
    "celkovy pocet fv panelu": "pv.count",
    "pocet instalovanych panelu": "pv.count",
    "vykon jednoho fv panelu": "pv.panel.wp",
    "vykon instalovanych panelu": "pv.panel.wp",
    "celkovy instalovany vykon fve": "energy.p_dc_kwp",
    "celkovy instalovany vykon fv panelu": "energy.p_dc_kwp",
    "azimut fv panelu sever 0": "pv.orientation.summary",
    "sklon fv konstrukce": "construction.tilt_deg",
    "sklon fv panelu strechy": "site.building.roof_tilt_deg",
    "stresni krytina": "site.building.roof_covering",
    "stavajici fve": "site.building.existing_pv",
    "instalovany vykon stavajici fve": "site.building.existing_pv_kwp",
    "pocet instalovanych stridacu": "pv.inverters.count",
    "vykon stridacu na ac strane": "energy.p_ac_kw",
    "cislo smlouvy o pripojeni distributor fve": "electrical.grid.contract_number",
    # panel / střídač – tabulky parametrů
    "oznaceni": "pv.panel.model",
    "jmenovity vykon": "pv.panel.wp",
    "jmenovite napeti": "pv.panel.vmp",
    "jmenovity proud": "pv.panel.imp",
    "ucinnost modulu": "pv.panel.efficiency",
    "rozmery v x s x h": "pv.panel.dimensions",
    "plocha modulu": "pv.panel.area",
    "typove oznaceni": "pv.inverters.0.model",
    "max vystupni ac vykon": "pv.inverters.0.p_ac_va",
    "max vystupni ac proud": "pv.inverters.0.i_ac_max",
    "max vstupni dc proud": "pv.inverters.0.i_dc_max",
    "max vstupni napeti": "pv.inverters.0.u_dc_max",
    "max vstupni dc vykon": "pv.inverters.0.p_dc_max",
    "euro ucinnost": "pv.inverters.0.efficiency",
    "rozmery menice v x s x h": "pv.inverters.0.dimensions",
    "vyrobce": "pv.panel.manufacturer",
    "typ": "pv.inverters.0.model",
    "kapacita": "pv.battery.capacity_kwh",
    "vyuzitelna kapacita": "pv.battery.usable_kwh",
    "celkovy pocet": "pv.battery.count",
    # energetika
    "instalovany vykon na strane dc": "energy.p_dc_kwp",
    "strana ac vystup ze stridace": "energy.p_ac_kw",
    "prepokladana rocni vyroba": "energy.annual_yield",
    "spotreba objektu za rok": "energy.consumption_mwh",
    "prima vlastni spotreba": "energy.self_consumption_mwh",
    "spotreba prebytku": "energy.surplus_use_mwh",
    "zahajeni vystavby": "meta.build_start",
    "ukonceni vystavby": "meta.build_end",
    "predpokladane naklady": "meta.cost",
    "plocha strechy zastavena fve": "site.building.pv_area_m2",
}

# Tabulka „Seznam strojů“ má popisek v prvním sloupci a dvě různé hodnoty
# vedle sebe (Označení | Počet), takže klíč musí znát i číslo sloupce.
ROW_COL_TO_KEY: dict[tuple[str, int], str] = {
    ("fotovoltaicky panel", 1): "pv.panel.wp",
    ("fotovoltaicky panel", 2): "pv.count",
    ("fv panel", 1): "pv.panel.wp",
    ("fv panel", 2): "pv.count",
    ("optimizer", 1): "pv.optimizers.model",
    ("optimizer", 2): "pv.optimizers.count",
    ("stridac", 1): "pv.inverters.0.model",
    ("stridac", 2): "pv.inverters.0.count",
    ("menic", 1): "pv.inverters.0.model",
    ("menic", 2): "pv.inverters.0.count",
    ("baterie", 1): "pv.battery.model",
    ("baterie", 2): "pv.battery.count",
    ("rozvadec rac", 1): "electrical.rac.spec",
    ("rozvadec rac", 2): "electrical.rac.count",
    ("rozvadec rdc", 1): "electrical.rdc.spec",
    ("rozvadec rdc", 2): "electrical.rdc.count",
}

# Popisky, které byly omylem zvýrazněné (bod Q-26) – při importu se
# nestanou proměnnou, jen se označí.
LABEL_SUSPECTS = re.compile(
    r"^(?:"
    r"[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ \-/]{2,}:"   # VELKÁ PÍSMENA zakončená dvojtečkou
    r"|String\s*č\.?"
    r"|Parametry\s+jednotliv\w+\s+string\w+:?"
    r"|Počet\s*\(ks\)"
    r"|Název\s+položky"
    r")\s*$"
)

# Maximální délka textu, který ještě bereme jako popisek proměnné.
# Delší text je věta, ne popisek – proměnná pak zůstane nenamapovaná
# a uživatel ji naváže v průvodci importem.
MAX_LABEL_LEN = 60


def _norm(s: str) -> str:
    """Popisek → porovnatelný tvar: bez diakritiky, malá písmena, bez interpunkce."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(" ", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def suggest_key(label: str | None) -> str | None:
    if not label:
        return None
    n = _norm(label)
    if n in LABEL_TO_KEY:
        return LABEL_TO_KEY[n]
    # zkusit bez koncového dvojtečkového zbytku a bez závorek
    n2 = _norm(re.sub(r"\(.*?\)", "", label))
    return LABEL_TO_KEY.get(n2)


def _segments_of(par: Paragraph) -> list[Segment]:
    """Runy odstavce → souvislé segmenty jedné role."""
    segments: list[Segment] = []
    for idx, run in enumerate(par.runs):
        if run.text == "":
            continue
        kind = run_kind(run)
        if segments and segments[-1].kind == kind:
            segments[-1].text += run.text
            segments[-1].run_indices.append(idx)
        else:
            segments.append(
                Segment(index=len(segments), kind=kind, text=run.text, run_indices=[idx])
            )
    return segments


def _label_for(par: Paragraph, seg: Segment, row_label: str | None) -> str | None:
    """
    Popisek proměnné. Priorita:
      1) první buňka řádku tabulky ("Celkový počet FV panelů | «100 ks»")
      2) fixní text před segmentem v témže odstavci ("Název stavby: «…»")
    """
    if row_label:
        return row_label.strip(" :\t")
    before = "".join(s.text for s in par_segments_before(par, seg)).strip()
    if not before:
        return None
    # Popisek uznáme jen tam, kde je oddělený dvojtečkou nebo tabulátorem –
    # jinak by se jako "popisek" tvářila celá předchozí věta.
    m = re.split(r"[:\t]", before)
    if len(m) < 2:
        return None
    cand = next((part.strip() for part in reversed(m[:-1]) if part.strip()), "")
    if not cand or len(cand) > MAX_LABEL_LEN:
        return None
    return cand


_PAR_SEG_CACHE: dict[int, list[Segment]] = {}


def par_segments_before(par: Paragraph, seg: Segment) -> list[Segment]:
    segs = _PAR_SEG_CACHE.get(id(par._p), [])
    return [s for s in segs if s.index < seg.index and s.kind == "fixed"]


def parse_paragraph(
    par: Paragraph, path: str, row_label: str | None = None, col: int | None = None
) -> ParagraphNode:
    segs = _segments_of(par)
    _PAR_SEG_CACHE[id(par._p)] = segs
    for s in segs:
        if s.kind == "fixed":
            continue
        if LABEL_SUSPECTS.match(s.text.strip()):
            s.suspect_label = True
            continue
        s.label = _label_for(par, s, row_label)
        s.key = None
        if col is not None and s.label:
            s.key = ROW_COL_TO_KEY.get((_norm(s.label), col))
        if s.key is None:
            s.key = suggest_key(s.label)
    style = par.style.name if par.style is not None else None
    return ParagraphNode(path=path, style=style, segments=segs, text=par.text)


def parse_container(parent, prefix: str, out: list[dict[str, Any]]) -> None:
    p_i = t_i = 0
    for block in iter_block_items(parent):
        if isinstance(block, Paragraph):
            path = f"{prefix}/p{p_i}"
            p_i += 1
            if not block.text.strip():
                continue
            node = parse_paragraph(block, path)
            out.append(_node_dict(node, "paragraph"))
        else:  # Table
            path = f"{prefix}/tbl{t_i}"
            t_i += 1
            table: Table = block
            grid = _text_grid(table)
            rows_out: list[dict[str, Any]] = []
            for r, row in enumerate(table.rows):
                first_cell_text = grid[r][0] if grid[r] else ""
                if len(first_cell_text) > MAX_LABEL_LEN:
                    first_cell_text = ""
                cells_out = []
                for c, cell in enumerate(row.cells):
                    cell_pars = []
                    for k, cp in enumerate(cell.paragraphs):
                        if not cp.text.strip():
                            continue
                        if len(table.columns) <= 3:
                            # tabulka popisek | hodnota
                            label = first_cell_text if c > 0 else None
                        else:
                            found = _cell_label(grid, r, c)
                            label = None if found == BLOCKED else found
                        node = parse_paragraph(
                            cp, f"{path}/r{r}/c{c}/p{k}", row_label=label, col=c
                        )
                        cell_pars.append(_node_dict(node, "paragraph"))
                    cells_out.append({"col": c, "paragraphs": cell_pars})
                rows_out.append(
                    {"row": r, "label": first_cell_text, "cells": cells_out}
                )
            out.append(
                {
                    "type": "table",
                    "path": path,
                    "rows": len(table.rows),
                    "cols": len(table.columns),
                    "repeatable_rows": detect_repeatable_rows(rows_out),
                    "content": rows_out,
                }
            )


def _text_grid(table: Table) -> list[list[str]]:
    return [[c.text.strip() for c in row.cells] for row in table.rows]


_COLON_LABEL = re.compile(r"^(.{2,%d}?):\s*$" % MAX_LABEL_LEN)


BLOCKED = "\x00blocked"


def _cell_label(grid: list[list[str]], r: int, c: int, lookback: int = 4) -> str | None:
    """
    Popisek buňky v široké tabulce (razítko má 5 sloupců).

      1) buňka vlevo v témže řádku, pokud končí dvojtečkou a není to
         jen sloučená buňka roztažená z prvního sloupce
         ("DATUM: | 7/2026", "ČÍSLO ZAKÁZKY: | 25JAB102")
      2) buňka nad ní ve stejném sloupci
         ("INVESTOR:" stojí nad názvem i adresou, ne vedle nich)

    Vrací BLOCKED, když nad buňkou stojí jiná hodnota – buňka pak patří
    do svislého bloku a popisek z prvního sloupce řádku by byl cizí.
    Bez toho by se „602 00 Brno“ ze sloupce ZHOTOVITEL napojilo na
    popisek INVESTOR z téhož řádku.

    Tabulky se dvěma až třemi sloupci (popisek | hodnota) tudy nechodí –
    tam platí jednodušší pravidlo „popisek je první buňka řádku“.
    """
    row = grid[r] if r < len(grid) else []
    first = row[0] if row else ""
    for cc in range(c - 1, 0, -1):
        txt = row[cc] if cc < len(row) else ""
        if not txt or txt == first:  # sloučená buňka z prvního sloupce
            continue
        m = _COLON_LABEL.match(txt)
        if m:
            return m.group(1).strip()
        break

    seen: set[str] = set()
    for rr in range(r - 1, max(-1, r - 1 - lookback), -1):
        if c >= len(grid[rr]):
            continue
        txt = grid[rr][c]
        if not txt or txt in seen:
            continue
        seen.add(txt)
        m = _COLON_LABEL.match(txt)
        if m:
            return m.group(1).strip()
        if len(txt) > 2:
            return BLOCKED
    return None


def _node_dict(node: ParagraphNode, typ: str) -> dict[str, Any]:
    return {
        "type": typ,
        "path": node.path,
        "style": node.style,
        "text": node.text,
        "segments": [asdict(s) for s in node.segments],
    }


def detect_repeatable_rows(rows_out: list[dict[str, Any]]) -> list[int]:
    """
    Řádek je opakovatelný, pokud má stejný tvar jako sousední řádek
    a obsahuje proměnné. Typicky tabulka stringů a tabulka kabeláže:
    generátor takový řádek naklonuje podle počtu položek a tím zachová
    formátování (bod 31).
    """
    shapes: list[tuple[str, bool]] = []
    for r in rows_out:
        has_var = any(
            s["kind"] == "variable"
            for c in r["cells"]
            for p in c["paragraphs"]
            for s in p["segments"]
        )
        shape = "|".join(
            "".join(
                s["kind"][0] for p in c["paragraphs"] for s in p["segments"]
            )
            for c in r["cells"]
        )
        shapes.append((shape, has_var))
    out: list[int] = []
    for i, (shape, has_var) in enumerate(shapes):
        if not has_var or not shape:
            continue
        same_prev = i > 0 and shapes[i - 1][0] == shape
        same_next = i + 1 < len(shapes) and shapes[i + 1][0] == shape
        if same_prev or same_next:
            out.append(i)
    return out


def parse_template(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    doc = docx.Document(str(path))
    blocks: list[dict[str, Any]] = []
    for i, sec in enumerate(doc.sections):
        parse_container(sec.header, f"hdr{i}", blocks)
        parse_container(sec.footer, f"ftr{i}", blocks)
    parse_container(doc, "body", blocks)

    variables: dict[str, dict[str, Any]] = {}
    generated: list[dict[str, Any]] = []
    suspects: list[dict[str, Any]] = []

    def walk(items: list[dict[str, Any]]):
        for b in items:
            if b["type"] == "table":
                for r in b["content"]:
                    for c in r["cells"]:
                        walk(c["paragraphs"])
                continue
            for s in b["segments"]:
                ref = {"path": b["path"], "segment": s["index"], "text": s["text"]}
                if s.get("suspect_label"):
                    suspects.append({**ref, "reason": "zvýrazněný popisek"})
                elif s["kind"] == "variable":
                    base = s.get("key") or f"unmapped.{len(variables)}"
                    val = s["text"].strip()
                    # Jeden popisek může v razítku nést víc řádků
                    # (INVESTOR: název / adresa). Druhý a další výskyt
                    # s jinou hodnotou dostane příponu a uživatel ho
                    # v průvodci importem dováže.
                    key = base
                    n = 1
                    while key in variables and val not in variables[key]["sample_values"]:
                        n += 1
                        key = f"{base}#{n}"
                    v = variables.setdefault(
                        key,
                        {
                            "key": key,
                            "label": s.get("label"),
                            "mapped": bool(s.get("key")) and n == 1,
                            "needs_binding": bool(s.get("key")) and n > 1,
                            "occurrences": [],
                            "sample_values": [],
                        },
                    )
                    v["occurrences"].append(ref)
                    if val not in v["sample_values"]:
                        v["sample_values"].append(val)
                elif s["kind"] == "generated":
                    generated.append(ref)

    walk(blocks)

    return {
        "source_file": path.name,
        "sections": len(doc.sections),
        "blocks": blocks,
        "variables": list(variables.values()),
        "generated_segments": generated,
        "suspect_labels": suspects,
        "stats": {
            "blocks": len(blocks),
            "variables": len(variables),
            "variable_occurrences": sum(len(v["occurrences"]) for v in variables.values()),
            "mapped_variables": sum(1 for v in variables.values() if v["mapped"]),
            "generated_segments": len(generated),
            "suspect_labels": len(suspects),
        },
    }


def main() -> None:  # pragma: no cover
    import sys

    manifest = parse_template(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(json.dumps(manifest["stats"], ensure_ascii=False, indent=2))
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
