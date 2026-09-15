"""
Navázání proměnných, které nemají popisek.

Většina hodnot v technické zprávě nesedí v tabulce „popisek | hodnota“,
ale uvnitř věty:

    „Na střechy objektu na parcele 1669 bude osazeno celkem 100 ks
     fotovoltaických panelů AIKO-A500-MAH60Mb o výkonu 500Wp.“

Parser u nich nemá podle čeho navrhnout klíč. Dají se ale navázat jinak:
**šablona sama je vyplněný projekt.** Hodnoty, které parser navázal
z tabulek (100 ks, 500 Wp, 50,0 kWp, SolarEdge SE33,3K …), jsou zároveň
slovníkem toho, jak tentýž údaj vypadá jinde v textu. Stačí ho v ostatních
zvýrazněných úsecích najít a nahradit novou hodnotou.

Bezpečnostní pravidla, aby se nerozbil text:
  * nahrazuje se **jen uvnitř žlutě zvýrazněných úseků**, nikdy ve fixním
    textu – ten musí zůstat beze změny (bod 7);
  * jen tokeny délky aspoň 2 znaky, na hranicích slova, takže „500“
    v „SolarEdge S500B“ zůstane;
  * delší tvary se zkoušejí dřív než kratší („33,3 kW“ před „33,3“);
  * každá náhrada se hlásí, aby šlo dohledat, co se kde změnilo (bod 17).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Klíče, jejichž hodnota se smí hledat jinde v textu. Schválně tu nejsou
# údaje, které jsou jinde v jiném významu (počet kusů rozvaděčů, účinnost),
# aby se nenahradilo něco nesouvisejícího.
SUBSTITUTABLE = {
    "pv.count",
    "pv.panel.wp",
    "pv.panel.model",
    "pv.panel.vmp",
    "pv.panel.imp",
    "pv.panel.dimensions",
    "pv.panel.area",
    "pv.panel.efficiency",
    "energy.p_dc_kwp",
    "energy.p_ac_kw",
    "energy.annual_yield",
    "energy.consumption_mwh",
    "pv.inverters.0.model",
    "pv.inverters.0.p_ac_va",
    "pv.inverters.0.i_ac_max",
    "pv.inverters.0.i_dc_max",
    "pv.inverters.0.u_dc_max",
    "pv.inverters.0.p_dc_max",
    "pv.inverters.0.dimensions",
    "site.cadastre.parcels",
    "site.cadastre.area",
    "site.address.municipality",
    "site.address.full",
    "site.building.roof_covering",
    "site.gps",
    "construction.tilt_deg",
    "electrical.grid.contract_number",
    "meta.name",
    "meta.order_number",
    "investor.name",
}

_NUM = re.compile(r"^\d[\d\s ]*(?:[.,]\d+)?$")


# Do NEOZNAČENÉHO textu se smí sáhnout jen u údajů, které jsou jednoznačně
# projektové. Napětí a proudy sem nepatří: „ochrana … do 1000 V na straně AC“
# je citace normy, ne parametr střídače, a přepsat ji by byla chyba.
FIXED_TEXT_SAFE = {
    "pv.panel.model",
    "pv.panel.wp",
    "pv.count",
    "pv.inverters.0.model",
    "energy.p_dc_kwp",
    "site.cadastre.parcels",
}


@dataclass
class Substitution:
    ref: str
    key: str
    old: str
    new: str


@dataclass
class BindReport:
    rewritten: int = 0
    substitutions: list[Substitution] = field(default_factory=list)
    untouched: list[dict[str, Any]] = field(default_factory=list)


def _variants(text: str) -> list[str]:
    """
    Tvary, ve kterých se hodnota může v textu objevit.
    „50,0 kWp“ se jinde píše jako „50,0kWp“ nebo jen „50,0“.
    """
    text = text.strip()
    if not text:
        return []
    out = [text]
    # "Pjm = 33,3 kW" se ve větě píše jen jako "33,3 kW"
    stripped = re.sub(r"^[A-Za-z\u00c0-\u017e]{1,8}\s*=\s*", "", text).strip()
    if stripped != text and len(stripped) >= 2:
        out.append(stripped)
        m0 = re.match(r"^([\d\s\u00a0]*\d(?:[.,]\d+)?)", stripped)
        if m0 and len(m0.group(1).strip()) >= 2:
            out.append(m0.group(1).strip())
    nbsp = text.replace(" ", " ")
    if nbsp != text:
        out.append(nbsp)
    no_unit_space = re.sub(r"[\s\u00a0]+(?=[A-Za-z\u03a9%\u00b0]+\d*$)", "", text)
    if no_unit_space != text and len(no_unit_space) >= 2:
        out.append(no_unit_space)
    tight = re.sub(r"\s+", "", text)
    if tight != text and len(tight) >= 2:
        out.append(tight)
    # číselné jádro bez jednotky: "500 Wp" → "500", "50,0 kWp" → "50,0"
    m = re.match(r"^([\d\s ]*\d(?:[.,]\d+)?)\s*([A-Za-zΩ%°/]+\d*)?$", text)
    if m and m.group(1):
        core = m.group(1).strip()
        if len(core) >= 2:
            out.append(core)
            core_tight = re.sub(r"[\s ]", "", core)
            if core_tight != core and len(core_tight) >= 2:
                out.append(core_tight)
    seen: set[str] = set()
    return [v for v in out if len(v) >= 2 and not (v in seen or seen.add(v))]


def build_pairs(
    manifest: dict[str, Any], data: dict[str, str]
) -> list[tuple[str, str, str]]:
    """
    Dvojice (klíč, starý tvar, nový tvar) seřazené od nejdelšího tvaru,
    aby se „33,3 kW“ nahradilo dřív než samotné „33,3“.
    """
    pairs: list[tuple[str, str, str]] = []
    for var in manifest["variables"]:
        key = var["key"]
        # Varianty s příponou (#2, #3) vznikly tam, kde se pod jedním
        # popiskem skrývá jiný údaj. Do slovníku nepatří – jinak by se
        # „SolarEdge“ z tabulky střídače přepsalo názvem stavby.
        if "#" in key:
            continue
        base = key
        if base not in SUBSTITUTABLE or base not in data:
            continue
        new = data[base]
        forms = list(var["sample_values"][:1])
        forms += _sibling_forms(manifest, base, forms[0] if forms else "")
        olds: list[str] = []
        for form in forms:
            olds += _variants(form)
        seen_old: set[str] = set()
        for old in [o for o in olds if not (o in seen_old or seen_old.add(o))]:
            if old == new:
                continue
            new_form = _matching_form(old, new)
            pairs.append((base, old, new_form))
    pairs.sort(key=lambda p: len(p[1]), reverse=True)
    return pairs


def _squash(s: str) -> str:
    return re.sub(r"[\s\u00a0]", "", s).lower()


def _sibling_forms(manifest: dict[str, Any], base: str, primary: str) -> list[str]:
    """
    Jiné zápisy téže hodnoty. Parser je uložil jako varianty s příponou
    (`pv.inverters.0.model#2`), protože se pod stejným popiskem lišily:
    v seznamu strojů je „SolarEdge SE33,3K“, v tabulce parametrů jen
    „SE33,3K“, ve větě „Solar Edge SE33,3K“.

    Berou se jen ty, které s primárním tvarem souvisí – jeden musí být
    částí druhého po odstranění mezer. Tím se do slovníku nedostane
    hodnota, která se na stejný popisek chytila omylem.
    """
    if not primary:
        return []
    ref = _squash(primary)
    out: list[str] = []
    for var in manifest["variables"]:
        if not var["key"].startswith(base + "#"):
            continue
        for val in var["sample_values"]:
            cand = _squash(val)
            if not cand or cand == ref:
                continue
            if cand in ref or ref in cand:
                out.append(val)
    return out


def _matching_form(old: str, new: str) -> str:
    """
    Nová hodnota ve stejném tvaru jako stará.
    Když je starý tvar jen číslo bez jednotky ("50,0"), vezme se
    i z nové hodnoty jen číslo – jinak by ve větě zůstalo "22,0 kWpkWp".
    Slepený tvar ("50,0kWp") se obnoví jen u číselných hodnot; u textu
    by slepení zničilo název ("MŠ Zkušební 1" → "MŠZkušební1").
    """
    if _NUM.match(old):
        m = re.match(r"^([\d\s\u00a0]*\d(?:[.,]\d+)?)", new.strip())
        if m:
            return m.group(1).strip()
    has_space_old = bool(re.search(r"[\s\u00a0]", old))
    starts_with_number = bool(re.match(r"^\d", old)) and bool(re.match(r"^\d", new.strip()))
    if not has_space_old and starts_with_number:
        return re.sub(r"[\s\u00a0]", "", new)
    return new


def _pattern_for(old: str) -> re.Pattern[str]:
    """
    Vzor tolerantní k mezerám. Tentýž typ střídače je v šabloně napsaný
    jednou „SolarEdge SE33,3K“ a jinde „Solar Edge SE33,3K“; bez téhle
    tolerance by se druhý zápis nenašel.
    """
    body = re.escape(old)
    if len(old) >= 6 and not _NUM.match(old):
        body = re.sub(r"(?:\\[\s\u00a0]|[\s\u00a0])+", r"\\s*", body)
        body = re.sub(r"(?<=[a-z\u00e0-\u017e])(?=[A-Z\u00c0-\u017d])", r"\\s*", body)
    return re.compile(
        r"(?<![0-9A-Za-z\u00c0-\u017e])" + body + r"(?![0-9A-Za-z\u00c0-\u017e])"
    )


def rewrite_free_text(
    manifest: dict[str, Any], data: dict[str, str], report: BindReport | None = None
) -> tuple[dict[str, str], BindReport]:
    """
    Projde zvýrazněné úseky bez navázaného klíče a přepíše v nich známé
    hodnoty. Vrací mapu "cesta#segment" → nový text.
    """
    report = report or BindReport()
    pairs = build_pairs(manifest, data)
    if not pairs:
        return {}, report

    out: dict[str, str] = {}
    for var in manifest["variables"]:
        if var.get("mapped") and var["key"].split("#")[0] in data:
            continue  # vyplní se přímo, ne přepisem
        for occ in var["occurrences"]:
            ref = f"{occ['path']}#{occ['segment']}"
            original = occ["text"]
            text = original
            used: list[Substitution] = []
            for key, old, new in pairs:
                pattern = _pattern_for(old)
                text, n = pattern.subn(new, text)
                if n:
                    used.append(Substitution(ref=ref, key=key, old=old, new=new))
            if text != original:
                out[ref] = text
                report.rewritten += 1
                report.substitutions.extend(used)
            else:
                report.untouched.append({"ref": ref, "text": original[:90]})
    return out, report


def find_unmarked_in_fixed(
    manifest: dict[str, Any], data: dict[str, str]
) -> list[dict[str, str]]:
    """
    Hodnoty projektu, které stojí v **neoznačeném** textu.

    V šabloně MŠ Tichá je ve větě „…celkem 100 ks fotovoltaických panelů
    AIKO-A500-MAH60Mb o výkonu 500Wp“ žlutě jen počet. Typ panelu a jeho
    výkon zvýrazněné nejsou, takže by v novém projektu zůstal panel
    z Tiché. Přesně tenhle druh zapomenutého označení popisuje bod 62.

    Vrací nálezy; rozhodnutí, jestli se mají přepsat, dělá volající.
    """
    pairs = [p for p in build_pairs(manifest, data) if p[0] in FIXED_TEXT_SAFE]
    hits: list[dict[str, str]] = []
    for block in _iter_paragraph_blocks(manifest["blocks"]):
        for seg in block["segments"]:
            if seg["kind"] != "fixed":
                continue
            for key, old, new in pairs:
                if _pattern_for(old).search(seg["text"]):
                    hits.append(
                        {
                            "path": block["path"],
                            "segment": str(seg["index"]),
                            "key": key,
                            "old": old,
                            "new": new,
                            "context": seg["text"][:120],
                        }
                    )
                    break
    return hits


def _iter_paragraph_blocks(blocks: list[dict[str, Any]]):
    for b in blocks:
        if b["type"] == "table":
            for row in b["content"]:
                for cell in row["cells"]:
                    yield from _iter_paragraph_blocks(cell["paragraphs"])
        else:
            yield b


def rewrite_unmarked(
    manifest: dict[str, Any], data: dict[str, str]
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """
    Přepíše nalezené hodnoty v neoznačeném textu a vrátí i soupis změn.

    Dělá se to jen u hodnot, které se přesně shodují s údajem tohoto
    projektu – ne u libovolného textu. Každá změna je v soupisu, takže
    jde zkontrolovat, co se kde přepsalo.
    """
    hits = find_unmarked_in_fixed(manifest, data)
    out: dict[str, str] = {}
    by_ref: dict[str, list[dict[str, str]]] = {}
    for h in hits:
        by_ref.setdefault(f"{h['path']}#{h['segment']}", []).append(h)

    texts = {
        f"{b['path']}#{s['index']}": s["text"]
        for b in _iter_paragraph_blocks(manifest["blocks"])
        for s in b["segments"]
    }
    pairs = [p for p in build_pairs(manifest, data) if p[0] in FIXED_TEXT_SAFE]
    for ref in by_ref:
        text = texts.get(ref)
        if text is None:
            continue
        new_text = text
        for key, old, new in pairs:
            new_text = _pattern_for(old).sub(new, new_text)
        if new_text != text:
            out[ref] = new_text
    return out, hits


def coverage(manifest: dict[str, Any]) -> dict[str, list[str]]:
    """
    Které nenavázané proměnné umí přepsat slovník sám.

    Většina hodnot uvnitř vět nepotřebuje ruční navázání – jsou to jiné
    zápisy údaje, který už navázaný je („50,0 kWp“ v tabulce, „50,0kWp“
    ve větě). Průvodce importem se na ně nemusí ptát a uživatel projde
    jen to, co opravdu vyžaduje rozhodnutí.

    Vrací mapu "cesta#segment" → klíče, které ten úsek pokrývají.
    """
    probe = {}
    for var in manifest["variables"]:
        key = var["key"]
        if "#" in key or key not in SUBSTITUTABLE or not var.get("mapped"):
            continue
        probe[key] = "ZASTUPNA-HODNOTA"  # jen pro zjištění shody

    pairs = build_pairs(manifest, probe)
    if not pairs:
        return {}

    out: dict[str, list[str]] = {}
    for var in manifest["variables"]:
        if var.get("mapped") and var["key"] in probe:
            continue
        for occ in var["occurrences"]:
            ref = f"{occ['path']}#{occ['segment']}"
            hits = [
                key for key, old, _ in pairs if _pattern_for(old).search(occ["text"])
            ]
            if hits:
                out[ref] = sorted(set(hits))
    return out
