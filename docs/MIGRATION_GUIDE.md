# راهنمای مهاجرت به ساختار جدید آداپترها

این راهنما نحوه مهاجرت از آداپترهای قدیمی به ساختار جدید بهبود‌یافته را توضیح می‌دهد.

## خلاصه تغییرات

### کلاس‌های پایه جدید
- `EnhancedBaseCrawler`: کلاس پایه اصلی با قابلیت‌های مشترک
- `EnhancedInternationalAdapter`: کلاس پایه برای ایرلاین‌های بین‌المللی
- `EnhancedPersianAdapter`: کلاس پایه برای ایرلاین‌های فارسی
- `CommonErrorHandler`: مدیریت خطای مشترک
- `AdapterUtils`: ابزارهای کمکی مشترک

### مزایای ساختار جدید
- ✅ حذف 80% کدهای تکراری
- ✅ مدیریت خطای یکپارچه
- ✅ پردازش متن فارسی خودکار
- ✅ اعتبارسنجی داده‌های استاندارد
- ✅ Factory Pattern بهبود‌یافته
- ✅ تست‌پذیری بهتر

## مهاجرت گام‌به‌گام

### گام ۱: تغییر کلاس پایه

#### قبل (آداپتر قدیمی):
```python
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from utils.persian_text_processor import PersianTextProcessor
from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring

class MahanAirAdapter(EnhancedPersianAdapter):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.mahan.aero"
        self.search_url = config["search_url"]
        self.persian_processor = PersianTextProcessor()
        self.rate_limiter = RateLimiter(...)
        self.error_handler = ErrorHandler(...)
        self.monitoring = Monitoring(...)
        self.logger = logging.getLogger(__name__)
```

#### بعد (آداپتر جدید):
```python
from adapters.base_adapters import EnhancedPersianAdapter, AdapterUtils
from adapters.base_adapters.common_error_handler import error_handler, safe_extract

class MahanAirAdapter(EnhancedPersianAdapter):
    # همه‌ی initialization خودکار انجام می‌شود!
    
    def _get_adapter_name(self) -> str:
        return "MahanAir"
    
    def _get_base_url(self) -> str:
        return "https://www.mahan.aero"
```

### گام ۲: حذف کدهای تکراری

#### قبل:
```python
async def _fill_search_form(self, search_params: Dict):
    try:
        await self.page.fill(
            self.config["extraction_config"]["search_form"]["origin_field"],
            self.persian_processor.process_text(search_params["origin"])
        )
        await self.page.fill(
            self.config["extraction_config"]["search_form"]["destination_field"],
            self.persian_processor.process_text(search_params["destination"])
        )
        # ... کدهای تکراری زیاد
    except Exception as e:
        self.logger.error(f"Error filling search form: {str(e)}")
        raise
```

#### بعد:
```python
async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
    # استفاده از پیاده‌سازی والدین برای قسمت‌های استاندارد
    await super()._fill_search_form(search_params)
    
    # فقط قسمت‌های خاص ماهان ایر
    await self._handle_mahan_air_specific_fields(search_params)

@error_handler("mahan_air_specific_form_handling")
async def _handle_mahan_air_specific_fields(self, search_params: Dict[str, Any]) -> None:
    # فقط فیلدهای خاص ماهان ایر
    if search_params.get("loyalty_member"):
        await self.page.check(".loyalty-member-checkbox")
```

### گام ۳: استفاده از ابزارهای مشترک

#### قبل:
```python
def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
    try:
        # کدهای طولانی برای استخراج داده‌ها
        price_text = element.select_one(".price").get_text()
        # پردازش دستی قیمت فارسی
        price = float(re.sub(r'[^\d]', '', price_text))
        
        time_text = element.select_one(".time").get_text()
        # پردازش دستی زمان
        # ...
    except Exception as e:
        self.logger.error(f"Error parsing: {e}")
        return None
```

#### بعد:
```python
def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
    # استفاده از parser والدین برای قسمت‌های استاندارد
    flight_data = super()._parse_flight_element(element)
    
    if not flight_data:
        return None
    
    # اضافه کردن فیلدهای خاص ماهان ایر
    config = self.config.get("extraction_config", {}).get("results_parsing", {})
    mahan_specific = self._extract_mahan_air_specific_fields(element, config)
    
    # ادغام با استفاده از utility
    return AdapterUtils.merge_flight_data(flight_data, mahan_specific)

@safe_extract(default_value={})
def _extract_mahan_air_specific_fields(self, element, config: Dict[str, Any]) -> Dict[str, Any]:
    # استخراج فیلدهای خاص با error handling خودکار
    mahan_specific = {}
    
    loyalty_points = self._extract_text(element, config.get("mahan_miles"))
    if loyalty_points:
        points_value = AdapterUtils.extract_numeric_value(
            self.persian_processor.process_text(loyalty_points)
        )
        mahan_specific["mahan_miles"] = int(points_value) if points_value > 0 else 0
    
    return mahan_specific
```

### گام ۴: استفاده از Factory جدید

#### قبل:
```python
# در کد اصلی
from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter

config = load_config("mahan_air")
adapter = MahanAirAdapter(config)
```

#### بعد:
```python
# در کد اصلی
from adapters.factories.adapter_factory import create_adapter

# ساده و تمیز!
adapter = create_adapter("mahan_air")

# یا با config سفارشی
adapter = create_adapter("mahan_air", {"custom": "value"})
```

## الگوهای مهاجرت برای انواع مختلف آداپتر

### آداپتر ایرلاین بین‌المللی

```python
from adapters.base_adapters import EnhancedInternationalAdapter

class LufthansaAdapter(EnhancedInternationalAdapter):
    def _get_adapter_name(self) -> str:
        return "Lufthansa"
    
    def _get_base_url(self) -> str:
        return "https://www.lufthansa.com"
    
    # فقط منطق خاص لوفت‌هانزا
    @error_handler("lufthansa_specific_handling")
    async def _handle_miles_and_more(self, search_params: Dict[str, Any]) -> None:
        if search_params.get("miles_and_more_number"):
            await self.page.fill("#miles-number", search_params["miles_and_more_number"])
```

### آداپتر تجمیع‌کننده (Aggregator)

```python
from adapters.base_adapters import EnhancedPersianAdapter

class AlibabaAdapter(EnhancedPersianAdapter):
    def _get_adapter_name(self) -> str:
        return "Alibaba"
    
    def _get_base_url(self) -> str:
        return "https://www.alibaba.ir"
    
    def _get_adapter_specific_config(self) -> Dict[str, Any]:
        return {
            "is_aggregator": True,
            "supports_multiple_airlines": True,
            "supports_comparison": True
        }
    
    # منطق خاص تجمیع‌کننده
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        flight_data = super()._parse_flight_element(element)
        
        if flight_data:
            # اضافه کردن اطلاعات تجمیع‌کننده
            flight_data["booking_source"] = "alibaba"
            flight_data["is_aggregated"] = True
        
        return flight_data
```

## چک‌لیست مهاجرت

### مرحله آماده‌سازی
- [ ] بررسی آداپتر فعلی و شناسایی کدهای تکراری
- [ ] تعیین نوع آداپتر (international/persian/aggregator)
- [ ] بررسی فیلدهای خاص آداپتر

### مرحله پیاده‌سازی
- [ ] تغییر کلاس پایه به Enhanced classes
- [ ] حذف initialization های تکراری
- [ ] جایگزینی error handling با decorators جدید
- [ ] استفاده از AdapterUtils برای عملیات مشترک
- [ ] اضافه کردن متدهای `_get_*` مورد نیاز

### مرحله تست
- [ ] تست عملکرد crawling اصلی
- [ ] تست error handling
- [ ] تست فیلدهای خاص آداپتر
- [ ] تست با Factory جدید
- [ ] مقایسه نتایج با آداپتر قدیمی

### مرحله نهایی‌سازی
- [ ] به‌روزرسانی configuration files
- [ ] به‌روزرسانی تست‌ها
- [ ] به‌روزرسانی مستندات
- [ ] حذف آداپتر قدیمی

## نکات مهم

### مدیریت خطا
```python
# استفاده از decorator برای error handling خودکار
@error_handler("operation_name")
async def my_method(self, params):
    # کد شما - خطاها خودکار مدیریت می‌شوند
    pass

# استفاده از safe_extract برای استخراج ایمن
@safe_extract(default_value="")
def extract_field(self, element):
    return element.select_one(".field").get_text()
```

### استفاده از Utils
```python
# استاندارد کردن کدهای فرودگاه
airport_code = AdapterUtils.normalize_airport_code("THR-Tehran")  # -> "THR"

# استخراج قیمت از متن
price = AdapterUtils.extract_numeric_value("۱۲,۰۰۰ تومان")  # -> 12000.0

# استاندارد کردن زمان
time = AdapterUtils.standardize_time_format("۱۴:۳۰")  # -> "14:30"

# ایجاد ID یکتا برای پرواز
flight_id = AdapterUtils.create_flight_id(flight_data)
```

### Configuration Management
```python
# بارگذاری config از factory
from adapters.factories.adapter_factory import get_factory

factory = get_factory()
config = factory.config_manager.load_config("adapter_name")

# ذخیره config جدید
factory.save_adapter_config("adapter_name", updated_config)
```

## مثال کامل: مهاجرت آداپتر ماهان ایر

### قبل (170 خط کد):
```python
class MahanAirAdapter(EnhancedPersianAdapter):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.mahan.aero"
        self.search_url = config["search_url"]
        self.persian_processor = PersianTextProcessor()
        self.rate_limiter = RateLimiter(...)
        self.error_handler = ErrorHandler(...)
        self.monitoring = Monitoring(...)
        self.logger = logging.getLogger(__name__)

    async def crawl(self, search_params: Dict) -> List[Dict]:
        try:
            self._validate_search_params(search_params)
            await self._navigate_to_search_page()
            await self._fill_search_form(search_params)
            results = await self._extract_flight_results()
            validated_results = self._validate_flight_data(results)
            self.monitoring.record_success()
            return validated_results
        except Exception as e:
            self.logger.error(f"Error crawling Mahan Air: {str(e)}")
            self.monitoring.record_error()
            raise

    # ... 140+ خط کد تکراری دیگر
```

### بعد (50 خط کد):
```python
class MahanAirAdapter(EnhancedPersianAdapter):
    def _get_adapter_name(self) -> str:
        return "MahanAir"
    
    def _get_base_url(self) -> str:
        return "https://www.mahan.aero"
    
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        await super()._fill_search_form(search_params)
        await self._handle_mahan_air_specific_fields(search_params)
    
    @error_handler("mahan_air_specific_form_handling")
    async def _handle_mahan_air_specific_fields(self, search_params: Dict[str, Any]) -> None:
        if search_params.get("loyalty_member"):
            await self.page.check(".loyalty-member-checkbox")
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        flight_data = super()._parse_flight_element(element)
        if not flight_data:
            return None
        
        config = self.config.get("extraction_config", {}).get("results_parsing", {})
        mahan_specific = self._extract_mahan_air_specific_fields(element, config)
        
        flight_data.update(mahan_specific)
        flight_data["airline_code"] = "W5"
        flight_data["source_adapter"] = "MahanAir"
        
        return flight_data
    
    @safe_extract(default_value={})
    def _extract_mahan_air_specific_fields(self, element, config: Dict[str, Any]) -> Dict[str, Any]:
        mahan_specific = {}
        
        loyalty_points = self._extract_text(element, config.get("mahan_miles"))
        if loyalty_points:
            points_value = AdapterUtils.extract_numeric_value(
                self.persian_processor.process_text(loyalty_points)
            )
            mahan_specific["mahan_miles"] = int(points_value) if points_value > 0 else 0
        
        return mahan_specific
```

## نتیجه

با مهاجرت به ساختار جدید:
- **70% کاهش کد**: از 170 خط به 50 خط
- **خوانایی بهتر**: تمرکز بر منطق خاص آداپتر
- **نگهداری آسان‌تر**: تغییرات مشترک در یک جا
- **تست‌پذیری بالاتر**: جداسازی مسئولیت‌ها
- **Error Handling یکپارچه**: مدیریت خطای استاندارد

این ساختار جدید توسعه آداپترهای جدید را بسیار سریع‌تر و قابل اعتمادتر می‌کند. 