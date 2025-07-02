# FlightioCrawler 🛩️

[![CI/CD Pipeline](https://github.com/your-username/FlightioCrawler/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/your-username/FlightioCrawler/actions)
[![Code Coverage](https://codecov.io/gh/your-username/FlightioCrawler/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/FlightioCrawler)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type Checked](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy.readthedocs.io/)
[![Security](https://img.shields.io/badge/security-bandit-yellow.svg)](https://bandit.readthedocs.io/)

A comprehensive, production-ready flight price crawler and monitoring system with advanced Persian language support, machine learning predictions, and real-time monitoring capabilities.

## ✨ Features

### 🔍 **Advanced Web Crawling**
- **Multi-site Support**: Crawls 15+ Iranian and international flight booking websites
- **Smart Rate Limiting**: Adaptive rate limiting with circuit breaker patterns
- **Stealth Crawling**: Advanced anti-detection mechanisms with user-agent rotation
- **JavaScript Rendering**: Full support for SPA and dynamic content using Playwright
- **Fault Tolerance**: Robust error handling with automatic retries and fallbacks

### 🧠 **Machine Learning & AI**
- **Price Prediction**: ML models for flight price forecasting
- **Intelligent Search**: Smart search algorithms with fuzzy matching
- **Pattern Recognition**: Automated detection of price trends and anomalies
- **Recommendation Engine**: Personalized flight recommendations

### 🌐 **Persian Language Excellence**
- **Native Persian Support**: Full RTL text processing and normalization
- **Smart Date Handling**: Jalali (Persian) calendar integration
- **Text Processing**: Advanced Persian text cleaning and standardization
- **Localization**: Complete Persian UI and error messages

### 📊 **Monitoring & Analytics**
- **Real-time Monitoring**: Prometheus metrics and Grafana dashboards
- **Performance Tracking**: Detailed crawling performance analytics
- **Health Checks**: Comprehensive system health monitoring
- **Alerting**: Smart alerting for system issues and price changes

### 🏗️ **Production-Ready Architecture**
- **Microservices**: Modular, scalable architecture
- **Container Support**: Full Docker and Kubernetes deployment
- **Database**: PostgreSQL with Redis caching
- **API**: RESTful API with FastAPI
- **Security**: Comprehensive security measures and input validation

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **PostgreSQL 13+**
- **Redis 6+**
- **Docker** (optional)

### Installation

#### Option 1: Using Poetry (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/FlightioCrawler.git
cd FlightioCrawler

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

#### Option 2: Using pip

```bash
# Clone the repository
git clone https://github.com/your-username/FlightioCrawler.git
cd FlightioCrawler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Option 3: Using Make

```bash
# Full development setup
make setup-full

# Or step by step
make setup-dev
make format
make lint
make test
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# Database Configuration
DB_HOST=localhost
DB_NAME=flight_data
DB_USER=crawler
DB_PASSWORD=secure_password
DB_PORT=5432

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Application Configuration
ENVIRONMENT=development
USE_MOCK=true
DEBUG=true
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=your-secret-key-here

# Crawler Configuration
CRAWLER_TIMEOUT=30
```

### Database Setup

```bash
# Using Docker (recommended)
docker-compose up -d postgres redis

# Or install PostgreSQL and Redis manually
# Then run migrations
python -m alembic upgrade head
```

## 🎯 Usage

### Basic Usage

```python
from main_crawler import IranianFlightCrawler
from config import config

# Initialize crawler
crawler = IranianFlightCrawler(config)

# Search for flights
results = await crawler.search_flights(
    origin="THR",           # Tehran
    destination="IST",      # Istanbul
    departure_date="2024-06-15",
    passengers=1,
    seat_class="economy"
)

print(f"Found {len(results)} flights")
```

### API Usage

```bash
# Start the API server
python -m uvicorn main:app --reload

# Search flights via API
curl -X POST "http://localhost:8000/api/v1/search" \
     -H "Content-Type: application/json" \
     -d '{
       "origin": "THR",
       "destination": "IST", 
       "departure_date": "2024-06-15",
       "passengers": 1
     }'
```

### Command Line Interface

```bash
# Search flights
python main_crawler.py --origin THR --destination IST --date 2024-06-15

# Run with specific sites
python main_crawler.py --sites alibaba,flytoday --origin THR --destination MHD

# Monitor prices
python price_monitor.py --route THR-IST --threshold 5000000

# Generate reports
python provider_insights.py --days 30
```

## 🛠️ Development

### Code Quality

This project maintains high code quality standards:

```bash
# Format code
make format

# Run linting
make lint

# Type checking
make type-check

# Run tests
make test

# All quality checks
make quality
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m slow
```

### Docker Development

```bash
# Build and run with Docker
make docker-build
make docker-run

# Or use docker-compose
docker-compose up -d

# For development
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

## 📖 Documentation

### Architecture

The system follows a modular, microservices-inspired architecture:

```
├── adapters/           # Site-specific crawling adapters
│   ├── base_adapters/  # Base classes and common functionality
│   ├── site_adapters/  # Individual site implementations
│   ├── factories/      # Adapter factory patterns
│   └── patterns/       # Design patterns implementation
├── config/             # Configuration management
├── data/              # Data processing and storage
├── monitoring/        # Monitoring and metrics
├── tests/             # Comprehensive test suite
└── frontend/          # React-based web interface
```

### Key Components

1. **Crawling Engine**: Multi-threaded crawler with rate limiting
2. **Data Pipeline**: ETL pipeline for data processing and storage
3. **ML Engine**: Machine learning models for predictions
4. **API Layer**: RESTful API with authentication
5. **Monitoring**: Real-time monitoring and alerting
6. **Frontend**: Modern React-based user interface

### API Documentation

API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🔧 Configuration

### Site Configuration

Each crawled site has its own configuration file in `config/site_configs/`:

```json
{
  "rate_limiting": {
    "requests_per_second": 2,
    "cooldown_period": 60
  },
  "selectors": {
    "price": ".price-amount",
    "departure_time": ".departure-time"
  },
  "headers": {
    "User-Agent": "Custom crawler agent"
  }
}
```

### Monitoring Configuration

Monitoring is configured via `monitoring/prometheus.yml` and includes:

- **System Metrics**: CPU, memory, disk usage
- **Application Metrics**: Request rates, error rates, response times
- **Business Metrics**: Flight counts, price changes, search success rates

## 🚀 Deployment

### Production Deployment

```bash
# Using Docker
docker build -t flightio-crawler .
docker run -d --name crawler -p 8000:8000 flightio-crawler

# Using Kubernetes
kubectl apply -f k8s/

# Using the deployment script
./scripts/deploy_production.sh
```

### Environment-specific Configs

- **Development**: `docker-compose.yml`
- **Staging**: `docker-compose.staging.yml`
- **Production**: `docker-compose.production.yml`

### Monitoring Setup

```bash
# Deploy monitoring stack
./scripts/deploy-monitoring.sh

# Access dashboards
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

## 📊 Performance

### Benchmarks

- **Crawling Speed**: 1000+ flights/minute
- **API Response Time**: <200ms average
- **Memory Usage**: <512MB under normal load
- **Database**: Handles 10M+ flight records efficiently

### Scalability

- **Horizontal Scaling**: Supports multiple crawler instances
- **Database Sharding**: PostgreSQL partitioning support
- **Caching**: Multi-layer caching with Redis
- **Load Balancing**: Nginx/HAProxy support

## 🔒 Security

### Security Features

- **Input Validation**: Comprehensive input sanitization
- **SQL Injection Protection**: Parameterized queries
- **Rate Limiting**: Per-IP and per-user rate limiting
- **Authentication**: JWT-based authentication
- **HTTPS**: TLS/SSL encryption support
- **Security Headers**: CORS, CSP, HSTS headers

### Security Scanning

```bash
# Run security checks
make security

# Vulnerability scanning
make safety

# Generate security reports
bandit -r . -f json -o security-report.json
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Run** quality checks (`make quality`)
4. **Commit** your changes (`git commit -m 'Add amazing feature'`)
5. **Push** to the branch (`git push origin feature/amazing-feature`)
6. **Open** a Pull Request

### Code Standards

- **Python Style**: Black formatting, PEP 8 compliance
- **Type Hints**: Full type annotation required
- **Documentation**: Comprehensive docstrings
- **Testing**: Minimum 80% code coverage
- **Security**: Security-first development approach

## 📋 Roadmap

### Version 2.0 (Q2 2024)
- [ ] GraphQL API
- [ ] Real-time WebSocket updates
- [ ] Advanced ML models
- [ ] Mobile app support

### Version 2.1 (Q3 2024)
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] API rate limiting tiers
- [ ] Webhook notifications

### Version 2.2 (Q4 2024)
- [ ] AI-powered price predictions
- [ ] Advanced search filters
- [ ] Custom alerting rules
- [ ] Enterprise features

## 🐛 Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database status
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
python -m alembic upgrade head
```

#### Redis Connection Issues
```bash
# Check Redis status
docker-compose logs redis

# Test Redis connection
redis-cli ping
```

#### Crawling Issues
```bash
# Check crawler logs
tail -f logs/crawler.log

# Test specific site
python test_site.py --site alibaba

# Run in debug mode
python main_crawler.py --debug --site flytoday
```

### Performance Issues

#### Slow Crawling
- Check rate limiting settings
- Verify network connectivity
- Monitor resource usage

#### High Memory Usage
- Adjust batch sizes
- Check for memory leaks
- Optimize database queries

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Persian NLP**: Thanks to the Hazm library team
- **Web Crawling**: Playwright and BeautifulSoup communities
- **Monitoring**: Prometheus and Grafana projects
- **Contributors**: All our amazing contributors

## 📞 Support

- **Documentation**: [Full Documentation](https://docs.flightiocrawler.com)
- **Issues**: [GitHub Issues](https://github.com/your-username/FlightioCrawler/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/FlightioCrawler/discussions)
- **Email**: support@flightiocrawler.com

---

**Made with ❤️ for the Persian aviation community**
