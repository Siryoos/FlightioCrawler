# Production Setup Guide

This document summarizes how to run the crawler against live Iranian travel websites.

1. **Validate Target Websites**
   
   Run the `production_url_validator` module to check connectivity, response times,
   robots.txt rules and potential anti-bot blocks for each configured site:
   ```bash
   python -m production_url_validator
   ```
   Review the output and disable any site that fails validation.

2. **Configure Production Endpoints**
   
   The file `config.py` defines `PRODUCTION_SITES` with real URLs and headers.
   Adjust rate limits or timeouts if needed.

3. **Run Crawlers Safely**
   
   Use `ProductionSafetyCrawler` to wrap your site crawler instances:
   ```python
   from production_safety_crawler import ProductionSafetyCrawler
   safety = ProductionSafetyCrawler()
   results = await safety.safe_crawl_with_verification("flytoday", crawler, params)
   ```
   This applies rate limiting, circuit breakers and robots.txt checks.

4. **Verify and Monitor**
   
   - `verify_website_individually` in `site_verifier.py` performs a full feature
     test on each site.
   - `ProductionMonitoring` exposes real-time metrics and can alert on issues.

5. **Quality Assurance**
   
   After scraping, pass the results through `RealDataQualityChecker` to ensure
   prices and times are realistic before storing them.
