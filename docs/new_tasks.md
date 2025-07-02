# Future Work for Real Data Crawling

The following tasks aim to improve the reliability of data collection across targeted travel sites:

1. **Automate Request Replay**
   - Implement a script to iterate over saved requests in `requests/pages` and verify that each page contains valid flight results.
   - Schedule periodic runs to refresh snapshots and ensure data accuracy.

2. **Enhance Site-Specific Crawlers**
   - Review each crawler in `site_crawlers.py` to confirm selectors reflect current DOM structures.
   - Add fallback logic for sites that rely heavily on JavaScript or API endpoints.

3. **Centralize Sanitized Filenames**
   - Consolidate filename sanitization to avoid inconsistencies like the `https_parto-ticket` prefix.
   - Include query parameters in a normalized way to prevent collisions.

4. **Update Documentation**
   - Sync `docs/real_data_setup.md` with current crawler implementations.
   - Provide examples of real scraping runs and expected output schemas.

5. **Expand Test Coverage**
   - Add unit tests for `AdvancedCrawler.sanitize_filename` and the real data validators.
   - Mock network interactions to keep tests deterministic.

