# FlightioCrawler

سیستم جامع کرال و مقایسه قیمت پرواز با ساختار بهبود‌یافته و حذف کدهای تکراری.

## 🚀 ویژگی‌های جدید (نسخه 2.0)

### ساختار بهبود‌یافته
- **حذف 80% کدهای تکراری** با کلاس‌های پایه هوشمند
- **مدیریت خطای یکپارچه** با error handling خودکار
- **Factory Pattern پیشرفته** برای ایجاد آداپترها
- **پردازش متن فارسی خودکار** برای سایت‌های ایرانی
- **ابزارهای کمکی مشترک** برای عملیات رایج

### کلاس‌های پایه جدید
- `EnhancedBaseCrawler`: کلاس پایه اصلی با قابلیت‌های مشترک
- `EnhancedInternationalAdapter`: برای ایرلاین‌های بین‌المللی
- `EnhancedPersianAdapter`: برای ایرلاین‌های فارسی با پردازش متن

## 📋 فهرست مطالب

- [نصب و راه‌اندازی](#نصب-و-راه‌اندازی)
- [استفاده سریع](#استفاده-سریع)
- [ساختار پروژه](#ساختار-پروژه)
- [توسعه آداپتر جدید](#توسعه-آداپتر-جدید)
- [مهاجرت از نسخه قدیمی](#مهاجرت-از-نسخه-قدیمی)
- [API Reference](#api-reference)

## 🛠 نصب و راه‌اندازی

### پیش‌نیازها
```bash
# Python 3.8+
pip install -r requirements.txt

# Playwright browsers
playwright install
```

### نصب سریع
```bash
git clone https://github.com/yourusername/FlightioCrawler.git
cd FlightioCrawler
pip install -r requirements.txt
playwright install
```

## 🚀 استفاده سریع

### ایجاد آداپتر با Factory
```python
from adapters.factories.adapter_factory import create_adapter

# ایجاد آداپتر ماهان ایر
mahan_adapter = create_adapter("mahan_air")

# جستجوی پرواز
results = await mahan_adapter.crawl({
    "origin": "THR",
    "destination": "MHD", 
    "departure_date": "2024-01-15",
    "passengers": 1,
    "seat_class": "economy"
})

print(f"یافت شد: {len(results)} پرواز")
```

### مقایسه قیمت چندین ایرلاین
```python
from adapters.factories.adapter_factory import create_adapter

# لیست ایرلاین‌های مورد نظر
airlines = ["mahan_air", "iran_air", "aseman_airlines"]

all_results = []
for airline in airlines:
    adapter = create_adapter(airline)
    results = await adapter.crawl(search_params)
    all_results.extend(results)

# مرتب‌سازی بر اساس قیمت
sorted_flights = sorted(all_results, key=lambda x: x['price'])
print(f"ارزان‌ترین پرواز: {sorted_flights[0]['price']} ریال")
```

### استفاده از آداپترهای بین‌المللی
```python
# ایجاد آداپتر Emirates
emirates = create_adapter("emirates")

# جستجوی پرواز بین‌المللی
international_results = await emirates.crawl({
    "origin": "DXB",
    "destination": "LHR",
    "departure_date": "2024-02-20",
    "passengers": 2,
    "seat_class": "business"
})
```

## 🏗 ساختار پروژه

```
FlightioCrawler/
├── adapters/
│   ├── base_adapters/           # کلاس‌های پایه جدید
│   │   ├── __init__.py         # Utils و helpers مشترک
│   │   ├── enhanced_base_crawler.py
│   │   ├── enhanced_international_adapter.py
│   │   ├── enhanced_persian_adapter.py
│   │   └── common_error_handler.py
│   ├── factories/
│   │   └── adapter_factory.py   # Factory pattern بهبود‌یافته
│   └── site_adapters/
│       ├── iranian_airlines/    # آداپترهای ایرلاین‌های ایرانی
│       ├── international_airlines/  # آداپترهای بین‌المللی
│       └── iranian_aggregators/ # آداپترهای تجمیع‌کننده
├── config/
│   └── site_configs/           # تنظیمات هر سایت
├── docs/
│   ├── MIGRATION_GUIDE.md      # راهنمای مهاجرت
│   └── API_REFERENCE.md        # مرجع API
└── tests/                      # تست‌های جامع
```

## 🔧 توسعه آداپتر جدید

### آداپتر ایرلاین ایرانی
```python
from adapters.base_adapters import EnhancedPersianAdapter
from adapters.base_adapters.common_error_handler import error_handler, safe_extract

class MyIranianAirlineAdapter(EnhancedPersianAdapter):
    def _get_adapter_name(self) -> str:
        return "MyAirline"
    
    def _get_base_url(self) -> str:
        return "https://www.myairline.ir"
    
    # فقط منطق خاص این ایرلاین
    @error_handler("specific_form_handling")
    async def _handle_specific_fields(self, search_params):
        # منطق خاص فرم
        pass
    
    @safe_extract(default_value={})
    def _extract_specific_fields(self, element, config):
        # استخراج فیلدهای خاص
        return {}
```

### آداپتر ایرلاین بین‌المللی
```python
from adapters.base_adapters import EnhancedInternationalAdapter

class MyInternationalAirlineAdapter(EnhancedInternationalAdapter):
    def _get_adapter_name(self) -> str:
        return "MyInternationalAirline"
    
    def _get_base_url(self) -> str:
        return "https://www.myairline.com"
    
    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "passengers"]
```

### ثبت آداپتر در Factory
```python
from adapters.factories.adapter_factory import get_factory

factory = get_factory()
factory.registry.register(
    "my_airline", 
    MyAirlineAdapter,
    config=my_config,
    metadata={
        "type": "persian",
        "airline_name": "My Airline",
        "description": "توضیحات ایرلاین",
        "features": ["domestic_routes", "charter_flights"]
    }
)
```

## 📊 آداپترهای پشتیبانی‌شده

### ایرلاین‌های ایرانی
- ✅ **ماهان ایر** (W5) - `mahan_air`
- ✅ **ایران ایر** (IR) - `iran_air`  
- ✅ **آسمان** (EP) - `aseman_airlines`
- ✅ **کاسپین** (RV) - `caspian_airlines`
- ✅ **قشم ایر** (QB) - `qeshm_air`
- ✅ **کارون ایر** (KAR) - `karun_air`
- ✅ **سپهران** (SPN) - `sepehran_air`

### ایرلاین‌های بین‌المللی
- ✅ **لوفت‌هانزا** (LH) - `lufthansa`
- ✅ **ایر فرانس** (AF) - `air_france`
- ✅ **بریتیش ایرویز** (BA) - `british_airways`
- ✅ **امارات** (EK) - `emirates`
- ✅ **ترکیش ایرلاینز** (TK) - `turkish_airlines`
- ✅ **قطر ایرویز** (QR) - `qatar_airways`
- ✅ **اتحاد** (EY) - `etihad_airways`
- ✅ **KLM** (KL) - `klm`
- ✅ **پگاسوس** (PC) - `pegasus`

### تجمیع‌کننده‌ها
- ✅ **علی‌بابا** - `alibaba`
- ✅ **فلایت آی او** - `flightio`
- ✅ **فلای تودی** - `flytoday`
- ✅ **سفرمارکت** - `safarmarket`
- ✅ **MZ724** - `mz724`
- ✅ **پارتو تیکت** - `parto_ticket`
- ✅ **بوک چارتر** - `book_charter`

## 🔄 مهاجرت از نسخه قدیمی

برای مهاجرت آداپترهای موجود به ساختار جدید، [راهنمای مهاجرت](docs/MIGRATION_GUIDE.md) را مطالعه کنید.

### خلاصه مزایای مهاجرت:
- **70% کاهش کد**: از 170 خط به 50 خط
- **خوانایی بهتر**: تمرکز بر منطق خاص
- **نگهداری آسان‌تر**: تغییرات مشترک در یک جا
- **تست‌پذیری بالاتر**: جداسازی مسئولیت‌ها

## 🛠 ابزارهای کمکی

### AdapterUtils
```python
from adapters.base_adapters import AdapterUtils

# استاندارد کردن کد فرودگاه
code = AdapterUtils.normalize_airport_code("THR-Tehran")  # -> "THR"

# استخراج قیمت از متن فارسی
price = AdapterUtils.extract_numeric_value("۱۲,۰۰۰ تومان")  # -> 12000.0

# استاندارد کردن زمان
time = AdapterUtils.standardize_time_format("۱۴:۳۰")  # -> "14:30"

# ایجاد ID یکتا
flight_id = AdapterUtils.create_flight_id(flight_data)
```

### مدیریت خطا
```python
from adapters.base_adapters.common_error_handler import error_handler, safe_extract

@error_handler("operation_name")
async def my_operation(self):
    # خطاها خودکار مدیریت می‌شوند
    pass

@safe_extract(default_value="")
def extract_data(self, element):
    # استخراج ایمن داده‌ها
    return element.get_text()
```

## 📈 نظارت و گزارش‌گیری

### آمار عملکرد
```python
from adapters.factories.adapter_factory import get_factory

factory = get_factory()
adapter = factory.create_adapter("mahan_air")

# دریافت آمار خطاها
error_stats = adapter.error_handler.get_error_statistics()
print(f"تعداد کل خطاها: {error_stats['total_errors']}")
```

### لیست آداپترها
```python
from adapters.factories.adapter_factory import list_adapters, search_adapters

# لیست همه آداپترها
all_adapters = list_adapters()

# جستجو در آداپترها
iranian_adapters = search_adapters("iranian")
charter_adapters = search_adapters("charter")
```

## 🧪 تست

### اجرای تست‌ها
```bash
# تست همه آداپترها
python -m pytest tests/

# تست آداپتر خاص
python -m pytest tests/platform_tests/test_mahan_air_adapter.py

# تست با coverage
python -m pytest --cov=adapters tests/
```

### تست آداپتر جدید
```python
import pytest
from adapters.factories.adapter_factory import create_adapter

@pytest.mark.asyncio
async def test_my_adapter():
    adapter = create_adapter("my_adapter")
    
    search_params = {
        "origin": "THR",
        "destination": "MHD",
        "departure_date": "2024-01-15",
        "passengers": 1,
        "seat_class": "economy"
    }
    
    results = await adapter.crawl(search_params)
    
    assert len(results) > 0
    assert all("price" in flight for flight in results)
```

## 🔧 تنظیمات

### Configuration Files
هر آداپتر configuration file مخصوص خود در `config/site_configs/` دارد:

```json
{
  "rate_limiting": {
    "requests_per_second": 2,
    "burst_limit": 5,
    "cooldown_period": 60
  },
  "extraction_config": {
    "search_form": {
      "origin_field": "#origin",
      "destination_field": "#destination",
      "date_field": "#departure_date"
    },
    "results_parsing": {
      "container": ".flight-result",
      "airline": ".airline-name",
      "price": ".price-value"
    }
  }
}
```

### Environment Variables
```bash
# تنظیمات اصلی
PLAYWRIGHT_HEADLESS=true
LOG_LEVEL=INFO
DATABASE_URL=postgresql://...

# تنظیمات rate limiting
DEFAULT_RATE_LIMIT=2
BURST_LIMIT=5

# تنظیمات monitoring
ENABLE_MONITORING=true
GRAFANA_URL=http://localhost:3000
```

## 📚 API Reference

### Factory Functions
```python
# ایجاد آداپتر
create_adapter(name: str, config: Optional[Dict] = None) -> EnhancedBaseCrawler

# لیست آداپترها
list_adapters() -> List[str]

# جستجو در آداپترها  
search_adapters(query: str) -> List[str]

# اطلاعات آداپتر
get_adapter_info(name: str) -> Dict[str, Any]
```

### Base Adapter Methods
```python
# متدهای اصلی
async def crawl(search_params: Dict[str, Any]) -> List[Dict[str, Any]]
async def _fill_search_form(search_params: Dict[str, Any]) -> None
async def _extract_flight_results() -> List[Dict[str, Any]]

# متدهای قابل override
def _get_adapter_name() -> str
def _get_base_url() -> str
def _get_required_search_fields() -> List[str]
```

## 🤝 مشارکت

### توسعه آداپتر جدید
1. کلاس آداپتر را با استفاده از کلاس‌های پایه ایجاد کنید
2. Configuration file مربوطه را اضافه کنید  
3. تست‌های مناسب بنویسید
4. Pull Request ایجاد کنید

### گزارش مشکل
- Issues را در GitHub ایجاد کنید
- لاگ‌ها و جزئیات خطا را ضمیمه کنید
- مراحل بازتولید مشکل را شرح دهید

## 📄 مجوز

این پروژه تحت مجوز MIT منتشر شده است. فایل [LICENSE](LICENSE) را برای جزئیات بیشتر مطالعه کنید.

## 🔗 لینک‌های مفید

- [راهنمای مهاجرت](docs/MIGRATION_GUIDE.md)
- [مرجع API](docs/API_REFERENCE.md)
- [راهنمای امنیت](docs/SECURITY_GUIDE.md)
- [راهنمای دپلوی](docs/DEPLOYMENT_CHECKLIST.md)

---

**FlightioCrawler v2.0** - سیستم کرال پرواز با ساختار بهبود‌یافته و حذف کدهای تکراری 
