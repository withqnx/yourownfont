"""FastAPI app: template download, font build, preview/download.

v1 builds synchronously (Latin only, sub-second). The async job queue described
in the plan is introduced in v2 when GPU-bound Hangul AI generation lands.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from .pipeline import build_from_scan
from .template import generate_template_pdf

app = FastAPI(title="YourOwnFont")

# In-memory store of built fonts: id -> (font_bytes, family, fmt). Fine for a
# single process MVP; swap for object storage when the job queue arrives.
_FONTS: dict[str, tuple[bytes, str, str]] = {}

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(FRONTEND.read_text(encoding="utf-8"))


@app.get("/api/template")
def template() -> Response:
    pdf = generate_template_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="yourownfont-template.pdf"'},
    )


@app.post("/api/build")
async def build(file: UploadFile = File(...), family: str = Form("YourOwnFont"),
                fmt: str = Form("ttf")) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty upload.")
    fmt = fmt.lower()
    if fmt not in ("ttf", "otf"):
        raise HTTPException(400, "fmt must be 'ttf' or 'otf'.")
    try:
        result = build_from_scan(data, family=family or "YourOwnFont", fmt=fmt)
    except ValueError as e:
        raise HTTPException(422, str(e))

    font_id = uuid.uuid4().hex
    _FONTS[font_id] = (result.font_bytes, result.family, result.fmt)
    return {
        "id": font_id,
        "family": result.family,
        "fmt": result.fmt,
        "total_cells": result.total_cells,
        "filled_cells": result.filled_cells,
    }


@app.get("/api/font/{font_id}")
def font(font_id: str) -> Response:
    entry = _FONTS.get(font_id)
    if entry is None:
        raise HTTPException(404, "Font not found or expired.")
    font_bytes, family, fmt = entry
    media = "font/otf" if fmt == "otf" else "font/ttf"
    return Response(
        content=font_bytes,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{family}.{fmt}"'},
    )
