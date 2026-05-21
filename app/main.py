import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.ratelimit import limiter, rate_limit_handler
from app.services.auto_close import waiting_customer_auto_close_loop

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    auto_close_task: asyncio.Task[None] | None = None
    if settings.waiting_customer_auto_close_enabled:
        auto_close_task = asyncio.create_task(waiting_customer_auto_close_loop())
    try:
        yield
    finally:
        if auto_close_task is not None:
            auto_close_task.cancel()
            with suppress(asyncio.CancelledError):
                await auto_close_task

# F-15 Phase 4.3: desabilitar /docs, /redoc e /openapi.json em produção.
_is_prod = (settings.environment or "").lower() == "production"
app = FastAPI(
    title=settings.app_name,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
    lifespan=lifespan,
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
