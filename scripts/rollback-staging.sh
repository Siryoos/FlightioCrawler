#!/bin/bash
# FlightIO Staging Rollback Script

set -euo pipefail

DEPLOYMENT_ID="${1:-unknown}"
COMPOSE_FILE="docker-compose.staging.yml"
BACKUP_DIR="./backups/staging"
LOG_FILE="./logs/rollback-staging-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$(dirname "$LOG_FILE")" "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

rollback_deployment() {
    log "Starting rollback for deployment: $DEPLOYMENT_ID"
    
    # Stop current services
    log "Stopping current services..."
    docker-compose -f "$COMPOSE_FILE" down || log "Warning: Some services already stopped"
    
    # Find previous version
    PREVIOUS_VERSION=$(find "$BACKUP_DIR" -name "docker-compose.staging.yml.*" -type f | sort -r | head -1)
    
    if [[ -z "$PREVIOUS_VERSION" ]]; then
        error_exit "No previous version found for rollback"
    fi
    
    log "Rolling back to: $(basename "$PREVIOUS_VERSION")"
    
    # Restore configuration
    cp "$PREVIOUS_VERSION" "$COMPOSE_FILE" || error_exit "Failed to restore configuration"
    
    # Pull and start services
    docker-compose -f "$COMPOSE_FILE" pull || error_exit "Failed to pull images"
    docker-compose -f "$COMPOSE_FILE" up -d || error_exit "Failed to start services"
    
    # Wait and verify
    sleep 30
    
    if verify_rollback; then
        log "Rollback completed successfully"
        return 0
    else
        error_exit "Rollback verification failed"
    fi
}

verify_rollback() {
    log "Verifying rollback..."
    
    local max_attempts=10
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8080/api/v1/health > /dev/null 2>&1; then
            log "Health check passed"
            return 0
        fi
        
        log "Health check attempt $attempt/$max_attempts failed, retrying..."
        sleep 10
        ((attempt++))
    done
    
    log "Health check failed after $max_attempts attempts"
    return 1
}

main() {
    log "FlightIO Staging Rollback Started"
    log "Deployment ID: $DEPLOYMENT_ID"
    
    if rollback_deployment; then
        log "Rollback completed successfully"
        exit 0
    else
        log "Rollback failed"
        exit 1
    fi
}

main "$@" 