import time
from persian_text import PersianTextProcessor


def test_parse_time_performance():
    processor = PersianTextProcessor()
    start = time.time()
    processor.parse_time("۱۰:۳۰ صبح")
    assert time.time() - start < 1
