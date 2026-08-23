FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN python -m compileall -q -f main.py skylinebot

RUN useradd --create-home --uid 10001 skyline \
    && mkdir -p /app/logs /app/storage/runtime /app/uploads \
    && chown -R skyline:skyline /app

USER skyline

ENV RUN_COMPONENTS=all \
    RUN_BOT=true \
    RUN_WEB=true \
    DASHBOARD_ENABLED=true \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "export WEB_PORT=\"${PORT:-${WEB_PORT:-8080}}\"; exec python main.py"]
