# Iranian Flight Crawler (خزنده پروازهای ایران)

A sophisticated web crawler system for Iranian flight booking websites with intelligent search capabilities, price monitoring, and multilingual support.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Developer Guide](#developer-guide)
- [Adding New Websites](#adding-new-websites)

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

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the database:
```bash
# Create PostgreSQL database
createdb flight_data

# Initialize database schema
psql -d flight_data -f init.sql
```

5. Configure Redis:
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
```

2. Update the configuration in `config.py` as needed.

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
tail -f flight_crawler.log
```

## Developer Guide | راهنمای توسعه‌دهنده

### Project Structure | ساختار پروژه

```
FlightioCrawler/
├── main_crawler.py          # Main crawler orchestrator
├── site_crawlers/          # Individual site crawlers
├── monitoring/             # Monitoring and error handling
├── data_manager/          # Data storage and caching
├── intelligent_search/     # Search optimization
├── price_monitor/         # Price monitoring
├── ml_predictor/          # Price prediction
└── multilingual_processor/ # Language processing
```

### Key Components | اجزای اصلی

1. **Crawler Orchestrator** (`main_crawler.py`)
   - Manages multiple site crawlers
   - Handles concurrent crawling
   - Implements error handling

2. **Site Crawlers** (`site_crawlers/`)
   - Individual crawlers for each website
   - Custom parsing logic
   - Rate limiting implementation

3. **Data Management** (`data_manager/`)
   - Database operations
   - Caching system
   - Data normalization

4. **Monitoring** (`monitoring/`)
   - Health checks
   - Error tracking
   - Performance metrics

## Adding New Websites | افزودن وب‌سایت‌های جدید

To add a new website to the crawler:

1. Create a new crawler class in `site_crawlers/`:
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

## License | مجوز

This project is licensed under the MIT License - see the LICENSE file for details. 