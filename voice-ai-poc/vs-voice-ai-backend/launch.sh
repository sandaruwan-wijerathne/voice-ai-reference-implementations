#!/bin/bash

# Launch script for the backend application
# This script activates the virtual environment and starts the FastAPI server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}🚀 Starting backend application...${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found!${NC}"
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}   Found .env.example. Please copy it to .env and fill in your values.${NC}"
    else
        echo -e "${YELLOW}   Please create a .env file with required environment variables.${NC}"
    fi
    echo -e "${YELLOW}   Continuing anyway...${NC}"
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Try to use Poetry first (preferred method)
if command_exists poetry; then
    echo -e "${GREEN}📦 Using Poetry for dependency management${NC}"
    
    # Check if dependencies are installed by checking if poetry.lock exists and packages are installed
    if [ ! -f "poetry.lock" ]; then
        echo -e "${YELLOW}⚠️  poetry.lock not found. Running 'poetry install'...${NC}"
        poetry install
    else
        # Check if packages are actually installed
        if ! poetry run python -c "import uvicorn" 2>/dev/null; then
            echo -e "${YELLOW}⚠️  Dependencies not installed. Running 'poetry install'...${NC}"
            poetry install
        fi
    fi
    
    # Run the application with Poetry (Poetry manages its own venv)
    echo -e "${GREEN}▶️  Starting server with Poetry...${NC}"
    poetry run uvicorn app:app --reload --host 0.0.0.0 --port 8000
else
    # Fallback to virtual environment
    echo -e "${YELLOW}📦 Poetry not found, using virtual environment${NC}"
    
    # Check if virtual environment exists
    if [ ! -d "bin" ] || [ ! -f "bin/activate" ]; then
        echo -e "${RED}❌ Virtual environment not found!${NC}"
        echo -e "${YELLOW}   Creating virtual environment...${NC}"
        # Try python3.12 first, fallback to python3
        if command_exists python3.12; then
            python3.12 -m venv .
        elif command_exists python3; then
            python3 -m venv .
        else
            echo -e "${RED}❌ Python 3 not found! Please install Python 3.12+${NC}"
            exit 1
        fi
    fi
    
    # Activate virtual environment
    echo -e "${GREEN}🔌 Activating virtual environment...${NC}"
    source bin/activate
    
    # Check if dependencies are installed
    if ! python -c "import uvicorn" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Dependencies not installed. Installing...${NC}"
        pip install --upgrade pip
        # Install dependencies from pyproject.toml if possible, otherwise install manually
        if [ -f "pyproject.toml" ]; then
            pip install fastapi uvicorn websockets twilio python-dotenv langchain-community langgraph langchain-openai python-multipart noisereduce numpy boto3 aws-sdk-bedrock-runtime
        fi
    fi
    
    # Run the application
    echo -e "${GREEN}▶️  Starting server...${NC}"
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
fi

