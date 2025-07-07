#!/bin/bash
# ==============================================================================
# FlightIO Unified Build Script
# Single script for all build and deployment operations
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="flightio"
DOCKER_COMPOSE_FILE="docker-compose.unified.yml"
ENV_FILE=".env"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage
show_usage() {
    echo "FlightIO Unified Build Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  build       Build all Docker images"
    echo "  start       Start all services"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  clean       Clean up containers, volumes, and images"
    echo "  logs        Show logs (optionally specify service)"
    echo "  status      Show service status"
    echo "  test        Run tests"
    echo "  deploy      Deploy to production"
    echo ""
    echo "Options:"
    echo "  --env       Environment (dev, staging, production)"
    echo "  --no-cache  Build without cache"
    echo "  --service   Specific service to operate on"
    echo ""
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    # Create necessary directories
    mkdir -p data/postgres data/redis logs data/storage
    
    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating default .env file..."
        cat > "$ENV_FILE" << EOF
# FlightIO Environment Configuration
ENVIRONMENT=production
DB_USER=crawler
DB_PASSWORD=crawler_password
DB_NAME=flight_data
REDIS_PASSWORD=
LOG_LEVEL=INFO
API_PORT=8000
FRONTEND_PORT=3000
GRAFANA_PASSWORD=admin
EOF
        log_success ".env file created"
    fi
    
    log_success "Environment setup completed"
}

# Build images
build_images() {
    local no_cache=""
    if [ "$1" == "--no-cache" ]; then
        no_cache="--no-cache"
    fi
    
    log_info "Building Docker images..."
    
    # Enable BuildKit for better caching
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    docker-compose -f "$DOCKER_COMPOSE_FILE" build $no_cache
    
    log_success "Docker images built successfully"
}

# Start services
start_services() {
    local service="$1"
    
    log_info "Starting services..."
    
    if [ -n "$service" ]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d "$service"
    else
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    fi
    
    log_success "Services started"
}

# Stop services
stop_services() {
    local service="$1"
    
    log_info "Stopping services..."
    
    if [ -n "$service" ]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" stop "$service"
    else
        docker-compose -f "$DOCKER_COMPOSE_FILE" stop
    fi
    
    log_success "Services stopped"
}

# Show logs
show_logs() {
    local service="$1"
    
    if [ -n "$service" ]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f "$service"
    else
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f
    fi
}

# Show status
show_status() {
    log_info "Service Status:"
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    
    echo ""
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}

# Clean up
cleanup() {
    log_warning "This will remove all containers, volumes, and images. Continue? (y/N)"
    read -r response
    
    if [ "$response" == "y" ] || [ "$response" == "Y" ]; then
        log_info "Cleaning up..."
        
        docker-compose -f "$DOCKER_COMPOSE_FILE" down -v
        docker system prune -af
        
        log_success "Cleanup completed"
    else
        log_info "Cleanup cancelled"
    fi
}

# Run tests
run_tests() {
    log_info "Running tests..."
    
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm api pytest tests/
    
    log_success "Tests completed"
}

# Deploy to production
deploy() {
    log_info "Deploying to production..."
    
    # Build images
    build_images --no-cache
    
    # Stop existing services
    stop_services
    
    # Start services
    start_services
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 30
    
    # Check health
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "API is healthy"
    else
        log_error "API health check failed"
        exit 1
    fi
    
    log_success "Deployment completed successfully!"
    
    echo ""
    echo "Access URLs:"
    echo "  - API: http://localhost:8000"
    echo "  - Frontend: http://localhost:3000"
    echo "  - API Docs: http://localhost:8000/docs"
}

# Main execution
main() {
    local command="$1"
    shift
    
    case "$command" in
        build)
            setup_environment
            build_images "$@"
            ;;
        start)
            setup_environment
            start_services "$@"
            ;;
        stop)
            stop_services "$@"
            ;;
        restart)
            stop_services "$@"
            start_services "$@"
            ;;
        logs)
            show_logs "$@"
            ;;
        status)
            show_status
            ;;
        clean)
            cleanup
            ;;
        test)
            run_tests
            ;;
        deploy)
            deploy
            ;;
        *)
            show_usage
            ;;
    esac
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed"
    exit 1
fi

# Run main function
main "$@" 