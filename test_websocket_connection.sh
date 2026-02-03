#!/bin/bash

# WebSocket Connection Test Script
# Tests if the backend WebSocket endpoint is working

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================"
echo "  WebSocket Connection Diagnostic"
echo "================================================"
echo ""

# Check if backend is running
echo "1️⃣  Checking Backend API..."
echo "--------------------------------"

if curl -s -f http://localhost:8000/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Backend API is running on port 8000"
else
    echo -e "${RED}✗${NC} Backend API is NOT running"
    echo ""
    echo "Start the backend first:"
    echo -e "  ${BLUE}uv run uvicorn src.application.api.main:app --reload --port 8000${NC}"
    exit 1
fi

echo ""
echo "2️⃣  Testing WebSocket Endpoint..."
echo "--------------------------------"

# Check if wscat is installed
if command -v wscat &> /dev/null; then
    echo -e "${GREEN}✓${NC} wscat is installed"
    echo ""
    echo "Testing WebSocket connection..."
    echo -e "${YELLOW}Connecting to: ws://localhost:8000/ws/chat/patient:demo/session:test${NC}"
    echo ""
    echo "If successful, you should see 'Connected'."
    echo "Press Ctrl+C to exit after testing."
    echo ""

    # Try to connect
    wscat -c ws://localhost:8000/ws/chat/patient:demo/session:test

else
    echo -e "${YELLOW}⚠${NC}  wscat is not installed"
    echo ""
    echo "Install wscat to test WebSocket connections:"
    echo -e "  ${BLUE}npm install -g wscat${NC}"
    echo ""
    echo "Or test with Python:"
    echo -e "  ${BLUE}uv run python test_websocket.py${NC}"
    echo ""

    # Try Python test if available
    if [ -f "test_websocket.py" ]; then
        echo "Running Python WebSocket test..."
        uv run python test_websocket.py
    fi
fi

echo ""
echo "================================================"
echo "  Diagnostic Complete"
echo "================================================"
