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
    )


if __name__ == "__main__":
    main()
