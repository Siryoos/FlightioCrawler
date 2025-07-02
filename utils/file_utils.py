import re
from urllib.parse import urlparse, parse_qs


def sanitize_filename(url: str) -> str:
    """Return a safe, normalized filename for storing a page snapshot."""
    parsed = urlparse(url)
    base = f"{parsed.netloc}{parsed.path}"
    query = parse_qs(parsed.query)
    if query:
        normalized = "_".join(f"{k}={v[0]}" for k, v in sorted(query.items()))
        base = f"{base}_{normalized}"
    # Replace unsupported characters
    filename = re.sub(r"[^\w\-_.]", "_", base)
    return filename[:200]
