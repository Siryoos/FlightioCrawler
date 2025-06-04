# FlightioCrawler Technical Specification | مشخصات فنی خزنده پروازهای ایران

## Implementation Details | جزئیات پیاده‌سازی

### 1. Core Classes | کلاس‌های اصلی

#### IranianFlightCrawler
```python
class IranianFlightCrawler:
    def __init__(self):
        self.monitor = CrawlerMonitor()
        self.error_handler = ErrorHandler()
        self.data_manager = DataManager()
        self.rate_limiter = RateLimiter()
        self.text_processor = PersianTextProcessor()
        
        # Advanced features
        self.intelligent_search = IntelligentSearchEngine()
        self.price_monitor = PriceMonitor()
        self.ml_predictor = FlightPricePredictor()
        self.multilingual = MultilingualProcessor()
```

#### Base Crawler Interface
```python
class BaseCrawler(ABC):
    @abstractmethod
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        pass
    
    @abstractmethod
    async def parse_flight_data(self, html: str) -> List[Dict]:
        pass
    
    @abstractmethod
    async def handle_errors(self, error: Exception) -> None:
        pass
```

### 2. Data Models | مدل‌های داده

#### Flight Data Model
```python
@dataclass
class FlightData:
    flight_id: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    price: float
    currency: str
    seat_class: str
    aircraft_type: Optional[str]
    duration_minutes: int
    flight_type: str
    scraped_at: datetime
    source_url: str
```

### 3. API Endpoints | نقاط پایانی API

#### Search API
```python
@router.get("/api/v1/search")
async def search_flights(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None,
    passengers: int = 1,
    seat_class: str = "economy"
) -> List[FlightData]:
    pass
```

#### Health API
```python
@router.get("/api/v1/health")
async def health_check() -> Dict[str, Any]:
    pass
```

### 4. Database Schema | طرح پایگاه داده

#### Flights Table
```sql
CREATE TABLE flights (
    id BIGSERIAL PRIMARY KEY,
    flight_id VARCHAR(100) UNIQUE,
    airline VARCHAR(100),
    flight_number VARCHAR(20),
    origin VARCHAR(10),
    destination VARCHAR(10),
    departure_time TIMESTAMPTZ,
    arrival_time TIMESTAMPTZ,
    price DECIMAL(12,2),
    currency VARCHAR(3),
    seat_class VARCHAR(50),
    aircraft_type VARCHAR(50),
    duration_minutes INTEGER,
    flight_type VARCHAR(20),
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    source_url TEXT
);

-- Indexes
CREATE INDEX idx_flights_route_date ON flights (origin, destination, departure_time);
CREATE INDEX idx_flights_scraped ON flights (scraped_at);
```

### 5. Caching Strategy | استراتژی کش

#### Redis Cache Structure
```python
# Cache keys
FLIGHT_CACHE_KEY = "flight:{flight_id}"
SEARCH_CACHE_KEY = "search:{origin}:{destination}:{date}"
RATE_LIMIT_KEY = "ratelimit:{ip}:{endpoint}"

# Cache TTLs
FLIGHT_CACHE_TTL = 3600  # 1 hour
SEARCH_CACHE_TTL = 1800  # 30 minutes
RATE_LIMIT_TTL = 60      # 1 minute
```

### 6. Error Handling | مدیریت خطا

#### Circuit Breaker Implementation
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    async def execute(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if self._should_reset():
                self._reset()
            else:
                raise CircuitBreakerOpenError()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
```

### 7. Rate Limiting | محدودیت نرخ

#### Rate Limiter Implementation
```python
class RateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.default_rate = 10  # requests per second

    async def check_rate_limit(self, key: str, rate: int = None) -> bool:
        current = await self.redis.get(key)
        if current and int(current) >= (rate or self.default_rate):
            return False
        await self.redis.incr(key)
        await self.redis.expire(key, 1)
        return True
```

### 8. Monitoring | نظارت

#### Metrics Collection
```python
class CrawlerMonitor:
    def __init__(self):
        self.metrics = {
            'requests_total': Counter('crawler_requests_total', 'Total requests made'),
            'errors_total': Counter('crawler_errors_total', 'Total errors encountered'),
            'response_time': Histogram('crawler_response_time', 'Response time in seconds'),
            'flights_scraped': Counter('crawler_flights_scraped', 'Total flights scraped')
        }

    async def record_request(self, site: str, duration: float):
        self.metrics['requests_total'].labels(site=site).inc()
        self.metrics['response_time'].labels(site=site).observe(duration)
```

### 9. Machine Learning Integration | یکپارچه‌سازی یادگیری ماشین

#### Price Predictor
```python
class FlightPricePredictor:
    def __init__(self, model_path: str):
        self.model = joblib.load(model_path)
        self.scaler = StandardScaler()

    def predict_price(self, features: Dict) -> float:
        scaled_features = self.scaler.transform([self._prepare_features(features)])
        return self.model.predict(scaled_features)[0]

    def _prepare_features(self, features: Dict) -> List[float]:
        return [
            features['duration_minutes'],
            features['days_until_departure'],
            features['is_weekend'],
            features['season']
        ]
```

### 10. Testing Strategy | استراتژی تست

#### Unit Tests
```python
class TestFlightCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = IranianFlightCrawler()
        self.mock_search_params = {
            'origin': 'THR',
            'destination': 'MHD',
            'departure_date': '2024-03-01'
        }

    async def test_search_flights(self):
        results = await self.crawler.search_flights(self.mock_search_params)
        self.assertIsInstance(results, list)
        self.assertTrue(all(isinstance(f, FlightData) for f in results))
```

### 11. Deployment Configuration | پیکربندی استقرار

#### Docker Configuration
```dockerfile
FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main_crawler.py"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  crawler:
    build: .
    depends_on:
      - postgres
      - redis
    environment:
      - DB_HOST=postgres
      - REDIS_HOST=redis
    volumes:
      - ./data:/app/data

  postgres:
    image: postgres:12
    environment:
      - POSTGRES_DB=flight_data
      - POSTGRES_USER=crawler
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 12. Performance Optimization | بهینه‌سازی عملکرد

#### Connection Pooling
```python
class DatabasePool:
    def __init__(self, min_connections: int = 5, max_connections: int = 20):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            min_connections,
            max_connections,
            **config.DATABASE.__dict__
        )

    async def get_connection(self):
        return self.pool.getconn()

    async def release_connection(self, conn):
        self.pool.putconn(conn)
```

### 13. Security Implementation | پیاده‌سازی امنیت

#### Authentication Middleware
```python
class AuthMiddleware:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def __call__(self, request: Request, call_next):
        token = request.headers.get('Authorization')
        if not token:
            raise HTTPException(status_code=401)
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            request.state.user = payload
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401)
        
        return await call_next(request)
```

### 14. Logging Configuration | پیکربندی ثبت رویدادها

#### Logging Setup
```python
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('flight_crawler.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Add JSON logging for structured logging
    json_handler = logging.FileHandler('flight_crawler.json')
    json_handler.setFormatter(JsonFormatter())
    logging.getLogger().addHandler(json_handler)
``` 