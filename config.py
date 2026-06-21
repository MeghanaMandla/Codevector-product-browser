"""
FastAPI application entrypoint. Run with:
    uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import router

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Browse ~200,000 products with consistent, fast cursor-based pagination.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, tags=["products"])


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
