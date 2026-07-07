"""FastAPI app for the 한글날 event site.

Serves the step-by-step wizard frontend and the font-maker API (사맛디 > 폰트
만들기). Font builds are synchronous (jamo composition, ~a few seconds).
"""
from __future__ import annotations

import datetime as dt
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import store
from .charset import WORDS
from .pipeline import build_from_scan
from .template import generate_template_pdf

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "changeme")

# Minimal Korean hate/abuse blocklist for 대나무숲/진심 submissions. Expandable.
BLOCKLIST = ["시발", "씨발", "병신", "지랄", "새끼", "좆", "썅", "닥쳐",
             "죽어", "꺼져", "장애인", "틀딱", "김치녀", "한남", "된장녀"]


def _blocked(text: str) -> bool:
    t = text.replace(" ", "")
    return any(w in t for w in BLOCKLIST)

app = FastAPI(title="YourOwnFont")

# In-memory store of built fonts: id -> (font_bytes, family, fmt). Fine for a
# single process MVP; swap for object storage when persistence lands.
_FONTS: dict[str, tuple[bytes, str, str]] = {}

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
FRONTEND = _FRONTEND_DIR / "index.html"

app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")


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
async def build(files: list[UploadFile] = File(...),
                family: str = Form("YourOwnFont"),
                fmt: str = Form("ttf")) -> dict:
    images = [await f.read() for f in files]
    images = [b for b in images if b]
    if not images:
        raise HTTPException(400, "Empty upload.")
    fmt = fmt.lower()
    if fmt not in ("ttf", "otf"):
        raise HTTPException(400, "fmt must be 'ttf' or 'otf'.")
    try:
        result = build_from_scan(images, family=family or "YourOwnFont", fmt=fmt)
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
        "syllables": result.syllables,
        "pages": result.pages,
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


MAX_IMG = 3_000_000  # ~2.2MB decoded; handwriting photos are resized client-side
POST_KINDS = ("bamboo", "letter")  # 대나무숲 / 그대에게


def _check_image(image: str) -> None:
    if not image or not image.startswith("data:image/"):
        raise HTTPException(400, "손글씨 사진을 올려주세요.")
    if len(image) > MAX_IMG:
        raise HTTPException(413, "이미지가 너무 큽니다.")


# ---------------- 제 ᄠᅳ들 · 대나무숲 / 그대에게 (손글씨 사진) ----------------
class PostIn(BaseModel):
    kind: str            # "bamboo" | "letter"
    image: str           # base64 data URL


@app.post("/api/posts")
def create_post(p: PostIn) -> dict:
    if p.kind not in POST_KINDS:
        raise HTTPException(400, "invalid kind")
    _check_image(p.image)
    pid = store.add_post(p.kind, p.image)
    return {"id": pid, "status": "visible"}


@app.get("/api/posts/{kind}")
def get_posts(kind: str) -> dict:
    if kind not in POST_KINDS:
        raise HTTPException(400, "invalid kind")
    return {"posts": store.list_posts(kind)}


@app.post("/api/posts/{pid}/report")
def report(pid: int) -> dict:
    ok = store.report_post(pid)
    if not ok:
        raise HTTPException(404, "not found")
    return {"status": "hidden"}


def _check_admin(token: str) -> None:
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "forbidden")


@app.get("/api/admin/queue")
def admin_queue(token: str = "") -> dict:
    _check_admin(token)
    return {"queue": store.review_queue()}


@app.post("/api/admin/posts/{pid}/moderate")
def admin_moderate(pid: int, allow: bool = Form(...), token: str = Form("")) -> dict:
    _check_admin(token)
    if not store.moderate(pid, allow):
        raise HTTPException(404, "not found")
    return {"status": "visible" if allow else "removed"}


# ---------------- 날로 ᄡᅮ메 편안킈 · 챌린지 ----------------
def _today() -> str:
    return dt.date.today().isoformat()


def _today_prompt() -> str:
    return WORDS[dt.date.today().toordinal() % len(WORDS)]


class ChallengeIn(BaseModel):
    who: str
    image: str


@app.get("/api/challenge/today")
def challenge_today() -> dict:
    return {"day": _today(), "prompt": _today_prompt()}


@app.post("/api/challenge")
def challenge_submit(c: ChallengeIn) -> dict:
    who = (c.who or "익명").strip()[:48]
    _check_image(c.image)
    store.add_challenge(who, _today(), _today_prompt(), c.image)
    return {"streak": store.challenge_streak(who)}


@app.get("/api/challenge/wall")
def challenge_wall() -> dict:
    return {"entries": store.challenge_wall()}


@app.get("/api/challenge/top")
def challenge_top() -> dict:
    return {"top": store.challenge_top(3)}


@app.post("/api/challenge/{cid}/like")
def challenge_like(cid: int) -> dict:
    likes = store.like_challenge(cid)
    if likes < 0:
        raise HTTPException(404, "not found")
    return {"likes": likes}


@app.get("/api/challenge/streak")
def challenge_streak(who: str = "") -> dict:
    return {"streak": store.challenge_streak(who.strip()[:48])}


# ---------------- 사각사각 · 소리 → 손글씨 의성어 ----------------
class SagakIn(BaseModel):
    sound: str
    image: str


@app.post("/api/sagak")
def sagak_submit(s: SagakIn) -> dict:
    sound = (s.sound or "").strip()[:32]
    if not sound:
        raise HTTPException(400, "invalid sound")
    _check_image(s.image)
    return {"id": store.add_sagak(sound, s.image)}


@app.get("/api/sagak/{sound}")
def sagak_list(sound: str) -> dict:
    return {"entries": store.list_sagak(sound.strip()[:32])}
