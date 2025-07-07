# راهنمای سیستم Rate Limiting

این سند راهنمای کاملی برای استفاده از سیستم rate limiting پیشرفته در FlightioCrawler ارائه می‌دهد.

## فهرست مطالب
- [نصب و راه‌اندازی](#نصب-و-راه‌اندازی)
- [تنظیمات](#تنظیمات)
- [انواع محدودیت‌ها](#انواع-محدودیت‌ها)
- [API Endpoints](#api-endpoints)
- [نظارت و مدیریت](#نظارت-و-مدیریت)
- [عیب‌یابی](#عیب‌یابی)

## نصب و راه‌اندازی

### پیش‌نیازها
```bash
# نصب Redis
apt-get install redis-server

# یا با Docker
docker run -d --name redis -p 6379:6379 redis:alpine
```

### فعال‌سازی در کد
```python
from fastapi import FastAPI
from rate_limiter import RateLimitMiddleware

app = FastAPI()

# اضافه کردن middleware
app.add_middleware(RateLimitMiddleware)
```

## تنظیمات

### تنظیمات پیش‌فرض
```python
RATE_LIMIT_CONFIGS = {
    "default": {
        "requests_per_minute": 60,    # 60 درخواست در دقیقه
        "requests_per_hour": 1000,    # 1000 درخواست در ساعت
        "burst_limit": 10             # حداکثر 10 درخواست پشت سر هم
    },
    "search": {
        "requests_per_minute": 20,
        "requests_per_hour": 200,
        "burst_limit": 5
    },
    "crawl": {
        "requests_per_minute": 5,
        "requests_per_hour": 50,
        "burst_limit": 2
    }
}
```

### انواع کاربران
```python
USER_TYPE_LIMITS = {
    "anonymous": 1.0,    # محدودیت پایه
    "registered": 2.0,   # 2 برابر محدودیت پایه
    "premium": 5.0,      # 5 برابر محدودیت پایه
    "admin": 10.0        # 10 برابر محدودیت پایه
}
```

## انواع محدودیت‌ها

### 1. محدودیت دقیقه‌ای
تعداد درخواست‌های مجاز در یک دقیقه

### 2. محدودیت ساعتی
تعداد درخواست‌های مجاز در یک ساعت

### 3. محدودیت Burst
تعداد درخواست‌های متوالی بدون وقفه

### 4. محدودیت بر اساس نوع کاربر
ضریب تعدیل بر اساس نوع کاربر

## IP Whitelist

### IP های پیش‌فرض در whitelist:
- `127.0.0.1` (localhost)
- `::1` (IPv6 localhost)
- `10.0.0.0/8` (شبکه خصوصی)
- `172.16.0.0/12` (شبکه خصوصی)
- `192.168.0.0/16` (شبکه خصوصی)

## API Endpoints

### دریافت آمار Rate Limiting
```http
GET /api/v1/rate-limits/stats?endpoint_type=search
```

**پاسخ:**
```json
{
    "rate_limit_stats": {
        "search": {
            "requests_success": "150",
            "requests_error": "5",
            "total_requests": "155"
        }
    },
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### دریافت تنظیمات فعلی
```http
GET /api/v1/rate-limits/config
```

**پاسخ:**
```json
{
    "endpoint_configs": {
        "search": {
            "requests_per_minute": 20,
            "requests_per_hour": 200,
            "burst_limit": 5
        }
    },
    "user_type_multipliers": {
        "anonymous": 1.0,
        "premium": 5.0
    }
}
```

### بروزرسانی تنظیمات
```http
PUT /api/v1/rate-limits/config
Content-Type: application/json

{
    "endpoint_type": "search",
    "requests_per_minute": 30,
    "requests_per_hour": 300,
    "burst_limit": 8
}
```

### بررسی وضعیت کلاینت
```http
GET /api/v1/rate-limits/client/192.168.1.100?endpoint_type=search
```

**پاسخ:**
```json
{
    "client_ip": "192.168.1.100",
    "endpoint_type": "search",
    "minute_requests": 5,
    "hour_requests": 45,
    "burst_requests": 1,
    "minute_remaining": 15,
    "hour_remaining": 155,
    "burst_remaining": 4
}
```

### ریست کردن محدودیت‌های کلاینت
```http
POST /api/v1/rate-limits/reset
Content-Type: application/json

{
    "client_ip": "192.168.1.100",
    "endpoint_type": "search"
}
```

### دریافت کلاینت‌های مسدود
```http
GET /api/v1/rate-limits/blocked?limit=50
```

### اضافه کردن IP به Whitelist
```http
POST /api/v1/rate-limits/whitelist
Content-Type: application/json

{
    "ip": "192.168.1.100",
    "duration_seconds": 3600
}
```

### بررسی وضعیت Whitelist
```http
GET /api/v1/rate-limits/whitelist/192.168.1.100
```

## Headers در پاسخ‌ها

### درخواست‌های موفق
```http
X-RateLimit-Remaining-Minute: 15
X-RateLimit-Remaining-Hour: 185
X-RateLimit-Remaining-Burst: 4
```

### درخواست‌های رد شده (HTTP 429)
```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200
Retry-After: 42
```

## نظارت و مدیریت

### لاگ‌ها
```python
# فعال‌سازی لاگ‌های تفصیلی
import logging
logging.getLogger('rate_limiter').setLevel(logging.DEBUG)
```

### Metrics در Prometheus
```
# Rate limit violations
rate_limit_violations_total{endpoint="search",limit_type="minute"}

# Active rate limited clients
rate_limited_clients_active{endpoint="search"}

# Rate limit performance
rate_limit_check_duration_seconds
```

### Dashboard Grafana
```json
{
    "title": "Rate Limiting Dashboard",
    "panels": [
        {
            "title": "Rate Limit Violations",
            "type": "graph",
            "targets": [
                {
                    "expr": "rate(rate_limit_violations_total[5m])",
                    "legendFormat": "{{endpoint}} - {{limit_type}}"
                }
            ]
        }
    ]
}
```

## عیب‌یابی

### مشکلات رایج

#### 1. Redis در دسترس نیست
**علامت:** تمام درخواست‌ها مجاز هستند
**راه‌حل:** بررسی اتصال Redis

```bash
redis-cli ping
```

#### 2. Rate limit خیلی سخت‌گیرانه است
**علامت:** درخواست‌های معمولی رد می‌شوند
**راه‌حل:** تنظیم مجدد محدودیت‌ها

```python
# افزایش محدودیت موقت
await rate_limit_manager.update_rate_limit_config("search", {
    "requests_per_minute": 50,
    "requests_per_hour": 500,
    "burst_limit": 10
})
```

#### 3. IP اشتباه مسدود شده
**راه‌حل:** اضافه کردن به whitelist

```python
await rate_limit_manager.whitelist_ip("192.168.1.100", 3600)
```

### بررسی سلامت سیستم
```bash
# بررسی Redis
redis-cli info memory

# بررسی کلیدهای rate limiting
redis-cli keys "rate_limit:*" | wc -l

# بررسی آمار
curl http://localhost:8000/api/v1/rate-limits/stats
```

### ابزارهای تست

#### تست محدودیت دقیقه‌ای
```bash
#!/bin/bash
for i in {1..25}; do
    curl -w "%{http_code}\n" -o /dev/null -s http://localhost:8000/search
    sleep 2
done
```

#### تست burst limit
```bash
#!/bin/bash
for i in {1..15}; do
    curl -w "%{http_code}\n" -o /dev/null -s http://localhost:8000/search &
done
wait
```

## پیکربندی پیشرفته

### تنظیم محدودیت‌های سفارشی
```python
# در config.py
CUSTOM_RATE_LIMITS = {
    "api_v1_heavy": {
        "requests_per_minute": 2,
        "requests_per_hour": 10,
        "burst_limit": 1
    }
}

# در main.py
@app.post("/api/v1/heavy-operation")
async def heavy_operation():
    # عملیات سنگین
    pass
```

### Middleware سفارشی
```python
class CustomRateLimitMiddleware(RateLimitMiddleware):
    def _get_endpoint_type(self, path: str) -> str:
        if path.startswith("/api/v2"):
            return "api_v2"
        return super()._get_endpoint_type(path)
```

### تنظیمات environment
```bash
# در .env
RATE_LIMIT_REDIS_URL=redis://localhost:6379/1
RATE_LIMIT_ENABLE_WHITELIST=true
RATE_LIMIT_DEFAULT_MINUTE_LIMIT=100
RATE_LIMIT_DEFAULT_HOUR_LIMIT=2000
```

## بهترین شیوه‌ها

### 1. تنظیم محدودیت‌ها
- شروع با محدودیت‌های ملایم
- نظارت مستمر و تنظیم تدریجی
- در نظر گیری peak traffic

### 2. مدیریت Whitelist
- محدود کردن whitelist به IP های ضروری
- استفاده از whitelist موقت برای عیب‌یابی
- مستندسازی تمام IP های whitelisted

### 3. نظارت
- راه‌اندازی alerts برای violation rate بالا
- بررسی منظم آمار rate limiting
- نگهداری لاگ‌های تفصیلی

### 4. عملکرد
- استفاده از Redis clustering برای scale
- تنظیم TTL مناسب برای کلیدها
- استفاده از pipeline برای عملیات batch

## پشتیبانی و سوالات متداول

### سوالات متداول

**س: چگونه محدودیت را برای کاربر خاص غیرفعال کنم؟**
ج: می‌توانید IP کاربر را به whitelist اضافه کنید یا نوع کاربر او را به admin تغییر دهید.

**س: آیا rate limiting روی WebSocket ها اعمال می‌شود؟**
ج: خیر، فعلاً فقط روی HTTP endpoints اعمال می‌شود.

**س: چگونه می‌توانم rate limit را کاملاً غیرفعال کنم؟**
ج: middleware را از FastAPI حذف کنید یا تمام محدودیت‌ها را به مقدار بسیار بالا تنظیم کنید.

### راه‌های تماس
- GitHub Issues: برای گزارش bug ها
- Documentation: برای راهنمای بیشتر
- Team Contact: برای پشتیبانی فنی

---

**نکته:** این سیستم rate limiting برای محیط production طراحی شده و قابلیت تنظیم بالایی دارد. همیشه قبل از اعمال تغییرات در production، در محیط test آزمایش کنید. 