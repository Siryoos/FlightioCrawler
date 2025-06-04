from data_manager import DataManager


def test_generate_cache_key():
    dm = DataManager.__new__(DataManager)
    params = {
        "origin": "THR",
        "destination": "MHD",
        "departure_date": "2024-01-01",
        "passengers": 1,
        "seat_class": "economy",
    }
    key = dm._generate_cache_key(params)
    assert key == "search:THR:MHD:2024-01-01:1:economy"
