#!/bin/sh
# Frontend Docker entrypoint script
# Configures WebSocket URL and starts nginx

set -e

echo "🚀 Starting AI Voice Agent Frontend..."

if [ -n "$WS_URL" ]; then
    FINAL_WS_URL="$WS_URL"
    echo "✓ Using explicit WebSocket URL: $FINAL_WS_URL"
    
elif [ -n "$BACKEND_SERVICE" ]; then
    BACKEND_HOST="$BACKEND_SERVICE"
    BACKEND_PORT="${BACKEND_PORT:-8000}"
    WS_PROTOCOL="${WS_PROTOCOL:-ws}"
    FINAL_WS_URL="${WS_PROTOCOL}://${BACKEND_HOST}:${BACKEND_PORT}/voice/browser/media-stream"
    echo "✓ Built WebSocket URL from service: $FINAL_WS_URL"
    
else
    FINAL_WS_URL="wss://vsvoice-demo.vetstoria.space/voice/browser/media-stream"
    echo "✓ Using default WebSocket URL: $FINAL_WS_URL"
fi

echo "Injecting WebSocket URL into config.js..."
echo "window.__WS_URL__=\"$FINAL_WS_URL\";" > /usr/share/nginx/html/config.js

echo "Updating index.html..."
sed -i "s|</head>|<script src=\"/config.js\"></script></head>|g" /usr/share/nginx/html/index.html

echo "Configuration complete!"
echo "Starting nginx..."

exec nginx -g "daemon off;"

