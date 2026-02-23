# AI Voice Agent Frontend

A React application for interacting with an AI voice agent via WebSocket.

## Features

- Start voice conversation with AI agent
- Real-time WebSocket connection with binary audio streaming
- Microphone audio capture and streaming
- Audio playback from AI agent
- Visual pulsing indicator when agent is speaking
- Restart and end conversation controls
- Connection status indicator
- Compatible with lanchang OpenAIVoiceReactAgent protocol

## Setup

### Quick Start (Using Launch Script)

Simply run the launch script:
```bash
./launch.sh
```

The script will:
- Automatically install dependencies if needed
- Create a `.env` file with default WebSocket URL if it doesn't exist
- Start the development server

### Manual Setup

1. Install dependencies:
```bash
npm install
```

2. Configure WebSocket URL (optional):
   - Create a `.env` file in the root directory
   - Add: `VITE_WS_URL=ws://your-backend-url:port/voice/browser/media-stream`
   - Default: `ws://localhost:8000/voice/browser/media-stream`

3. Start development server:
```bash
npm run dev
```

4. Build for production:
```bash
npm run build
```

### Browser Permissions

The app requires microphone access to stream audio to the voice agent. When you click "Start Voice Conversation", your browser will prompt you to allow microphone access. Make sure to grant permission for the app to work properly.

## WebSocket Protocol

This implementation is compatible with **lanchang OpenAIVoiceReactAgent** and uses AudioWorklet for high-quality audio processing.

### Audio Processing
- **Input**: Microphone audio is captured using AudioWorklet, converted to PCM16 format (24kHz sample rate), buffered, and sent as base64-encoded JSON messages
- **Output**: Audio from the agent is received as base64-encoded PCM16 data in JSON messages and played through AudioWorklet
- **Buffer Size**: Audio is buffered in 4800-byte chunks before sending

### JSON Message Format

#### Messages Sent to Backend:
- `input_audio_buffer.append` - Send buffered audio data:
  ```json
  {
    "type": "input_audio_buffer.append",
    "audio": "<base64-encoded-pcm16-audio>"
  }
  ```

#### Messages Received from Backend:
- `response.audio.delta` - Audio chunk from agent (base64-encoded PCM16):
  ```json
  {
    "type": "response.audio.delta",
    "delta": "<base64-encoded-pcm16-audio>"
  }
  ```
- `response.audio.done` - Agent finished sending audio
- `response.done` - Response completed
- `response.audio_transcript.done` - Transcript of agent's speech
- `conversation.item.input_audio_transcription.completed` - User's speech transcription
- `session.update` - Session configuration updates
- `error` - Error messages

## Project Structure

```
frontend/
├── public/
│   └── static/
│       ├── audio-processor-worklet.js    # AudioWorklet for microphone capture
│       └── audio-playback-worklet.js     # AudioWorklet for audio playback
├── src/
│   ├── App.jsx          # Main application component
│   ├── App.css          # Application styles
│   ├── main.jsx         # React entry point
│   └── index.css        # Global styles
├── index.html           # HTML entry point
├── vite.config.js       # Vite configuration
├── package.json         # Dependencies
└── launch.sh            # Launch script
```

## Technical Details

- **Audio Format**: PCM16 (16-bit signed integers)
- **Sample Rate**: 24kHz
- **Audio Processing**: AudioWorklet for low-latency audio processing
- **Buffering**: Input audio is buffered in 4800-byte chunks before transmission

