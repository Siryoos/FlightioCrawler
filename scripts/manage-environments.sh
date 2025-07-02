#!/bin/bash

# FlightIO Environment Management Script
# Easy management of different Docker Compose environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENTS=("local" "dev" "staging" "test" "production")
DEFAULT_ENVIRONMENT="local"
PROJECT_NAME="flightio"

# Function to show help
show_help() {
    echo -e "${BLUE}FlightIO Environment Management Script${NC}"
    echo -e "${YELLOW}Usage: $0 [COMMAND] [ENVIRONMENT] [OPTIONS]${NC}"
    echo ""
    echo -e "${GREEN}Commands:${NC}"
    echo "  start [env]      Start an environment (default: local)"
    echo "  stop [env]       Stop an environment"
    echo "  restart [env]    Restart an environment"
    echo "  logs [env]       Show logs for an environment"
    echo "  status [env]     Show status of an environment"
    echo "  clean [env]      Clean up an environment (remove containers and volumes)"
    echo "  build [env]      Build images for an environment"
    echo "  test             Run tests in test environment"
    echo "  migrate [env]    Run database migrations"
    echo "  shell [env]      Open shell in API container"
    echo "  db-shell [env]   Open database shell"
    echo "  list             List all available environments"
    echo "  ps               Show running containers"
    echo "  cleanup          Clean up all stopped containers and unused images"
    echo ""
    echo -e "${GREEN}Environments:${NC}"
    echo "  local            Local development (minimal resources)"
    echo "  dev              Development with full features"
    echo "  staging          Staging environment"
    echo "  test             Testing environment with test tools"
    echo "  production       Production environment"
    echo ""
    echo -e "${GREEN}Options:${NC}"
    echo "  --profile PROFILE   Use specific docker-compose profile"
    echo "  --no-build         Don't rebuild images"
    echo "  --force            Force action without confirmation"
    echo "  --detach           Run in detached mode"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  $0 start local                    # Start local development"
    echo "  $0 start dev --profile frontend   # Start dev with frontend"
    echo "  $0 test                          # Run all tests"
    echo "  $0 logs staging api              # Show staging API logs"
    echo "  $0 clean test --force            # Force clean test environment"
}

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

# Function to validate environment
validate_environment() {
    local env=$1
    if [[ ! " ${ENVIRONMENTS[@]} " =~ " ${env} " ]]; then
        log_error "Invalid environment: $env"
        log_info "Available environments: ${ENVIRONMENTS[*]}"
        exit 1
    fi
}

# Function to get docker-compose file for environment
get_compose_file() {
    local env=$1
    case $env in
        "local")
            echo "docker-compose.local.yml"
            ;;
        "dev")
            echo "docker-compose.dev.yml"
            ;;
        "staging")
            echo "docker-compose.staging.yml"
            ;;
        "test")
            echo "docker-compose.test.yml"
            ;;
        "production")
            echo "docker-compose.yml"
            ;;
        *)
            echo "docker-compose.yml"
            ;;
    esac
}

# Function to get environment-specific project name
get_project_name() {
    local env=$1
    echo "${PROJECT_NAME}-${env}"
}

# Function to build docker-compose command
build_compose_cmd() {
    local env=$1
    local compose_file=$(get_compose_file $env)
    local project_name=$(get_project_name $env)
    
    echo "docker-compose -f $compose_file -p $project_name"
}

# Function to start environment
start_environment() {
    local env=$1
    local profile=$2
    local no_build=$3
    local detach=$4
    
    validate_environment $env
    
    log_info "Starting $env environment..."
    
    local compose_cmd=$(build_compose_cmd $env)
    local options=""
    
    if [[ $profile ]]; then
        options="$options --profile $profile"
    fi
    
    if [[ $no_build != "true" ]]; then
        log_info "Building images..."
        $compose_cmd build
    fi
    
    if [[ $detach == "true" ]]; then
        options="$options -d"
    fi
    
    $compose_cmd up $options
    
    if [[ $? -eq 0 ]]; then
        log_success "$env environment started successfully"
        show_environment_info $env
    else
        log_error "Failed to start $env environment"
        exit 1
    fi
}

# Function to stop environment
stop_environment() {
    local env=$1
    validate_environment $env
    
    log_info "Stopping $env environment..."
    
    local compose_cmd=$(build_compose_cmd $env)
    $compose_cmd down
    
    log_success "$env environment stopped"
}

# Function to show environment status
show_status() {
    local env=$1
    validate_environment $env
    
    log_info "Status of $env environment:"
    
    local compose_cmd=$(build_compose_cmd $env)
    $compose_cmd ps
}

# Function to show logs
show_logs() {
    local env=$1
    local service=$2
    validate_environment $env
    
    log_info "Showing logs for $env environment..."
    
    local compose_cmd=$(build_compose_cmd $env)
    if [[ $service ]]; then
        $compose_cmd logs -f $service
    else
        $compose_cmd logs -f
    fi
}

# Function to clean environment
clean_environment() {
    local env=$1
    local force=$2
    validate_environment $env
    
    if [[ $force != "true" ]]; then
        echo -e "${YELLOW}Warning: This will remove all containers and volumes for $env environment.${NC}"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Aborted"
            exit 0
        fi
    fi
    
    log_info "Cleaning $env environment..."
    
    local compose_cmd=$(build_compose_cmd $env)
    $compose_cmd down -v --remove-orphans
    
    log_success "$env environment cleaned"
}

# Function to run tests
run_tests() {
    local test_type=$1
    
    log_info "Running tests..."
    
    local compose_cmd=$(build_compose_cmd "test")
    
    # Start test environment
    $compose_cmd up -d postgres-test redis-test
    
    # Wait for services to be ready
    sleep 10
    
    case $test_type in
        "unit")
            $compose_cmd run --rm test-runner python -m pytest tests/unit/ -v
            ;;
        "integration")
            $compose_cmd up --build -d api-test
            sleep 15
            $compose_cmd run --rm integration-test
            ;;
        "performance")
            $compose_cmd up --build -d api-test
            sleep 15
            $compose_cmd run --rm --profile performance performance-test
            ;;
        "security")
            $compose_cmd up --build -d api-test
            sleep 15
            $compose_cmd run --rm --profile security security-test
            ;;
        "all"|"")
            # Run all tests
            $compose_cmd up --build -d api-test
            sleep 15
            $compose_cmd run --rm test-runner python -m pytest tests/ -v --tb=short
            ;;
        *)
            log_error "Unknown test type: $test_type"
            exit 1
            ;;
    esac
    
    # Cleanup
    $compose_cmd down
    
    log_success "Tests completed"
}

# Function to show environment information
show_environment_info() {
    local env=$1
    
    echo -e "\n${GREEN}🎉 $env environment is running!${NC}"
    echo -e "${BLUE}Environment Information:${NC}"
    
    case $env in
        "local")
            echo -e "  📱 API: http://localhost:8000"
            echo -e "  📊 API Docs: http://localhost:8000/docs"
            echo -e "  🗄️  Database: localhost:5432"
            echo -e "  📦 Redis: localhost:6379"
            ;;
        "dev")
            echo -e "  📱 API: http://localhost:8000"
            echo -e "  🌐 Frontend: http://localhost:3001"
            echo -e "  📊 API Docs: http://localhost:8000/docs"
            echo -e "  🗄️  Database: localhost:5432"
            echo -e "  📦 Redis: localhost:6379"
            echo -e "  🔧 pgAdmin: http://localhost:5050"
            ;;
        "staging")
            echo -e "  📱 API: http://localhost:8000"
            echo -e "  🌐 Frontend: http://localhost:3001"
            echo -e "  📊 API Docs: http://localhost:8000/docs"
            ;;
        "test")
            echo -e "  📱 API: http://localhost:8000"
            echo -e "  🗄️  Test Database: localhost:5433"
            echo -e "  📦 Test Redis: localhost:6380"
            echo -e "  🔧 pgAdmin: http://localhost:5051"
            ;;
    esac
    
    echo -e "\n${YELLOW}Useful Commands:${NC}"
    echo -e "  View logs: $0 logs $env"
    echo -e "  Stop: $0 stop $env"
    echo -e "  Shell: $0 shell $env"
}

# Function to open shell
open_shell() {
    local env=$1
    local service=${2:-"api"}
    validate_environment $env
    
    local compose_cmd=$(build_compose_cmd $env)
    local container_name=$(get_project_name $env)_${service}_1
    
    log_info "Opening shell in $service container..."
    
    if [[ $env == "local" && $service == "api" ]]; then
        container_name="${PROJECT_NAME}-api-local"
    elif [[ $env == "dev" && $service == "api" ]]; then
        container_name="${PROJECT_NAME}-api-dev"
    fi
    
    docker exec -it $container_name /bin/bash || \
    $compose_cmd exec $service /bin/bash
}

# Function to open database shell
open_db_shell() {
    local env=$1
    validate_environment $env
    
    local compose_cmd=$(build_compose_cmd $env)
    
    log_info "Opening database shell for $env environment..."
    
    case $env in
        "local")
            $compose_cmd exec postgres psql -U local_user -d flight_data_local
            ;;
        "dev")
            $compose_cmd exec postgres psql -U crawler_dev -d flight_data_dev
            ;;
        "test")
            $compose_cmd exec postgres-test psql -U test_user -d flight_data_test
            ;;
        *)
            $compose_cmd exec postgres psql -U crawler -d flight_data
            ;;
    esac
}

# Main execution
main() {
    local command=$1
    local environment=$2
    local profile=""
    local no_build="false"
    local force="false"
    local detach="false"
    
    # Parse additional arguments
    shift 2 2>/dev/null || true
    while [[ $# -gt 0 ]]; do
        case $1 in
            --profile)
                profile="$2"
                shift 2
                ;;
            --no-build)
                no_build="true"
                shift
                ;;
            --force)
                force="true"
                shift
                ;;
            --detach)
                detach="true"
                shift
                ;;
            *)
                # Handle service name for logs command
                if [[ $command == "logs" && -z $service ]]; then
                    service="$1"
                fi
                shift
                ;;
        esac
    done
    
    # Set default environment if not provided
    if [[ -z $environment && $command != "test" && $command != "list" && $command != "ps" && $command != "cleanup" && $command != "help" ]]; then
        environment=$DEFAULT_ENVIRONMENT
    fi
    
    case $command in
        "start")
            start_environment $environment $profile $no_build $detach
            ;;
        "stop")
            stop_environment $environment
            ;;
        "restart")
            stop_environment $environment
            start_environment $environment $profile $no_build $detach
            ;;
        "status")
            show_status $environment
            ;;
        "logs")
            show_logs $environment $service
            ;;
        "clean")
            clean_environment $environment $force
            ;;
        "build")
            validate_environment $environment
            local compose_cmd=$(build_compose_cmd $environment)
            $compose_cmd build
            ;;
        "test")
            run_tests $environment
            ;;
        "shell")
            open_shell $environment $3
            ;;
        "db-shell")
            open_db_shell $environment
            ;;
        "list")
            echo -e "${GREEN}Available environments:${NC}"
            for env in "${ENVIRONMENTS[@]}"; do
                echo "  - $env"
            done
            ;;
        "ps")
            echo -e "${GREEN}Running containers:${NC}"
            docker ps --filter "label=com.docker.compose.project"
            ;;
        "cleanup")
            log_info "Cleaning up Docker system..."
            docker system prune -f
            log_success "Cleanup completed"
            ;;
        "help"|""|*)
            show_help
            ;;
    esac
}

# Check if Docker and Docker Compose are available
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

# Run main function
main "$@" 