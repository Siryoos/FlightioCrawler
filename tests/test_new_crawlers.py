from config import config
import re

with open('site_crawlers.py', 'r', encoding='utf-8') as f:
    SITE_CRAWLERS_TEXT = f.read()

EXPECTED_DOMAINS = {
    'flightio.com',
    'flytoday.ir',
    'alibaba.ir',
    'safarmarket.com',
    'mz724.ir',
    'partocrs.com',
    'parto-ticket.ir',
    'bookcharter724.ir',
    'bookcharter.ir',
    'mrbilit.com',
    'snapptrip.com',
}

def test_domains_list():
    for domain in EXPECTED_DOMAINS:
        assert domain in config.CRAWLER.DOMAINS

def test_crawler_classes_exist():
    for cls in [
        'FlightioCrawler',
        'Mz724Crawler',
        'PartoCRSCrawler',
        'PartoTicketCrawler',
        'BookCharter724Crawler',
        'BookCharterCrawler',
        'MrbilitCrawler',
        'SnapptripCrawler',
    ]:
        assert re.search(rf'class\s+{cls}\b', SITE_CRAWLERS_TEXT)
