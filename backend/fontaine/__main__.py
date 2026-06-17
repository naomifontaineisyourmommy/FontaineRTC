"""Entrypoint:  python -m fontaine  (role chosen via FONTAINE_ROLE env)."""

import uvicorn

from .config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "fontaine.app:create_app",
        factory=True,
        host=settings.panel_host,
        port=settings.panel_port,
        log_level="info",
        # Long-lived SSE log streams would otherwise hold the process open on
        # shutdown, making `systemctl restart` wait for the systemd stop timeout.
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    main()
