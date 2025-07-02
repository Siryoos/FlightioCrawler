# راه‌اندازی محیط تولید FlightIO

این راهنما شما را از مرحله توسعه به محیط تولید کامل هدایت می‌کند.

## ۱. پیش‌نیازها

### سیستم‌عامل و نرم‌افزارها
- Ubuntu 20.04+ یا CentOS 8+
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+
- PostgreSQL 15+ (اختیاری - می‌تواند در Docker اجرا شود)
- Redis 7+ (اختیاری - می‌تواند در Docker اجرا شود)

### منابع سیستم (حداقل توصیه‌شده)
- **RAM**: 8GB (16GB برای بار کاری سنگین)
- **CPU**: 4 هسته
- **فضای دیسک**: 50GB
- **شبکه**: اتصال پایدار به اینترنت

## ۲. راه‌اندازی سریع با Docker

### مرحله ۱: کلون پروژه
```bash
git clone <repository-url>
cd FlightioCrawler
```

### مرحله ۲: تنظیم متغیرهای محیطی
```bash
# کپی فایل نمونه
cp production.env production.env.local

# ویرایش فایل با اطلاعات واقعی
nano production.env.local
```

**متغیرهای ضروری برای تغییر:**
```bash
# رمزهای امنیتی - حتماً تغییر دهید!
DB_PASSWORD=your_secure_database_password_here
SECRET_KEY=your_super_secret_key_minimum_32_characters
REDIS_PASSWORD=your_redis_password

# تنظیمات شبکه
API_HOST=0.0.0.0
API_PORT=8000

# محیط تولید
USE_MOCK=false
ENVIRONMENT=production
DEBUG=false
```

### مرحله ۳: اجرای خودکار
```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

## ۳. راه‌اندازی دستی

### مرحله ۱: آماده‌سازی دیتابیس
```bash
# نصب PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# ایجاد کاربر و دیتابیس
sudo -u postgres psql
CREATE USER crawler WITH PASSWORD 'secure_password';
CREATE DATABASE flight_data OWNER crawler;
GRANT ALL PRIVILEGES ON DATABASE flight_data TO crawler;
\q

# اجرای اسکریپت اولیه
psql -U crawler -d flight_data -f init.sql
```

### مرحله ۲: نصب Redis
```bash
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# تنظیم رمز عبور (اختیاری)
sudo nano /etc/redis/redis.conf
# اضافه کردن: requirepass your_redis_password
sudo systemctl restart redis-server
```

### مرحله ۳: نصب Poetry و وابستگی‌ها
```bash
pip install poetry
poetry install --without dev
```

### مرحله ۴: راه‌اندازی Celery
```bash
# Worker
celery -A tasks worker --loglevel=info --detach

# Beat Scheduler  
celery -A tasks beat --loglevel=info --detach
```

### مرحله ۵: اجرای API
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## ۴. مانیتورینگ و نظارت

### Prometheus + Grafana
بعد از راه‌اندازی Docker Compose:

1. **Prometheus**: http://localhost:9090
2. **Grafana**: http://localhost:3000 (admin/admin)

### داشبوردهای آماده
داشبوردهای Grafana در `monitoring/grafana_dashboards/` قرار دارند:
- `business.json`: آمار کسب‌وکار
- `crawler-performance.json`: عملکرد crawler ها
- `database.json`: آمار دیتابیس
- `redis.json`: آمار Redis

### هشدارها
تنظیمات هشدار در `monitoring/alert_rules.yml` تعریف شده‌اند:
- پایین بودن سرویس‌ها
- مصرف بالای منابع
- خطاهای crawler

## ۵. تنظیمات امنیتی

### فایروال
```bash
# باز کردن پورت‌های ضروری
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

### SSL/TLS (برای دامنه واقعی)
```bash
# نصب Certbot
sudo apt install certbot

# دریافت گواهی
sudo certbot certonly --standalone -d yourdomain.com

# کپی گواهی‌ها به nginx
sudo cp /etc/letsencrypt/live/yourdomain.com/* nginx/ssl/
```

### محدودیت نرخ درخواست
تنظیمات در `nginx/nginx.conf`:
- API: 10 درخواست در ثانیه
- Crawl: 2 درخواست در ثانیه

## ۶. بهینه‌سازی عملکرد

### تنظیمات Crawler
در `config/site_configs/*.json`:
```json
{
  "rate_limiting": {
    "requests_per_second": 1,
    "cooldown_period": 60
  }
}
```

### تنظیمات دیتابیس
در `postgresql.conf`:
```
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
```

### تنظیمات Redis
در `redis.conf`:
```
maxmemory 512mb
maxmemory-policy allkeys-lru
```

## ۷. پشتیبان‌گیری

### دیتابیس
```bash
# پشتیبان‌گیری روزانه
pg_dump -U crawler flight_data > backup_$(date +%Y%m%d).sql

# بازیابی
psql -U crawler -d flight_data < backup_20240101.sql
```

### Redis
```bash
# پشتیبان‌گیری
redis-cli --rdb dump.rdb

# بازیابی
sudo cp dump.rdb /var/lib/redis/
sudo systemctl restart redis-server
```

## ۸. عیب‌یابی

### مشکلات رایج

#### 1. خطای اتصال به دیتابیس
```bash
# بررسی وضعیت PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -c "SELECT version();"
```

#### 2. خطای اتصال به Redis
```bash
# بررسی وضعیت Redis
sudo systemctl status redis-server
redis-cli ping
```

#### 3. خطای Selenium/Chrome
```bash
# نصب وابستگی‌های Chrome
sudo apt install chromium-browser chromium-chromedriver
```

#### 4. مشکل دسترسی‌ها
```bash
# بررسی مجوزها
ls -la logs/ data/
sudo chown -R $USER:$USER logs/ data/
```

### لاگ‌ها
```bash
# لاگ‌های Docker
docker-compose -f docker-compose.production.yml logs -f api

# لاگ‌های سیستم
tail -f logs/flight_crawler.log

# لاگ‌های Celery
tail -f logs/celery.log
```

## ۹. به‌روزرسانی

### به‌روزرسانی کد
```bash
git pull origin main
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

### به‌روزرسانی دیتابیس
```bash
# اجرای migration ها (در صورت وجود)
python scripts/migrate_database.py
```

## ۱۰. سوالات متداول

**س: چگونه crawler ها را از حالت mock به واقعی تغییر دهم؟**
ج: در فایل `production.env` مقدار `USE_MOCK=false` را قرار دهید.

**س: چگونه سایت جدیدی اضافه کنم؟**
ج: 
1. فایل adapter جدید در `adapters/site_adapters/` بسازید
2. کانفیگ سایت در `config/site_configs/` اضافه کنید  
3. سایت را به `main_crawler.py` اضافه کنید

**س: چگونه نرخ crawler را تنظیم کنم؟**
ج: فایل JSON مربوط به سایت در `config/site_configs/` را ویرایش کنید.

**س: چگونه هشدارها را تنظیم کنم؟**
ج: فایل `monitoring/alert_rules.yml` را ویرایش کرده و Webhook های Slack/Email را در `production.env` تنظیم کنید.

## پشتیبانی

برای مشکلات فنی:
1. ابتدا لاگ‌ها را بررسی کنید
2. مستندات API را مطالعه کنید
3. Issue جدید در GitHub ایجاد کنید

---

**نکته امنیتی**: همیشه رمزهای پیش‌فرض را تغییر دهید و از HTTPS استفاده کنید! 
