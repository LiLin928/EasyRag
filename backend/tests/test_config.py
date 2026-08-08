import pytest
from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("INIT_ADMIN_PASSWORD", "pw12345")
    s = Settings(_env_file=None)            # ignore .env, use monkeypatched env only
    assert s.database_url == "postgresql+asyncpg://u:p@host/db"
    assert s.secret_key == "test-secret"
    assert s.jwt_access_expire == 7200       # default
    assert s.api_prefix == "/api/v2"          # default


def test_settings_missing_required_raises(monkeypatch):
    for k in ("DATABASE_URL", "SECRET_KEY", "INIT_ADMIN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(Exception):
        Settings(_env_file=None)             # no .env, no env → required fields missing
