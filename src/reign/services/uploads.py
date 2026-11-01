"""Shared limited-upload reader (chunked, aborts before OOM)."""

from fastapi import HTTPException, UploadFile

CHUNK_SIZE = 1024 * 1024


async def read_limited_upload(file: UploadFile, limit: int, label: str) -> bytes:
    """Read upload in chunks, raise 413 once the cap is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"{label} too large")
        chunks.append(chunk)
    return b"".join(chunks)
