#!/bin/bash
# =============================================================================
# FlightIO Server Setup Script
# اسکریپت راه‌اندازی سرور برای پروژه FlightIO
# =============================================================================

set -e

# متغیرهای رنگی برای خروجی
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# توابع کمکی
print_header() {
    echo -e "\n${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==============================================================================${NC}\n"
}

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# تشخیص سیستم عامل
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$NAME
            VERSION=$VERSION_ID
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    else
        print_error "سیستم عامل پشتیبانی نمی‌شود"
        exit 1
    fi
    print_status "سیستم عامل تشخیص داده شد: $OS"
}

# بررسی دسترسی root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "این اسکریپت باید با دسترسی sudo اجرا شود"
        print_status "لطفاً دوباره اجرا کنید: sudo $0"
        exit 1
    fi
}

# تعریف متغیرهای پروژه
setup_variables() {
    PROJECT_NAME="FlightioCrawler"
    PROJECT_DIR="/opt/flightio"
    BACKUP_DIR="/var/backups/flightio"
    LOG_DIR="/var/log/flightio"
    SERVICE_USER="flightio"
    
    # Git repository URL (باید تغییر دهید)
    GIT_REPO="${GIT_REPO:-https://github.com/your-username/FlightioCrawler.git}"
    
    print_status "متغیرهای پروژه تنظیم شد"
}

# بروزرسانی سیستم
update_system() {
    print_header "بروزرسانی سیستم"
    
    if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
        apt update -y
        apt upgrade -y
        apt install -y curl wget git build-essential software-properties-common ca-certificates gnupg lsb-release
    elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]]; then
        yum update -y
        yum install -y curl wget git gcc gcc-c++ make yum-utils
    elif [[ $OS == *"Fedora"* ]]; then
        dnf update -y
        dnf install -y curl wget git gcc gcc-c++ make
    fi
    
    print_status "سیستم بروزرسانی شد ✓"
}

# نصب Docker
install_docker() {
    print_header "نصب Docker"
    
    if command -v docker &> /dev/null; then
        print_status "Docker قبلاً نصب شده است"
        docker --version
        return
    fi
    
    if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
        # حذف نسخه‌های قدیمی
        apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
        
        # نصب وابستگی‌ها
        apt install -y apt-transport-https ca-certificates curl gnupg lsb-release
        
        # اضافه کردن GPG key
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # اضافه کردن repository
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # نصب Docker
        apt update -y
        apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
    elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]]; then
        yum install -y yum-utils
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    fi
    
    # راه‌اندازی Docker
    systemctl start docker
    systemctl enable docker
    
    print_status "Docker نصب شد ✓"
    docker --version
}

# نصب Docker Compose (standalone)
install_docker_compose() {
    print_header "نصب Docker Compose"
    
    if command -v docker-compose &> /dev/null; then
        print_status "Docker Compose قبلاً نصب شده است"
        docker-compose --version
        return
    fi
    
    # دانلود آخرین نسخه
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    
    # ایجاد symlink
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    print_status "Docker Compose نصب شد ✓"
    docker-compose --version
}

# نصب Python و Poetry
install_python_poetry() {
    print_header "نصب Python و Poetry"
    
    if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
        add-apt-repository ppa:deadsnakes/ppa -y
        apt update -y
        apt install -y python3.11 python3.11-dev python3.11-venv python3-pip python3.11-distutils
        
        # تنظیم Python به عنوان پیش‌فرض
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
        
    elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]]; then
        yum install -y python3 python3-devel python3-pip
    fi
    
    # نصب Poetry
    if ! command -v poetry &> /dev/null; then
        curl -sSL https://install.python-poetry.org | python3 -
        export PATH="/root/.local/bin:$PATH"
        echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc
    fi
    
    print_status "Python و Poetry نصب شد ✓"
    python3 --version
    poetry --version
}

# نصب Node.js (برای Frontend)
install_nodejs() {
    print_header "نصب Node.js"
    
    if command -v node &> /dev/null; then
        print_status "Node.js قبلاً نصب شده است"
        node --version
        return
    fi
    
    # نصب Node.js 20 LTS
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    
    print_status "Node.js نصب شد ✓"
    node --version
    npm --version
}

# نصب PostgreSQL
install_postgresql() {
    print_header "نصب PostgreSQL"
    
    if command -v psql &> /dev/null; then
        print_status "PostgreSQL قبلاً نصب شده است"
        return
    fi
    
    if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
        apt install -y postgresql postgresql-contrib postgresql-client
    elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]]; then
        yum install -y postgresql postgresql-server postgresql-contrib
        postgresql-setup --initdb
    fi
    
    systemctl start postgresql
    systemctl enable postgresql
    
    print_status "PostgreSQL نصب شد ✓"
}

# نصب Redis
install_redis() {
    print_header "نصب Redis"
    
    if command -v redis-server &> /dev/null || command -v redis-cli &> /dev/null; then
        print_status "Redis قبلاً نصب شده است"
        return
    fi
    
    if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
        apt install -y redis-server
    elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]]; then
        yum install -y redis
    fi
    
    systemctl start redis
    systemctl enable redis
    
    print_status "Redis نصب شد ✓"
}

# نصب Nginx
install_nginx() {
    print_header "نصب Nginx"
    
    if command -v nginx &> /dev/null; then
        print_status "Nginx قبلاً نصب شده است"
        return
    fi
    
    if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
        apt install -y nginx
    elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]]; then
        yum install -y nginx
    fi
    
    systemctl start nginx
    systemctl enable nginx
    
    print_status "Nginx نصب شد ✓"
}

# ایجاد کاربر سیستم
create_system_user() {
    print_header "ایجاد کاربر سیستم"
    
    if id "$SERVICE_USER" &>/dev/null; then
        print_status "کاربر $SERVICE_USER قبلاً وجود دارد"
    else
        useradd -r -s /bin/bash -d $PROJECT_DIR -m $SERVICE_USER
        usermod -aG docker $SERVICE_USER
        print_status "کاربر $SERVICE_USER ایجاد شد ✓"
    fi
}

# ایجاد دایرکتوری‌ها
create_directories() {
    print_header "ایجاد دایرکتوری‌ها"
    
    mkdir -p $PROJECT_DIR
    mkdir -p $BACKUP_DIR
    mkdir -p $LOG_DIR
    mkdir -p /etc/flightio
    
    chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
    chown -R $SERVICE_USER:$SERVICE_USER $LOG_DIR
    chown -R $SERVICE_USER:$SERVICE_USER $BACKUP_DIR
    
    print_status "دایرکتوری‌ها ایجاد شد ✓"
}

# کلون پروژه
clone_project() {
    print_header "دانلود پروژه"
    
    if [ -d "$PROJECT_DIR/.git" ]; then
        print_status "پروژه قبلاً دانلود شده است، در حال بروزرسانی..."
        cd $PROJECT_DIR
        sudo -u $SERVICE_USER git pull origin main || sudo -u $SERVICE_USER git pull origin master
    else
        print_status "در حال کلون پروژه..."
        sudo -u $SERVICE_USER git clone $GIT_REPO $PROJECT_DIR
    fi
    
    chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
    print_status "پروژه دانلود شد ✓"
}

# تولید رمزهای امن
generate_passwords() {
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    SECRET_KEY=$(openssl rand -hex 32)
    GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-12)
}

# تنظیم محیط
setup_environment() {
    print_header "تنظیم محیط"
    
    cd $PROJECT_DIR
    
    # تولید رمزهای امن
    generate_passwords
    
    # ایجاد فایل production.env
    cat > production.env << EOF
# Database Configuration
DB_HOST=postgres
DB_NAME=flight_data
DB_USER=crawler
DB_PASSWORD=$DB_PASSWORD
DB_PORT=5432

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=$REDIS_PASSWORD

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security
SECRET_KEY=$SECRET_KEY

# Crawler Configuration
LOG_LEVEL=INFO
USE_MOCK=false
CRAWLER_TIMEOUT=30
ENVIRONMENT=production
DEBUG=false

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=$GRAFANA_PASSWORD

# Celery Configuration
CELERY_BROKER_URL=redis://:$REDIS_PASSWORD@redis:6379/0
CELERY_RESULT_BACKEND=redis://:$REDIS_PASSWORD@redis:6379/0

# External Services (اختیاری)
SLACK_WEBHOOK_URL=
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=
EMAIL_PASSWORD=
EOF
    
    # تنظیم permissions
    chmod 600 production.env
    chown $SERVICE_USER:$SERVICE_USER production.env
    
    # ایجاد فایل backup برای رمزها
    cat > /etc/flightio/passwords.txt << EOF
# رمزهای امنیتی FlightIO - $(date)
DB_PASSWORD=$DB_PASSWORD
REDIS_PASSWORD=$REDIS_PASSWORD
SECRET_KEY=$SECRET_KEY
GRAFANA_PASSWORD=$GRAFANA_PASSWORD
EOF
    chmod 600 /etc/flightio/passwords.txt
    
    print_status "محیط تنظیم شد ✓"
    print_warning "رمزهای امنیتی در /etc/flightio/passwords.txt ذخیره شد"
}

# تنظیم دیتابیس
setup_database() {
    print_header "تنظیم دیتابیس"
    
    # ایجاد کاربر و دیتابیس PostgreSQL
    sudo -u postgres psql -c "CREATE USER crawler WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE flight_data OWNER crawler;" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE flight_data TO crawler;" 2>/dev/null || true
    
    # اجرای اسکریپت init
    if [ -f "$PROJECT_DIR/init.sql" ]; then
        PGPASSWORD=$DB_PASSWORD psql -h localhost -U crawler -d flight_data -f $PROJECT_DIR/init.sql 2>/dev/null || true
    fi
    
    print_status "دیتابیس تنظیم شد ✓"
}

# تنظیم فایروال
setup_firewall() {
    print_header "تنظیم فایروال"
    
    if command -v ufw &> /dev/null; then
        ufw --force enable
        ufw allow ssh
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw allow 8000/tcp
        ufw allow 3000/tcp
        ufw allow 3001/tcp
        ufw allow 9090/tcp
        print_status "فایروال تنظیم شد ✓"
    elif command -v firewall-cmd &> /dev/null; then
        systemctl start firewalld
        systemctl enable firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --permanent --add-port=8000/tcp
        firewall-cmd --permanent --add-port=3000/tcp
        firewall-cmd --permanent --add-port=3001/tcp
        firewall-cmd --permanent --add-port=9090/tcp
        firewall-cmd --reload
        print_status "فایروال تنظیم شد ✓"
    else
        print_warning "فایروال یافت نشد"
    fi
}

# نصب وابستگی‌های Python
install_python_dependencies() {
    print_header "نصب وابستگی‌های Python"
    
    cd $PROJECT_DIR
    
    # نصب با Poetry (اگر موجود باشد)
    if [ -f "pyproject.toml" ] && command -v poetry &> /dev/null; then
        sudo -u $SERVICE_USER /root/.local/bin/poetry config virtualenvs.create true
        sudo -u $SERVICE_USER /root/.local/bin/poetry config virtualenvs.in-project true
        sudo -u $SERVICE_USER /root/.local/bin/poetry install --no-dev
        print_status "وابستگی‌ها با Poetry نصب شد ✓"
    # نصب با pip (fallback)
    elif [ -f "requirements.txt" ]; then
        sudo -u $SERVICE_USER python3 -m venv venv
        sudo -u $SERVICE_USER ./venv/bin/pip install --upgrade pip
        sudo -u $SERVICE_USER ./venv/bin/pip install -r requirements.txt
        print_status "وابستگی‌ها با pip نصب شد ✓"
    else
        print_error "فایل pyproject.toml یا requirements.txt یافت نشد"
        exit 1
    fi
}

# نصب وابستگی‌های Frontend
install_frontend_dependencies() {
    print_header "نصب وابستگی‌های Frontend"
    
    if [ -d "$PROJECT_DIR/frontend" ]; then
        cd $PROJECT_DIR/frontend
        sudo -u $SERVICE_USER npm install
        sudo -u $SERVICE_USER npm run build
        print_status "Frontend آماده شد ✓"
    else
        print_warning "دایرکتوری frontend یافت نشد"
    fi
}

# دپلوی پروژه
deploy_project() {
    print_header "دپلوی پروژه"
    
    cd $PROJECT_DIR
    
    # ساخت و اجرای container ها
    sudo -u $SERVICE_USER docker-compose -f docker-compose.production.yml down --remove-orphans 2>/dev/null || true
    sudo -u $SERVICE_USER docker-compose -f docker-compose.production.yml build --no-cache
    sudo -u $SERVICE_USER docker-compose -f docker-compose.production.yml up -d
    
    # انتظار برای راه‌اندازی سرویس‌ها
    print_status "انتظار برای راه‌اندازی سرویس‌ها..."
    sleep 60
    
    print_status "پروژه دپلوی شد ✓"
}

# تست سرویس‌ها
test_services() {
    print_header "تست سرویس‌ها"
    
    # تست API
    for i in {1..5}; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_status "API در حال اجرا است ✓"
            break
        else
            print_warning "در حال انتظار برای API... ($i/5)"
            sleep 10
        fi
    done
    
    # تست Frontend
    if curl -f http://localhost:3001 > /dev/null 2>&1; then
        print_status "Frontend در حال اجرا است ✓"
    else
        print_warning "Frontend در دسترس نیست"
    fi
    
    # تست Monitoring
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        print_status "Grafana در حال اجرا است ✓"
    else
        print_warning "Grafana در دسترس نیست"
    fi
    
    # نمایش وضعیت containers
    cd $PROJECT_DIR
    sudo -u $SERVICE_USER docker-compose -f docker-compose.production.yml ps
}

# ایجاد اسکریپت‌های کمکی
create_helper_scripts() {
    print_header "ایجاد اسکریپت‌های کمکی"
    
    # اسکریپت شروع
    cat > /usr/local/bin/flightio-start << 'EOF'
#!/bin/bash
cd /opt/flightio
sudo -u flightio docker-compose -f docker-compose.production.yml up -d
EOF
    
    # اسکریپت توقف
    cat > /usr/local/bin/flightio-stop << 'EOF'
#!/bin/bash
cd /opt/flightio
sudo -u flightio docker-compose -f docker-compose.production.yml down
EOF
    
    # اسکریپت restart
    cat > /usr/local/bin/flightio-restart << 'EOF'
#!/bin/bash
cd /opt/flightio
sudo -u flightio docker-compose -f docker-compose.production.yml restart
EOF
    
    # اسکریپت logs
    cat > /usr/local/bin/flightio-logs << 'EOF'
#!/bin/bash
cd /opt/flightio
sudo -u flightio docker-compose -f docker-compose.production.yml logs -f "$@"
EOF
    
    # اسکریپت status
    cat > /usr/local/bin/flightio-status << 'EOF'
#!/bin/bash
cd /opt/flightio
sudo -u flightio docker-compose -f docker-compose.production.yml ps
EOF
    
    # اسکریپت backup
    cat > /usr/local/bin/flightio-backup << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/flightio"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# پشتیبان‌گیری دیتابیس
docker exec flightio-postgres pg_dump -U crawler flight_data > $BACKUP_DIR/database_$DATE.sql

# پشتیبان‌گیری فایل‌های تنظیمات
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/flightio/production.env

# حذف فایل‌های قدیمی (بیش از 30 روز)
find $BACKUP_DIR -name "*.sql" -type f -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -type f -mtime +30 -delete

echo "پشتیبان‌گیری انجام شد: $BACKUP_DIR/database_$DATE.sql"
EOF
    
    chmod +x /usr/local/bin/flightio-*
    
    print_status "اسکریپت‌های کمکی ایجاد شد ✓"
}

# تنظیم systemd service
create_systemd_service() {
    print_header "تنظیم Systemd Service"
    
    cat > /etc/systemd/system/flightio.service << 'EOF'
[Unit]
Description=FlightIO Crawler Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/flightio
ExecStart=/usr/local/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.production.yml down
User=flightio
Group=flightio

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable flightio.service
    
    print_status "Systemd service تنظیم شد ✓"
}

# تنظیم cron jobs
setup_cron_jobs() {
    print_header "تنظیم Cron Jobs"
    
    # پشتیبان‌گیری روزانه در ساعت 2 صبح
    (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/flightio-backup") | crontab -
    
    print_status "Cron jobs تنظیم شد ✓"
}

# نمایش اطلاعات نهایی
show_final_info() {
    print_header "راه‌اندازی تنظیمات نهایی"
    
    echo -e "\n${GREEN}تمام عملیات با موفقیت انجام شد. پروژه به طور کامل راه‌اندازی شد.${NC}"
    echo -e "برای مدیریت پروژه، از اسکریپت‌های کمکی استفاده کنید:${NC}"
    echo -e "  - ${GREEN}flightio-start${NC} برای راه‌اندازی سرور"
    echo -e "  - ${GREEN}flightio-stop${NC} برای توقف سرور"
    echo -e "  - ${GREEN}flightio-restart${NC} برای راه‌اندازی مجدد سرور"
    echo -e "  - ${GREEN}flightio-logs${NC} برای مشاهده لاگ‌ها"
    echo -e "  - ${GREEN}flightio-status${NC} برای نمایش وضعیت سرور"
    echo -e "  - ${GREEN}flightio-backup${NC} برای انجام پشتیبان‌گیری${NC}"
}

# اجرای تابع اصلی
main() {
    detect_os
    check_root
    setup_variables
    update_system
    install_docker
    install_docker_compose
    install_python_poetry
    install_nodejs
    install_postgresql
    install_redis
    install_nginx
    create_system_user
    create_directories
    clone_project
    setup_environment
    setup_database
    setup_firewall
    install_python_dependencies
    install_frontend_dependencies
    deploy_project
    test_services
    create_helper_scripts
    create_systemd_service
    setup_cron_jobs
    show_final_info
}

# اجرای تابع اصلی
main 