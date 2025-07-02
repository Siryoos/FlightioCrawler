# FlightIO Production Deployment Script for Windows
param(
    [switch]$SystemD = $false
)

Write-Host "🚀 Starting FlightIO Production Deployment" -ForegroundColor Green

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if production.env file exists
if (-not (Test-Path "production.env")) {
    Write-Error "production.env file not found!"
    Write-Status "Creating production.env from template..."
    
    if (Test-Path "production.env.example") {
        Copy-Item "production.env.example" "production.env"
    } else {
        Write-Error "production.env.example not found. Please create production.env manually."
        exit 1
    }
    
    Write-Warning "Please edit production.env with your actual configuration before continuing."
    exit 1
}

Write-Status "Environment file found ✓"

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Status "Docker is running ✓"
} catch {
    Write-Error "Docker is not running. Please start Docker Desktop and try again."
    exit 1
}

# Check if Docker Compose is available
try {
    docker-compose --version | Out-Null
    Write-Status "Docker Compose is available ✓"
} catch {
    Write-Error "docker-compose is not installed. Please install it and try again."
    exit 1
}

# Create required directories
Write-Status "Creating required directories..."
$directories = @("logs", "data\storage", "requests\pages", "models", "nginx\ssl", "systemd")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Status "Created directory: $dir"
    }
}

# Build and start services
Write-Status "Building and starting services..."
docker-compose -f docker-compose.production.yml down --remove-orphans
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d

# Wait for services to be healthy
Write-Status "Waiting for services to be healthy..."
Start-Sleep -Seconds 30

# Check service health
$services = @("postgres", "redis", "api", "celery-worker", "celery-beat", "frontend")
foreach ($service in $services) {
    $status = docker-compose -f docker-compose.production.yml ps $service
    if ($status -match "Up") {
        Write-Status "$service is running ✓"
    } else {
        Write-Error "$service failed to start"
        docker-compose -f docker-compose.production.yml logs $service
        exit 1
    }
}

# Run database initialization
Write-Status "Initializing database..."
try {
    python scripts/setup_production.py
    Write-Status "Database initialization completed ✓"
} catch {
    Write-Warning "Database initialization had issues. Check logs above."
}

# Test API endpoint
Write-Status "Testing API endpoint..."
Start-Sleep -Seconds 10
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Status "API health check passed ✓"
    } else {
        Write-Error "API health check failed with status: $($response.StatusCode)"
    }
} catch {
    Write-Error "API health check failed: $($_.Exception.Message)"
    docker-compose -f docker-compose.production.yml logs api
    exit 1
}

# Show service status
Write-Status "Deployment completed! Service status:"
docker-compose -f docker-compose.production.yml ps

Write-Status "🎉 FlightIO is now running in production mode!"
Write-Host ""
Write-Host "Access URLs:"
Write-Host "  - Frontend: http://localhost (via Nginx)"
Write-Host "  - API: http://localhost:8000"
Write-Host "  - Grafana: http://localhost:3000 (admin/admin)"
Write-Host "  - Prometheus: http://localhost:9090"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  - View logs: docker-compose -f docker-compose.production.yml logs -f [service]"
Write-Host "  - Stop all: docker-compose -f docker-compose.production.yml down"
Write-Host "  - Restart service: docker-compose -f docker-compose.production.yml restart [service]"
Write-Host ""
Write-Status "Check the logs and monitoring dashboards to ensure everything is working correctly."

# Optional: Set up Windows services (if requested)
if ($SystemD) {
    Write-Status "Setting up Windows services..."
    Write-Warning "Windows service setup not implemented yet. Use Docker Compose for now."
} 