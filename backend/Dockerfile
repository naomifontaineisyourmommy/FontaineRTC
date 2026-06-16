# Build context is the repo root (see docker-compose.yml): paths are repo-relative.
FROM python:3.12-slim

WORKDIR /app

# System deps: ffmpeg for the node role's videochannel transport.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/fontaine backend/fontaine
RUN pip install --no-cache-dir ./backend

# Built SPA (committed in the repo) so the container serves the UI without Node.
COPY frontend/dist ./spa
ENV FONTAINE_DIST_DIR=/app/spa

EXPOSE 8080
CMD ["python", "-m", "fontaine"]
