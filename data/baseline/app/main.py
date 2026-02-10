"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.routers import health

app = FastAPI(
    title="Sample App",
    description="Baseline application for DESMET evaluation",
    version="0.1.0",
)

app.include_router(health.router)
