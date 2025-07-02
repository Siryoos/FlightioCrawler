#!/bin/bash

# FlightIO Optimized Build Script
# Implements parallel builds, advanced caching, and build performance optimizations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="${REGISTRY:-ghcr.io/flightio}"
TAG="${TAG:-latest}"
BUILD_CONTEXT="${BUILD_CONTEXT:-.}"
PARALLEL_BUILDS="${PARALLEL_BUILDS:-4}"
CACHE_FROM="${CACHE_FROM:-type=gha}"
CACHE_TO="${CACHE_TO:-type=gha,mode=max}"
PLATFORM="${PLATFORM:-linux/amd64,linux/arm64}"

# Build targets
TARGETS=(
    "api:Dockerfile.api"
    "crawler:Dockerfile.crawler" 
    "monitor:Dockerfile.monitor"
    "worker:Dockerfile.worker"
    "frontend:frontend/Dockerfile"
)

echo -e "${BLUE}🚀 Starting FlightIO Optimized Build Process...${NC}"

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

# Function to get build metadata
get_build_metadata() {
    local service=$1
    echo "org.opencontainers.image.title=FlightIO-${service}"
    echo "org.opencontainers.image.description=FlightIO ${service} service"
    echo "org.opencontainers.image.version=$(git describe --tags --always 2>/dev/null || echo 'dev')"
    echo "org.opencontainers.image.revision=$(git rev-parse HEAD 2>/dev/null || echo 'unknown')"
    echo "org.opencontainers.image.created=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "org.opencontainers.image.source=${GITHUB_SERVER_URL:-}/${GITHUB_REPOSITORY:-}"
}

# Function to build a single service
build_service() {
    local target=$1
    local service=$(echo $target | cut -d: -f1)
    local dockerfile=$(echo $target | cut -d: -f2)
    local context_dir=$BUILD_CONTEXT
    
    # Adjust context for frontend
    if [[ $service == "frontend" ]]; then
        context_dir="frontend"
    fi
    
    log_info "Building $service service..."
    
    local build_start=$(date +%s)
    
    # Prepare build arguments
    local build_args=""
    local labels=""
    while IFS= read -r label; do
        labels="$labels --label $label"
    done <<< "$(get_build_metadata $service)"
    
    # Build with BuildKit optimizations
    docker buildx build \
        --file "$dockerfile" \
        --context "$context_dir" \
        --tag "$REGISTRY/$service:$TAG" \
        --tag "$REGISTRY/$service:latest" \
        --platform "$PLATFORM" \
        --cache-from "$CACHE_FROM" \
        --cache-to "$CACHE_TO" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --build-arg BUILDX_EXPERIMENTAL=1 \
        $labels \
        --push \
        . 2>&1 | tee "build-$service.log" &
    
    local build_pid=$!
    echo $build_pid > "build-$service.pid"
    
    log_info "Started build for $service (PID: $build_pid)"
}

# Function to wait for build completion
wait_for_builds() {
    log_info "Waiting for all builds to complete..."
    local failed_builds=()
    
    for target in "${TARGETS[@]}"; do
        local service=$(echo $target | cut -d: -f1)
        if [ -f "build-$service.pid" ]; then
            local pid=$(cat "build-$service.pid")
            
            if wait $pid; then
                local build_end=$(date +%s)
                log_success "$service build completed successfully"
                rm -f "build-$service.pid"
            else
                log_error "$service build failed"
                failed_builds+=($service)
                rm -f "build-$service.pid"
            fi
        fi
    done
    
    if [ ${#failed_builds[@]} -gt 0 ]; then
        log_error "Failed builds: ${failed_builds[*]}"
        return 1
    fi
    
    log_success "All builds completed successfully!"
}

# Function to prune build cache
cleanup_build_cache() {
    log_info "Cleaning up build cache..."
    docker builder prune -f --filter until=168h || true
    docker system prune -f --filter until=24h || true
    log_success "Build cache cleanup completed"
}

# Function to analyze build performance
analyze_build_performance() {
    log_info "Analyzing build performance..."
    
    echo -e "\n${BLUE}📊 Build Performance Report:${NC}"
    echo "==============================="
    
    for target in "${TARGETS[@]}"; do
        local service=$(echo $target | cut -d: -f1)
        if [ -f "build-$service.log" ]; then
            local build_time=$(grep -o "DONE.*" "build-$service.log" | tail -1 || echo "N/A")
            local image_size=$(docker images --format "{{.Size}}" "$REGISTRY/$service:$TAG" 2>/dev/null || echo "N/A")
            
            echo -e "${GREEN}$service:${NC}"
            echo "  Build Time: $build_time"
            echo "  Image Size: $image_size"
            echo "  Log File: build-$service.log"
            echo ""
        fi
    done
}

# Function to setup BuildKit
setup_buildkit() {
    log_info "Setting up Docker BuildKit..."
    
    # Enable BuildKit
    export DOCKER_BUILDKIT=1
    export BUILDX_EXPERIMENTAL=1
    
    # Create buildx instance if it doesn't exist
    if ! docker buildx inspect flightio-builder >/dev/null 2>&1; then
        docker buildx create --name flightio-builder --use \
            --driver docker-container \
            --driver-opt network=host \
            --buildkitd-flags '--allow-insecure-entitlement network.host' || true
    else
        docker buildx use flightio-builder
    fi
    
    # Start the builder
    docker buildx inspect --bootstrap
    
    log_success "BuildKit setup completed"
}

# Function to pre-build base images
prebuild_base_images() {
    log_info "Pre-building base images for better caching..."
    
    # Build base Python image with common dependencies
    cat > Dockerfile.base << 'EOF'
FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Pre-install common Python packages
RUN pip install --upgrade pip setuptools wheel
EOF
    
    docker buildx build \
        --file Dockerfile.base \
        --tag "$REGISTRY/base:$TAG" \
        --platform "$PLATFORM" \
        --cache-from "$CACHE_FROM" \
        --cache-to "$CACHE_TO" \
        --push \
        . || log_warning "Base image build failed, continuing..."
    
    rm -f Dockerfile.base
    log_success "Base image pre-building completed"
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --tag)
                TAG="$2"
                shift 2
                ;;
            --parallel)
                PARALLEL_BUILDS="$2"
                shift 2
                ;;
            --platform)
                PLATFORM="$2"
                shift 2
                ;;
            --no-cache)
                CACHE_FROM=""
                CACHE_TO=""
                shift
                ;;
            --cleanup)
                cleanup_build_cache
                exit 0
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --registry REGISTRY    Container registry (default: $REGISTRY)"
                echo "  --tag TAG             Image tag (default: $TAG)"
                echo "  --parallel COUNT      Parallel builds (default: $PARALLEL_BUILDS)"
                echo "  --platform PLATFORM   Target platforms (default: $PLATFORM)"
                echo "  --no-cache            Disable build cache"
                echo "  --cleanup             Clean build cache and exit"
                echo "  --help               Show this help"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    log_info "Build configuration:"
    log_info "  Registry: $REGISTRY"
    log_info "  Tag: $TAG"
    log_info "  Parallel builds: $PARALLEL_BUILDS"
    log_info "  Platform: $PLATFORM"
    log_info "  Cache from: $CACHE_FROM"
    log_info "  Cache to: $CACHE_TO"
    
    # Setup BuildKit
    setup_buildkit
    
    # Pre-build base images
    prebuild_base_images
    
    # Start parallel builds
    local build_count=0
    local active_builds=0
    
    for target in "${TARGETS[@]}"; do
        # Limit parallel builds
        while [ $active_builds -ge $PARALLEL_BUILDS ]; do
            sleep 1
            active_builds=$(jobs -r | wc -l)
        done
        
        build_service "$target"
        ((active_builds++))
        ((build_count++))
        
        log_info "Started build $build_count/${#TARGETS[@]}"
    done
    
    # Wait for all builds to complete
    wait_for_builds
    
    # Analyze performance
    analyze_build_performance
    
    # Calculate total time
    local end_time=$(date +%s)
    local total_time=$((end_time - start_time))
    
    log_success "🎉 All builds completed in ${total_time}s!"
    
    # Cleanup logs
    log_info "Cleaning up build logs..."
    rm -f build-*.log build-*.pid
}

# Trap for cleanup on exit
trap 'rm -f build-*.pid; jobs -p | xargs -r kill 2>/dev/null' EXIT

# Run main function
main "$@" 