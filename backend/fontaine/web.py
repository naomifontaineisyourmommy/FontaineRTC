"""Serve the built React SPA (frontend/dist) and fall back to index.html for
client-side routing. Enabled from app.py once the frontend is built.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def mount_spa(app: FastAPI) -> None:
    if not _DIST.exists():
        return
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        return FileResponse(_DIST / "index.html")
