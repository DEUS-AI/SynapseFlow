#!/bin/bash

# Service Management Script
# Easily start/stop services for Medical Knowledge Management System

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_usage() {
    echo "Usage: ./manage_services.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start-db        Start database services (Neo4j, Redis, Qdrant)"
    echo "  stop-db         Stop database services"
    echo "  start-all       Start all services (databases + backend + frontend)"
    echo "  stop-all        Stop all services"
    echo "  status          Check service status"
    echo "  restart-db      Restart database services"
    echo "  logs [service]  View logs for a service"
    echo "  help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./manage_services.sh start-db"
    echo "  ./manage_services.sh status"
    echo "  ./manage_services.sh logs neo4j"
}

start_databases() {
    echo -e "${GREEN}Starting database services...${NC}"
    docker compose -f docker compose.memory.yml up -d

    echo ""
    echo -e "${GREEN}✅ Database services started!${NC}"
    echo ""
    echo "Services started:"
    echo "  • Neo4j:   http://localhost:7474 (Browser)"
    echo "  • Redis:   localhost:6379"
    echo "  • Qdrant:  http://localhost:6333"
    echo ""
    echo "To start backend: ./manage_services.sh start-backend"
    echo "To check status:  ./manage_services.sh status"
}

stop_databases() {
    echo -e "${YELLOW}Stopping database services...${NC}"
    docker compose -f docker compose.memory.yml down

    echo ""
    echo -e "${GREEN}✅ Database services stopped${NC}"
}

start_backend() {
    echo -e "${GREEN}Starting backend...${NC}"
    echo ""
    echo "Run this in a separate terminal:"
    echo ""
    echo "  uv run uvicorn src.application.api.main:app --reload --port 8000"
    echo ""
    echo "Or use: nohup uv run uvicorn src.application.api.main:app --reload --port 8000 > backend.log 2>&1 &"
}

start_frontend() {
    echo -e "${GREEN}Starting frontend...${NC}"
    echo ""
    echo "Run this in a separate terminal:"
    echo ""
    echo "  cd frontend && npm run dev"
    echo ""
    echo "Or use: cd frontend && nohup npm run dev > ../frontend.log 2>&1 &"
}

start_all() {
    start_databases
    sleep 3
    echo ""
    start_backend
    echo ""
    start_frontend
}

stop_all() {
    echo -e "${YELLOW}Stopping all services...${NC}"

    # Stop Docker services
    docker compose -f docker compose.memory.yml down

    # Try to stop backend/frontend if running
    echo "Checking for running backend/frontend processes..."

    # Find and kill uvicorn processes
    UVICORN_PID=$(lsof -ti:8000)
    if [ ! -z "$UVICORN_PID" ]; then
        echo "  Stopping backend (PID: $UVICORN_PID)..."
        kill $UVICORN_PID
    fi

    # Find and kill node/npm processes on 4321
    NODE_PID=$(lsof -ti:4321)
    if [ ! -z "$NODE_PID" ]; then
        echo "  Stopping frontend (PID: $NODE_PID)..."
        kill $NODE_PID
    fi

    echo ""
    echo -e "${GREEN}✅ All services stopped${NC}"
}

restart_databases() {
    echo -e "${YELLOW}Restarting database services...${NC}"
    docker compose -f docker compose.memory.yml restart

    echo ""
    echo -e "${GREEN}✅ Database services restarted${NC}"
}

show_status() {
    ./check_services.sh
}

show_logs() {
    local service=$1

    if [ -z "$service" ]; then
        echo "Showing logs for all database services..."
        docker compose -f docker compose.memory.yml logs -f
    else
        echo "Showing logs for $service..."
        docker compose -f docker compose.memory.yml logs -f "$service"
    fi
}

# Main script logic
case "$1" in
    start-db)
        start_databases
        ;;
    stop-db)
        stop_databases
        ;;
    start-backend)
        start_backend
        ;;
    start-frontend)
        start_frontend
        ;;
    start-all)
        start_all
        ;;
    stop-all)
        stop_all
        ;;
    restart-db)
        restart_databases
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_usage
        exit 1
        ;;
esac
