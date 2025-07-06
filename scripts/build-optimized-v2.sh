#!/bin/bash

# ==============================================================================
# FlightIO Enhanced Build Optimization Script v2.0
# Features: Advanced caching, parallel builds, performance monitoring, CI/CD ready
# ==============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="${REGISTRY:-ghcr.io/flightio}"
TAG="${TAG:-$(git describe --tags --always 2>/dev/null || echo 'latest')}"
BUILD_CONTEXT="${BUILD_CONTEXT:-.}"
PARALLEL_BUILDS="${PARALLEL_BUILDS:-$(nproc)}"
CACHE_FROM="${CACHE_FROM:-type=gha,scope=flightio}"
CACHE_TO="${CACHE_TO:-type=gha,mode=max,scope=flightio}"
PLATFORM="${PLATFORM:-linux/amd64,linux/arm64}"
BUILD_TYPE="${BUILD_TYPE:-production}"
ENABLE_PROGRESS="${ENABLE_PROGRESS:-true}"
ENABLE_METRICS="${ENABLE_METRICS:-true}"

# Build targets with optimized Dockerfiles
TARGETS=(
    "api:Dockerfile.optimized:production"
    "crawler:Dockerfile.optimized:production"
    "monitor:Dockerfile.monitor:production"
    "worker:Dockerfile.worker:production"
    "frontend:frontend/Dockerfile.optimized:runner"
)

# Performance tracking
BUILD_START_TIME=$(date +%s)
BUILD_METRICS_FILE="build-metrics-$(date +%Y%m%d_%H%M%S).json"

echo -e "${BLUE}🚀 Starting FlightIO Enhanced Build Process v2.0...${NC}"
echo -e "${CYAN}Build Configuration:${NC}"
echo "  Registry: $REGISTRY"
echo "  Tag: $TAG"
echo "  Platform: $PLATFORM"
echo "  Parallel Builds: $PARALLEL_BUILDS"
echo "  Build Type: $BUILD_TYPE"
echo "  Cache From: $CACHE_FROM"
echo "  Cache To: $CACHE_TO"

# Function to log messages with timestamps
log_info() {
    echo -e "${BLUE}[$(date +%H:%M:%S)] [INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] [SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] [WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] [ERROR]${NC} $1"
}

log_metric() {
    echo -e "${PURPLE}[$(date +%H:%M:%S)] [METRIC]${NC} $1"
}

# Function to get build metadata with enhanced information
get_build_metadata() {
    local service=$1
    local git_sha=$(git rev-parse HEAD 2>/dev/null || echo 'unknown')
    local git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')
    local build_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    echo "org.opencontainers.image.title=FlightIO-${service}"
    echo "org.opencontainers.image.description=FlightIO ${service} service - Optimized build"
    echo "org.opencontainers.image.version=${TAG}"
    echo "org.opencontainers.image.revision=${git_sha}"
    echo "org.opencontainers.image.created=${build_date}"
    echo "org.opencontainers.image.source=${GITHUB_SERVER_URL:-}/${GITHUB_REPOSITORY:-}"
    echo "org.opencontainers.image.vendor=FlightIO"
    echo "org.opencontainers.image.licenses=MIT"
    echo "com.flightio.build.branch=${git_branch}"
    echo "com.flightio.build.type=${BUILD_TYPE}"
    echo "com.flightio.build.platform=${PLATFORM}"
}

# Function to setup advanced BuildKit configuration
setup_advanced_buildkit() {
    log_info "Setting up advanced Docker BuildKit configuration..."
    
    # Enable BuildKit with advanced features
    export DOCKER_BUILDKIT=1
    export BUILDX_EXPERIMENTAL=1
    export DOCKER_CLI_EXPERIMENTAL=enabled
    
    # Create advanced buildx instance
    if ! docker buildx inspect flightio-advanced-builder >/dev/null 2>&1; then
        docker buildx create --name flightio-advanced-builder --use \
            --driver docker-container \
            --driver-opt network=host \
            --driver-opt image=moby/buildkit:latest \
            --buildkitd-flags '--allow-insecure-entitlement network.host --allow-insecure-entitlement security.insecure' || true
    else
        docker buildx use flightio-advanced-builder
    fi
    
    # Start the builder with optimizations
    docker buildx inspect --bootstrap
    
    log_success "Advanced BuildKit setup completed"
}

# Function to build a single service with enhanced features
build_service() {
    local target=$1
    local service=$(echo $target | cut -d: -f1)
    local dockerfile=$(echo $target | cut -d: -f2)
    local stage=$(echo $target | cut -d: -f3)
    local context_dir=$BUILD_CONTEXT
    
    # Adjust context for frontend
    if [[ $service == "frontend" ]]; then
        context_dir="frontend"
    fi
    
    log_info "Building $service service (stage: $stage)..."
    
    local build_start=$(date +%s)
    local build_log_file="build-${service}-$(date +%Y%m%d_%H%M%S).log"
    
    # Prepare build arguments and labels
    local build_args=""
    local labels=""
    while IFS= read -r label; do
        labels="$labels --label $label"
    done <<< "$(get_build_metadata $service)"
    
    # Build with advanced optimizations
    local progress_flag=""
    if [[ "$ENABLE_PROGRESS" == "true" ]]; then
        progress_flag="--progress=plain"
    fi
    
    # Build command with all optimizations
    docker buildx build \
        --file "$dockerfile" \
        --target "$stage" \
        --context "$context_dir" \
        --tag "$REGISTRY/$service:$TAG" \
        --tag "$REGISTRY/$service:latest" \
        --platform "$PLATFORM" \
        --cache-from "$CACHE_FROM" \
        --cache-to "$CACHE_TO" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --build-arg BUILDX_EXPERIMENTAL=1 \
        --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
        --build-arg VCS_REF=$(git rev-parse HEAD 2>/dev/null || echo 'unknown') \
        --build-arg VERSION=$TAG \
        $labels \
        $progress_flag \
        --push \
        . 2>&1 | tee "$build_log_file" &
    
    local build_pid=$!
    echo $build_pid > "build-$service.pid"
    echo "$build_start" > "build-$service.start"
    
    log_info "Started build for $service (PID: $build_pid, Log: $build_log_file)"
}

# Function to wait for builds with enhanced monitoring
wait_for_builds() {
    log_info "Waiting for all builds to complete with enhanced monitoring..."
    local failed_builds=()
    local successful_builds=()
    
    for target in "${TARGETS[@]}"; do
        local service=$(echo $target | cut -d: -f1)
        if [ -f "build-$service.pid" ]; then
            local pid=$(cat "build-$service.pid")
            local start_time=$(cat "build-$service.start")
            
            if wait $pid; then
                local end_time=$(date +%s)
                local duration=$((end_time - start_time))
                local image_size=$(docker images --format "{{.Size}}" "$REGISTRY/$service:$TAG" 2>/dev/null || echo "N/A")
                
                log_success "$service build completed successfully (Duration: ${duration}s, Size: $image_size)"
                successful_builds+=("$service")
                
                # Record metrics
                if [[ "$ENABLE_METRICS" == "true" ]]; then
                    echo "{\"service\":\"$service\",\"status\":\"success\",\"duration\":$duration,\"size\":\"$image_size\",\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}" >> "$BUILD_METRICS_FILE"
                fi
                
                rm -f "build-$service.pid" "build-$service.start"
            else
                local end_time=$(date +%s)
                local duration=$((end_time - start_time))
                
                log_error "$service build failed after ${duration}s"
                failed_builds+=("$service")
                
                # Record metrics
                if [[ "$ENABLE_METRICS" == "true" ]]; then
                    echo "{\"service\":\"$service\",\"status\":\"failed\",\"duration\":$duration,\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}" >> "$BUILD_METRICS_FILE"
                fi
                
                rm -f "build-$service.pid" "build-$service.start"
            fi
        fi
    done
    
    # Summary
    echo -e "\n${CYAN}📊 Build Summary:${NC}"
    echo "==============================="
    echo -e "${GREEN}Successful builds: ${#successful_builds[@]}${NC}"
    echo -e "${RED}Failed builds: ${#failed_builds[@]}${NC}"
    
    if [ ${#successful_builds[@]} -gt 0 ]; then
        echo -e "\n${GREEN}✅ Successful:${NC} ${successful_builds[*]}"
    fi
    
    if [ ${#failed_builds[@]} -gt 0 ]; then
        echo -e "\n${RED}❌ Failed:${NC} ${failed_builds[*]}"
        return 1
    fi
    
    log_success "All builds completed successfully!"
}

# Function to analyze build performance with detailed metrics
analyze_build_performance() {
    log_info "Analyzing build performance with detailed metrics..."
    
    echo -e "\n${BLUE}📈 Detailed Build Performance Report:${NC}"
    echo "============================================="
    
    local total_duration=0
    local total_size=0
    
    for target in "${TARGETS[@]}"; do
        local service=$(echo $target | cut -d: -f1)
        local build_log_file=$(ls build-${service}-*.log 2>/dev/null | tail -1 || echo "")
        
        if [ -n "$build_log_file" ] && [ -f "$build_log_file" ]; then
            local build_time=$(grep -o "DONE.*" "$build_log_file" | tail -1 || echo "N/A")
            local image_size=$(docker images --format "{{.Size}}" "$REGISTRY/$service:$TAG" 2>/dev/null || echo "N/A")
            local layer_count=$(docker history "$REGISTRY/$service:$TAG" 2>/dev/null | wc -l || echo "N/A")
            
            echo -e "\n${GREEN}$service:${NC}"
            echo "  Build Time: $build_time"
            echo "  Image Size: $image_size"
            echo "  Layer Count: $layer_count"
            echo "  Log File: $build_log_file"
            
            # Extract numeric values for calculations
            if [[ "$image_size" =~ ([0-9.]+)([KMGT]B) ]]; then
                local size_value=${BASH_REMATCH[1]}
                local size_unit=${BASH_REMATCH[2]}
                # Convert to MB for comparison
                case $size_unit in
                    KB) total_size=$(echo "$total_size + $size_value / 1024" | bc -l) ;;
                    MB) total_size=$(echo "$total_size + $size_value" | bc -l) ;;
                    GB) total_size=$(echo "$total_size + $size_value * 1024" | bc -l) ;;
                esac
            fi
        fi
    done
    
    # Overall statistics
    local overall_duration=$(( $(date +%s) - BUILD_START_TIME ))
    echo -e "\n${PURPLE}📊 Overall Statistics:${NC}"
    echo "  Total Build Time: ${overall_duration}s"
    echo "  Total Image Size: ${total_size}MB"
    echo "  Average Build Time: $((overall_duration / ${#TARGETS[@]}))s per service"
    echo "  Parallel Efficiency: $(echo "scale=2; ${overall_duration} / (${#TARGETS[@]} * 60)" | bc -l)x"
    
    # Save metrics to file
    if [[ "$ENABLE_METRICS" == "true" ]]; then
        echo "{\"overall\":{\"total_duration\":$overall_duration,\"total_size_mb\":$total_size,\"services_count\":${#TARGETS[@]},\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}}" >> "$BUILD_METRICS_FILE"
        log_metric "Build metrics saved to $BUILD_METRICS_FILE"
    fi
}

# Function to cleanup build artifacts with intelligent retention
cleanup_build_artifacts() {
    log_info "Cleaning up build artifacts with intelligent retention..."
    
    # Keep recent build logs (last 10)
    find . -name "build-*.log" -type f -printf '%T@ %p\n' | sort -nr | tail -n +11 | cut -d' ' -f2- | xargs rm -f 2>/dev/null || true
    
    # Keep recent metrics files (last 5)
    find . -name "build-metrics-*.json" -type f -printf '%T@ %p\n' | sort -nr | tail -n +6 | cut -d' ' -f2- | xargs rm -f 2>/dev/null || true
    
    # Cleanup Docker build cache (keep last 7 days)
    docker builder prune -f --filter until=168h || true
    
    # Cleanup system cache (keep last 24 hours)
    docker system prune -f --filter until=24h || true
    
    log_success "Build artifacts cleanup completed"
}

# Function to validate build results
validate_build_results() {
    log_info "Validating build results..."
    
    local validation_errors=()
    
    for target in "${TARGETS[@]}"; do
        local service=$(echo $target | cut -d: -f1)
        
        # Check if image exists
        if ! docker images "$REGISTRY/$service:$TAG" | grep -q "$REGISTRY/$service"; then
            validation_errors+=("$service: Image not found")
            continue
        fi
        
        # Check image size (should be reasonable)
        local image_size=$(docker images --format "{{.Size}}" "$REGISTRY/$service:$TAG" 2>/dev/null)
        if [[ "$image_size" =~ ([0-9.]+)GB ]] && (( $(echo "${BASH_REMATCH[1]} > 5" | bc -l) )); then
            validation_errors+=("$service: Image size too large ($image_size)")
        fi
        
        # Check if image has expected labels
        if ! docker inspect "$REGISTRY/$service:$TAG" | grep -q "org.opencontainers.image.title"; then
            validation_errors+=("$service: Missing required labels")
        fi
    done
    
    if [ ${#validation_errors[@]} -gt 0 ]; then
        log_warning "Build validation found issues:"
        for error in "${validation_errors[@]}"; do
            echo "  - $error"
        done
        return 1
    else
        log_success "All builds validated successfully!"
    fi
}

# Main execution flow
main() {
    # Setup
    setup_advanced_buildkit
    
    # Start builds
    for target in "${TARGETS[@]}"; do
        build_service "$target"
    done
    
    # Wait for completion
    wait_for_builds
    
    # Analysis and cleanup
    analyze_build_performance
    validate_build_results
    cleanup_build_artifacts
    
    # Final summary
    local total_duration=$(( $(date +%s) - BUILD_START_TIME ))
    echo -e "\n${GREEN}🎉 Build process completed successfully!${NC}"
    echo -e "${CYAN}Total duration: ${total_duration}s${NC}"
    echo -e "${CYAN}Metrics saved to: $BUILD_METRICS_FILE${NC}"
}

# Error handling
trap 'log_error "Build process interrupted"; exit 1' INT TERM

# Execute main function
main "$@" 