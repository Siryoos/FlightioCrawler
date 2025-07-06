# راهنمای الگوهای طراحی (Design Patterns Guide)

این راهنما شامل توضیح کامل الگوهای طراحی پیاده‌سازی شده در سیستم FlightioCrawler می‌باشد. هر الگو برای حل مشکلات خاصی طراحی شده و استفاده از آن‌ها باعث بهبود قابل توجه معماری و قابلیت نگهداری کد خواهد شد.

## فهرست مطالب

1. [Factory Pattern - الگوی کارخانه](#factory-pattern)
2. [Strategy Pattern - الگوی استراتژی](#strategy-pattern)
3. [Observer Pattern - الگوی ناظر](#observer-pattern)
4. [Builder Pattern - الگوی سازنده](#builder-pattern)
5. [Singleton Pattern - الگوی تک‌نمونه](#singleton-pattern)
6. [Command Pattern - الگوی فرمان](#command-pattern)
7. [نحوه ترکیب الگوها](#pattern-composition)
8. [بهترین روش‌های استفاده](#best-practices)

---

## Factory Pattern - الگوی کارخانه

### مفهوم
الگوی Factory برای ایجاد انواع مختلف آداپترها بدون اینکه کد مصرف‌کننده نیاز به دانستن جزئیات ایجاد داشته باشد استفاده می‌شود.

### فایل‌های مرتبط
- `adapters/factories/unified_adapter_factory.py`

### استفاده اساسی

```python
from adapters.factories.unified_adapter_factory import get_unified_factory

# Get the unified factory
factory = get_unified_factory()

# Create adapters
alibaba_adapter = factory.create_adapter("alibaba")
parto_adapter = factory.create_adapter("parto")
```

### استفاده پیشرفته

```python
from adapters.factories.enhanced_adapter_factory import (
    EnhancedAdapterFactory, 
    AdapterType,
    get_adapter_registry
)

# دریافت لیست آداپترهای موجود
registry = get_adapter_registry()
persian_adapters = registry.get_adapters_by_type(AdapterType.PERSIAN)

# ایجاد آداپتر با استراتژی خاص
factory = EnhancedAdapterFactory()
factory.set_creation_strategy("module_creation")
adapter = factory.create_adapter("new_site")

# ثبت آداپتر جدید
from my_adapter import MyCustomAdapter
registry.register_adapter(
    "my_custom_site",
    MyCustomAdapter,
    AdapterType.PERSIAN,
    "My Custom Site"
)
```

### مزایا
- **انعطاف‌پذیری**: اضافه کردن آداپتر جدید بدون تغییر کد موجود
- **مدیریت متمرکز**: تمام منطق ایجاد آداپتر در یک مکان
- **پیکربندی پویا**: امکان تنظیم آداپترها از فایل‌های پیکربندی

---

## Strategy Pattern - الگوی استراتژی

### مفهوم
الگوی Strategy برای انتخاب الگوریتم تجزیه مناسب بر اساس نوع داده‌های دریافتی استفاده می‌شود.

### فایل‌های مرتبط
- `adapters/strategies/parsing_strategies.py`

### استفاده اساسی

```python
from adapters.strategies.parsing_strategies import (
    ParsingStrategyFactory,
    ParseContext,
    PersianParsingStrategy
)

# انتخاب خودکار استراتژی
factory = ParsingStrategyFactory()
strategy = factory.get_strategy(ParseContext.PERSIAN_DOMESTIC)

# تجزیه داده‌های خام
raw_data = {
    'price': '۱,۲۰۰,۰۰۰ ریال',
    'time': '۱۴:۳۰',
    'airline': 'ماهان'
}

result = strategy.parse(raw_data)
print(f"قیمت: {result.data['price']}")  # 1200000
print(f"زمان: {result.data['departure_time']}")  # 14:30
```

### استفاده پیشرفته

```python
# استفاده مستقیم از استراتژی خاص
persian_strategy = PersianParsingStrategy()

# تنظیم نقشه‌برداری شرکت هوایی
airline_mapping = {
    'ماهان': 'Mahan Air',
    'ایران ایر': 'Iran Air'
}
persian_strategy.set_airline_mapping(airline_mapping)

# تجزیه با تنظیمات سفارشی
options = {
    'validate_price': True,
    'convert_currency': True,
    'normalize_text': True
}

result = persian_strategy.parse(raw_data, **options)

# ترکیب چندین استراتژی
from adapters.strategies.parsing_strategies import InternationalParsingStrategy

results = []
for data_source in mixed_data_sources:
    if data_source['type'] == 'persian':
        strategy = PersianParsingStrategy()
    else:
        strategy = InternationalParsingStrategy()
    
    result = strategy.parse(data_source['data'])
    results.append(result)
```

### مزایا
- **انعطاف‌پذیری**: امکان تغییر الگوریتم تجزیه بدون تغییر کد اصلی
- **قابلیت توسعه**: اضافه کردن استراتژی‌های جدید آسان
- **تست‌پذیری**: امکان تست مستقل هر استراتژی

---

## Observer Pattern - الگوی ناظر

### مفهوم
الگوی Observer برای مدیریت رویدادها و اطلاع‌رسانی به اجزای مختلف سیستم هنگام وقوع تغییرات استفاده می‌شود.

### فایل‌های مرتبط
- `adapters/patterns/observer_pattern.py`

### استفاده اساسی

```python
from adapters.patterns.observer_pattern import (
    CrawlerEventSystem,
    LoggingObserver,
    MetricsObserver,
    EventType
)

# ایجاد سیستم رویداد
event_system = CrawlerEventSystem()

# افزودن ناظران
logging_observer = LoggingObserver()
metrics_observer = MetricsObserver()

event_system.add_observer(logging_observer)
event_system.add_observer(metrics_observer)

# ارسال رویداد
event_system.emit_crawl_started("alibaba", {
    'origin': 'THR',
    'destination': 'IST'
})

# ارسال رویداد خطا
event_system.emit_error("alibaba", Exception("Connection timeout"))
```

### استفاده پیشرفته

```python
from adapters.patterns.observer_pattern import DatabaseObserver, AlertObserver

# ناظر پایگاه داده
db_observer = DatabaseObserver(
    buffer_size=100,
    flush_interval=30
)

# ناظر هشدار
alert_observer = AlertObserver(
    alert_channels=['email', 'slack'],
    thresholds={
        'error_rate': 0.1,  # 10% خطا
        'response_time': 30.0  # 30 ثانیه
    }
)

# اضافه کردن ناظران جدید
event_system.add_observer(db_observer)
event_system.add_observer(alert_observer)

# ایجاد ناظر سفارشی
class CustomObserver:
    def update(self, event):
        if event.event_type == EventType.CRAWL_COMPLETED:
            # پردازش خاص برای تکمیل خزنده‌سازی
            self.process_crawl_completion(event)
    
    def process_crawl_completion(self, event):
        print(f"خزنده‌سازی {event.source} تکمیل شد")

# استفاده از context manager
from adapters.patterns.observer_pattern import event_context

with event_context() as events:
    events.add_observer(CustomObserver())
    
    # عملیات خزنده‌سازی
    events.emit_crawl_started("test_site", {})
    # ... انجام خزنده‌سازی ...
    events.emit_crawl_completed("test_site", {"results": 10})
```

### مزایا
- **انفصال**: اجزای سیستم مستقل از یکدیگر عمل می‌کنند
- **قابلیت توسعه**: اضافه کردن ناظر جدید آسان
- **مانیتورینگ**: امکان نظارت بر تمام رویدادهای سیستم

---

## Builder Pattern - الگوی سازنده

### مفهوم
الگوی Builder برای ایجاد پیکربندی‌های پیچیده به صورت گام به گام استفاده می‌شود.

### فایل‌های مرتبط
- `adapters/patterns/builder_pattern.py`

### استفاده اساسی

```python
from adapters.patterns.builder_pattern import (
    create_adapter_config,
    create_rate_limiting_config,
    ConfigurationDirector
)

# ایجاد پیکربندی ساده
config = (create_adapter_config()
    .with_basic_info(
        base_url="https://example.com",
        currency="IRR",
        adapter_type="persian",
        airline_name="نمونه ایرلاین"
    )
    .with_features(["search", "booking"])
    .build())

# ایجاد پیکربندی محدودیت نرخ
rate_config = (create_rate_limiting_config()
    .with_requests_per_second(2.0)
    .with_burst_limit(5)
    .for_persian_sites()
    .build())
```

### استفاده پیشرفته

```python
from adapters.patterns.builder_pattern import (
    AdapterConfigBuilder,
    RateLimitingConfigBuilder,
    ErrorHandlingConfigBuilder,
    MonitoringConfigBuilder
)

# ایجاد پیکربندی کامل
builder = AdapterConfigBuilder()

config = (builder
    .with_basic_info(
        base_url="https://alibaba.ir",
        currency="IRR", 
        adapter_type="persian",
        airline_name="علی‌بابا"
    )
    .configure_rate_limiting(lambda rl: rl
        .for_persian_sites()
        .with_domain_limit("alibaba.ir", 1.5)
        .with_adaptive_rate_limiting(True)
    )
    .configure_error_handling(lambda eh: eh
        .for_production()
        .with_circuit_breaker(failure_threshold=3)
        .with_timeout("page_load", 30)
    )
    .configure_monitoring(lambda m: m
        .for_production()
        .with_alert_threshold("error_rate", 0.05)
        .enable_performance_monitoring()
    )
    .build())

# استفاده از Director برای پیکربندی‌های از پیش تعریف شده
director = ConfigurationDirector()

mahan_config = director.build_mahan_air_config()
lufthansa_config = director.build_lufthansa_config()
```

### مزایا
- **خوانایی**: کد برای ایجاد پیکربندی خوانا و قابل فهم
- **انعطاف‌پذیری**: امکان ایجاد پیکربندی‌های مختلف
- **قابلیت استفاده مجدد**: امکان ذخیره و استفاده مجدد از پیکربندی‌ها

---

## Singleton Pattern - الگوی تک‌نمونه

### مفهوم
الگوی Singleton تضمین می‌کند که از یک کلاس تنها یک نمونه وجود داشته باشد و دسترسی سراسری به آن فراهم باشد.

### فایل‌های مرتبط
- `adapters/patterns/singleton_pattern.py`

### استفاده اساسی

```python
from adapters.patterns.singleton_pattern import (
    get_database_manager,
    get_configuration_manager,
    get_cache_manager,
    DatabaseConnectionInfo
)

# مدیر پایگاه داده
db_manager = get_database_manager()
db_manager.initialize(DatabaseConnectionInfo(
    database_path="crawler.db",
    timeout=30
))

# اجرای کوئری
results = db_manager.execute_query(
    "SELECT * FROM flights WHERE price < ?", 
    (1000000,)
)

# مدیر پیکربندی
config_manager = get_configuration_manager()
config_manager.initialize([
    "config/rate_limit_config.json",
    "config/site_configs/alibaba.json"
])

rate_limit = config_manager.get("rate_limiting.requests_per_second", 2.0)

# مدیر کَش
cache_manager = get_cache_manager()
cache_manager.initialize(default_ttl=3600, max_size=1000)

# ذخیره در کَش
cache_manager.set("search_results_THR_IST", results, ttl=1800)

# دریافت از کَش
cached_results = cache_manager.get("search_results_THR_IST")
```

### استفاده پیشرفته

```python
from adapters.patterns.singleton_pattern import (
    ResourcePool,
    managed_resources,
    get_logging_manager
)

# مدیر منابع
resource_pool = ResourcePool()

# ثبت منابع
resource_pool.register_resource("database", db_manager)
resource_pool.register_resource("cache", cache_manager)
resource_pool.register_resource("config", config_manager)

# مقداردهی تمام منابع
resource_pool.initialize_all()

# استفاده از context manager
with managed_resources("database", "cache") as pool:
    db = pool.get_resource("database")
    cache = pool.get_resource("cache")
    
    # عملیات با منابع
    data = db.execute_query("SELECT * FROM flights")
    cache.set("all_flights", data)

# مدیر لاگ
log_manager = get_logging_manager()
log_manager.initialize(log_level="INFO", log_file="crawler.log")

logger = log_manager.get_logger("my_module")
logger.info("شروع خزنده‌سازی")
```

### مزایا
- **کنترل منابع**: مدیریت بهینه منابع مشترک سیستم
- **دسترسی سراسری**: امکان دسترسی از هر جای برنامه
- **Thread-Safe**: پیاده‌سازی ایمن برای محیط چندنخی

---

## Command Pattern - الگوی فرمان

### مفهوم
الگوی Command عملیات را به صورت اشیاء کپسوله می‌کند و امکان صف‌بندی، لاگ‌گیری و بازگشت عملیات را فراهم می‌کند.

### فایل‌های مرتبط
- `adapters/patterns/command_pattern.py`

### استفاده اساسی

```python
from adapters.patterns.command_pattern import (
    CrawlSiteCommand,
    CommandInvoker,
    CommandPriority
)

# ایجاد دستور خزنده‌سازی
crawl_command = CrawlSiteCommand(
    site_url="https://alibaba.ir",
    adapter_name="alibaba",
    search_params={
        'origin': 'THR',
        'destination': 'IST',
        'date': '2024-06-15'
    },
    priority=CommandPriority.HIGH
)

# اجرای دستور
invoker = CommandInvoker(max_workers=4)
future = invoker.execute_command(crawl_command)

# دریافت نتیجه
result = future.result()
if result.success:
    print(f"خزنده‌سازی موفق: {len(result.data)} پرواز")
else:
    print(f"خطا: {result.error}")
```

### استفاده پیشرفته

```python
from adapters.patterns.command_pattern import (
    MacroCommand,
    ValidateDataCommand,
    SaveDataCommand,
    create_crawl_and_save_workflow,
    command_invoker_context
)

# ایجاد گردش کار پیچیده
site_configs = [
    {'url': 'https://alibaba.ir', 'adapter': 'alibaba', 'priority': CommandPriority.HIGH},
    {'url': 'https://flytoday.ir', 'adapter': 'flytoday', 'priority': CommandPriority.NORMAL}
]

validation_rules = {
    'required_fields': ['price', 'departure_time', 'airline'],
    'field_types': {'price': 'number'},
    'value_ranges': {'price': {'min': 100000, 'max': 10000000}}
}

workflow = create_crawl_and_save_workflow(
    site_configs=site_configs,
    search_params={'origin': 'THR', 'destination': 'IST'},
    validation_rules=validation_rules,
    table_name="flights"
)

# اجرای گردش کار
with command_invoker_context(max_workers=8) as invoker:
    # اجرای ناهمزمان
    future = invoker.execute_command(workflow)
    
    # صف‌بندی دستورات اضافی
    for priority_site in priority_sites:
        cmd = CrawlSiteCommand(
            site_url=priority_site['url'],
            adapter_name=priority_site['adapter'],
            search_params=search_params,
            priority=CommandPriority.CRITICAL
        )
        invoker.queue_command(cmd)
    
    # مانیتورینگ وضعیت
    stats = invoker.get_statistics()
    print(f"دستورات در حال اجرا: {stats['running_commands']}")
    print(f"دستورات در صف: {stats['queued_commands']}")
    
    # بازگشت آخرین دستور
    undo_result = invoker.undo_last_command()
    if undo_result:
        print("آخرین دستور لغو شد")

# ایجاد دستور سفارشی
class CustomCrawlCommand(Command):
    def __init__(self, custom_params):
        super().__init__("custom_crawl", "دستور خزنده‌سازی سفارشی")
        self.custom_params = custom_params
    
    def execute(self, **kwargs):
        # منطق خزنده‌سازی سفارشی
        return CommandResult(success=True, data="انجام شد")
    
    def can_undo(self):
        return True
    
    def undo(self):
        # منطق بازگشت
        return CommandResult(success=True, data="لغو شد")
```

### مزایا
- **انعطاف‌پذیری**: امکان ایجاد گردش‌کارهای پیچیده
- **مدیریت صف**: اجرای دستورات با اولویت‌بندی
- **قابلیت بازگشت**: امکان لغو عملیات انجام شده

---

## نحوه ترکیب الگوها

### ترکیب Factory + Strategy + Observer

```python
from adapters.factories.unified_adapter_factory import get_unified_factory
from adapters.strategies.parsing_strategies import ParsingStrategyFactory
from adapters.patterns.observer_pattern import CrawlerEventSystem, LoggingObserver

# تنظیم سیستم رویداد
event_system = CrawlerEventSystem()
event_system.add_observer(LoggingObserver())

# ایجاد آداپتر
factory = get_unified_factory()
adapter = factory.create_adapter("alibaba")

# تنظیم استراتژی تجزیه
strategy_factory = ParsingStrategyFactory()
parsing_strategy = strategy_factory.get_strategy_for_adapter("alibaba")

# خزنده‌سازی با رویدادگیری
event_system.emit_crawl_started("alibaba", search_params)

try:
    raw_results = adapter.search_flights(**search_params)
    parsed_results = parsing_strategy.parse(raw_results)
    
    event_system.emit_crawl_completed("alibaba", {
        'results_count': len(parsed_results),
        'duration': execution_time
    })
    
except Exception as e:
    event_system.emit_error("alibaba", e)
```

### ترکیب Command + Singleton + Builder

```python
from adapters.patterns.command_pattern import CrawlSiteCommand, CommandInvoker
from adapters.patterns.singleton_pattern import get_database_manager, get_cache_manager
from adapters.patterns.builder_pattern import create_adapter_config

# پیکربندی با Builder
config = (create_adapter_config()
    .for_persian_airline("https://alibaba.ir", "علی‌بابا")
    .configure_rate_limiting(lambda rl: rl.for_persian_sites())
    .build())

# استفاده از Singleton resources
db_manager = get_database_manager()
cache_manager = get_cache_manager()

# ایجاد دستور خزنده‌سازی
class EnhancedCrawlCommand(CrawlSiteCommand):
    def execute(self, **kwargs):
        # بررسی کَش
        cache_key = f"crawl_{self.adapter_name}_{hash(str(self.search_params))}"
        cached_result = cache_manager.get(cache_key)
        
        if cached_result:
            return CommandResult(success=True, data=cached_result)
        
        # اجرای خزنده‌سازی
        result = super().execute(**kwargs)
        
        # ذخیره در کَش و پایگاه داده
        if result.success:
            cache_manager.set(cache_key, result.data, ttl=1800)
            
            # ذخیره در پایگاه داده
            for flight in result.data:
                db_manager.execute_non_query(
                    "INSERT INTO flights (origin, destination, price, airline) VALUES (?, ?, ?, ?)",
                    (flight['origin'], flight['destination'], flight['price'], flight['airline'])
                )
        
        return result

# اجرای دستور
invoker = CommandInvoker()
command = EnhancedCrawlCommand("https://alibaba.ir", "alibaba", search_params)
future = invoker.execute_command(command)
```

---

## بهترین روش‌های استفاده

### 1. شروع تدریجی
- ابتدا از Factory Pattern برای مدیریت آداپترها شروع کنید
- سپس Observer Pattern برای مانیتورینگ اضافه کنید
- در نهایت Command Pattern برای گردش‌کارهای پیچیده

### 2. مدیریت خطا
```python
try:
    # استفاده از الگوها
    result = command.execute()
except Exception as e:
    # لاگ خطا با Observer
    event_system.emit_error("system", e)
    
    # تلاش مجدد با Command
    if command.can_retry():
        retry_result = invoker.execute_command(command)
```

### 3. تست‌نویسی
```python
# تست Factory Pattern
def test_adapter_creation():
    factory = get_unified_factory()
    adapter = factory.create_adapter("test_adapter")
    assert adapter is not None

# تست Command Pattern
def test_command_execution():
    command = MockCrawlCommand()
    result = command.execute()
    assert result.success

# تست Observer Pattern
def test_event_notification():
    observer = MockObserver()
    event_system = CrawlerEventSystem()
    event_system.add_observer(observer)
    
    event_system.emit_test_event()
    assert observer.received_events > 0
```

### 4. Performance Optimization

```python
# استفاده بهینه از کَش
def optimized_crawling():
    cache = get_cache_manager()
    
    # کَش نتایج جستجو
    cache_key = generate_cache_key(search_params)
    results = cache.get(cache_key)
    
    if not results:
        results = perform_crawling()
        cache.set(cache_key, results, ttl=1800)
    
    return results

# مدیریت منابع
def resource_efficient_crawling():
    with managed_resources("database", "cache") as pool:
        # استفاده از منابع
        db = pool.get_resource("database")
        cache = pool.get_resource("cache")
        
        # عملیات خزنده‌سازی...
        pass
    # منابع به صورت خودکار آزاد می‌شوند
```

### 5. مانیتورینگ و دیباگ

```python
# تنظیم مانیتورینگ کامل
def setup_monitoring():
    event_system = CrawlerEventSystem()
    
    # اضافه کردن ناظران مختلف
    event_system.add_observer(LoggingObserver())
    event_system.add_observer(MetricsObserver())
    event_system.add_observer(DatabaseObserver())
    
    # تنظیم هشدارها
    alert_observer = AlertObserver(
        thresholds={
            'error_rate': 0.1,
            'response_time': 30.0
        }
    )
    event_system.add_observer(alert_observer)
    
    return event_system

# دیباگ گردش‌کار
def debug_workflow():
    invoker = CommandInvoker(enable_history=True)
    
    # اجرای دستورات
    for command in commands:
        future = invoker.execute_command(command)
        result = future.result()
        
        print(f"دستور {command.name}: {'موفق' if result.success else 'ناموفق'}")
    
    # مشاهده آمار
    stats = invoker.get_statistics()
    print(f"نرخ موفقیت: {stats['success_rate']:.2f}%")
    
    # تاریخچه دستورات
    history = invoker.get_command_history()
    for cmd in history[-10:]:  # آخرین 10 دستور
        print(f"{cmd.name}: {cmd.context.status.value}")
```

---

## خلاصه

استفاده از این الگوهای طراحی باعث بهبود قابل توجه کیفیت کد، قابلیت نگهداری و انعطاف‌پذیری سیستم FlightioCrawler می‌شود. هر الگو برای حل مشکلات خاصی طراحی شده و ترکیب آن‌ها امکان ایجاد سیستمی قدرتمند و قابل اعتماد را فراهم می‌کند.

برای شروع، پیشنهاد می‌شود ابتدا از Factory Pattern استفاده کرده و سپس تدریجاً سایر الگوها را به سیستم اضافه کنید. همیشه اصول SOLID را رعایت کرده و تست‌های مناسب برای هر بخش بنویسید.

### منابع اضافی
- [Factory Pattern Implementation](../adapters/factories/unified_adapter_factory.py)
- [Observer Pattern Implementation](../adapters/patterns/observer_pattern.py)
- [Command Pattern Implementation](../adapters/patterns/command_pattern.py)
- [Builder Pattern Implementation](../adapters/patterns/builder_pattern.py)
- [Singleton Pattern Implementation](../adapters/patterns/singleton_pattern.py)