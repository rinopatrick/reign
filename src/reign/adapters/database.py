"""Database engine registry — one SQLite file per local profile.

Design (issue #38):
- Single-user desktop app, no login. Profiles isolate data by directory:
  `<data_dir>/profiles/<slug>/reign.db` (+ `backups/` alongside).
- The `default` profile transparently uses the legacy `./reign.db` location
  so existing users migrate with zero action.
- Slug rules: 1-32 chars, lowercase letters/digits/hyphen only.
  Anything else raises ProfileError (mapped to 400).
- `get_session` serves the configured default profile and stays Depends-safe
  (no Request parameter — FastAPI inspects dependency signatures).
  Routes needing per-request switching read the `X-Reign-Profile` header
  themselves via `profile_from_header` + `session_for_profile`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from reign.config import settings
from reign.exceptions import ProfileError

Base = declarative_base()

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
DEFAULT_PROFILE = "default"
PROFILE_HEADER = "x-reign-profile"

_engines: dict[str, object] = {}
_sessions: dict[str, async_sessionmaker[AsyncSession]] = {}
_default_profile = os.getenv("REIGN_PROFILE", DEFAULT_PROFILE)


def validate_slug(slug: str) -> str:
    """Normalize + validate a profile slug, raising ProfileError on misuse."""
    slug = (slug or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise ProfileError("Invalid profile slug (1-32 chars, lowercase letters/digits/hyphen)")
    return slug


def set_default_profile(slug: str) -> str:
    """Validate a fallback profile name (tests pin the default profile)."""
    return validate_slug(slug)


def active_profile() -> str:
    """Configured default profile (REIGN_PROFILE env or "default")."""
    return validate_slug(_default_profile or DEFAULT_PROFILE)


def _data_root() -> Path:
    """App data dir; REIGN_DATA_DIR overrides (desktop sets per-OS path)."""
    override = os.getenv("REIGN_DATA_DIR")
    if override:
        return Path(override)
    if settings.backups_dir != "./backups":
        return Path(settings.backups_dir).parent
    return Path()


def profile_db_url(slug: str) -> str:
    """Database URL for a profile. `default` keeps the legacy location."""
    slug = validate_slug(slug)
    explicit = os.getenv("DATABASE_URL")
    if slug == DEFAULT_PROFILE and explicit:
        return explicit
    if slug == DEFAULT_PROFILE:
        return settings.database_url
    root = _data_root()
    db_path = root / "profiles" / slug / "reign.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


def get_engine(slug: str):
    """Cached async engine per profile slug."""
    slug = validate_slug(slug)
    engine = _engines.get(slug)
    if engine is None:
        engine = create_async_engine(profile_db_url(slug), future=True)
        _engines[slug] = engine
    return engine


def get_session_factory(slug: str) -> async_sessionmaker[AsyncSession]:
    """Cached session factory per profile slug."""
    slug = validate_slug(slug)
    factory = _sessions.get(slug)
    if factory is None:
        factory = async_sessionmaker(get_engine(slug), expire_on_commit=False)
        _sessions[slug] = factory
    return factory


# Backwards-compatible single-profile objects (used by desktop/tests).
# Delegate to the default profile engine so there is exactly one database file
# and schema path per profile; init_db() migrates it via ensure_schema_version.
engine = get_engine(DEFAULT_PROFILE)
AsyncSessionLocal = get_session_factory(DEFAULT_PROFILE)


async def init_db(profile: str | None = None) -> None:
    """Create all tables for a profile, then run pending forward migrations."""
    from reign.utils.seed import ensure_schema_version  # noqa: PLC0415  # lazy: breaks models import cycle

    slug = validate_slug(profile or _default_profile)
    eng = get_engine(slug)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory(slug)
    async with factory() as session:
        await ensure_schema_version(session)


async def get_session():
    """Yield a session for the configured default profile (Depends-safe)."""
    async with get_session_factory(active_profile())() as session:
        yield session


async def session_for_profile(slug: str):
    """Yield a session for an explicit profile slug."""
    async with get_session_factory(validate_slug(slug))() as session:
        yield session
