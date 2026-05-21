from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.ratelimit import limiter, rate_limit_handler

settings = get_settings()

# F-15 Phase 4.3: desabilitar /docs, /redoc e /openapi.json em produção.
_is_prod = (settings.environment or "").lower() == "production"
app = FastAPI(
    title=settings.app_name,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

# F-11 Phase 4.5: CORS estrito — sem wildcard em origins/methods/headers.
# Startup assert proibe origin '*'.
if any(o == "*" for o in settings.cors_origins):
    raise ValueError("CORS_ORIGINS não pode conter '*' — listar origens explicitamente.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=600,
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
