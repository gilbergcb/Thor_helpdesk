import ipaddress
import logging
import mimetypes
import socket
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.security_flags import FlagMode, audit_log, flag_mode

logger = logging.getLogger("media.storage")


def _allowed_hosts() -> list[str]:
    raw = get_settings().ssrf_allowed_hosts or ""
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def _host_allowed(host: str, allowlist: list[str]) -> bool:
    h = host.lower()
    for entry in allowlist:
        if entry.startswith("."):
            if h.endswith(entry) or h == entry[1:]:
                return True
        elif h == entry:
            return True
    return False


def _resolves_to_private(host: str) -> bool:
    """Bloqueia IPs internos / loopback / link-local (defense-in-depth)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # se não resolve, trata como suspeito
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _ssrf_check(url: str) -> str | None:
    """Aplica SECURITY_SSRF_ALLOWLIST. Retorna None se ok, ou string=motivo se bloqueado.
    Em modo audit, o caller só loga; em enforce, abortar."""
    settings = get_settings()
    mode = flag_mode(settings.security_ssrf_allowlist)
    if mode is FlagMode.OFF:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        reason = f"scheme_blocked:{parsed.scheme}"
    elif not parsed.hostname:
        reason = "missing_host"
    elif not _host_allowed(parsed.hostname, _allowed_hosts()):
        reason = f"host_not_allowlisted:{parsed.hostname}"
    elif _resolves_to_private(parsed.hostname):
        reason = f"private_ip:{parsed.hostname}"
    else:
        return None

    if mode is FlagMode.AUDIT:
        audit_log("ssrf.download", reason=reason, url=url)
        return None  # audit não bloqueia
    return reason  # enforce

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
    blocked = _ssrf_check(url)
    if blocked is not None:
        logger.warning("media download blocked by SSRF guard url=%s reason=%s", url, blocked)
        return None

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
