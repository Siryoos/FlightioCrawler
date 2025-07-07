# FlightIO Crawler - Unified & Optimized

A high-performance, unified flight data crawler system with simplified architecture and optimized build process.

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone <repository>
cd FlightioCrawler

# 2. Build everything
./build.sh build

# 3. Start all services
./build.sh start

# 4. Access the application
# API: http://localhost:8000
# Frontend: http://localhost:3000
# Health: http://localhost:8080/health
```

## 📋 Key Features

- **Unified Architecture**: Single Dockerfile, single config, single entry point
- **Optimized Build**: Multi-stage builds with efficient caching
- **Simplified Dependencies**: One requirements file for all services
- **Unified Monitoring**: Single monitoring system for all metrics
- **Environment-based Configuration**: Easy deployment across environments

## 🏗️ Architecture

### Unified Components

1. **Dockerfile.unified**: Multi-stage Dockerfile for all services
2. **requirements.unified.txt**: Consolidated dependencies
3. **docker-compose.unified.yml**: Single compose file
4. **config/unified_config.yml**: Centralized configuration
5. **main_unified.py**: Single entry point for all services
6. **monitoring/unified_monitor.py**: Consolidated monitoring

### Services

- **API**: REST API for flight searches
- **Crawler**: Automated flight data collection
- **Worker**: Background task processing
- **Frontend**: React-based user interface

## 🛠️ Usage

### Build Commands

```bash
# Build all images
./build.sh build

# Build without cache
./build.sh build --no-cache

# Start services
./build.sh start

# Stop services
./build.sh stop

# View logs
./build.sh logs [service]

# Check status
./build.sh status

# Deploy to production
./build.sh deploy

# Clean up everything
./build.sh clean
```

### Environment Configuration

Create a `.env` file:

```env
# Application
ENVIRONMENT=production
SERVICE_TYPE=api
LOG_LEVEL=INFO

# Database
DB_USER=crawler
DB_PASSWORD=your_secure_password
DB_NAME=flight_data

# Redis
REDIS_PASSWORD=your_redis_password

# API
API_PORT=8000
API_WORKERS=4

# Frontend
FRONTEND_PORT=3000

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001
```

### Running Different Services

```bash
# Run as API
SERVICE_TYPE=api ./build.sh start api

# Run as Crawler
SERVICE_TYPE=crawler ./build.sh start crawler

# Run as Worker
SERVICE_TYPE=worker ./build.sh start worker

# Run Frontend
SERVICE_TYPE=frontend ./build.sh start frontend
```

## 📁 Project Structure

```
FlightioCrawler/
├── Dockerfile.unified          # Single Dockerfile for all services
├── docker-compose.unified.yml  # Unified compose configuration
├── requirements.unified.txt    # All Python dependencies
├── build.sh                   # Unified build script
├── main_unified.py            # Single entry point
├── .env                       # Environment configuration
├── config/
│   └── unified_config.yml     # Unified configuration
├── adapters/
│   ├── unified_base_adapter.py # Base adapter with common logic
│   └── site_adapters/         # Site-specific implementations
├── monitoring/
│   └── unified_monitor.py     # Unified monitoring system
├── api/                       # API routes and logic
├── frontend/                  # React frontend
└── tests/                     # Test suite
```

## 🔧 Development

### Adding a New Site Adapter

1. Create a new adapter file in `adapters/site_adapters/`
2. Extend `UnifiedBaseAdapter`
3. Implement only site-specific methods:

```python
from adapters.unified_base_adapter import UnifiedBaseAdapter

class NewSiteAdapter(UnifiedBaseAdapter):
    def get_site_name(self) -> str:
        return "newsite"
        
    async def parse_search_results(self, content: str, origin: str, 
                                 destination: str, date: str) -> List[Dict]:
        # Site-specific parsing logic
        pass
```

### Monitoring

Access monitoring endpoints:

- Health Check: http://localhost:8080/health
- Prometheus Metrics: http://localhost:8080/metrics
- Detailed Status: http://localhost:8080/status

## 🚀 Production Deployment

```bash
# 1. Set production environment
export ENVIRONMENT=production

# 2. Configure secrets
echo "your_db_password" > secrets/db_password.txt
echo "your_redis_password" > secrets/redis_password.txt

# 3. Deploy
./build.sh deploy

# 4. Monitor
./build.sh logs -f
```

## 🧹 Cleanup

To remove old files and complete the unification:

```bash
# This will backup and remove old files
./cleanup_project.sh
```

## 📊 Performance Optimizations

- **Docker BuildKit**: Enabled for faster builds
- **Multi-stage builds**: Smaller final images
- **Layer caching**: Optimized dependency installation
- **Unified monitoring**: Reduced overhead
- **Simplified configuration**: Faster startup

## 🤝 Contributing

1. Use the unified base adapter for new sites
2. Add dependencies to `requirements.unified.txt`
3. Update `config/unified_config.yml` for new configurations
4. Follow the single entry point pattern in `main_unified.py`

## 📝 License

[Your License Here]

---

**Note**: This is the unified version of FlightIO. For the legacy structure, check the backup directory created by `cleanup_project.sh`. 