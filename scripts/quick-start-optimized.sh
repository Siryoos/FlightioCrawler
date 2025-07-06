#!/bin/bash

# ==============================================================================
# FlightIO Optimized Quick Start Script
# One-command setup and build for the optimized system
# ==============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 FlightIO Optimized Quick Start${NC}"
echo "======================================"

# Function to log messages
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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3 first."
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed. Please install Node.js first."
        exit 1
    fi
    
    log_success "All prerequisites are satisfied!"
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    # Create necessary directories
    mkdir -p data/postgres data/redis logs data/storage
    
    # Create secrets if they don't exist
    mkdir -p secrets
    if [ ! -f secrets/db_password.txt ]; then
        echo "crawler_password_$(date +%s)" > secrets/db_password.txt
        log_warning "Created default database password. Please change it for production."
    fi
    
    if [ ! -f secrets/redis_password.txt ]; then
        echo "redis_password_$(date +%s)" > secrets/redis_password.txt
        log_warning "Created default Redis password. Please change it for production."
    fi
    
    if [ ! -f secrets/secret_key.txt ]; then
        openssl rand -hex 32 > secrets/secret_key.txt
        log_success "Generated secure secret key."
    fi
    
    if [ ! -f secrets/jwt_secret.txt ]; then
        openssl rand -hex 32 > secrets/jwt_secret.txt
        log_success "Generated secure JWT secret."
    fi
    
    log_success "Environment setup completed!"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    
    # Install Python dependencies
    python3 -m pip install --upgrade pip setuptools wheel
    python3 -m pip install --no-cache-dir -r requirements.txt
    
    # Install frontend dependencies
    cd frontend
    npm ci --cache=/tmp/npm-cache
    cd ..
    
    log_success "Dependencies installed successfully!"
}

# Build optimized images
build_images() {
    log_info "Building optimized Docker images..."
    
    # Make build script executable
    chmod +x scripts/build-optimized-v2.sh
    
    # Run optimized build
    ./scripts/build-optimized-v2.sh
    
    log_success "Docker images built successfully!"
}

# Start services
start_services() {
    log_info "Starting optimized services..."
    
    # Start production services
    docker-compose -f docker-compose.optimized.yml --profile production up -d
    
    log_success "Services started successfully!"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    # Wait for database
    log_info "Waiting for PostgreSQL..."
    timeout=60
    while ! docker-compose -f docker-compose.optimized.yml exec -T postgres pg_isready -U crawler -d flight_data >/dev/null 2>&1; do
        if [ $timeout -le 0 ]; then
            log_error "PostgreSQL failed to start within 60 seconds"
            exit 1
        fi
        sleep 1
        timeout=$((timeout - 1))
    done
    
    # Wait for Redis
    log_info "Waiting for Redis..."
    timeout=30
    while ! docker-compose -f docker-compose.optimized.yml exec -T redis redis-cli ping >/dev/null 2>&1; do
        if [ $timeout -le 0 ]; then
            log_error "Redis failed to start within 30 seconds"
            exit 1
        fi
        sleep 1
        timeout=$((timeout - 1))
    done
    
    # Wait for API
    log_info "Waiting for API service..."
    timeout=60
    while ! curl -f http://localhost:8000/api/v1/system/health >/dev/null 2>&1; do
        if [ $timeout -le 0 ]; then
            log_error "API service failed to start within 60 seconds"
            exit 1
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    
    # Wait for Frontend
    log_info "Waiting for Frontend service..."
    timeout=60
    while ! curl -f http://localhost:3000 >/dev/null 2>&1; do
        if [ $timeout -le 0 ]; then
            log_error "Frontend service failed to start within 60 seconds"
            exit 1
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    
    log_success "All services are ready!"
}

# Show status
show_status() {
    echo -e "\n${CYAN}📊 Service Status:${NC}"
    echo "=================="
    
    # Show running containers
    docker-compose -f docker-compose.optimized.yml ps
    
    echo -e "\n${CYAN}🌐 Access URLs:${NC}"
    echo "==============="
    echo "Frontend: http://localhost:3000"
    echo "API: http://localhost:8000"
    echo "API Docs: http://localhost:8000/docs"
    echo "Grafana: http://localhost:3001 (admin/admin)"
    echo "Prometheus: http://localhost:9090"
    
    echo -e "\n${CYAN}📝 Useful Commands:${NC}"
    echo "===================="
    echo "View logs: docker-compose -f docker-compose.optimized.yml logs -f"
    echo "Stop services: docker-compose -f docker-compose.optimized.yml down"
    echo "Restart services: docker-compose -f docker-compose.optimized.yml restart"
    echo "Check health: curl http://localhost:8000/api/v1/system/health"
    
    echo -e "\n${GREEN}🎉 FlightIO is ready to use!${NC}"
}

# Main execution
main() {
    echo -e "${BLUE}Starting FlightIO optimized setup...${NC}"
    
    check_prerequisites
    setup_environment
    install_dependencies
    build_images
    start_services
    wait_for_services
    show_status
}

# Error handling
trap 'log_error "Setup process interrupted"; exit 1' INT TERM

# Execute main function
main "$@" 