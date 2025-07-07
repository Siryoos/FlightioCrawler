# راهنمای امنیتی FlightioCrawler

## 🔒 خلاصه امنیتی

FlightioCrawler از بهترین پراتیک‌های امنیتی برای محافظت در برابر تهدیدات رایج استفاده می‌کند.

## 🛡️ محافظت‌های پیاده‌سازی شده

### 1. SQL Injection Prevention

#### ✅ استفاده از SQLAlchemy ORM
- **هیچ raw SQL query** در پروژه وجود ندارد
- تمام database operations از **SQLAlchemy ORM** استفاده می‌کنند
- **Parameterized queries** به صورت خودکار توسط ORM مدیریت می‌شوند

#### ✅ Input Validation Layer
```python
class InputValidator:
    @staticmethod
    def validate_airport_code(code: str) -> str:
        """Validates IATA/ICAO airport codes"""
        
    @staticmethod
    def validate_route_string(route: str) -> tuple[str, str]:
        """Validates route format (e.g., 'THR-IST')"""
        
    @staticmethod
    def sanitize_string(text: str, max_length: int = 255) -> str:
        """Sanitizes string input to prevent injection"""
        
    @staticmethod
    def validate_positive_integer(value: any, min_value: int = 1, max_value: int = 1000) -> int:
        """Validates positive integers within bounds"""
```

### 2. Cross-Site Scripting (XSS) Prevention

#### ✅ HTML Escaping
- تمام ورودی‌های کاربر با `html.escape()` پاکسازی می‌شوند
- کاراکترهای خطرناک (`<`, `>`, `"`, `'`, `;`, `\`) حذف می‌شوند

#### ✅ Content Security Policy
- استفاده از `bleach` library برای HTML sanitization
- محدودیت length برای جلوگیری از buffer overflow

### 3. Input Validation & Sanitization

#### ✅ Airport Code Validation
```python
# Valid Examples:
validate_airport_code("THR")     # ✅ Returns "THR"
validate_airport_code("OIII")    # ✅ Returns "OIII"

# Blocked Examples:
validate_airport_code("'; DROP TABLE--")  # ❌ Raises ValueError
validate_airport_code("<script>")         # ❌ Raises ValueError
```

#### ✅ Route String Validation
```python
# Valid Examples:
validate_route_string("THR-IST")  # ✅ Returns ("THR", "IST")

# Blocked Examples:
validate_route_string("THR'; DELETE--")  # ❌ Raises ValueError
```

#### ✅ Integer Validation
```python
# Valid Examples:
validate_positive_integer(5)     # ✅ Returns 5
validate_positive_integer("10")  # ✅ Returns 10

# Blocked Examples:
validate_positive_integer("1; DROP--")  # ❌ Raises ValueError
validate_positive_integer(-1)           # ❌ Raises ValueError
```

## 🧪 Security Testing

### Test Coverage
- **Input Validation Tests**: 100% coverage
- **SQL Injection Tests**: شامل تمام attack vectors
- **XSS Prevention Tests**: شامل HTML/JavaScript injection
- **Integration Tests**: بررسی عدم استفاده از raw SQL

### مثال‌های تست
```python
def test_sql_injection_blocked():
    malicious_inputs = [
        "'; DROP TABLE flights; --",
        "' OR 1=1 --", 
        "UNION SELECT * FROM users",
        "<script>alert('xss')</script>"
    ]
    
    for malicious_input in malicious_inputs:
        with pytest.raises(ValueError):
            InputValidator.validate_airport_code(malicious_input)
```

## 📋 Security Checklist

### ✅ Database Security
- [x] استفاده از SQLAlchemy ORM
- [x] عدم استفاده از raw SQL
- [x] Parameterized queries
- [x] Input validation برای تمام database operations

### ✅ Input Security  
- [x] Validation برای تمام user inputs
- [x] String sanitization
- [x] Type checking
- [x] Length limitations
- [x] Character whitelisting

### ✅ Error Handling
- [x] Security error logging
- [x] Graceful error handling
- [x] عدم افشای اطلاعات حساس در error messages

### ✅ Dependencies
- [x] Security libraries در requirements.txt:
  - `bleach>=6.0.0` - HTML sanitization
  - `validators>=0.20.0` - Input validation
  - `cryptography>=41.0.0` - Security functions
  - `python-slugify>=8.0.0` - Safe string generation

## 🚨 Security Monitoring

### Logging
تمام تلاش‌های امنیتی مشکوک ثبت می‌شوند:
```python
logger.error(f"Input validation error: {e}")
```

### Error Tracking
- Input validation errors
- SQL injection attempts  
- XSS attempts
- Invalid data format attempts

## 🔧 Security Configuration

### Environment Variables
```bash
# Database Security
DATABASE_USER=crawler_user
DATABASE_PASSWORD=secure_random_password
DATABASE_SSL_MODE=require

# Redis Security  
REDIS_PASSWORD=secure_redis_password
REDIS_SSL=true
```

### Best Practices for Deployment

#### 1. Database
- استفاده از dedicated database user با minimal permissions
- فعال‌سازی SSL/TLS connections
- Regular security updates

#### 2. Redis
- استفاده از password authentication
- فعال‌سازی SSL/TLS
- Network isolation

#### 3. Application
- Running with minimal privileges
- Input sanitization at multiple layers
- Regular dependency updates

## 🛠️ Security Maintenance

### Regular Tasks
1. **Dependency Updates**: بررسی و به‌روزرسانی ماهانه security libraries
2. **Security Tests**: اجرای تست‌های امنیتی در CI/CD pipeline
3. **Code Review**: بررسی امنیتی تمام تغییرات کد
4. **Monitoring**: پایش logs برای تشخیص تهدیدات

### Security Incident Response
1. **Detection**: از logs و monitoring
2. **Analysis**: بررسی نوع و شدت تهدید  
3. **Mitigation**: اقدامات فوری برای متوقف کردن حمله
4. **Recovery**: بازگردانی سرویس‌ها
5. **Post-Incident**: بررسی و بهبود امنیت

## 📞 Contact

برای گزارش مسائل امنیتی:
- Email: security@flightiocrawler.com
- تیکت در repository با label "security"

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/14/core/security.html)
- [Python Security Best Practices](https://python.org/dev/security/)

---

**نکته**: این document باید به‌روزرسانی شود هر زمان که تغییرات امنیتی جدیدی اعمال می‌شود. 