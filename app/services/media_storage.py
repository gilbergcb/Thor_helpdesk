import logging
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger("media.storage")

EXTENSION_BY_MIME: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "application/pdf": ".pdf",
}


def _extension_for(mime_type: str | None, fallback_url: str | None) -> str:
    if mime_type:
        clean = mime_type.split(";")[0].strip().lower()
        if clean in EXTENSION_BY_MIME:
            return EXTENSION_BY_MIME[clean]
        guess = mimetypes.guess_extension(clean)
        if guess:
            return guess
    if fallback_url:
        suffix = Path(fallback_url.split("?")[0]).suffix
        if suffix and len(suffix) <= 6:
            return suffix
    return ".bin"


def download_to_storage(url: str, mime_type: str | None = None) -> str | None:
    """Fetch a Z-API media URL and persist locally. Returns relative storage key."""
    settings = get_settings()
    base_dir = Path(settings.media_storage_dir)
    today = datetime.utcnow()
    sub = Path(today.strftime("%Y/%m"))
    target_dir = base_dir / sub
    target_dir.mkdir(parents=True, exist_ok=True)

    extension = _extension_for(mime_type, url)
    filename = f"{uuid.uuid4().hex}{extension}"
    relative = sub / filename
    absolute = base_dir / relative

    try:
        with httpx.stream("GET", url, timeout=30.0, follow_redirects=True) as response:
            response.raise_for_status()
            with absolute.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("media download failed for %s: %s", url, exc)
        if absolute.exists():
            absolute.unlink(missing_ok=True)
        return None

    return str(relative).replace("\\", "/")


def resolve_storage_path(storage_key: str) -> Path | None:
    settings = get_settings()
    base = Path(settings.media_storage_dir).resolve()
    candidate = (base / storage_key).resolve()
    if base not in candidate.parents and candidate != base:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate
