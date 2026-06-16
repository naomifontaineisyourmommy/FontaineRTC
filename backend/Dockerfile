FROM python:3.12-slim

WORKDIR /app

# System deps: ffmpeg for the node role's videochannel transport.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY fontaine ./fontaine

EXPOSE 8080
CMD ["python", "-m", "fontaine"]
