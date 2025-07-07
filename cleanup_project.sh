#!/bin/bash
# ==============================================================================
# FlightIO Project Cleanup Script
# Removes unnecessary files while preserving essential functionality
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Files to remove
FILES_TO_REMOVE=(
    # Old Dockerfiles
    "Dockerfile"
    "Dockerfile.api"
    "Dockerfile.crawler"
    "Dockerfile.worker"
    "Dockerfile.monitor"
    "Dockerfile.optimized"
    "frontend/Dockerfile"
    "frontend/Dockerfile.optimized"
    
    # Old docker-compose files
    "docker-compose.yml"
    "docker-compose.override.yml"
    "docker-compose.optimized.yml"
    
    # Old requirements files
    "requirements.txt"
    "requirements-crawler.txt"
    "api-extras.txt"
    "worker-extras.txt"
    "monitor-extras.txt"
    
    # Old build scripts
    "scripts/build-optimized.sh"
    "scripts/build-optimized.ps1"
    "scripts/build-optimized-v2.sh"
    "scripts/build-cached.sh"
    "scripts/deploy_production.sh"
    "scripts/deploy_production.ps1"
    "scripts/manage-environments.sh"
    "scripts/quick-start-optimized.sh"
    
    # Duplicate monitoring files
    "monitoring.py"
    "unified_memory_monitor.py"
    "monitoring/production_memory_monitor.py"
    "monitoring/memory_health_endpoint.py"
    "monitoring/enhanced_monitoring_system.py"
    "monitoring/db_performance_monitor.py"
    "monitoring/comprehensive_health_checks.py"
    "monitoring/health_checks.py"
    "monitoring/enhanced_prometheus_metrics.py"
    "monitoring/unified_monitoring.py"
    
    # Old config files
    "config/development.env"
    "config/staging.env"
    "config/production.env"
    "config/local.env"
    "config/error_handling_config.json"
    "config/logging_config.json"
    "config/rate_limit_config.json"
    
    # Duplicate main files
    "main_crawler.py"
    "local_crawler.py"
    "production_safety_crawler.py"
    "enhanced_stealth_crawler.py"
    "stealth_crawler.py"
    "real_data_crawler.py"
    
    # Old adapter files (keeping only unified ones)
    "adapters/site_adapters/iranian_airlines/alibaba_adapter.py"
    "adapters/site_adapters/iranian_airlines/alibaba_adapter_enhanced.py"
    
    # Test and example files
    "test_dependencies.py"
    "test_real_requests.py"
    "examples/"
    
    # Documentation files (optional - uncomment if you want to remove)
    # "docs/"
    # "*.md"
)

# Directories to remove
DIRS_TO_REMOVE=(
    "scripts/deployment-monitor.py"
    "scripts/start_production_monitoring.py"
    "docker/"
    "k8s/"
)

# Backup directory
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"

# Create backup
create_backup() {
    log_info "Creating backup in $BACKUP_DIR..."
    mkdir -p "$BACKUP_DIR"
    
    # Backup files that will be removed
    for file in "${FILES_TO_REMOVE[@]}"; do
        if [ -f "$file" ]; then
            dir=$(dirname "$file")
            mkdir -p "$BACKUP_DIR/$dir"
            cp "$file" "$BACKUP_DIR/$file"
        fi
    done
    
    # Backup directories
    for dir in "${DIRS_TO_REMOVE[@]}"; do
        if [ -d "$dir" ]; then
            cp -r "$dir" "$BACKUP_DIR/$dir"
        fi
    done
    
    log_success "Backup created"
}

# Remove files
remove_files() {
    log_info "Removing unnecessary files..."
    
    for file in "${FILES_TO_REMOVE[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            log_info "Removed: $file"
        fi
    done
    
    for dir in "${DIRS_TO_REMOVE[@]}"; do
        if [ -d "$dir" ]; then
            rm -rf "$dir"
            log_info "Removed directory: $dir"
        fi
    done
    
    log_success "Cleanup completed"
}

# Create new structure info
create_info_file() {
    cat > "UNIFIED_PROJECT_INFO.md" << EOF
# FlightIO Unified Project Structure

## Overview
This project has been optimized and unified to reduce complexity and improve maintainability.

## Key Changes

### 1. Single Dockerfile
- **File**: \`Dockerfile.unified\`
- Replaces all service-specific Dockerfiles
- Multi-stage build for all services
- Optimized caching and minimal layers

### 2. Unified Requirements
- **File**: \`requirements.unified.txt\`
- Single requirements file for all services
- No more separate extras files

### 3. Simplified Docker Compose
- **File**: \`docker-compose.unified.yml\`
- Single compose file for all environments
- Uses environment variables for configuration

### 4. Unified Configuration
- **File**: \`config/unified_config.yml\`
- Single configuration file
- Environment variables for overrides

### 5. Single Build Script
- **File**: \`build.sh\`
- Replaces all build and deployment scripts
- Simple commands: build, start, stop, deploy

### 6. Unified Base Adapter
- **File**: \`adapters/unified_base_adapter.py\`
- All common crawler functionality
- Site adapters only implement parsing logic

### 7. Unified Monitoring
- **File**: \`monitoring/unified_monitor.py\`
- Single monitoring system
- Includes health checks, metrics, and Prometheus

## Usage

\`\`\`bash
# Build all services
./build.sh build

# Start services
./build.sh start

# Deploy to production
./build.sh deploy

# View logs
./build.sh logs

# Check status
./build.sh status
\`\`\`

## Environment Variables

Create a \`.env\` file with:
\`\`\`
ENVIRONMENT=production
DB_USER=crawler
DB_PASSWORD=your_password
LOG_LEVEL=INFO
\`\`\`

EOF
    
    log_success "Created project info file"
}

# Main execution
main() {
    log_warning "This will remove many files from your project. Continue? (y/N)"
    read -r response
    
    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        log_info "Cleanup cancelled"
        exit 0
    fi
    
    # Create backup
    create_backup
    
    # Remove files
    remove_files
    
    # Create info file
    create_info_file
    
    log_success "Project cleanup completed!"
    log_info "Backup created in: $BACKUP_DIR"
    log_info "Read UNIFIED_PROJECT_INFO.md for details about the new structure"
}

# Run main
main 