#!/bin/bash

# FlightioCrawler System Dependencies Installation Script
# This script installs all necessary system dependencies for the crawler

set -e

echo "🔧 Installing FlightioCrawler System Dependencies..."

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
    OS="windows"
else
    echo "❌ Unsupported operating system: $OSTYPE"
    exit 1
fi

echo "📱 Detected OS: $OS"

# Install system dependencies based on OS
if [[ "$OS" == "linux" ]]; then
    echo "🐧 Installing Linux dependencies..."
    
    # Update package manager
    sudo apt-get update
    
    # Install basic system packages
    sudo apt-get install -y \
        curl \
        wget \
        git \
        build-essential \
        python3-dev \
        python3-pip \
        python3-venv \
        pkg-config \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        libpq-dev \
        redis-server \
        postgresql \
        postgresql-contrib \
        nginx \
        software-properties-common \
        ca-certificates \
        gnupg \
        lsb-release
    
    # Install Chromium and browser dependencies
    echo "🌐 Installing Chromium and browser dependencies..."
    sudo apt-get install -y \
        chromium-browser \
        chromium-chromedriver \
        xvfb \
        x11-xkb-utils \
        xkb-data \
        x11-utils \
        libasound2 \
        libatk-bridge2.0-0 \
        libdrm2 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libxss1 \
        libxtst6 \
        fonts-liberation \
        libappindicator1 \
        libasound2 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libdrm2 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxi6 \
        libxtst6 \
        libgconf-2-4 \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libgtk-3-0 \
        libgdk-pixbuf2.0-0

    # Install Persian fonts
    echo "🔤 Installing Persian fonts..."
    sudo apt-get install -y \
        fonts-farsiweb \
        fonts-liberation \
        fonts-noto \
        fonts-noto-color-emoji \
        fonts-dejavu-core \
        fontconfig

    # Install Node.js (for some web automation tools)
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs

elif [[ "$OS" == "mac" ]]; then
    echo "🍎 Installing macOS dependencies..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install basic packages
    brew install \
        python3 \
        postgresql \
        redis \
        nginx \
        git \
        curl \
        wget \
        pkg-config \
        openssl \
        libffi \
        libxml2 \
        libxslt \
        jpeg \
        zlib \
        node

    # Install Chromium
    echo "🌐 Installing Chromium..."
    brew install --cask chromium
    
    # Install chromedriver
    brew install chromedriver

elif [[ "$OS" == "windows" ]]; then
    echo "🪟 Windows dependencies installation..."
    echo "Please install the following manually:"
    echo "1. Python 3.8+ from https://python.org"
    echo "2. PostgreSQL from https://www.postgresql.org/download/windows/"
    echo "3. Redis from https://github.com/microsoftarchive/redis/releases"
    echo "4. Google Chrome from https://www.google.com/chrome/"
    echo "5. ChromeDriver from https://chromedriver.chromium.org/"
    echo "6. Git from https://git-scm.com/download/win"
fi

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install --upgrade pip setuptools wheel

# Install Playwright and download browsers
echo "🎭 Installing Playwright browsers..."
pip3 install playwright
playwright install chromium
playwright install-deps chromium

# Install required system Python packages
echo "📦 Installing system Python packages..."
pip3 install --upgrade \
    certifi \
    urllib3 \
    requests \
    aiohttp \
    beautifulsoup4 \
    lxml \
    selenium \
    psycopg2-binary \
    redis \
    python-dotenv

# Set up environment variables
echo "🔧 Setting up environment variables..."
cat > .env.system << EOF
# System Configuration
CHROME_BIN=/usr/bin/chromium-browser
CHROMEDRIVER_PATH=/usr/bin/chromedriver
SSL_VERIFY=false
HEADLESS=true
DISPLAY=:99

# Database URLs
DATABASE_URL=postgresql://postgres:password@localhost:5432/flight_data
REDIS_URL=redis://localhost:6379/0

# Security
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
SSL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
EOF

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs screenshots temp data/cache

# Set permissions
chmod +x scripts/*.sh
chmod +x scripts/*.py

# Install and configure PostgreSQL
echo "🐘 Configuring PostgreSQL..."
if [[ "$OS" == "linux" ]]; then
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    # Create database user and database
    sudo -u postgres psql -c "CREATE USER flight_user WITH ENCRYPTED PASSWORD 'secure_password';"
    sudo -u postgres psql -c "CREATE DATABASE flight_data OWNER flight_user;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE flight_data TO flight_user;"
fi

# Install and configure Redis
echo "🔴 Configuring Redis..."
if [[ "$OS" == "linux" ]]; then
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
fi

# Update font cache
echo "🔤 Updating font cache..."
if [[ "$OS" == "linux" ]]; then
    sudo fc-cache -fv
fi

# Create systemd service for development
if [[ "$OS" == "linux" ]]; then
    echo "🔧 Creating systemd service template..."
    cat > flightio-crawler.service << EOF
[Unit]
Description=FlightioCrawler Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/FlightioCrawler
Environment=PATH=/usr/bin:/usr/local/bin
Environment=PYTHONPATH=/path/to/FlightioCrawler
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi

echo "✅ System dependencies installation completed!"
echo ""
echo "📋 Next steps:"
echo "1. Update the database configuration in .env.system"
echo "2. Run 'python3 -m pip install -r requirements.txt' to install Python dependencies"
echo "3. Run 'python3 init_db.py' to initialize the database"
echo "4. Test the installation with 'python3 test_dependencies.py'"
echo ""
echo "🔧 Configuration files created:"
echo "- .env.system (system environment variables)"
echo "- flightio-crawler.service (systemd service template)"
echo ""
echo "⚠️  Don't forget to:"
echo "- Update database passwords in production"
echo "- Configure SSL certificates for production"
echo "- Set up proper firewall rules"
echo "- Configure monitoring and logging" 