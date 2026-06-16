"""Node role HTTP API.

Skeleton — endpoints are ported in migration phase 2. Target surface (parity
with OlcRTC-VPS):

    GET  /                      -> SPA (node dashboard)
    POST /api/v1                -> encrypted node API (list, *_user, *_all, ...)
    GET  /sse/{uid}             -> live log stream (Server-Sent Events)
    GET  /logs/{uid}/download   -> per-instance log download
    ...

See docs/PROTOCOL.md for the encrypted action set.
"""

from fastapi import APIRouter

router = APIRouter(tags=["node"])


@router.get("/api/v1/_placeholder")
def placeholder() -> dict:
    return {"role": "node", "status": "skeleton", "todo": "migration phase 2"}
