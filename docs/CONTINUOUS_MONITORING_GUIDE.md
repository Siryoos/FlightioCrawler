# 🔍 راهنمای جامع Continuous Memory Monitoring

## 📋 معرفی

سیستم **Continuous Memory Monitoring** یک راه‌حل جامع و خودکار برای نظارت مداوم حافظه در محیط تولید سیستم Flight Crawler است که قابلیت‌های زیر را فراهم می‌کند:

- 🔄 **نظارت real-time** بر مصرف حافظه و منابع سیستم
- 🚨 **هشدارهای هوشمند** با سطح‌بندی warning, critical, emergency
- 🔧 **پاسخ خودکار** به مشکلات حافظه (Garbage Collection, Cache Cleanup)
- 📊 **Dashboard تعاملی** برای visualisation و analytics
- 🌐 **Health Check API** برای monitoring external
- 📈 **Prometheus Metrics** برای ادغام با monitoring stack

---

## 🚀 راه‌اندازی سریع

### 1. راه‌اندازی با Production Script

```bash
# راه‌اندازی کامل سیستم با memory monitoring
python scripts/start_production_monitoring.py

# راه‌اندازی با تنظیمات سفارشی
python scripts/start_production_monitoring.py \
    --config config/production.json \
    --health-port 8080 \
    --prometheus-port 9091 \
    --log-level INFO
```

### 2. راه‌اندازی دستی اجزای جداگانه

```python
from monitoring.production_memory_monitor import ProductionMemoryMonitor
from monitoring.memory_health_endpoint import MemoryHealthServer

# ایجاد memory monitor
monitor = ProductionMemoryMonitor("monitoring/monitoring_config.json")

# راه‌اندازی monitoring
await monitor.start_monitoring()

# راه‌اندازی health server
health_server = MemoryHealthServer(monitor, port=8080)
await health_server.start_server()
```

---

## ⚙️ تنظیمات

### فایل تنظیمات اصلی: `monitoring/monitoring_config.json`

```json
{
  "monitoring": {
    "check_interval": 30,
    "enable_tracemalloc": true,
    "prometheus_port": 9091
  },
  "thresholds": {
    "memory_warning_mb": 1024,
    "memory_critical_mb": 2048,
    "memory_emergency_mb": 4096,
    "memory_percent_warning": 70,
    "memory_percent_critical": 85,
    "memory_percent_emergency": 95
  },
  "alerting": {
    "webhook_url": "https://your-webhook.com/alerts",
    "slack_webhook": "https://hooks.slack.com/your-webhook"
  },
  "auto_response": {
    "enabled": true,
    "critical_actions": {
      "force_gc": true,
      "clear_caches": true,
      "throttle_operations": true
    }
  }
}
```

### تنظیمات Environment Variables

```bash
# Production environment
export MEMORY_HEALTH_PORT=8080
export PROMETHEUS_PORT=9091
export MONITORING_LOG_LEVEL=INFO

# Alert configurations  
export SLACK_WEBHOOK_URL="https://hooks.slack.com/your-webhook"
export ALERT_EMAIL="alerts@yourcompany.com"
```

---

## 🔧 API Endpoints

### Health Check اصلی

```bash
# بررسی سلامت کلی سیستم
curl http://localhost:8080/health

# Response:
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 3600,
  "monitoring_active": true,
  "memory_usage_mb": 512.3,
  "memory_percentage": 45.2,
  "active_alerts": 0
}
```

### Memory Metrics تفصیلی

```bash
# دریافت metrics تفصیلی حافظه
curl http://localhost:8080/health/memory

# Response:
{
  "timestamp": "2024-01-15T10:30:00Z",
  "rss_mb": 512.3,
  "vms_mb": 1024.7,
  "percent": 45.2,
  "available_mb": 2048.5,
  "swap_percent": 12.3,
  "gc_collections": 1250,
  "gc_objects": 50000
}
```

### Alert Summary

```bash
# خلاصه هشدارهای 24 ساعت گذشته
curl http://localhost:8080/health/alerts?hours=24

# Response:
{
  "total_alerts": 5,
  "active_alerts": 1,
  "resolved_alerts": 4,
  "by_severity": {
    "warning": 3,
    "critical": 2
  },
  "by_component": {
    "system_memory": 4,
    "swap_memory": 1
  }
}
```

### Metrics History

```bash
# تاریخچه metrics ساعت گذشته
curl http://localhost:8080/health/metrics/history?hours=1
```

### اقدامات دستی

```bash
# اجبار Garbage Collection
curl -X POST http://localhost:8080/health/actions/gc

# Response:
{
  "success": true,
  "collected_objects": 1234,
  "before_objects": 55000,
  "after_objects": 53766,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 📊 Prometheus Metrics

### Metrics در دسترس

```
# Memory usage metrics
memory_usage_bytes{component="rss_mb"}
memory_usage_bytes{component="vms_mb"}
memory_usage_bytes{component="percent"}
memory_usage_bytes{component="available_mb"}
memory_usage_bytes{component="swap_percent"}

# Alert metrics
memory_alerts_sent_total{severity="warning"}
memory_alerts_sent_total{severity="critical"}
memory_alerts_sent_total{severity="emergency"}

# Performance metrics
memory_check_duration_seconds
memory_cleanup_operations_total
memory_leaks_detected_total
```

### نمونه Queries

```promql
# میانگین مصرف حافظه در 5 دقیقه گذشته
avg_over_time(memory_usage_bytes{component="rss_mb"}[5m])

# تعداد alerts در ساعت گذشته
increase(memory_alerts_sent_total[1h])

# 95th percentile زمان بررسی حافظه
histogram_quantile(0.95, rate(memory_check_duration_seconds_bucket[5m]))
```

---

## 🎨 Grafana Dashboard

### Import Dashboard

1. فایل `monitoring/grafana_memory_dashboard.json` را import کنید
2. Data source را به Prometheus متصل کنید
3. Dashboard را customize کنید

### Panels کلیدی

- 📊 **Memory Usage (MB)**: نمایش میزان مصرف حافظه با threshold رنگی
- 📈 **Memory Usage Trend**: روند تغییرات حافظه در طول زمان
- ⚠️ **Memory Alerts**: تعداد کل alerts
- 🔄 **Memory Percentage**: درصد استفاده از حافظه (Gauge)
- 💾 **Swap Usage**: نمایش میزان استفاده از Swap
- 🗑️ **Garbage Collection**: آمار GC objects
- 🚨 **Alert Timeline**: Timeline alerts ها
- ⏱️ **Check Response Time**: زمان پاسخ health checks

---

## 🚨 راه‌اندازی Alerting

### Slack Integration

```json
{
  "alerting": {
    "slack_webhook": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    "alert_levels": {
      "critical": {
        "channels": ["log", "slack"]
      },
      "emergency": {
        "channels": ["log", "slack", "email"]
      }
    }
  }
}
```

### Webhook Integration

```json
{
  "alerting": {
    "webhook_url": "https://your-monitoring-system.com/alerts",
    "rate_limit_seconds": 300
  }
}
```

### نمونه Alert Payload

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "severity": "critical",
  "component": "system_memory",
  "memory_usage": 2048.5,
  "threshold": 2048.0,
  "message": "🚨 CRITICAL: Memory usage 2048.5MB exceeds critical threshold",
  "metadata": {
    "percent": 85.2,
    "available_mb": 512.3
  }
}
```

---

## 🔄 Automated Response System

### اقدامات خودکار

#### Warning Level:
- ✅ Force Garbage Collection
- ✅ Log Warning Message

#### Critical Level:
- ✅ Multiple Garbage Collection Cycles
- ✅ Clear Application Caches
- ✅ Throttle Concurrent Operations
- ✅ Send Alert Notifications

#### Emergency Level:
- ✅ Aggressive Memory Cleanup
- ✅ Emergency Cache Clearing
- ✅ Kill Non-Essential Threads
- ✅ Immediate Alert Broadcasting
- ✅ Preparation for Graceful Restart

### تنظیمات Auto Response

```json
{
  "auto_response": {
    "enabled": true,
    "emergency_actions": {
      "force_gc": true,
      "multiple_gc_cycles": 3,
      "clear_all_caches": true,
      "emergency_throttle": true,
      "send_immediate_alert": true
    }
  }
}
```

---

## 📈 Monitoring Best Practices

### 1. Threshold Setting

```json
{
  "thresholds": {
    "memory_warning_mb": 1024,    // 1GB - هشدار اولیه
    "memory_critical_mb": 2048,   // 2GB - وضعیت بحرانی
    "memory_emergency_mb": 4096,  // 4GB - وضعیت اضطراری
    "memory_percent_warning": 70, // 70% - هشدار درصدی
    "memory_percent_critical": 85 // 85% - بحرانی درصدی
  }
}
```

### 2. Check Interval Optimization

```json
{
  "monitoring": {
    "check_interval": 30,          // بررسی هر 30 ثانیه
    "history_size": 2000,          // نگهداری 2000 record
    "enable_tracemalloc": true     // ردیابی دقیق allocation
  }
}
```

### 3. Rate Limiting

```json
{
  "alerting": {
    "rate_limit_seconds": 300      // محدودیت 5 دقیقه بین alerts مشابه
  }
}
```

---

## 🐛 Troubleshooting

### مشکلات رایج و حل آنها

#### 1. Memory Monitor شروع نمی‌شود

```bash
# بررسی logs
tail -f logs/production.log | grep -i memory

# بررسی config file
python -c "import json; print(json.load(open('monitoring/monitoring_config.json')))"
```

#### 2. Health Server در دسترس نیست

```bash
# بررسی port availability
netstat -tulpn | grep :8080

# تست connection
curl -v http://localhost:8080/health
```

#### 3. Prometheus Metrics نمایش داده نمی‌شود

```bash
# بررسی metrics endpoint
curl http://localhost:9091/metrics | grep memory_usage

# بررسی Prometheus config
# در prometheus.yml باید scrape job تعریف باشد:
- job_name: 'flight-crawler-memory'
  static_configs:
    - targets: ['localhost:9091']
```

#### 4. Alerts ارسال نمی‌شود

```bash
# تست webhook
curl -X POST https://your-webhook.com/test \
  -H "Content-Type: application/json" \
  -d '{"test": "alert"}'

# بررسی Slack webhook
curl -X POST YOUR_SLACK_WEBHOOK \
  -H "Content-Type: application/json" \
  -d '{"text": "Test alert from Flight Crawler"}'
```

---

## 📚 Advanced Features

### 1. Memory Leak Detection

سیستم به طور خودکار pattern های مشکوک حافظه را شناسایی می‌کند:

```python
# فعال‌سازی leak detection
{
  "monitoring": {
    "enable_tracemalloc": true,
    "leak_detection": {
      "enabled": true,
      "threshold_growth_rate": 0.1,  // 10% growth rate
      "monitoring_window": 300       // 5 minutes
    }
  }
}
```

### 2. Predictive Alerting

```json
{
  "experimental": {
    "predictive_alerting": true,
    "prediction_window": 600,        // 10 minutes
    "trend_threshold": 0.05          // 5% trend
  }
}
```

### 3. Integration با External Systems

```python
# Custom alert handler
async def custom_alert_handler(alert):
    # ارسال به external monitoring system
    await send_to_external_system(alert)

# اضافه کردن handler
monitor.alert_manager.add_handler(custom_alert_handler)
```

---

## 🎯 Performance Impact

### Monitoring Overhead

- **CPU Usage**: < 2% در حالت عادی
- **Memory Usage**: ~10MB برای monitoring system
- **Network**: ~1KB/s برای metrics export
- **Disk I/O**: ~100KB/hour برای logging

### Optimizations Applied

```json
{
  "performance": {
    "monitoring_overhead_limit_percent": 5,
    "max_monitoring_time_seconds": 2,
    "async_processing": true,
    "batch_processing": true
  }
}
```

---

## ✅ Verification Checklist

- [ ] Memory monitor راه‌اندازی شده و فعال است
- [ ] Health endpoints پاسخ می‌دهند
- [ ] Prometheus metrics در دسترس است
- [ ] Grafana dashboard import شده
- [ ] Alert channels تست شده‌اند
- [ ] Auto response actions فعال است
- [ ] Thresholds متناسب با environment تنظیم شده
- [ ] Logging صحیح کار می‌کند
- [ ] Graceful shutdown تست شده

---

## 📖 مراجع

- [Production Memory Monitor API](monitoring/production_memory_monitor.py)
- [Health Check Endpoints](monitoring/memory_health_endpoint.py)
- [Configuration Schema](monitoring/monitoring_config.json)
- [Grafana Dashboard](monitoring/grafana_memory_dashboard.json)
- [Performance Guide](PERFORMANCE_GUIDE.md)

---

## 🆘 پشتیبانی

در صورت بروز مشکل یا نیاز به راهنمایی:

1. **Logs**: بررسی فایل‌های log در `logs/`
2. **Health Status**: چک کردن `/health` endpoint
3. **Metrics**: مراجعه به Prometheus metrics
4. **Documentation**: مطالعه این راهنما و کد source

---

*✨ با سیستم Continuous Memory Monitoring، عملکرد Flight Crawler در محیط تولید با اطمینان کامل نظارت می‌شود!* 