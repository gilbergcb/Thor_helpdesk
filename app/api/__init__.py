from fastapi import APIRouter

from app.api import admin, auth, media, tickets, webhooks

api_router = APIRouter()
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(media.router)
api_router.include_router(tickets.router)
api_router.include_router(webhooks.router)
