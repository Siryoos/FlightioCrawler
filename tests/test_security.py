from config import config


def test_secret_key_exists():
    assert hasattr(config, "SECRET_KEY")
