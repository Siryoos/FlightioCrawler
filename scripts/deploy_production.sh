#!/bin/bash

# FlightIO Production Deployment Script
set -e

echo "🚀 Starting FlightIO Production Deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f "production.env" ]; then
    print_error "production.env file not found!"
    print_status "Creating production.env from template..."
    cp production.env.example production.env 2>/dev/null || {
        print_error "production.env.example not found. Please create production.env manually."
        exit 1
    }
    print_warning "Please edit production.env with your actual configuration before continuing."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' production.env | xargs)

# Validate required environment variables
required_vars=("DB_PASSWORD" "SECRET_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        print_error "Required environment variable $var is not set in production.env"
        exit 1
    fi
done

print_status "Environment variables validated ✓"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

print_status "Docker is running ✓"

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install it and try again."
    exit 1
fi

print_status "Docker Compose is available ✓"

# Create required directories
print_status "Creating required directories..."
mkdir -p logs data/storage requests/pages models nginx/ssl systemd

# Build and start services
print_status "Building and starting services..."
docker-compose -f docker-compose.production.yml down --remove-orphans
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 30

# Check service health
services=("postgres" "redis" "api" "celery-worker" "celery-beat" "frontend")
for service in "${services[@]}"; do
    if docker-compose -f docker-compose.production.yml ps $service | grep -q "Up"; then
        print_status "$service is running ✓"
    else
        print_error "$service failed to start"
        docker-compose -f docker-compose.production.yml logs $service
        exit 1
    fi
done

# Run database initialization
print_status "Initializing database..."
python3 scripts/setup_production.py || {
    print_warning "Database initialization had issues. Check logs above."
}

# Test API endpoint
print_status "Testing API endpoint..."
sleep 10
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_status "API health check passed ✓"
else
    print_error "API health check failed"
    docker-compose -f docker-compose.production.yml logs api
    exit 1
fi

# Show service status
print_status "Deployment completed! Service status:"
docker-compose -f docker-compose.production.yml ps

print_status "🎉 FlightIO is now running in production mode!"
echo ""
echo "Access URLs:"
echo "  - Frontend: http://localhost (via Nginx)"
echo "  - API: http://localhost:8000"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose -f docker-compose.production.yml logs -f [service]"
echo "  - Stop all: docker-compose -f docker-compose.production.yml down"
echo "  - Restart service: docker-compose -f docker-compose.production.yml restart [service]"
echo ""
print_status "Check the logs and monitoring dashboards to ensure everything is working correctly."

# Optional: Set up systemd services for non-Docker deployment
if [ "$1" = "--systemd" ]; then
    print_status "Setting up systemd services..."
    if [ "$EUID" -ne 0 ]; then
        print_warning "Run with sudo to install systemd services: sudo $0 --systemd"
    else
        cp systemd/*.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable flightio-*
        print_status "Systemd services installed. Start with: systemctl start flightio-api"
    fi
fi 