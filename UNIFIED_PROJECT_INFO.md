# FlightIO Unified Project Structure

## Overview
This project has been optimized and unified to reduce complexity and improve maintainability.

## Key Changes

### 1. Single Dockerfile
- **File**: `Dockerfile.unified`
- Replaces all service-specific Dockerfiles
- Multi-stage build for all services
- Optimized caching and minimal layers

### 2. Unified Requirements
- **File**: `requirements.unified.txt`
- Single requirements file for all services
- No more separate extras files

### 3. Simplified Docker Compose
- **File**: `docker-compose.unified.yml`
- Single compose file for all environments
- Uses environment variables for configuration

### 4. Unified Configuration
- **File**: `config/unified_config.yml`
- Single configuration file
- Environment variables for overrides

### 5. Single Build Script
- **File**: `build.sh`
- Replaces all build and deployment scripts
- Simple commands: build, start, stop, deploy

### 6. Unified Base Adapter
- **File**: `adapters/unified_base_adapter.py`
- All common crawler functionality
- Site adapters only implement parsing logic

### 7. Unified Monitoring
- **File**: `monitoring/unified_monitor.py`
- Single monitoring system
- Includes health checks, metrics, and Prometheus

## Usage

```bash
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
```

## Environment Variables

Create a `.env` file with:
```
ENVIRONMENT=production
DB_USER=crawler
DB_PASSWORD=your_password
LOG_LEVEL=INFO
```

