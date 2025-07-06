# FlightioCrawler Architecture Documentation

## 🎉 NEW: Unified Architecture (2024)

**FlightioCrawler has undergone a comprehensive consolidation effort!**

**Status**: ✅ **COMPLETE** - All 7 major consolidation tasks completed with 87.1% test success rate

### Quick Start with Unified Components

```python
# Error Handling - Use the unified error handler
from adapters.base_adapters.enhanced_error_handler import EnhancedErrorHandler

# Rate Limiting - Use the unified rate limiter with circuit breaker
from rate_limiter import UnifiedRateLimiter

# Persian Text Processing - Use the unified processor
from persian_text import PersianTextProcessor

# Parsing Strategies - Use the unified parsing strategies
from adapters.strategies.parsing_strategies import PersianParsingStrategy
```

### 📋 Consolidation Achievements

1. ✅ **Error Handling Consolidation** - Single `EnhancedErrorHandler` with circuit breaker integration
2. ✅ **Base Crawler Consolidation** - Unified `EnhancedBaseCrawler` for all adapters
3. ✅ **Factory Consolidation** - Single `SiteCrawlerFactory` for all crawler types
4. ✅ **Persian Text Processing** - Unified `PersianTextProcessor` with compatibility wrappers
5. ✅ **Rate Limiter Consolidation** - `UnifiedRateLimiter` with circuit breaker integration
6. ✅ **Parsing Strategies** - Centralized parsing with strategy pattern
7. ✅ **Circuit Breaker Integration** - Comprehensive failure protection across all components

### 🔗 Detailed Documentation

**For comprehensive information about the unified architecture, see:**
👉 **[Unified Architecture Guide](docs/UNIFIED_ARCHITECTURE_GUIDE.md)**

This guide includes:
- Complete usage examples for all unified components
- Migration guide from legacy code
- Performance benefits and best practices
- Integration test results (87.1% success rate)

---

## Legacy Architecture Documentation

*The following documentation describes the original architecture before consolidation. For new development, please use the unified architecture described above.*

## System Overview | مرور سیستم

The FlightioCrawler is a distributed system designed to crawl, process, and analyze flight data from multiple Iranian travel websites. The system is built with scalability, reliability, and maintainability in mind.

## Architecture Diagram | نمودار معماری

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway Layer                        │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ Health API  │  │ Search API  │  │ Monitor API │  │ Auth    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Core Components                           │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ Crawler     │  │ Data        │  │ Search      │  │ Price   │ │
│  │ Orchestrator│  │ Manager     │  │ Engine      │  │ Monitor │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Site Crawlers                            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ FlyToday    │  │ Alibaba     │  │ SafarMarket │              │
│  │ Crawler     │  │ Crawler     │  │ Crawler     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Storage                             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ PostgreSQL  │  │ Redis       │  │ File        │              │
│  │ Database    │  │ Cache       │  │ Storage     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details | جزئیات اجزا

### 1. API Gateway Layer | لایه دروازه API

#### Health API
- Endpoint: `/api/v1/health`
- Purpose: System health monitoring
- Features:
  - Crawler status
  - Database connectivity
  - Redis connectivity
  - Error rates
  - Performance metrics

#### Search API
- Endpoint: `/api/v1/search`
- Purpose: Flight search and filtering
- Features:
  - Intelligent search
  - Price comparison
  - Filtering options
  - Sorting capabilities

#### Monitor API
- Endpoint: `/api/v1/monitor`
- Purpose: System monitoring and metrics
- Features:
  - Real-time metrics
  - Error tracking
  - Performance monitoring
  - Rate limiting stats

### 2. Core Components | اجزای اصلی

#### Crawler Orchestrator
- Manages multiple site crawlers
- Implements concurrent crawling
- Handles error recovery
- Manages rate limiting
- Features:
  - Circuit breaker pattern
  - Retry mechanism
  - Load balancing
  - Resource management

#### Data Manager
- Handles data persistence
- Manages caching
- Implements data normalization
- Features:
  - Data validation
  - Schema management
  - Cache invalidation
  - Data consistency

#### Search Engine
- Implements intelligent search
- Optimizes search strategies
- Features:
  - Query optimization
  - Result ranking
  - Filter optimization
  - Cache management

#### Price Monitor
- Tracks price changes
- Implements price alerts
- Features:
  - Real-time monitoring
  - Price prediction
  - Alert system
  - Trend analysis

### 3. Site Crawlers | خزنده‌های سایت

#### Base Crawler
- Abstract base class for all crawlers
- Common functionality:
  - Rate limiting
  - Error handling
  - Data extraction
  - Response parsing

#### Individual Site Crawlers
- FlyToday Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
  
- Alibaba Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
  
- SafarMarket Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
- MZ724 Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
- PartoCRS Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
- Parto Ticket Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
- BookCharter724 Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules
- BookCharter Crawler
  - Site-specific parsing
  - Custom error handling
  - Rate limiting rules

### 4. Data Storage | ذخیره‌سازی داده

#### PostgreSQL Database
- Schema:
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
  ```

#### Redis Cache
- Usage:
  - Session management
  - Rate limiting
  - Temporary data storage
  - Cache invalidation

#### File Storage
- Logs
- ML models
- Configuration files
- Backup data

## Data Flow | جریان داده

1. **Search Request Flow**:
   ```
   Client → API Gateway → Search Engine → Data Manager → Response
   ```

2. **Crawling Flow**:
   ```
   Crawler Orchestrator → Site Crawlers → Data Manager → Storage
   ```

3. **Monitoring Flow**:
   ```
   Site Crawlers → Monitor API → Metrics Storage → Dashboard
   ```

## Security Measures | اقدامات امنیتی

1. **Authentication**:
   - JWT-based authentication
   - Role-based access control
   - API key management

2. **Rate Limiting**:
   - Per-IP rate limiting
   - Per-user rate limiting
   - Per-endpoint rate limiting

3. **Data Protection**:
   - Data encryption
   - Secure storage
   - Access logging

## Error Handling | مدیریت خطا

1. **Circuit Breaker Pattern**:
   - Prevents cascading failures
   - Automatic recovery
   - Fallback mechanisms

2. **Retry Mechanism**:
   - Exponential backoff
   - Maximum retry attempts
   - Error logging

3. **Error Monitoring**:
   - Real-time error tracking
   - Error categorization
   - Alert system

## Performance Optimization | بهینه‌سازی عملکرد

1. **Caching Strategy**:
   - Multi-level caching
   - Cache invalidation
   - Cache warming

2. **Concurrency**:
   - Async operations
   - Parallel processing
   - Resource pooling

3. **Database Optimization**:
   - Indexing
   - Query optimization
   - Connection pooling

## Monitoring and Logging | نظارت و ثبت رویدادها

1. **Metrics**:
   - System metrics
   - Business metrics
   - Performance metrics

2. **Logging**:
   - Application logs
   - Error logs
   - Access logs

3. **Alerting**:
   - Error alerts
   - Performance alerts
   - Security alerts

## Deployment | استقرار

1. **Requirements**:
   - Python 3.8+
   - PostgreSQL 12+
   - Redis 6+
   - Node.js 14+

2. **Environment Setup**:
   - Virtual environment
   - Dependencies installation
   - Configuration setup

3. **Deployment Steps**:
   - Database migration
   - Service startup
   - Health checks
   - Monitoring setup

## Scaling Strategy | استراتژی مقیاس‌پذیری

1. **Horizontal Scaling**:
   - Multiple crawler instances
   - Load balancing
   - Database replication

2. **Vertical Scaling**:
   - Resource optimization
   - Performance tuning
   - Cache optimization

3. **Data Partitioning**:
   - Sharding strategy
   - Data distribution
   - Query optimization 

_End of document_
