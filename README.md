# Iranian Flight Crawler (خزنده پروازهای ایران)

A sophisticated web crawler system for Iranian flight booking websites with intelligent search capabilities, price monitoring, and multilingual support.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [User Guide](#user-guide)
- [Developer Guide](#developer-guide)
- [Production Setup](#production-setup)
- [Adding New Websites](#adding-new-websites)
- [Chain-of-Thought Design](#chain-of-thought-design)

## Overview | مرور کلی

This project is a comprehensive flight crawler system designed to aggregate flight information from various Iranian travel websites. It includes advanced features like intelligent search, price monitoring, and multilingual support.

این پروژه یک سیستم خزنده جامع برای جمع‌آوری اطلاعات پرواز از وب‌سایت‌های مختلف سفر ایران است. این سیستم شامل ویژگی‌های پیشرفته مانند جستجوی هوشمند، نظارت بر قیمت و پشتیبانی چند زبانه است.

## Features | ویژگی‌ها

- Multi-site crawling (Flytoday, Alibaba, Safarmarket, MZ724, PartoCRS, Parto Ticket, BookCharter724, BookCharter)
- Intelligent search optimization
- Real-time price monitoring
- Persian text processing
- Error handling and circuit breaking
- Rate limiting
- Caching system
- Health monitoring
- Multilingual support

## Prerequisites | پیش‌نیازها

- Python 3.8+
- PostgreSQL
- Redis
- Node.js (for WebSocket support)

## Installation | نصب

1. Clone the repository:
```bash
git clone https://github.com/yourusername/FlightioCrawler.git
cd FlightioCrawler
```

2. Install Poetry and project dependencies:
```bash
pip install poetry
poetry install --with dev
```

3. Activate the environment:
```bash
poetry shell
```

4. Install Playwright browsers:
```bash
playwright install
```

5. Set up the database:
```bash
# Create PostgreSQL database
createdb flight_data

# Initialize database schema
psql -d flight_data -f init.sql
```

6. Configure Redis:
```bash
# Start Redis server
redis-server
```

## Configuration | پیکربندی

1. Create a `.env` file in the project root:
```env
DB_HOST=localhost
DB_NAME=flight_data
DB_USER=crawler
DB_PASSWORD=secure_password
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0
DEBUG_MODE=false
```

2. Update the configuration in `config.py` as needed.
3. If PostgreSQL is not available the crawler will automatically create a
   `data/flight_data.sqlite` file and use it as a local database so crawled
   flights persist across restarts.
4. Set `DEBUG_MODE=true` to enable verbose logging during development.
5. Validate target websites before running crawlers:
```bash
python -m production_url_validator
```

## Usage | استفاده

1. Start the crawler:
```bash
python main_crawler.py
```

2. Monitor the crawler:
```bash
# Check health status
curl http://localhost:8000/health

# View logs
tail -f logs/flight_crawler.log

# View error logs
tail -f logs/error.log
```

3. Launch the API and UI:
```bash
python main.py
```

4. Crawl a single website directly:
```python
from main_crawler import IranianFlightCrawler
import asyncio

crawler = IranianFlightCrawler()
flights = asyncio.run(
    crawler.crawl_site(
        "alibaba.ir",
        {"origin": "THR", "destination": "MHD", "departure_date": "2024-01-01"}
    )
)
print(f"Found {len(flights)} flights")
```
5. Crawl all airport combinations for the next two weeks:
```bash
python scripts/crawl_airport_combinations.py
```
Open `http://localhost:8000/ui` in your browser to access the control panel.

6. Import sample pages for debugging:
```bash
python scripts/parse_saved_pages.py
```

## User Guide | راهنمای کاربر

For step-by-step docker instructions see [USER_GUIDE.md](USER_GUIDE.md).

برای دستورالعمل نصب سریع با داکر به فایل [USER_GUIDE.md](USER_GUIDE.md) مراجعه کنید.


## Developer Guide | راهنمای توسعه‌دهنده

### Project Structure | ساختار پروژه

```
FlightioCrawler/
├── main_crawler.py          # Main crawler orchestrator
├── site_crawlers.py         # Individual site crawlers
├── monitoring/              # Monitoring and error handling
├── data_manager.py          # Data storage and caching
├── intelligent_search.py    # Search optimization
├── price_monitor.py         # Price monitoring
├── flight_monitor.py        # Periodic multi-site monitoring
├── ml_predictor.py          # Price prediction
└── multilingual_processor.py # Language processing
```

### Key Components | اجزای اصلی

1. **Crawler Orchestrator** (`main_crawler.py`)
   - Manages multiple site crawlers
   - Handles concurrent crawling
   - Implements error handling

2. **Site Crawlers** (`site_crawlers.py`)
   - Individual crawlers for each website
   - Custom parsing logic
   - Rate limiting implementation

3. **Data Management** (`data_manager.py`)
   - Database operations
   - Caching system
   - Data normalization

4. **Monitoring** (`monitoring/`)
   - Health checks
   - Error tracking
   - Performance metrics

5. **Flight Monitoring System** (`flight_monitor.py`)
   - Runs continuous crawling loops
   - Platform-specific intervals

## Production Setup | راه‌اندازی محیط تولید

For real-world deployments the project includes several production utilities:

- **ProductionURLValidator** – verifies target websites individually and checks
  HTTP responses, robots.txt rules and possible anti-bot blocks.
- **ProductionSafetyCrawler** – wraps site crawlers with rate limiting and
  circuit breakers to avoid service disruption.
- **RealDataCrawler** – fetches live flight information and validates extracted
  prices, times and flight numbers.
- **RealDataQualityChecker** – ensures scraped results contain realistic data.
- **ProductionMonitoring** – exposes health metrics and alerts on crawling
  issues.
- **Dummy placeholders** – `FlytodayCrawler`, `PartoCRSCrawler`,
  `PartoTicketCrawler`, `BookCharter724Crawler` and `BookCharterCrawler`
  currently return dummy results. Replace their implementations with real
  scraping logic or subclasses of `RealDataCrawler`.

See [docs/real_data_setup.md](docs/real_data_setup.md) for full instructions.

### Monitoring Stack

Deployment manifests for Prometheus, Grafana and Alertmanager are stored in the
`k8s` directory. Use the helper scripts to manage them on your cluster:

```bash
scripts/deploy-monitoring.sh   # deploys all monitoring components
scripts/cleanup-monitoring.sh  # removes the monitoring stack
```

To enable real-data crawling, first run `python -m production_url_validator`
to verify each site is accessible. Instantiate `RealDataCrawler` for your
target and replace any dummy implementations. Always respect website terms of
service and local regulations before scraping production systems.

## Adding New Websites | افزودن وب‌سایت‌های جدید

To add a new website to the crawler:

1. Create a new crawler class in `site_crawlers.py`:
```python
from base_crawler import BaseCrawler

class NewSiteCrawler(BaseCrawler):
    def __init__(self, rate_limiter, text_processor, monitor, error_handler):
        super().__init__(rate_limiter, text_processor, monitor, error_handler)
        self.site_name = "newsite.com"
        
    async def search_flights(self, search_params):
        # Implement site-specific crawling logic
        pass
```

2. Add the new crawler to `main_crawler.py`:
```python
self.crawlers["newsite.com"] = NewSiteCrawler(
    self.rate_limiter,
    self.text_processor,
    self.monitor,
    self.error_handler
)
```

3. Update configuration in `config.py`:
```python
CRAWLER.DOMAINS.append("newsite.com")
```

4. Implement site-specific parsing and error handling.

### Best Practices | بهترین شیوه‌ها

1. **Rate Limiting**
   - Implement proper delays between requests
   - Respect website robots.txt
   - Use rotating user agents

2. **Error Handling**
   - Implement circuit breakers
   - Log all errors
   - Implement retry mechanisms

3. **Data Processing**
   - Normalize all data
   - Validate before storage
   - Implement proper caching

4. **Testing**
   - Write unit tests for new crawlers
   - Test error scenarios
   - Validate data consistency

## Contributing | مشارکت

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Chain-of-Thought Design

Refer to [docs/chain_of_thought_monitoring.md](docs/chain_of_thought_monitoring.md) for a high-level design covering URL validation, content detection, extraction logic and monitoring best practices.

## Future Work

Planned improvements for real data crawling are tracked in [docs/new_tasks.md](docs/new_tasks.md).

## License | مجوز

This project is licensed under the MIT License - see the LICENSE file for details. 
