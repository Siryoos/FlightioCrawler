import os
import re
from bs4 import BeautifulSoup

PAGES_DIR = os.path.join(os.path.dirname(__file__), os.pardir, 'requests', 'pages')


def page_has_flight_results(html: str) -> bool:
    """Simple heuristic to check if a saved page contains flight listings."""
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.resu, .flight-result, .flight-item'):
        return True
    price_text = soup.find(string=re.compile(r'\d{1,3}(,\d{3})+'))
    return bool(price_text)


def replay_all() -> dict:
    results = {}
    for name in os.listdir(PAGES_DIR):
        if not name.endswith('.html'):
            continue
        path = os.path.join(PAGES_DIR, name)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        results[name] = page_has_flight_results(html)
    return results


if __name__ == '__main__':
    summary = replay_all()
    for file, ok in summary.items():
        status = 'OK' if ok else 'MISSING'
        print(f'{file}: {status}')
