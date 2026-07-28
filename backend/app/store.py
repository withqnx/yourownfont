"""Persistence for handwritten-photo submissions.

All user content is a fountain-pen handwriting *photo* (base64 data URL), never
keyboard text. SQLite by default; set DATABASE_URL for a free Neon/Supabase
Postgres to persist across redeploys.
"""
from __future__ import annotations

import datetime as _dt
import os

from sqlalchemy import (Column, DateTime, Integer, MetaData, String, Table,
                        Text, create_engine, func, insert, select, update)

_url = os.environ.get("DATABASE_URL", "").strip()
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)
if not _url:
    _dir = os.environ.get("DATA_DIR", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    _url = f"sqlite:///{os.path.join(_dir, 'data.db')}"

# pool_pre_ping: serverless Postgres (Neon/Supabase) drops idle connections; ping
# and reconnect before each use so a suspended DB doesn't surface as a 500.
engine = create_engine(_url, future=True, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})
meta = MetaData()

# 제 ᄠᅳ들 — 대나무숲(bamboo) / 그대에게(letter). Image posts.
posts = Table(
    "posts", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String(16)),
    Column("image", Text),             # base64 data URL of the handwriting photo
    Column("status", String(16)),      # visible | hidden | removed
    Column("reports", Integer, default=0),
    Column("created_at", DateTime),
)

# 사각사각 — 소리를 듣고 쓴 의성어 손글씨 사진.
sagak = Table(
    "sagak", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sound", String(32)),
    Column("image", Text),
    Column("created_at", DateTime),
)

# 날로 ᄡᅮ메 편안킈 — daily-word challenge. Image + likes.
challenge = Table(
    "challenge", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("who", String(48)),         # anonymous browser id
    Column("day", String(10)),
    Column("prompt", String(20)),
    Column("image", Text),
    Column("likes", Integer, default=0),
    Column("created_at", DateTime),
)

# 제뜨들 — 운영자에게 보내는 '문구 요청' (텍스트만).
requests = Table(
    "requests", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("text", Text),
    Column("created_at", DateTime),
)

meta.create_all(engine)


def _now():
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------- 제뜨들 문구 요청 (운영자 확인) ----------------
def add_request(text: str) -> int:
    with engine.begin() as c:
        r = c.execute(insert(requests).values(text=text, created_at=_now()))
        return int(r.inserted_primary_key[0])


def list_requests(limit: int = 500) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(requests).order_by(requests.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


# ---------------- posts (대나무숲 / 그대에게) ----------------
def add_post(kind: str, image: str) -> int:
    with engine.begin() as c:
        r = c.execute(insert(posts).values(kind=kind, image=image, status="visible",
                                           reports=0, created_at=_now()))
        return int(r.inserted_primary_key[0])


def list_posts(kind: str, limit: int = 100) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(posts).where(posts.c.kind == kind, posts.c.status == "visible")
                         .order_by(posts.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def report_post(pid: int) -> bool:
    with engine.begin() as c:
        row = c.execute(select(posts).where(posts.c.id == pid)).mappings().first()
        if not row:
            return False
        c.execute(update(posts).where(posts.c.id == pid).values(
            status="hidden", reports=(row["reports"] or 0) + 1))
    return True


def review_queue(limit: int = 200) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(posts).where(posts.c.status == "hidden")
                         .order_by(posts.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def moderate(pid: int, allow: bool) -> bool:
    with engine.begin() as c:
        r = c.execute(update(posts).where(posts.c.id == pid).values(
            status="visible" if allow else "removed"))
    return r.rowcount > 0


# ---------------- challenge (날로 ᄡᅮ메 편안킈) ----------------
def add_challenge(who: str, day: str, prompt: str, image: str) -> int:
    with engine.begin() as c:
        r = c.execute(insert(challenge).values(who=who, day=day, prompt=prompt,
                                               image=image, likes=0, created_at=_now()))
        return int(r.inserted_primary_key[0])


def challenge_wall(limit: int = 60) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(challenge).order_by(challenge.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def challenge_top(n: int = 3) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(challenge).order_by(challenge.c.likes.desc(), challenge.c.id.desc())
                         .limit(n)).mappings().all()
    return [dict(r) for r in rows]


def like_challenge(cid: int) -> int:
    with engine.begin() as c:
        row = c.execute(select(challenge).where(challenge.c.id == cid)).mappings().first()
        if not row:
            return -1
        likes = (row["likes"] or 0) + 1
        c.execute(update(challenge).where(challenge.c.id == cid).values(likes=likes))
    return likes


def add_sagak(sound: str, image: str) -> int:
    with engine.begin() as c:
        r = c.execute(insert(sagak).values(sound=sound, image=image, created_at=_now()))
        return int(r.inserted_primary_key[0])


def list_sagak(sound: str, limit: int = 40) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(sagak).where(sagak.c.sound == sound)
                         .order_by(sagak.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def challenge_streak(who: str) -> int:
    with engine.begin() as c:
        n = c.execute(select(func.count(func.distinct(challenge.c.day)))
                      .where(challenge.c.who == who)).scalar()
    return int(n or 0)


def stats() -> dict:
    """Ops/diagnostics: which DB is live + row counts. 'postgresql' here means
    DATABASE_URL is wired and uploads persist; 'sqlite' means ephemeral disk."""
    with engine.begin() as c:
        def n(t):
            return int(c.execute(select(func.count()).select_from(t)).scalar() or 0)
        return {"db": engine.url.get_backend_name(),
                "posts": n(posts), "challenge": n(challenge), "sagak": n(sagak)}


# ---------------- 함께 쓰는 벽 (한 마디 + 편지 통합 피드) ----------------
def wall(limit: int = 40) -> list[dict]:
    with engine.begin() as c:
        ch = c.execute(select(challenge.c.image, challenge.c.prompt, challenge.c.created_at)
                       .order_by(challenge.c.id.desc()).limit(limit)).all()
        lt = c.execute(select(posts.c.image, posts.c.created_at)
                       .where(posts.c.kind == "letter", posts.c.status == "visible")
                       .order_by(posts.c.id.desc()).limit(limit)).all()
    items = [{"image": r[0], "label": r[1] or "오늘의 한 마디",
              "at": r[2].isoformat() if r[2] else ""} for r in ch]
    items += [{"image": r[0], "label": "그대에게",
               "at": r[1].isoformat() if r[1] else ""} for r in lt]
    items.sort(key=lambda x: x["at"], reverse=True)
    return items[:limit]


def wall_count() -> int:
    with engine.begin() as c:
        n1 = c.execute(select(func.count()).select_from(challenge)).scalar() or 0
        n2 = c.execute(select(func.count()).select_from(posts)
                       .where(posts.c.kind == "letter", posts.c.status == "visible")).scalar() or 0
    return int(n1) + int(n2)
