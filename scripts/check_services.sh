#!/bin/bash

# Services Health Check Script
# Checks all services in the Medical Knowledge Management System

echo "================================================"
echo "  Medical Knowledge System - Service Health"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check service
check_service() {
    local name=$1
    local check_command=$2
    local port=$3

    printf "%-20s (Port %-5s): " "$name" "$port"

    if eval "$check_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not Running${NC}"
        return 1
    fi
}

# Track overall status
all_services_up=true

echo "📦 Database Services:"
echo "--------------------"

# Neo4j
if ! check_service "Neo4j Browser" "curl -s http://localhost:7474" "7474"; then
    all_services_up=false
fi

# FalkorDB
if ! check_service "FalkorDB" "curl -s http://localhost:3000" "3000"; then
    echo -e "   ${YELLOW}Note: FalkorDB is optional${NC}"
fi

# Redis
if ! check_service "Redis" "redis-cli ping" "6379"; then
    all_services_up=false
fi

# Qdrant
if ! check_service "Qdrant" "curl -s http://localhost:6333/health" "6333"; then
    all_services_up=false
fi

echo ""
echo "🔧 Application Services:"
echo "------------------------"

# Backend API
if ! check_service "Backend API" "curl -s http://localhost:8000/docs" "8000"; then
    all_services_up=false
fi

# Frontend
if ! check_service "Frontend" "curl -s http://localhost:4321" "4321"; then
    all_services_up=false
fi

echo ""
echo "================================================"

# Summary
if [ "$all_services_up" = true ]; then
    echo -e "${GREEN}✅ All critical services are running!${NC}"
    echo ""
    echo "Access points:"
    echo "  • Frontend:        http://localhost:4321"
    echo "  • Backend API:     http://localhost:8000/docs"
    echo "  • Neo4j Browser:   http://localhost:7474"
    echo "  • Qdrant:          http://localhost:6333/dashboard"
else
    echo -e "${RED}❌ Some services are not running${NC}"
    echo ""
    echo "To start missing services:"
    echo ""
    echo "  Databases:"
    echo "    docker compose -f docker compose.memory.yml up -d"
    echo ""
    echo "  Backend:"
    echo "    uv run uvicorn src.application.api.main:app --reload --port 8000"
    echo ""
    echo "  Frontend:"
    echo "    cd frontend && npm run dev"
    echo ""
    echo "See SERVICES_GUIDE.md for detailed instructions."
fi

echo "================================================"
echo ""

# Detailed status
echo "📊 Detailed Container Status:"
echo "------------------------------"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "neo4j|redis|qdrant|falkor|NAMES"

echo ""
echo "For more details, see: SERVICES_GUIDE.md"
