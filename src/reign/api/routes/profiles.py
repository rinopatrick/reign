"""Local profile management routes (issue #38)."""

import contextlib
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from reign.adapters.database import (
    DEFAULT_PROFILE,
    PROFILE_HEADER,
    get_session_factory,
    init_db,
    validate_slug,
)
from reign.exceptions import ProfileError
from reign.utils.seed import ensure_schema_version, seed_categories, seed_demo_account

router = APIRouter()

MAX_SLUG_LEN = 32


class ProfileCreate(BaseModel):
    slug: str


def _profiles_root() -> Path:
    override = os.getenv("REIGN_DATA_DIR")
    base = Path(override) if override else Path()
    root = base / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    return root


async def profile_session(request: Request):
    """Session for the X-Reign-Profile header, else the default profile."""
    slug = request.headers.get(PROFILE_HEADER, "") or DEFAULT_PROFILE
    slug = validate_slug(slug)
    await init_db(slug)
    async with get_session_factory(slug)() as session:
        yield session


@contextlib.asynccontextmanager
async def _session_for(slug: str):
    factory = get_session_factory(validate_slug(slug))
    async with factory() as session:
        yield session


@router.get("", response_model=list[str])
async def list_profiles():
    """List known profile slugs (default always present)."""
    slugs: set[str] = {DEFAULT_PROFILE}
    for child in _profiles_root().iterdir():
        if not child.is_dir():
            continue
        try:
            slugs.add(validate_slug(child.name))
        except ProfileError:
            continue
    return sorted(slugs)


@router.post("", status_code=201)
async def create_profile(data: ProfileCreate):
    """Create + initialize a profile's database (idempotent)."""
    try:
        slug = validate_slug(data.slug)
    except ProfileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if slug == DEFAULT_PROFILE:
        return {"profile": slug, "created": False}
    await init_db(slug)
    async with _session_for(slug) as s:
        await ensure_schema_version(s)
        await seed_categories(s)
        await seed_demo_account(s)
    return {"profile": slug, "created": True}
