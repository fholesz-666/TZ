"""
Pre-flight kontrola.

Každý test je postavený na chybě, která se opravdu stala v dodaných
dokumentacích. Když test spadne, znamená to, že by taková chyba znovu
prošla do dokumentu.
"""
from __future__ import annotations

import copy
from typing import Any

from app.validate import preflight

GOOD: dict[str, Any] = {
    "pv": {
        "count": 40,
        "panel": {"wp": 550, "voc": 49.5, "isc": 14.05, "vmp": 41.2, "imp": 13.21},
        "inverters": [
            {"label": "INV1", "p_ac_kw": 20.0, "u_dc_max": 1000, "i_mppt_max": 26}
        ],
        "strings": [
            {"id": "1.1", "panel_count": 14, "inverter": "INV1"},
            {"id": "1.2", "panel_count": 13, "inverter": "INV1"},
            {"id": "1.3", "panel_count": 13, "inverter": "INV1"},
        ],
        "orientation": [
            {"azimuth": 95, "count": 20},
            {"azimuth": 275, "count": 20},
        ],
        "optimizers": {"ratio": "1:1", "count": 40, "u_off": 1.0},
        "safe_roof_voltage": 14,
    },
    "energy": {
        "p_dc_kwp": 22.0,
        "p_ac_kw": 20.0,
        "specific_yield": 980,
        "annual_yield_mwh": 21.56,
    },
    "lps": {"variant": "neizolovany", "down_conductors": 10},
}


def _codes(data: dict[str, Any]) -> set[str]:
    return {f.code for f in preflight(data).findings}


def test_valid_project_passes() -> None:
    pf = preflight(GOOD)
    assert pf.ok, [str(f) for f in pf.findings]
    assert not pf.findings


def test_pv01_sauna() -> None:
    """Sauna 25JAB054: 76 × 500 Wp = 38 kWp, v bilanci zůstalo 44 kWp."""
    data = copy.deepcopy(GOOD)
    data["pv"]["count"] = 76
    data["pv"]["panel"]["wp"] = 500
    data["energy"]["p_dc_kwp"] = 44.0
    assert "PV-01" in _codes(data)


def test_pv02_strings_sum() -> None:
    data = copy.deepcopy(GOOD)
    data["pv"]["strings"][0]["panel_count"] = 25
    assert "PV-02" in _codes(data)


def test_pv03_orientation_sum() -> None:
    """MŠ Tichá: 42 + 42 panelů, projekt má 100."""
    data = copy.deepcopy(GOOD)
    data["pv"]["count"] = 100
    data["pv"]["orientation"] = [
        {"azimuth": 57, "count": 42},
        {"azimuth": 237, "count": 42},
    ]
    assert "PV-03" in _codes(data)


def test_pv04_duplicate_string_ids() -> None:
    """MŠ Tichá: výpis uváděl 1.1, 1.2, 1.1, 1.2."""
    data = copy.deepcopy(GOOD)
    data["pv"]["strings"] = [
        {"id": "1.1", "panel_count": 10, "inverter": "INV1"},
        {"id": "1.2", "panel_count": 10, "inverter": "INV1"},
        {"id": "1.1", "panel_count": 10, "inverter": "INV1"},
        {"id": "1.2", "panel_count": 10, "inverter": "INV1"},
    ]
    assert "PV-04" in _codes(data)


def test_pv05_unknown_inverter() -> None:
    data = copy.deepcopy(GOOD)
    data["pv"]["strings"][0]["inverter"] = "INV9"
    assert "PV-05" in _codes(data)


def test_pv06_string_voltage_over_limit() -> None:
    data = copy.deepcopy(GOOD)
    data["pv"]["strings"] = [{"id": "1.1", "panel_count": 40, "inverter": "INV1"}]
    data["pv"]["orientation"] = [{"azimuth": 180, "count": 40}]
    assert "PV-06" in _codes(data)


def test_pv07_string_current_over_mppt() -> None:
    data = copy.deepcopy(GOOD)
    data["pv"]["inverters"][0]["i_mppt_max"] = 12
    assert "PV-07" in _codes(data)


def test_pv09_optimizer_count_per_roof() -> None:
    """
    RD Procházková: 19 panelů na každou ze dvou střech, poměr 1:2.
    Správně je 2 × 10 = 20 kusů; počítat z celku (38/2 = 19) je chyba.
    """
    data = copy.deepcopy(GOOD)
    data["pv"]["count"] = 38
    data["pv"]["panel"]["wp"] = 670
    data["energy"]["p_dc_kwp"] = 25.46
    data["energy"]["annual_yield_mwh"] = 24.95
    data["pv"]["orientation"] = [
        {"azimuth": 90, "count": 19},
        {"azimuth": 270, "count": 19},
    ]
    data["pv"]["strings"] = [{"id": "1.1", "panel_count": 38, "inverter": "INV1"}]
    data["pv"]["optimizers"] = {"ratio": "1:2", "count": 19, "u_off": 0.6}
    data["pv"]["safe_roof_voltage"] = 22.8
    assert "PV-09" in _codes(data)

    data["pv"]["optimizers"]["count"] = 20
    assert "PV-09" not in _codes(data)


def test_en01_annual_yield() -> None:
    data = copy.deepcopy(GOOD)
    data["energy"]["annual_yield_mwh"] = 43.69
    assert "EN-01" in _codes(data)


def test_safe01_frozen_voltage() -> None:
    """
    V1: ve všech pěti projektech shodně 28 V, přestože stringy měly
    19 až 25 panelů a optimizér drží 1 V na panel.
    """
    data = copy.deepcopy(GOOD)
    data["pv"]["strings"] = [
        {"id": "1.1", "panel_count": 25, "inverter": "INV1"},
        {"id": "1.2", "panel_count": 15, "inverter": "INV1"},
    ]
    data["pv"]["safe_roof_voltage"] = 28
    assert "SAFE-01" in _codes(data)


def test_el01_breaker_below_current() -> None:
    data = copy.deepcopy(GOOD)
    data["electrical"] = {"protection": {"breaker_a": 20, "cable_ampacity_a": 40}}
    assert "EL-01" in _codes(data)


def test_lps01_conflict() -> None:
    """MŠ Tichá: kapitola 2.6 úprava stávajícího × kapitola 3.15 nová soustava."""
    data = copy.deepcopy(GOOD)
    data["lps"] = {"variant": "neni", "down_conductors": 10}
    assert "LPS-01" in _codes(data)


def test_rule_failure_does_not_crash() -> None:
    """Rozbité pravidlo nesmí shodit generování, jen se ohlásí."""

    def broken(data: dict[str, Any], pf: Any) -> None:
        raise RuntimeError("nefunguje")

    pf = preflight(GOOD, rules=[broken])
    assert pf.findings and pf.findings[0].severity == "warning"


def test_missing_data_is_not_an_error() -> None:
    """Prázdný projekt se nekontroluje proti ničemu – jen se nic nehlásí."""
    assert preflight({}).ok
