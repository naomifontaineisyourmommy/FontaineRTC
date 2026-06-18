"""Serve the built React SPA (frontend/dist).

Any real file under dist (index.html, assets/*, fonts/*, naomi.jpg, …) is served
directly; every other path falls back to index.html for client-side routing.
Enabled from app.py once the frontend is built. Path override: FONTAINE_DIST_DIR.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

_DIST = Path(
    os.environ.get("FONTAINE_DIST_DIR")
    or Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
)


def mount_spa(app: FastAPI) -> None:
    if not _DIST.exists():
        return
    dist = _DIST.resolve()
    index = dist / "index.html"

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        if full_path:
            target = (dist / full_path).resolve()
            # serve real files within dist; guard against path traversal
            if target.is_file() and dist in target.parents:
                return FileResponse(target)
        return FileResponse(index)
