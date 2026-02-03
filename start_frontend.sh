#!/bin/bash

# Frontend Startup Script with Backend Check
# Ensures backend is running before starting frontend to avoid proxy errors

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================================"
echo "  Frontend Startup - Prerequisites Check"
echo "================================================"
echo ""

# Function to check if service is running
check_service() {
    local name=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name is running"
        return 0
    else
        echo -e "${RED}✗${NC} $name is NOT running"
        return 1
    fi
}

# Track if all checks pass
all_checks_passed=true

echo "1️⃣  Checking Backend Services..."
echo "--------------------------------"

# Check Backend API (required for proxy)
if ! check_service "Backend API" "http://localhost:8000/docs"; then
    all_checks_passed=false
    echo -e "${YELLOW}   → Start backend: ${BLUE}uv run uvicorn src.application.api.main:app --reload --port 8000${NC}"
fi

# Check Neo4j (required by backend)
if ! check_service "Neo4j" "http://localhost:7474"; then
    all_checks_passed=false
    echo -e "${YELLOW}   → Start databases: ${BLUE}docker compose -f docker-compose.memory.yml up -d${NC}"
fi

# Check Redis (required by backend)
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis is running"
else
    echo -e "${RED}✗${NC} Redis is NOT running"
    all_checks_passed=false
    echo -e "${YELLOW}   → Start databases: ${BLUE}docker compose -f docker-compose.memory.yml up -d${NC}"
fi

# Check Qdrant (required by backend)
if ! check_service "Qdrant" "http://localhost:6333/health"; then
    all_checks_passed=false
    echo -e "${YELLOW}   → Start databases: ${BLUE}docker compose -f docker-compose.memory.yml up -d${NC}"
fi

echo ""
echo "2️⃣  Checking Frontend..."
echo "--------------------------------"

# Check if node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠${NC}  node_modules not found"
    echo -e "${BLUE}   Installing dependencies...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${GREEN}✓${NC} Dependencies installed"
fi

echo ""

# Decision: Start or abort
if [ "$all_checks_passed" = true ]; then
    echo "================================================"
    echo -e "${GREEN}✓ All prerequisites met!${NC}"
    echo "================================================"
    echo ""
    echo "Starting frontend on http://localhost:4321"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""

    cd frontend

    # Clear Vite cache if it exists
    if [ -d "node_modules/.vite" ]; then
        echo -e "${BLUE}Clearing Vite cache...${NC}"
        rm -rf node_modules/.vite
    fi

    npm run dev

else
    echo "================================================"
    echo -e "${RED}✗ Prerequisites not met${NC}"
    echo "================================================"
    echo ""
    echo "Please start the required services first:"
    echo ""
    echo "1. Start database services:"
    echo -e "   ${BLUE}docker compose -f docker-compose.memory.yml up -d${NC}"
    echo ""
    echo "2. Verify services are running:"
    echo -e "   ${BLUE}./check_services.sh${NC}"
    echo ""
    echo "3. Start backend API:"
    echo -e "   ${BLUE}uv run uvicorn src.application.api.main:app --reload --port 8000${NC}"
    echo ""
    echo "4. Then run this script again:"
    echo -e "   ${BLUE}./start_frontend.sh${NC}"
    echo ""
    exit 1
fi
