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
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/json": ".json",
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


# ----------------------------------------------------------------------------
# Upload via portal público (Fase A — anexos do cliente final).
# ----------------------------------------------------------------------------

# Whitelist de MIMEs aceitos via portal. Bloqueia explicitamente:
#   - image/svg+xml (XSS por SVG inline)
#   - text/html (XSS)
#   - application/zip e variantes (drop de malware)
#   - executáveis
ALLOWED_UPLOAD_MIMES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/json",
    }
)


def _detect_mime_from_bytes(head: bytes, declared: str | None) -> str | None:
    """Detecta MIME a partir dos primeiros bytes.
    Usa python-magic se disponível; fallback em magic-bytes manuais.
    Retorna o MIME confiável ou None."""
    try:
        import magic  # type: ignore[import-not-found]
    except ImportError:
        magic = None

    if magic is not None:
        try:
            detected = magic.from_buffer(head, mime=True)
            if detected:
                return detected.split(";")[0].strip().lower()
        except Exception as exc:  # noqa: BLE001
            logger.warning("magic.from_buffer falhou: %s — usando fallback", exc)

    # Fallback simples por magic bytes (cobre os MIMEs da whitelist).
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"%PDF":
        return "application/pdf"
    if head[:1] == b"{":
        # heurística JSON — não decisiva, deixa o declared decidir se for compatível
        if declared == "application/json":
            return "application/json"
    # texto plano: heurística pobre, mas se declared é text/* e bytes são printáveis...
    if declared and declared.startswith("text/"):
        try:
            head.decode("utf-8")
            return declared
        except UnicodeDecodeError:
            return None
    return None


class UploadValidationError(Exception):
    """Levantada quando o arquivo recusou a validação MIME/size."""


def save_uploaded_file(
    raw: bytes,
    declared_mime: str | None,
    *,
    max_bytes: int,
) -> tuple[str, str, int]:
    """Persiste bytes em /app/media/YYYY/MM/<uuid>.<ext>.

    Retorna (storage_key, mime_type_confirmado, byte_size).

    Levanta UploadValidationError se:
      - tamanho > max_bytes
      - MIME detectado não está na whitelist
      - MIME detectado diverge significativamente do declared (anti-polyglot)
    """
    byte_size = len(raw)
    if byte_size > max_bytes:
        raise UploadValidationError(
            f"arquivo excede o tamanho maximo de {max_bytes // (1024 * 1024)} MB"
        )
    if byte_size == 0:
        raise UploadValidationError("arquivo vazio")

    detected = _detect_mime_from_bytes(raw[:4096], declared_mime)
    if detected is None:
        raise UploadValidationError("tipo de arquivo nao reconhecido")
    if detected not in ALLOWED_UPLOAD_MIMES:
        raise UploadValidationError(f"tipo de arquivo nao permitido: {detected}")
    # anti-polyglot: se cliente declarou imagem e detectamos PDF (ou vice-versa), recusa.
    if declared_mime:
        d = declared_mime.split(";")[0].strip().lower()
        # permite mismatch só dentro do mesmo "grupo" (image/* ↔ image/*).
        if d != detected:
            d_group = d.split("/", 1)[0]
            det_group = detected.split("/", 1)[0]
            if d_group != det_group:
                raise UploadValidationError(
                    f"tipo declarado ({d}) diverge do conteudo ({detected})"
                )

    settings = get_settings()
    base_dir = Path(settings.media_storage_dir)
    today = datetime.utcnow()
    sub = Path(today.strftime("%Y/%m"))
    target_dir = base_dir / sub
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = EXTENSION_BY_MIME.get(detected, mimetypes.guess_extension(detected) or ".bin")
    filename = f"{uuid.uuid4().hex}{ext}"
    relative = sub / filename
    absolute = base_dir / relative

    try:
        with absolute.open("wb") as handle:
            handle.write(raw)
    except OSError as exc:
        logger.error("falha ao gravar upload %s: %s", absolute, exc)
        raise UploadValidationError("erro interno ao salvar arquivo") from exc

    storage_key = str(relative).replace("\\", "/")
    return storage_key, detected, byte_size


def resolve_storage_path(storage_key: str) -> Path | None:
    settings = get_settings()
    base = Path(settings.media_storage_dir).resolve()
    candidate = (base / storage_key).resolve()
    if base not in candidate.parents and candidate != base:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate
