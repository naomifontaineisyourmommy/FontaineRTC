"""Admin role HTTP API.

Skeleton — endpoints are ported in migration phase 3. Target surface (parity
with OlcRTC-AdminVPS):

    GET  /                      -> SPA (admin dashboard)
    POST /push/v1/{server_id}   -> receive encrypted state push from a node
    POST /api/login             -> session login
    POST /api/data              -> aggregated dashboard data
    POST /api/server/*          -> add/edit/delete server, proxy node actions
    POST /api/group/*           -> group management
    POST /api/v1                -> encrypted external API (list)
    ...

See docs/PROTOCOL.md for the encrypted action set.
"""

from fastapi import APIRouter

router = APIRouter(tags=["admin"])


@router.get("/api/v1/_placeholder")
def placeholder() -> dict:
    return {"role": "admin", "status": "skeleton", "todo": "migration phase 3"}
