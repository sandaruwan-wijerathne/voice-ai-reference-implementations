#!/bin/bash

# AI Voice Agent Frontend Launch Script

set -e

echo "🚀 Starting AI Voice Agent Frontend..."

# Check if node_modules exists, if not install dependencies
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Check if .env file exists, if not create a template
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file template..."
    echo "VITE_WS_URL=ws://localhost:8000/voice/browser/media-stream" > .env
    echo "✅ Created .env file with default WebSocket URL"
    echo "   Edit .env to change the WebSocket URL if needed"
fi

# Start the development server
echo "🎯 Starting development server..."
npm run dev

