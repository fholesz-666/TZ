"""
HTTP rozhraní dokumentové služby.

Běží odděleně od webu (Next.js), protože práce s OOXML je v Pythonu
přímočařejší. Web ji volá server-side, nikdy z prohlížeče.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

<<<<<<< HEAD
from .binder import coverage
=======
>>>>>>> 4983c203b5000ea7e0a7121fde63d894aa6b7dda
from .parser import parse_template
from .render import render, values_from_manifest

app = FastAPI(title="FVE docx engine", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse")
async def parse(file: UploadFile) -> dict[str, Any]:
    """Import šablony → manifest s kandidáty na proměnné."""
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Očekávám soubor .docx")
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
<<<<<<< HEAD
        manifest = parse_template(tmp_path)
        # Průvodce importem se nemusí ptát na úseky, které umí přepsat
        # slovník sám – označíme je, ať jsou v přehledu odděleně.
        covered = coverage(manifest)
        for var in manifest["variables"]:
            keys: set[str] = set()
            for occ in var["occurrences"]:
                keys.update(covered.get(f"{occ['path']}#{occ['segment']}", []))
            var["covered_by"] = sorted(keys)
        return manifest
=======
        return parse_template(tmp_path)
>>>>>>> 4983c203b5000ea7e0a7121fde63d894aa6b7dda
    finally:
        tmp_path.unlink(missing_ok=True)


class RenderRequest(BaseModel):
    manifest: dict[str, Any]
    data: dict[str, str]


@app.post("/render")
async def render_document(file: UploadFile, body: RenderRequest) -> dict[str, Any]:
    """
    Naplní šablonu daty projektu.

    Vrací i seznam nevyplněných segmentů – ty zůstanou v dokumentu
    zvýrazněné, aby se stará hodnota ze šablony nedala splést
    s platným údajem (bod 50).
    """
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "template.docx"
        out = Path(d) / "out.docx"
        src.write_bytes(await file.read())
        values = values_from_manifest(body.manifest, body.data)
        report = render(src, out, values)
        return {
            "filled": report.filled,
            "unfilled": report.unfilled,
            "missing_paths": report.missing_paths,
            "document": out.read_bytes().hex(),
        }
