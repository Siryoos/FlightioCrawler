#!/bin/bash
# FlightIO Production Rollback Script

set -euo pipefail

DEPLOYMENT_ID="${1:-unknown}"
COMPOSE_FILE="docker-compose.production.yml"
BACKUP_DIR="./backups/production"
LOG_FILE="./logs/rollback-production-$(date +%Y%m%d-%H%M%S).log"
HEALTH_CHECK_TIMEOUT=300

mkdir -p "$(dirname "$LOG_FILE")" "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $1"
    send_critical_alert "Production rollback failed: $1"
    exit 1
}

rollback_deployment() {
    log "Starting production rollback for: $DEPLOYMENT_ID"
    
    # Find previous version
    PREVIOUS_VERSION=$(find "$BACKUP_DIR" -name "docker-compose.production.yml.*" -type f | sort -r | head -1)
    
    if [[ -z "$PREVIOUS_VERSION" ]]; then
        error_exit "No previous version found for rollback"
    fi
    
    log "Rolling back to: $(basename "$PREVIOUS_VERSION")"
    
    # Backup current failed state
    cp "$COMPOSE_FILE" "$BACKUP_DIR/failed-$(date +%Y%m%d-%H%M%S).yml"
    
    # Restore previous configuration
    cp "$PREVIOUS_VERSION" "$COMPOSE_FILE"
    
    # Graceful rollback
    graceful_service_rollback
    
    return 0
}

graceful_service_rollback() {
    log "Performing graceful service rollback..."
    
    # Scale down gradually
    docker-compose -f "$COMPOSE_FILE" up -d --scale api=1 --scale crawler=1
    sleep 30
    
    # Full rollback
    docker-compose -f "$COMPOSE_FILE" down
    docker-compose -f "$COMPOSE_FILE" pull
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log "Graceful rollback completed"
}

verify_production_health() {
    log "Verifying production health..."
    
    local start_time=$(date +%s)
    local max_wait_time=$HEALTH_CHECK_TIMEOUT
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [[ $elapsed -gt $max_wait_time ]]; then
            log "Health check timeout after ${max_wait_time}s"
            return 1
        fi
        
        if check_api_health && check_database_health && perform_light_load_test; then
            log "All health checks passed"
            return 0
        fi
        
        log "Health checks failed, retrying in 15s..."
        sleep 15
    done
}

check_api_health() {
    curl -f -s --max-time 10 "https://api.flightio.com/api/v1/health" > /dev/null 2>&1
}

check_database_health() {
    local response=$(curl -f -s --max-time 15 "https://api.flightio.com/api/v1/health/database" 2>/dev/null || echo "")
    [[ -n "$response" ]] && echo "$response" | grep -q "healthy"
}

perform_light_load_test() {
    log "Performing light load test..."
    
    local success_count=0
    local total_requests=5
    
    for i in $(seq 1 $total_requests); do
        if curl -f -s --max-time 10 "https://api.flightio.com/api/v1/airports" > /dev/null 2>&1; then
            ((success_count++))
        fi
        sleep 2
    done
    
    local success_rate=$((success_count * 100 / total_requests))
    log "Load test success rate: ${success_rate}%"
    
    [[ $success_rate -ge 80 ]]
}

send_critical_alert() {
    local message="$1"
    
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 CRITICAL: $message\", \"channel\":\"#alerts\"}" \
            "$SLACK_WEBHOOK_URL" 2>/dev/null || true
    fi
}

main() {
    log "FlightIO Production Rollback Started"
    log "Deployment ID: $DEPLOYMENT_ID"
    
    # Send rollback start notification
    send_critical_alert "Production rollback initiated for deployment $DEPLOYMENT_ID"
    
    if rollback_deployment && verify_production_health; then
        log "Production rollback completed successfully"
        
        # Send success notification
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"✅ Production rollback completed successfully for deployment $DEPLOYMENT_ID\"}" \
            "${SLACK_WEBHOOK_URL:-}" 2>/dev/null || true
        
        exit 0
    else
        error_exit "Production rollback failed"
    fi
}

# Safety check - require confirmation for production
if [[ "${FORCE_ROLLBACK:-}" != "true" ]]; then
    log "Production rollback requires confirmation"
    log "Set FORCE_ROLLBACK=true to proceed"
    exit 1
fi

main "$@" 