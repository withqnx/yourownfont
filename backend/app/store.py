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
    Column("subject", Text),           # 어느 단어/문장에 대한 글인지 (갤러리 필터)
    Column("image", Text),             # base64 data URL of the handwriting photo
    Column("status", String(16)),      # visible | hidden | removed
    Column("reports", Integer, default=0),
    Column("perm", Integer, default=0),# 1=재열기(영구) → 신고에도 안 숨김
    Column("created_at", DateTime),
)

# 사각사각 — 소리를 듣고 쓴 의성어 손글씨 사진.
sagak = Table(
    "sagak", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sound", String(32)),
    Column("image", Text),
    Column("status", String(16)),
    Column("reports", Integer, default=0),
    Column("perm", Integer, default=0),
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


def _ensure_columns():
    """기존 테이블에 추가된 컬럼 보강 (create_all은 기존 테이블 컬럼을 못 늘림)."""
    from sqlalchemy import text as _t
    pg = engine.url.get_backend_name().startswith("postgres")
    cols = [("posts", "subject", "TEXT"), ("posts", "perm", "INTEGER DEFAULT 0"),
            ("sagak", "status", "VARCHAR(16)"), ("sagak", "reports", "INTEGER DEFAULT 0"),
            ("sagak", "perm", "INTEGER DEFAULT 0")]
    for tbl, col, typ in cols:
        sql = (f'ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {typ}' if pg
               else f'ALTER TABLE {tbl} ADD COLUMN {col} {typ}')
        try:
            with engine.begin() as c:
                c.execute(_t(sql))
        except Exception:
            pass


_ensure_columns()


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
def add_post(kind: str, image: str, subject: str = "") -> int:
    with engine.begin() as c:
        r = c.execute(insert(posts).values(kind=kind, subject=subject, image=image,
                                           status="visible", reports=0, perm=0, created_at=_now()))
        return int(r.inserted_primary_key[0])


def list_posts(kind: str, subject: str | None = None, limit: int = 300) -> list[dict]:
    w = [posts.c.kind == kind, posts.c.status == "visible"]
    if subject is not None:
        w.append(posts.c.subject == subject)
    with engine.begin() as c:
        rows = c.execute(select(posts).where(*w)
                         .order_by(posts.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def _report(tbl, iid: int) -> bool:
    with engine.begin() as c:
        row = c.execute(select(tbl).where(tbl.c.id == iid)).mappings().first()
        if not row:
            return False
        vals = {"reports": (row["reports"] or 0) + 1}
        if not row["perm"]:            # 영구(재열기)면 신고 받아도 안 숨김
            vals["status"] = "hidden"
        c.execute(update(tbl).where(tbl.c.id == iid).values(**vals))
    return True


def report_post(pid: int) -> bool:
    return _report(posts, pid)


def report_sagak(sid: int) -> bool:
    return _report(sagak, sid)


def review_queue(limit: int = 300) -> list[dict]:
    out = []
    with engine.begin() as c:
        for r in c.execute(select(posts).where(posts.c.status == "hidden")
                           .order_by(posts.c.id.desc()).limit(limit)).mappings():
            out.append({"t": "post", "id": r["id"], "image": r["image"],
                        "subject": r["subject"], "reports": r["reports"], "kind": r["kind"]})
        for r in c.execute(select(sagak).where(sagak.c.status == "hidden")
                           .order_by(sagak.c.id.desc()).limit(limit)).mappings():
            out.append({"t": "sagak", "id": r["id"], "image": r["image"],
                        "subject": r["sound"], "reports": r["reports"]})
    out.sort(key=lambda x: x["id"], reverse=True)
    return out


def moderate(t: str, iid: int, allow: bool) -> bool:
    tbl = sagak if t == "sagak" else posts
    with engine.begin() as c:
        if allow:                      # 다시 열기 = 영구(perm=1), 이후 신고 무시
            r = c.execute(update(tbl).where(tbl.c.id == iid).values(status="visible", perm=1))
        else:
            r = c.execute(update(tbl).where(tbl.c.id == iid).values(status="removed"))
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
        r = c.execute(insert(sagak).values(sound=sound, image=image, status="visible",
                                           reports=0, perm=0, created_at=_now()))
        return int(r.inserted_primary_key[0])


def list_sagak(sound: str, limit: int = 60) -> list[dict]:
    with engine.begin() as c:
        rows = c.execute(select(sagak).where(sagak.c.sound == sound, sagak.c.status == "visible")
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
