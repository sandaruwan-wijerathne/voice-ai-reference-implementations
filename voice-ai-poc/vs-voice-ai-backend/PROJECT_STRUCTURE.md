# Project Structure Summary

## Overview
**Petvisor Voice API** is a FastAPI-based backend system that provides AI-powered veterinary appointment booking services through voice (WebSocket) interfaces. The system integrates with OpenAI's realtime voice models and Vetstoria API for appointment management.

## Technology Stack
- **Framework**: FastAPI (Python 3.12+)
- **AI/ML**: LangChain, OpenAI (`gpt-realtime` model)
- **Communication**: WebSockets
- **Dependency Management**: Poetry
- **Database**: SQLite with S3 backup support
- **API Integration**: Vetstoria (veterinary practice management system)
- **Audio Processing**: Spectral gating for noise reduction

## Project Architecture

### Core Application Files

#### `app.py`
- FastAPI application entry point
- Configures CORS middleware (allows all origins in current setup)
- Includes main router from `routes.py`

#### `routes.py`
- Main router configuration
- Health check endpoint (`GET /health`) - checks database and API status
- Root endpoint (`GET /`) - requires API key authentication
- Version endpoint (`GET /version`) - returns application version
- Includes voice routes (`/voice/*`)

### Route Handlers

#### `voice_routes.py`
Handles voice-based interactions:
- **`GET /voice/`**: Health check endpoint (requires API key)
- **`/voice/browser/*`**: Browser-based WebSocket voice interface (includes router from `openai_speech_to_speech/websocket_openai.py`)
- **`/voice/ws-test`**: Test WebSocket endpoint (echo server for testing)

### AI Integration Modules

#### `openai_speech_to_speech/`
OpenAI Realtime API integration module:
- **`constants_openai.py`**: System instructions and voice configuration
  - `SYSTEM_INSTRUCTION_VOICE`: Detailed instructions for voice agent behavior
  - `VOICE`: Voice configuration (default: 'marin')
  - Dynamic system instructions that include API data (species, appointment types, schedules)
  
- **`websocket_openai.py`**: Browser-based WebSocket handler
  - Main WebSocket endpoint handler for `/voice/browser/media-stream`
  - Creates conversation records in database
  - Manages WebSocket context variables for tools
  - Integrates with `OpenAIVoiceReactAgent` from `langchain_openai/`
  - Tracks appointment booking status
  - Endpoint: `WebSocket /voice/browser/media-stream`
  
- **`websocket_gpt_realtime.py`**: Alternative WebSocket implementation (similar to `websocket_openai.py`)

- **`langchain_openai/`**: LangChain OpenAI integration
  - **`__init__.py`**: Contains `OpenAIVoiceReactAgent` class
    - Manages OpenAI Realtime API WebSocket connections
    - Handles voice input/output streaming
    - Processes tool calls for appointment booking
    - Event handling for voice interactions
    - Message exchange tracking with token usage
    - Audio processing integration (spectral gating)
    - Supports `gpt-realtime` model
  
  - **`utils.py`**: Async stream merging utilities
    - `amerge()`: Merges multiple async streams into one

### External API Integration

#### `vetstoria/`
Vetstoria practice management system integration:
- **`api.py`**: Main API client
  - Authentication with Bearer token
  - Methods:
    - `authenticate()`: Authenticates and stores auth token
    - `get_species()`: Retrieve available pet species (Dog, Cat)
    - `get_appointment_types()`: Get appointment types (Vaccinations, Consultation, Dental, Nurse appointment)
    - `get_schedules()`: Get available clinicians (Dr Meredith Grey, Dr Gregory House)
    - `get_slots()`: Retrieve available time slots for booking
    - `place_appointment()`: Create new appointment booking

- **`settings.py`**: Vetstoria API configuration (base URL, auth URL, credentials)
  - Uses Pydantic BaseSettings for environment variable management

### Utility Modules

#### `utils/`
Shared utility functions and tools:
- **`tools.py`**: LangChain tools for voice interface
  - `get_available_time_slots`: Retrieves available appointment slots from Vetstoria
  - `place_appointment`: Creates appointments in Vetstoria system
  - `close_websocket`: Tool to gracefully close WebSocket connections
  - Defines static lists for species, appointment types, and schedules
  - Includes time period categorization (MORNING/AFTERNOON/EVENING)
  - Context variables for WebSocket, conversation tracking, and appointment status
  - Detailed tool descriptions for voice interactions

- **`utils.py`**: General utilities
  - `websocket_stream()`: WebSocket streaming helper function
  - Converts WebSocket messages to async iterator

- **`audio_processing.py`**: Audio processing utilities
  - `process_audio_with_spectral_gating()`: Noise reduction using spectral gating
  - `should_process_audio_event()`: Determines if audio event should be processed
  - Uses `noisereduce` library for noise reduction

- **`db_backup.py`**: Database backup utilities
  - `upload_db_to_s3()`: Uploads SQLite database to S3 with timestamp-based folder structure
  - Configurable S3 bucket and region via environment variables

- **`backup_db_cli.py`**: CLI script for manual database backups
  - Can be used with cron jobs for automated backups

### Authentication

#### `auth.py`
API key authentication:
- `verify_api_key()`: Dependency for HTTP endpoint authentication
  - Validates API key from `X-API-Key` header
  - Returns user dictionary if valid
  - Raises 401 if invalid or missing
  
- `verify_websocket_api_key()`: WebSocket authentication
  - Validates API key from WebSocket query parameters (`?api_key=...`)
  - Closes connection with error if invalid
  - Returns user dictionary if valid

### Scripts

#### `launch.sh`
Application launch script for starting the FastAPI server
- Checks for Poetry installation
- Verifies dependencies
- Starts development server with auto-reload

#### `scripts/`
Deployment and maintenance scripts:
- **`docker-entrypoint.sh`**: Docker container entrypoint
  - Starts cron daemon for automated backups
  - Starts FastAPI application
  - Configures logging for cron jobs
  
- **`backup-cron`**: Cron job configuration file
  - Defines schedule for database backups
  
- **`cron_backup.sh`**: Shell wrapper for cron backup jobs
  - Executes Python backup script
  - Handles logging and error reporting

## Key Features

### 1. Voice Communication
- **Browser WebSocket**: Real-time voice interaction via browser
- **OpenAI Realtime API**: Direct integration with GPT-4o-realtime-preview for voice conversations

### 2. AI Assistant
- Conversational booking assistant for voice calls
- Multi-step appointment booking flow:
  1. Pet species selection (Cat/Dog)
  2. Appointment type (Vaccinations, Consultation, Dental, Nurse appointment)
  3. Clinician selection (Dr Meredith Grey, Dr Gregory House)
  4. Preferred date and time
  5. Time slot selection (from available slots)
  6. Confirmation and booking placement

### 3. Tool Integration
- LangChain tools for:
  - Slot availability checking (`get_available_time_slots`)
  - Appointment booking (`place_appointment`)
- Dynamic tool binding to OpenAI Realtime API

## API Endpoints Summary

### Health Checks
- `GET /health` - Main health check (checks database and API status)
- `GET /` - Root endpoint (requires API key via `X-API-Key` header)
- `GET /version` - Returns application version
- `GET /voice/` - Voice API health check (requires API key)
- `GET /voice/browser/` - Browser routes health check (requires API key)

### Voice Endpoints
- `WebSocket /voice/browser/media-stream` - Browser voice interface
  - Real-time bidirectional audio streaming
  - Uses OpenAI Realtime API (`gpt-realtime` model) for voice processing
  - Requires API key as query parameter: `?api_key=your_api_key`
  - Integrates with booking tools
  - Tracks conversations and message exchanges
  - Includes audio noise reduction processing
  
- `WebSocket /voice/ws-test` - Test WebSocket endpoint
  - Simple echo server for testing WebSocket connections
  - Requires API key as query parameter: `?api_key=your_api_key`

## Data Flow

### Voice Booking Flow
1. WebSocket connection established from browser with API key
2. API key verified and user authenticated
3. Conversation record created in database
4. Audio stream processed by OpenAI Voice React Agent
5. Audio noise reduction applied (spectral gating)
6. Real-time transcription and response generation
7. Tools invoked when booking intent detected:
   - `get_available_time_slots` → Vetstoria API
   - `place_appointment` → Vetstoria API
8. Message exchanges logged with token usage
9. Audio response streamed back to client
10. Booking confirmation communicated via voice
11. Conversation record updated when connection closes
12. Appointment booking status tracked in database

## Environment Variables Required

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Vetstoria
BASE_URL=your_vetstoria_base_url
AUTH_URL=your_vetstoria_auth_url
PARTNER_KEY=your_partner_key
SITE_HASH=your_site_hash
SECRET=your_secret
SITE_ID=your_site_id
BOOKING_HASH=your_booking_hash

# Database Backup (Optional)
DB_BACKUP_BUCKET=vs-voice-dev-db-backups  # S3 bucket for backups
AWS_REGION=eu-west-1                       # AWS region
```

## Dependencies (Key Packages)
- `fastapi` - Web framework
- `langchain-core`, `langchain-openai`, `langchain-community` - AI/ML framework
- `langgraph` - LangChain graph execution
- `websockets` - WebSocket support
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation and settings management
- `pydantic-settings` - Settings management
- `uvicorn` - ASGI server
- `requests` - HTTP client for Vetstoria API
- `boto3` - AWS SDK for S3 backups
- `noisereduce` - Audio noise reduction
- `numpy` - Numerical operations for audio processing
- `twilio` - SMS/voice communication (if needed)
- `python-multipart` - Multipart form data support

## Database Schema

### Tables

#### `users`
- `id` (INTEGER PRIMARY KEY)
- `username` (TEXT UNIQUE)
- `api_key` (TEXT UNIQUE)
- `created_at` (TIMESTAMP)

#### `conversations`
- `id` (INTEGER PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY to users)
- `start_time` (TIMESTAMP)
- `end_time` (TIMESTAMP)
- `rating` (INTEGER)
- `appointment_booked` (INTEGER, 0 or 1)

#### `message_exchanges`
- `id` (INTEGER PRIMARY KEY)
- `conversation_id` (INTEGER, FOREIGN KEY to conversations)
- `timestamp` (TIMESTAMP)
- `user_input` (TEXT)
- `ai_response` (TEXT)
- `input_tokens` (INTEGER)
- `output_tokens` (INTEGER)
- `total_tokens` (INTEGER)

## Current State & Notes
- CORS is currently set to allow all origins (should be restricted in production)
- Voice-only implementation (text/SMS functionality removed)
- Uses OpenAI Realtime API (`gpt-realtime` model) for voice interactions
- Vetstoria API integration for appointment management
- Static data lists defined in `utils/tools.py` for species, appointment types, and schedules
- System instructions dynamically include API data (species, appointment types, schedules)
- API key authentication required for all endpoints (except `/health` and `/version`)
- Audio processing with spectral gating for noise reduction
- Conversation and message exchange tracking with token usage
- Automated database backups to S3 via cron jobs
