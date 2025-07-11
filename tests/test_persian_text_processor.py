import datetime
import sys
import types
import pytest


# Provide a minimal stub for the config module required by persian_text
@pytest.fixture(autouse=True)
def patch_config(monkeypatch):
    stub = types.ModuleType("config")
    stub.config = object()
    monkeypatch.setitem(sys.modules, "config", stub)


from persian_text import PersianTextProcessor


def test_extract_price():
    processor = PersianTextProcessor()
    price, currency = processor.extract_price("قیمت این بلیط ۳۰۰,۰۰۰ تومان")
    assert price == 300000.0
    assert currency == "IRR"


def test_parse_persian_date():
    processor = PersianTextProcessor()
    # Persian date 1402/08/15 should correspond to Gregorian date 2023-11-06
    result = processor.parse_persian_date("۱۴۰۲/۰۸/۱۵")
    assert isinstance(result, datetime.datetime)
    assert result.date() == datetime.date(2023, 11, 6)


def test_parse_time():
    processor = PersianTextProcessor()
    result = processor.parse_time("۱۰:۳۰ صبح")
    assert isinstance(result, datetime.datetime)
    assert result.hour == 10
    assert result.minute == 30


def test_extract_duration_hours():
    processor = PersianTextProcessor()
    assert processor.extract_duration("۲ ساعت") == 120


def test_extract_duration_minutes():
    processor = PersianTextProcessor()
    assert processor.extract_duration("۹۰") == 90


def test_extract_duration_hours_and_minutes():
    processor = PersianTextProcessor()
    # "۲ ساعت و ۳۰ دقیقه" should be 150 minutes
    assert processor.extract_duration("۲ ساعت و ۳۰ دقیقه") == 150
