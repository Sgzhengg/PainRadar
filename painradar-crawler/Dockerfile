FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENABLE_CDP_MODE=False \
    HEADLESS=True \
    MEDIACRAWLER_HOME=/app/MediaCrawler \
    COOKIE_DIR=/data/cookies \
    TASK_DB=/data/tasks.db \
    RESULT_DIR=/data/results \
    MAX_CONCURRENT_TASKS=1

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
    && git init /app/MediaCrawler \
    && cd /app/MediaCrawler \
    && git remote add origin "${MEDIACRAWLER_REPO}" \
    && git fetch --depth 1 origin "${MEDIACRAWLER_REF}" \
    && git checkout --detach FETCH_HEAD \
    && rm -rf .git
RUN pip install --no-cache-dir -r MediaCrawler/requirements.txt \
    && python -m playwright install --with-deps chromium

# Node is only needed at runtime by MediaCrawler's execjs signature helper.
# Keep it in a late layer so future code changes don't invalidate the browser
# and Python dependency layers above.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY app.py runner.py storage.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /data/cookies /data/results /app/MediaCrawler/browser_data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
