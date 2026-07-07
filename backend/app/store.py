"""Persistence for 제 ᄠᅳ들 (대나무숲/진심) posts and 날로 ᄡᅮ메 편안킈 challenge.

Uses SQLite by default; if DATABASE_URL is set (e.g. a free Neon/Supabase
Postgres) it uses that instead — so data persists across redeploys once the
env var is configured. No schema change needed to switch.
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

engine = create_engine(_url, future=True,
                       connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})
meta = MetaData()

posts = Table(
    "posts", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String(16)),        # "bamboo" (대나무숲) | "truth" (진심)
    Column("text", Text),
    Column("status", String(16)),      # "visible" | "hidden" | "removed"
    Column("reports", Integer, default=0),
    Column("created_at", DateTime),
)

challenge = Table(
    "challenge", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("who", String(40)),         # nickname
    Column("day", String(10)),         # YYYY-MM-DD
    Column("prompt", String(20)),
    Column("text", Text),
    Column("created_at", DateTime),
)

meta.create_all(engine)


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------- posts (대나무숲 / 진심) ----------------
def add_post(kind: str, text: str) -> int:
    with engine.begin() as c:
        r = c.execute(insert(posts).values(
            kind=kind, text=text, status="visible", reports=0, created_at=_now()))
        return int(r.inserted_primary_key[0])


def list_posts(kind: str, limit: int = 100) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(
            select(posts).where(posts.c.kind == kind, posts.c.status == "visible")
            .order_by(posts.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def report_post(pid: int) -> bool:
    """Hide immediately on report; queue for admin review."""
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
def add_challenge(who: str, day: str, prompt: str, text: str) -> int:
    with engine.begin() as c:
        r = c.execute(insert(challenge).values(
            who=who, day=day, prompt=prompt, text=text, created_at=_now()))
        return int(r.inserted_primary_key[0])


def challenge_wall(limit: int = 60) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(challenge).order_by(challenge.c.id.desc())
                         .limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def challenge_streak(who: str) -> int:
    """Count of distinct days this nickname has submitted."""
    with engine.begin() as c:
        n = c.execute(select(func.count(func.distinct(challenge.c.day)))
                      .where(challenge.c.who == who)).scalar()
    return int(n or 0)
