#!/bin/bash

# Comprehensive Dependency Installation Script for FlightIO Crawler
# This script installs all required system dependencies for different operating systems

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            echo "ubuntu"
        elif command -v yum &> /dev/null; then
            echo "centos"
        elif command -v dnf &> /dev/null; then
            echo "fedora"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install system dependencies for Ubuntu/Debian
install_ubuntu_deps() {
    log_info "Installing system dependencies for Ubuntu/Debian..."
    
    # Update package index
    sudo apt-get update -y
    
    # Install basic development tools
    sudo apt-get install -y \
        build-essential \
        wget \
        curl \
        git \
        unzip \
        ca-certificates \
        gnupg \
        lsb-release
    
    # Install Python development headers
    sudo apt-get install -y \
        python3-dev \
        python3-pip \
        python3-venv
    
    # Install PostgreSQL client libraries
    sudo apt-get install -y \
        postgresql-client \
        libpq-dev
    
    # Install Chromium and WebDriver
    sudo apt-get install -y \
        chromium-browser \
        chromium-chromedriver
    
    # Install fonts for Persian text rendering
    sudo apt-get install -y \
        fonts-noto \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fonts-liberation \
        fonts-dejavu-core
    
    # Install additional dependencies for browser automation
    sudo apt-get install -y \
        libnss3 \
        libatk-bridge2.0-0 \
        libdrm2 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libxss1 \
        libasound2
    
    log_success "Ubuntu/Debian system dependencies installed"
}

# Install system dependencies for CentOS/RHEL
install_centos_deps() {
    log_info "Installing system dependencies for CentOS/RHEL..."
    
    # Install EPEL repository
    sudo yum install -y epel-release
    
    # Install basic development tools
    sudo yum groupinstall -y "Development Tools"
    sudo yum install -y \
        wget \
        curl \
        git \
        unzip
    
    # Install Python development headers
    sudo yum install -y \
        python3-devel \
        python3-pip
    
    # Install PostgreSQL client libraries
    sudo yum install -y \
        postgresql-devel
    
    # Install Chromium
    sudo yum install -y chromium
    
    # Install fonts
    sudo yum install -y \
        google-noto-fonts \
        google-noto-cjk-fonts \
        google-noto-emoji-fonts \
        liberation-fonts \
        dejavu-fonts
    
    log_success "CentOS/RHEL system dependencies installed"
}

# Install system dependencies for Fedora
install_fedora_deps() {
    log_info "Installing system dependencies for Fedora..."
    
    # Install basic development tools
    sudo dnf groupinstall -y "Development Tools"
    sudo dnf install -y \
        wget \
        curl \
        git \
        unzip
    
    # Install Python development headers
    sudo dnf install -y \
        python3-devel \
        python3-pip
    
    # Install PostgreSQL client libraries
    sudo dnf install -y \
        postgresql-devel
    
    # Install Chromium
    sudo dnf install -y chromium
    
    # Install fonts
    sudo dnf install -y \
        google-noto-fonts \
        google-noto-cjk-fonts \
        google-noto-emoji-fonts \
        liberation-fonts \
        dejavu-fonts
    
    log_success "Fedora system dependencies installed"
}

# Install system dependencies for macOS
install_macos_deps() {
    log_info "Installing system dependencies for macOS..."
    
    # Check if Homebrew is installed
    if ! command_exists brew; then
        log_info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Update Homebrew
    brew update
    
    # Install basic tools
    brew install wget curl git
    
    # Install PostgreSQL client
    brew install postgresql
    
    # Install Chromium
    brew install --cask chromium
    
    # Install fonts for Persian text rendering
    brew install --cask font-noto-sans
    brew install --cask font-noto-sans-cjk
    brew install --cask font-noto-color-emoji
    
    log_success "macOS system dependencies installed"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --upgrade pip
    
    # Install required Python packages
    python3 -m pip install --upgrade \
        certifi \
        aiohttp \
        beautifulsoup4 \
        selenium \
        playwright \
        asyncpg \
        redis \
        psutil \
        urllib3 \
        lxml \
        requests
    
    log_success "Python dependencies installed"
}

# Install and setup Playwright
install_playwright() {
    log_info "Installing Playwright browsers..."
    
    # Install Playwright browsers
    python3 -m playwright install chromium --with-deps
    python3 -m playwright install firefox --with-deps
    python3 -m playwright install webkit --with-deps
    
    log_success "Playwright browsers installed"
}

# Verify installations
verify_installations() {
    log_info "Verifying installations..."
    
    local errors=0
    
    # Check Python
    if command_exists python3; then
        log_success "Python3: $(python3 --version)"
    else
        log_error "Python3 not found"
        ((errors++))
    fi
    
    # Check pip
    if command_exists pip3; then
        log_success "pip3: $(pip3 --version | cut -d' ' -f1-2)"
    else
        log_error "pip3 not found"
        ((errors++))
    fi
    
    # Check PostgreSQL client
    if command_exists psql; then
        log_success "PostgreSQL client: $(psql --version)"
    else
        log_warning "PostgreSQL client not found (optional)"
    fi
    
    # Check Chromium/Chrome
    if command_exists chromium-browser; then
        log_success "Chromium browser found"
    elif command_exists chromium; then
        log_success "Chromium found"
    elif command_exists google-chrome; then
        log_success "Google Chrome found"
    else
        log_warning "No Chromium/Chrome browser found"
    fi
    
    # Check Python packages
    local packages=("aiohttp" "beautifulsoup4" "selenium" "playwright" "asyncpg" "redis" "certifi")
    for package in "${packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            log_success "Python package '$package' available"
        else
            log_error "Python package '$package' not available"
            ((errors++))
        fi
    done
    
    # Check Playwright browsers
    if python3 -c "from playwright.sync_api import sync_playwright; sync_playwright().start()" 2>/dev/null; then
        log_success "Playwright installation verified"
    else
        log_error "Playwright installation failed"
        ((errors++))
    fi
    
    if [ $errors -eq 0 ]; then
        log_success "All verifications passed!"
        return 0
    else
        log_error "$errors verification(s) failed"
        return 1
    fi
}

# Create requirements.txt if it doesn't exist
create_requirements() {
    if [ ! -f "requirements.txt" ]; then
        log_info "Creating requirements.txt..."
        cat > requirements.txt << EOF
# Core dependencies
aiohttp>=3.8.0
beautifulsoup4>=4.11.0
selenium>=4.0.0
playwright>=1.30.0
asyncpg>=0.27.0
redis>=4.3.0
certifi>=2022.0.0
urllib3>=1.26.0
psutil>=5.9.0
lxml>=4.9.0
requests>=2.28.0

# Additional dependencies
python-dotenv>=0.19.0
pydantic>=1.10.0
fastapi>=0.85.0
uvicorn>=0.18.0

# Development dependencies
pytest>=7.0.0
pytest-asyncio>=0.20.0
black>=22.0.0
flake8>=5.0.0
mypy>=0.991
EOF
        log_success "requirements.txt created"
    fi
}

# Main installation function
main() {
    log_info "Starting FlightIO Crawler dependency installation..."
    
    # Detect operating system
    OS=$(detect_os)
    log_info "Detected operating system: $OS"
    
    # Create requirements.txt
    create_requirements
    
    # Install system dependencies based on OS
    case $OS in
        ubuntu)
            install_ubuntu_deps
            ;;
        centos)
            install_centos_deps
            ;;
        fedora)
            install_fedora_deps
            ;;
        macos)
            install_macos_deps
            ;;
        windows)
            log_warning "Windows detected. Please install dependencies manually:"
            log_info "1. Install Python 3.8+ from https://python.org"
            log_info "2. Install Google Chrome or Chromium browser"
            log_info "3. Run: pip install -r requirements.txt"
            log_info "4. Run: playwright install chromium --with-deps"
            exit 0
            ;;
        *)
            log_error "Unsupported operating system: $OS"
            exit 1
            ;;
    esac
    
    # Install Python dependencies
    install_python_deps
    
    # Install Playwright
    install_playwright
    
    # Verify installations
    if verify_installations; then
        log_success "✓ All dependencies installed successfully!"
        log_info "You can now run the FlightIO Crawler"
    else
        log_error "✗ Some dependencies failed to install"
        log_info "Please check the errors above and install missing dependencies manually"
        exit 1
    fi
}

# Check if script is run with sudo when needed
check_sudo() {
    if [[ $EUID -eq 0 ]] && [[ "$OS" != "macos" ]]; then
        log_error "This script should not be run as root (except for specific system package installations)"
        log_info "The script will use sudo when needed for system packages"
        exit 1
    fi
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_sudo
    main "$@"
fi 