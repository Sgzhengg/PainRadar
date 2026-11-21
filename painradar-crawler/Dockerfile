FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENABLE_CDP_MODE=False \
    HEADLESS=True \
    MEDIACRAWLER_HOME=/app/MediaCrawler \
    COOKIE_DIR=/data/cookies \
    TASK_DB=/data/tasks.db \
    RESULT_DIR=/data/results

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# MediaCrawler is cloned at build time, so the third-party repo never has to be
# committed. Pin a commit/tag with --build-arg MEDIACRAWLER_REF=<sha-or-tag>.
ARG MEDIACRAWLER_REPO=https://github.com/NanmiCoder/MediaCrawler.git
ARG MEDIACRAWLER_REF=main
RUN rm -rf /app/MediaCrawler \
    && (git clone --depth 1 --branch "${MEDIACRAWLER_REF}" "${MEDIACRAWLER_REPO}" /app/MediaCrawler \
        || (rm -rf /app/MediaCrawler \
            && git clone "${MEDIACRAWLER_REPO}" /app/MediaCrawler \
            && cd /app/MediaCrawler && git checkout "${MEDIACRAWLER_REF}"))
RUN pip install --no-cache-dir -r MediaCrawler/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY app.py runner.py storage.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /data/cookies /data/results /app/MediaCrawler/browser_data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
