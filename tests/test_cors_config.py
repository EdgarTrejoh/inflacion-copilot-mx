import pytest

from api.cors import CorsConfigError, get_allowed_origins


def test_cors_defaults_to_local_vite_origins(monkeypatch):
    monkeypatch.delenv("COPILOT_ALLOWED_ORIGINS", raising=False)

    assert get_allowed_origins() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_accepts_multiple_configured_origins():
    assert get_allowed_origins(
        "https://app.example.test, https://admin.example.test/"
    ) == [
        "https://app.example.test",
        "https://admin.example.test",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "https://*.example.test",
        "javascript:alert(1)",
        "https://user:password@example.test",
        "https://example.test/path",
        "https://example.test?token=sensitive",
    ],
)
def test_cors_rejects_invalid_or_unsafe_origins(value):
    with pytest.raises(CorsConfigError, match="COPILOT_ALLOWED_ORIGINS"):
        get_allowed_origins(value)
