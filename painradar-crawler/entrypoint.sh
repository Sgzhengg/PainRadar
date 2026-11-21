#!/bin/sh
set -e

# Persist MediaCrawler's Chrome profile on the Zeabur volume. MediaCrawler writes
# to "$(pwd)/browser_data", so linking that path to /data makes QR-login state
# survive redeploys without any copy step.
if mkdir -p /data/browser_data 2>/dev/null; then
    rm -rf /app/MediaCrawler/browser_data
    ln -s /data/browser_data /app/MediaCrawler/browser_data
fi

exec "$@"
