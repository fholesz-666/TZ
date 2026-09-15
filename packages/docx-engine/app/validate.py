"""
Pre-flight kontrola projektových dat (body 28 a 42).

Pravidla jsou psaná podle chyb, které se opravdu staly v dodaných
dokumentacích – u každého je v `origin` uvedeno, odkud se vzalo.
Nic se tu neopravuje; kontrola jen hlásí, protože o technickém řešení
rozhoduje projektant (bod 43).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

Severity = str  # "error" | "warning" | "info"


@dataclass
class Finding:
    code: str
    severity: Severity
    title: str
    detail: str
    origin: str = ""

    def __str__(self) -> str:  # pragma: no cover
        mark = {"error": "❌", "warning": "⚠", "info": "ℹ"}.get(self.severity, "•")
        return f"{mark} {self.code}  {self.title} — {self.detail}"


@dataclass
class Preflight:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, *args: Any, **kw: Any) -> None:
        self.findings.append(Finding(*args, **kw))


def _get(data: dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _num(value: Any) -> float | None:
    """Číslo z hodnoty, která může být text s jednotkou („22,0 kWp“)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace(" ", " ").strip().replace(" ", "").replace(",", ".")
    out = ""
    for ch in cleaned:
        if ch.isdigit() or (ch == "." and "." not in out) or (ch == "-" and not out):
            out += ch
        elif out:
            break
    try:
        return float(out)
    except ValueError:
        return None


def _close(a: float, b: float, tol: float = 0.02) -> bool:
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) <= tol


# --------------------------------------------------------------------------
# Jednotlivá pravidla
# --------------------------------------------------------------------------


def rule_pv01(data: dict[str, Any], pf: Preflight) -> None:
    """Instalovaný výkon odpovídá počtu panelů a jejich výkonu."""
    count = _num(_get(data, "pv.count"))
    wp = _num(_get(data, "pv.panel.wp"))
    kwp = _num(_get(data, "energy.p_dc_kwp"))
    if count is None or wp is None or kwp is None:
        return
    expected = count * wp / 1000
    if not _close(kwp, expected):
        pf.add(
            "PV-01",
            "error",
            "Instalovaný výkon nesedí s počtem panelů",
            f"{count:g} × {wp:g} Wp = {expected:.2f} kWp, v projektu je {kwp:g} kWp",
            origin="Sauna 25JAB054: 76 ks × 500 Wp = 38 kWp, v bilanci bylo 44 kWp",
        )


def rule_pv02(data: dict[str, Any], pf: Preflight) -> None:
    """Součet panelů ve stringech odpovídá celkovému počtu."""
    count = _num(_get(data, "pv.count"))
    strings = _get(data, "pv.strings") or []
    if count is None or not strings:
        return
    total = sum(_num(s.get("panel_count")) or 0 for s in strings)
    if total != count:
        pf.add(
            "PV-02",
            "error",
            "Součet panelů ve stringech nesedí",
            f"stringy dávají {total:g} panelů, projekt má {count:g}",
        )


def rule_pv03(data: dict[str, Any], pf: Preflight) -> None:
    """Součet panelů podle orientací odpovídá celkovému počtu."""
    count = _num(_get(data, "pv.count"))
    items = _get(data, "pv.orientation") or []
    if count is None or not items:
        return
    total = sum(_num(i.get("count")) or 0 for i in items)
    if total != count:
        pf.add(
            "PV-03",
            "error",
            "Součet panelů podle orientací nesedí",
            f"orientace dávají {total:g} panelů, projekt má {count:g}",
            origin="MŠ Tichá 25JAB102: 42 + 42 panelů při 100 panelech v projektu",
        )


def rule_pv04(data: dict[str, Any], pf: Preflight) -> None:
    """Označení stringů jsou jedinečná."""
    strings = _get(data, "pv.strings") or []
    ids = [str(s.get("id")) for s in strings]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        pf.add(
            "PV-04",
            "error",
            "Dvakrát použité označení stringu",
            "opakuje se: " + ", ".join(dupes),
            origin="MŠ Tichá: výpis uváděl 1.1, 1.2, 1.1, 1.2",
        )


def rule_pv05(data: dict[str, Any], pf: Preflight) -> None:
    """Každý string má přiřazený střídač, který v projektu existuje."""
    strings = _get(data, "pv.strings") or []
    labels = {i.get("label") for i in (_get(data, "pv.inverters") or [])}
    for s in strings:
        inv = s.get("inverter")
        if not inv:
            pf.add("PV-05", "error", "String bez střídače", f"string {s.get('id')}")
        elif labels and inv not in labels:
            pf.add(
                "PV-05",
                "error",
                "String odkazuje na neexistující střídač",
                f"string {s.get('id')} → {inv}; v projektu jsou {sorted(labels)}",
            )


def rule_pv06(data: dict[str, Any], pf: Preflight) -> None:
    """Napětí stringu naprázdno při −10 °C nepřekročí vstup střídače."""
    voc = _num(_get(data, "pv.panel.voc"))
    beta = _num(_get(data, "pv.panel.beta_voc_pct_per_k"))
    if voc is None:
        return
    beta = -0.27 if beta is None else beta
    factor = 1 + (beta / 100) * (-10 - 25)
    inverters = {i.get("label"): i for i in (_get(data, "pv.inverters") or [])}
    for s in _get(data, "pv.strings") or []:
        n = _num(s.get("panel_count")) or 0
        inv = inverters.get(s.get("inverter"), {})
        umax = _num(inv.get("u_dc_max"))
        if not umax:
            continue
        u = n * voc * factor
        if u > umax:
            pf.add(
                "PV-06",
                "error",
                "Napětí stringu překračuje vstup střídače",
                f"string {s.get('id')}: {u:.0f} V při −10 °C > {umax:g} V",
            )
        elif u > umax * 0.95:
            pf.add(
                "PV-06",
                "warning",
                "Napětí stringu je těsně pod limitem střídače",
                f"string {s.get('id')}: {u:.0f} V při −10 °C, limit {umax:g} V",
            )


def rule_pv07(data: dict[str, Any], pf: Preflight) -> None:
    """Proud stringu nepřekročí dovolený proud MPPT."""
    isc = _num(_get(data, "pv.panel.isc"))
    if isc is None:
        return
    inverters = {i.get("label"): i for i in (_get(data, "pv.inverters") or [])}
    current = isc * 1.25
    for s in _get(data, "pv.strings") or []:
        inv = inverters.get(s.get("inverter"), {})
        imax = _num(inv.get("i_mppt_max"))
        if imax and current > imax:
            pf.add(
                "PV-07",
                "error",
                "Proud stringu překračuje MPPT",
                f"string {s.get('id')}: {current:.1f} A (Isc × 1,25) > {imax:g} A",
            )


def rule_pv08(data: dict[str, Any], pf: Preflight) -> None:
    """Poměr DC/AC je v obvyklém rozsahu."""
    kwp = _num(_get(data, "energy.p_dc_kwp"))
    pac = _num(_get(data, "energy.p_ac_kw"))
    if not kwp or not pac:
        return
    ratio = kwp / pac
    if ratio < 0.8 or ratio > 1.8:
        pf.add(
            "PV-08",
            "warning",
            "Neobvyklý poměr DC/AC",
            f"{kwp:g} kWp / {pac:g} kW = {ratio:.2f}",
        )


def rule_pv09(data: dict[str, Any], pf: Preflight) -> None:
    """
    Počet optimizérů odpovídá rozložení po střechách.

    Nesmí se počítat z celku: 19 panelů na každou ze dvou střech znamená
    2 × 10 kusů, ne 19. Zaokrouhluje se na každé střeše zvlášť.
    """
    opt = _get(data, "pv.optimizers") or {}
    stated = _num(opt.get("count"))
    ratio = str(opt.get("ratio") or "1:1")
    try:
        per_unit = int(ratio.split(":")[1])
    except (IndexError, ValueError):
        return
    items = _get(data, "pv.orientation") or []
    if not items or stated is None:
        return
    expected = sum(math.ceil((_num(i.get("count")) or 0) / per_unit) for i in items)
    if stated != expected:
        pf.add(
            "PV-09",
            "error",
            "Počet optimizérů nesedí",
            f"při poměru {ratio} po střechách vychází {expected} ks, v projektu {stated:g} ks",
            origin="RD Procházková: 19 + 19 panelů → 20 ks, ne 19",
        )


def rule_en01(data: dict[str, Any], pf: Preflight) -> None:
    """Roční výroba odpovídá výkonu a měrné výrobě."""
    kwp = _num(_get(data, "energy.p_dc_kwp"))
    spec = _num(_get(data, "energy.specific_yield"))
    yield_mwh = _num(_get(data, "energy.annual_yield_mwh"))
    if not kwp or not spec or yield_mwh is None:
        return
    expected = kwp * spec / 1000
    if not _close(yield_mwh, expected):
        pf.add(
            "EN-01",
            "error",
            "Roční výroba nesedí s výkonem",
            f"{kwp:g} kWp × {spec:g} kWh/kWp = {expected:.2f} MWh, v projektu {yield_mwh:g} MWh",
        )


def rule_safe01(data: dict[str, Any], pf: Preflight) -> None:
    """
    Bezpečné napětí na střeše je odvozené, ne pevné číslo.

    V dodaných projektech byla ve všech pěti dokumentech stejná hodnota
    28 V, přestože stringy měly 19 až 25 panelů.
    """
    opt = _get(data, "pv.optimizers") or {}
    u_off = _num(opt.get("u_off"))
    stated = _num(_get(data, "pv.safe_roof_voltage"))
    strings = _get(data, "pv.strings") or []
    if u_off is None or not strings:
        if stated is not None and u_off is None:
            pf.add(
                "SAFE-01",
                "warning",
                "Bezpečné napětí není doložené",
                "chybí výstupní napětí optimizéru ve vypnutém stavu z datasheetu",
            )
        return
    expected = max((_num(s.get("panel_count")) or 0) for s in strings) * u_off
    if stated is not None and not _close(stated, expected, 0.001):
        pf.add(
            "SAFE-01",
            "error",
            "Bezpečné napětí na střeše nesedí",
            f"největší string má {expected / u_off:.0f} panelů × {u_off:g} V = "
            f"{expected:.1f} V, v projektu je {stated:g} V",
            origin="V1: ve všech pěti projektech shodně 28 V",
        )


def rule_el01(data: dict[str, Any], pf: Preflight) -> None:
    """Jistič pokrývá výstupní proud a kabel pokrývá jistič."""
    pac = _num(_get(data, "energy.p_ac_kw"))
    breaker = _num(_get(data, "electrical.protection.breaker_a"))
    ampacity = _num(_get(data, "electrical.protection.cable_ampacity_a"))
    if not pac:
        return
    current = pac * 1000 / (math.sqrt(3) * 400)
    if breaker and breaker < current:
        pf.add(
            "EL-01",
            "error",
            "Jistič je menší než výstupní proud",
            f"I = {current:.1f} A, jistič {breaker:g} A",
        )
    if breaker and ampacity and ampacity < breaker:
        pf.add(
            "EL-01",
            "error",
            "Kabel neunese jistič",
            f"jistič {breaker:g} A, dovolené zatížení kabelu {ampacity:g} A",
        )


def rule_lps01(data: dict[str, Any], pf: Preflight) -> None:
    """Varianta LPS je zvolená a je jen jedna."""
    lps = _get(data, "lps") or {}
    variant = lps.get("variant")
    allowed = {"neni", "izolovany", "neizolovany", "oddaleny"}
    if variant is None:
        pf.add("LPS-01", "warning", "Není zvolená varianta LPS", "vyberte jednu ze čtyř")
    elif variant not in allowed:
        pf.add(
            "LPS-01",
            "error",
            "Neznámá varianta LPS",
            f"{variant!r}; povolené jsou {sorted(allowed)}",
        )
    elif variant == "neni" and (lps.get("down_conductors") or lps.get("air_terminals")):
        pf.add(
            "LPS-01",
            "error",
            "Projekt bez LPS má zadané svody nebo jímače",
            "buď je LPS, nebo nejsou jeho části",
            origin="MŠ Tichá: kap. 2.6 úprava stávajícího × kap. 3.15 nová soustava",
        )


RULES: list[Callable[[dict[str, Any], Preflight], None]] = [
    rule_pv01,
    rule_pv02,
    rule_pv03,
    rule_pv04,
    rule_pv05,
    rule_pv06,
    rule_pv07,
    rule_pv08,
    rule_pv09,
    rule_en01,
    rule_safe01,
    rule_el01,
    rule_lps01,
]


def preflight(data: dict[str, Any], rules: Iterable[Callable] | None = None) -> Preflight:
    pf = Preflight()
    for rule in rules or RULES:
        try:
            rule(data, pf)
        except Exception as exc:  # pravidlo nesmí shodit generování
            pf.add(
                rule.__name__.upper(),
                "warning",
                "Kontrolu se nepodařilo provést",
                f"{type(exc).__name__}: {exc}",
            )
    return pf
