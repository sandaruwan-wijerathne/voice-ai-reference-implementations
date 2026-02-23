# Petvisor Voice API Backend

Backend for the Petvisor Voice API - an AI-powered voice assistant for veterinary appointment booking.

## Prerequisites

- Python 3.12+
- Poetry (Python dependency management)
- OpenAI API key
- Vetstoria API credentials

## Setup

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Set up environment variables**:
   
   Create a `.env` file in the root directory with the following variables:
   
   ```env
   # OpenAI
   OPENAI_API_KEY=your_openai_api_key_here
   
   # Vetstoria API
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

4. **Activate Poetry shell** (optional but recommended):
   ```bash
   poetry shell
   ```

## Running the Application

### Development Server

Run the FastAPI application using uvicorn:

```bash
poetry run uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Or if you're in the Poetry shell:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc

### Production Server

For production, use:
```bash
poetry run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Health Checks
- `GET /health` - Main health check endpoint (checks database and API status)
- `GET /` - Root endpoint (requires API key via `X-API-Key` header)
- `GET /version` - Returns application version
- `GET /voice/` - Voice API health check (requires API key)
- `GET /voice/browser/` - Browser routes health check (requires API key)

### Voice Endpoints
- `WebSocket /voice/browser/media-stream` - Browser voice interface
  - Real-time bidirectional audio streaming
  - Uses OpenAI Realtime API (`gpt-realtime` model)
  - Requires API key as query parameter: `?api_key=your_api_key`
  - Supports appointment booking via voice conversation
  - Tracks conversations and message exchanges in database
  - Includes audio noise reduction processing
  
- `WebSocket /voice/ws-test` - Test WebSocket endpoint
  - Simple echo server for testing WebSocket connections
  - Requires API key as query parameter: `?api_key=your_api_key`

## Project Structure

```
backend/
├── app.py                          # FastAPI application entry point
├── routes.py                       # Main router configuration
├── voice_routes.py                 # Voice route handlers
├── auth.py                         # API key authentication
├── openai_speech_to_speech/        # OpenAI Realtime API integration
│   ├── __init__.py                 # Package initialization
│   ├── constants_openai.py         # System instructions and voice configuration
│   ├── websocket_openai.py         # Browser WebSocket handler
│   ├── websocket_gpt_realtime.py   # Alternative WebSocket implementation
│   └── langchain_openai/           # LangChain OpenAI integration
│       ├── __init__.py             # OpenAIVoiceReactAgent implementation
│       └── utils.py                # Async stream merging utilities
├── database/                       # Database layer
│   ├── __init__.py                 # Database initialization & utilities
│   ├── init_database.py            # Database initialization CLI
│   ├── manage_conversations.py     # Conversation management
│   └── manage_users.py             # User management
├── utils/                          # Utility modules
│   ├── tools.py                    # LangChain tools for booking
│   ├── utils.py                    # General utilities (WebSocket streaming)
│   ├── audio_processing.py         # Audio noise reduction utilities
│   ├── db_backup.py                # S3 backup/restore functions
│   └── backup_db_cli.py            # Backup CLI script (for cron)
├── scripts/                        # Deployment scripts
│   ├── backup-cron                 # Cron job configuration
│   ├── cron_backup.sh              # Shell wrapper for cron jobs
│   └── docker-entrypoint.sh        # Docker entrypoint script
├── vetstoria/                      # Vetstoria API integration
│   ├── api.py                      # Vetstoria API client
│   └── settings.py                 # API configuration
├── Dockerfile                      # Docker container configuration
├── launch.sh                       # Development launch script
└── pyproject.toml                  # Poetry dependencies
```

## Features

- **Voice-Based Booking**: Real-time voice conversation for appointment booking
- **OpenAI Realtime API**: Direct integration with `gpt-realtime` model
- **Vetstoria Integration**: Seamless appointment management via Vetstoria API
- **WebSocket Support**: Real-time bidirectional audio streaming
- **Tool Integration**: LangChain tools for slot checking and booking placement
- **Audio Processing**: Spectral gating for noise reduction on input audio
- **Conversation Tracking**: Database logging of conversations, message exchanges, and token usage
- **User Management**: API key-based authentication system
- **Automated Backups**: SQLite database backed up to S3 via cron/EventBridge
- **Auto-Restore**: Automatically restores from latest S3 backup on startup if database is missing

## Booking Flow

The voice assistant guides users through:
1. Pet species selection (Cat/Dog)
2. Appointment type selection
3. Clinician preference
4. Date and time selection
5. Confirmation and booking placement

## Development

### Code Structure
- Voice AI logic: `openai_speech_to_speech/langchain_openai/`
- WebSocket handlers: `openai_speech_to_speech/websocket_openai.py`
- Booking tools: `utils/tools.py`
- API integration: `vetstoria/api.py`
- Database management: `database/`
- Authentication: `auth.py`

### Environment Variables
All configuration is managed through environment variables. See the `.env` example above.

### Database Backup & Restore
For detailed information about the backup system, see the database utilities in `utils/`.

Quick commands:
```bash
# Manual backup
python utils/backup_db_cli.py

# List available backups
python utils/restore_db_cli.py --list

# Restore latest backup
python utils/restore_db_cli.py
```

Setup automated backups with cron or AWS EventBridge.

## Database

The application uses SQLite for data storage. The database is located at `data/voice-ai.db` and includes:

- **users**: API key management and user accounts
- **conversations**: Conversation records with start/end times, ratings, and booking status
- **message_exchanges**: Individual message exchanges with token usage tracking

### Database Initialization

Initialize the database:
```bash
python -m database.init_database
```

Check database status:
```bash
python -m database.init_database --check
```

### Database Management

**User Management:**
```bash
# Create a new user with auto-generated API key
python database/manage_users.py create user@example.com

# Create a user with custom API key
python database/manage_users.py create user@example.com custom_api_key_here

# List all users
python database/manage_users.py list

# Verify an API key
python database/manage_users.py verify your_api_key_here
```

**Conversation Management:**
```bash
# List all conversations
python database/manage_conversations.py list

# Show details for a specific conversation
python database/manage_conversations.py show <conversation_id>

# List message exchanges for a conversation
python database/manage_conversations.py messages <conversation_id>
```

## Notes

- CORS is currently set to allow all origins (restrict in production)
- Uses OpenAI Realtime API (`gpt-realtime` model) for voice interactions
- Vetstoria API handles all appointment management
- Static data (species, appointment types, schedules) defined in `utils/tools.py`
- API key authentication required for all endpoints (except `/health` and `/version`)
- Audio processing uses spectral gating for noise reduction (requires `noisereduce` and `numpy`)
