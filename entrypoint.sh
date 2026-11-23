#!/usr/bin/env bash
set -e

# Start bgutil POT token generator on port 4416 if built
if [ -f "/app/bgutil-ytdlp-pot-provider/server/build/main.js" ]; then
    echo "Starting YouTube POT token generator on port 4416..."
    node /app/bgutil-ytdlp-pot-provider/server/build/main.js -p 4416 -H 127.0.0.1 > /dev/null 2>&1 &
fi

echo "Starting PeakCut Studio on port ${PORT:-7860}..."
exec python -m studio.server
