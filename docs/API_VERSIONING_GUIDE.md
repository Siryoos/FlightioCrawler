# API Versioning and Migration Guide

## Overview

The FlightioCrawler API now supports versioning to ensure backward compatibility while allowing for future enhancements. This document provides comprehensive information about API versioning, migration paths, and best practices.

## API Versioning Strategy

### Version Format
- **Current Version**: v1
- **Future Versions**: v2, v3, etc.
- **Legacy Support**: Unversioned endpoints (deprecated)

### Supported Versions

| Version | Status | Introduced | Deprecated | Sunset |
|---------|--------|------------|------------|--------|
| v1      | Active | 2024-01-01 | -          | -      |
| Legacy  | Deprecated | 2023-01-01 | 2024-01-01 | 2025-12-31 |

## Version Detection Methods

The API supports multiple methods for specifying the desired API version (in order of priority):

### 1. HTTP Header (Recommended)
```http
X-API-Version: v1
```

### 2. Accept Header with Vendor Media Type
```http
Accept: application/vnd.flightio.v1+json
```

### 3. Query Parameter
```http
GET /api/v1/flights/search?version=v1
```

### 4. URL Path (Default for v1)
```http
GET /api/v1/flights/search
```

## API Endpoints

### v1 API Structure

#### Flights Endpoints
- `POST /api/v1/flights/search` - Search for flights
- `GET /api/v1/flights/recent` - Get recent flights
- `POST /api/v1/flights/crawl` - Manual crawl trigger
- `POST /api/v1/flights/search/intelligent` - Intelligent search
- `GET /api/v1/flights/predict` - Price predictions
- `GET /api/v1/flights/trend/{route}` - Price trends
- `POST /api/v1/flights/routes` - Add route
- `GET /api/v1/flights/routes` - List routes
- `DELETE /api/v1/flights/routes/{route_id}` - Delete route

#### System Endpoints
- `GET /api/v1/system/health` - Health check
- `GET /api/v1/system/metrics` - System metrics
- `GET /api/v1/system/stats` - System statistics
- `POST /api/v1/system/reset` - Reset statistics
- `GET /api/v1/system/info` - System information
- `GET /api/v1/system/airports` - List airports
- `GET /api/v1/system/airports/countries` - List countries
- `POST /api/v1/system/cache/clear` - Clear cache
- `GET /api/v1/system/version` - Version information

#### Monitoring Endpoints
- `POST /api/v1/monitoring/alerts` - Create price alert
- `GET /api/v1/monitoring/alerts` - List price alerts
- `DELETE /api/v1/monitoring/alerts/{alert_id}` - Delete alert
- `POST /api/v1/monitoring/start` - Start monitoring
- `POST /api/v1/monitoring/stop` - Stop monitoring
- `GET /api/v1/monitoring/status` - Monitoring status
- `GET /api/v1/monitoring/insights` - Provider insights

#### Sites Endpoints
- `GET /api/v1/sites/status` - All sites status
- `GET /api/v1/sites/{site_name}/status` - Specific site status
- `POST /api/v1/sites/{site_name}/test` - Test site
- `GET /api/v1/sites/{site_name}/health` - Site health check
- `POST /api/v1/sites/{site_name}/enable` - Enable site
- `POST /api/v1/sites/{site_name}/disable` - Disable site
- `POST /api/v1/sites/{site_name}/reset` - Reset site errors
- `GET /api/v1/sites/{site_name}/metrics` - Site metrics

#### Rate Limiting Endpoints
- `GET /api/v1/rate-limits/stats` - Rate limit statistics
- `GET /api/v1/rate-limits/config` - Rate limit configuration
- `PUT /api/v1/rate-limits/config` - Update configuration
- `GET /api/v1/rate-limits/client/{client_ip}` - Client status
- `POST /api/v1/rate-limits/reset` - Reset client limits
- `GET /api/v1/rate-limits/blocked` - Blocked clients
- `POST /api/v1/rate-limits/whitelist` - Add to whitelist
- `GET /api/v1/rate-limits/whitelist/{ip}` - Check whitelist
- `DELETE /api/v1/rate-limits/whitelist/{ip}` - Remove from whitelist

#### WebSocket Endpoints
- `WS /api/v1/monitoring/ws/prices/{user_id}` - Price alerts
- `WS /api/v1/monitoring/ws/dashboard` - Dashboard updates
- `WS /api/v1/sites/ws/{site_name}/logs` - Site logs

## Migration Guide

### Legacy to v1 Migration

#### Endpoint Mapping

| Legacy Endpoint | v1 Endpoint |
|----------------|-------------|
| `POST /search` | `POST /api/v1/flights/search` |
| `GET /health` | `GET /api/v1/system/health` |
| `GET /metrics` | `GET /api/v1/system/metrics` |
| `GET /stats` | `GET /api/v1/system/stats` |
| `POST /reset` | `POST /api/v1/system/reset` |
| `GET /flights/recent` | `GET /api/v1/flights/recent` |
| `GET /airports` | `GET /api/v1/system/airports` |
| `POST /routes` | `POST /api/v1/flights/routes` |
| `GET /routes` | `GET /api/v1/flights/routes` |
| `DELETE /routes/{id}` | `DELETE /api/v1/flights/routes/{id}` |
| `POST /crawl` | `POST /api/v1/flights/crawl` |
| `GET /predict` | `GET /api/v1/flights/predict` |
| `GET /trend/{route}` | `GET /api/v1/flights/trend/{route}` |
| `POST /alerts` | `POST /api/v1/monitoring/alerts` |
| `GET /alerts` | `GET /api/v1/monitoring/alerts` |
| `DELETE /alerts/{id}` | `DELETE /api/v1/monitoring/alerts/{id}` |
| `POST /monitor/start` | `POST /api/v1/monitoring/start` |
| `POST /monitor/stop` | `POST /api/v1/monitoring/stop` |
| `GET /monitor/status` | `GET /api/v1/monitoring/status` |
| `WS /ws/prices/{user_id}` | `WS /api/v1/monitoring/ws/prices/{user_id}` |
| `WS /ws/dashboard` | `WS /api/v1/monitoring/ws/dashboard` |

### Migration Steps

1. **Update Base URLs**
   - Change from `https://api.flightio.com/search` to `https://api.flightio.com/api/v1/flights/search`

2. **Add Version Headers**
   ```http
   X-API-Version: v1
   ```

3. **Update Response Handling**
   - All v1 responses include a `version` field
   - Responses include additional metadata fields

4. **Update Error Handling**
   - v1 uses consistent error response format
   - HTTP status codes remain the same

### Example Migration

#### Before (Legacy)
```javascript
// Legacy API call
const response = await fetch('/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    origin: 'THR',
    destination: 'IST',
    date: '2024-06-01'
  })
});
```

#### After (v1)
```javascript
// v1 API call
const response = await fetch('/api/v1/flights/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Version': 'v1'
  },
  body: JSON.stringify({
    origin: 'THR',
    destination: 'IST',
    date: '2024-06-01'
  })
});

const data = await response.json();
// v1 responses include version info
console.log(data.version); // "v1"
```

## Content Negotiation

The API supports content negotiation for different response formats:

### JSON (Default)
```http
Accept: application/json
```

### Vendor-specific JSON
```http
Accept: application/vnd.flightio.v1+json
```

### Future Support
- XML: `application/vnd.flightio.v1+xml`
- YAML: `application/vnd.flightio.v1+yaml`

## Deprecation Policy

### Deprecation Levels

1. **INFO**: Version will be deprecated in the future
2. **WARNING**: Version is deprecated but still supported
3. **CRITICAL**: Version will be removed soon

### Deprecation Headers

Deprecated endpoints include these headers:

```http
Deprecation: true
X-API-Deprecation-Level: warning
X-API-Deprecation-Message: This endpoint is deprecated. Use /api/v1/flights/search
Sunset: Sun, 31 Dec 2025 23:59:59 GMT
```

### Timeline

- **Legacy Endpoints**: Deprecated January 1, 2024
- **Migration Deadline**: June 30, 2025
- **Sunset Date**: December 31, 2025

## Error Handling

### v1 Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "origin",
      "issue": "Airport code must be 3 characters"
    }
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "v1"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

## Rate Limiting

### v1 Rate Limits

| Endpoint Type | Requests/Minute | Requests/Hour | Burst Limit |
|---------------|-----------------|---------------|-------------|
| Search | 30 | 500 | 5 |
| System | 60 | 1000 | 10 |
| Admin | 120 | 2000 | 20 |

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1609459200
X-RateLimit-RetryAfter: 60
```

## Best Practices

### 1. Always Specify Version
```http
X-API-Version: v1
```

### 2. Handle Deprecation Warnings
```javascript
if (response.headers.get('Deprecation') === 'true') {
  console.warn('API endpoint is deprecated:', 
    response.headers.get('X-API-Deprecation-Message'));
}
```

### 3. Implement Proper Error Handling
```javascript
if (!response.ok) {
  const error = await response.json();
  throw new Error(`API Error: ${error.error.message}`);
}
```

### 4. Use Appropriate Content Types
```http
Accept: application/vnd.flightio.v1+json
Content-Type: application/json
```

### 5. Monitor Rate Limits
```javascript
const remaining = response.headers.get('X-RateLimit-Remaining');
if (remaining < 5) {
  console.warn('Rate limit nearly exceeded');
}
```

## Testing

### Test Endpoints

Use these endpoints to test versioning:

```bash
# Test version detection
curl -H "X-API-Version: v1" https://api.flightio.com/api/v1/system/version

# Test content negotiation
curl -H "Accept: application/vnd.flightio.v1+json" https://api.flightio.com/api/v1/system/info

# Test legacy endpoint (with deprecation warning)
curl https://api.flightio.com/health
```

## Support

### Migration Support
- **Email**: api-support@flightio.com
- **Documentation**: https://docs.flightio.com/api/migration
- **Status Page**: https://status.flightio.com

### Monitoring
- **Health Check**: `GET /api/v1/system/health`
- **Version Info**: `GET /api/v1/system/version`
- **API Docs**: `GET /api/v1/docs`

## Changelog

### Version 1.0.0 (2024-01-01)
- Initial versioned API release
- Added comprehensive v1 endpoints
- Implemented backward compatibility
- Added deprecation warnings for legacy endpoints
- Introduced content negotiation
- Added rate limiting per endpoint type

### Legacy (Pre-2024)
- Unversioned API endpoints
- Basic functionality without versioning
- Now deprecated with sunset date of 2025-12-31 