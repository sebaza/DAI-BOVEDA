"""Boveda DAI - standalone host of the Percepcion / Termometro Institucional module."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base
from app.routers import auth, percepcion, tasks
from app.services.percepcion.db import percepcion_write_engine

logger = logging.getLogger("boveda")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Importing the percepcion router registered every model in Base.metadata. create_all
    # is checkfirst: it creates MISSING tables (a fresh local SQLite) and never touches or
    # alters tables that already exist (e.g. the mirror tables owned by the worker).
    try:
        Base.metadata.create_all(percepcion_write_engine)
    except Exception:  # noqa: BLE001 - read-only DB / no DDL permission: the module degrades by itself
        logger.warning("Base.metadata.create_all failed; continuing with the existing schema.", exc_info=True)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # bearer token in a header, no cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tasks-Token"],
)

app.include_router(auth.router)
app.include_router(percepcion.router)
app.include_router(tasks.router, prefix="/tasks")
app.include_router(tasks.router, prefix="/ai-tasks", include_in_schema=False)  # legacy Torre path


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
