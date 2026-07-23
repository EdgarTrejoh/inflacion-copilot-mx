import os
from urllib.parse import urlparse


DEFAULT_LOCAL_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class CorsConfigError(RuntimeError):
    pass


def _validate_origin(origin: str) -> str:
    if origin == "*" or "*" in origin:
        raise CorsConfigError(
            "COPILOT_ALLOWED_ORIGINS no admite origenes comodin."
        )

    parsed = urlparse(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise CorsConfigError(
            "COPILOT_ALLOWED_ORIGINS contiene un origen invalido."
        )

    return origin.rstrip("/")


def get_allowed_origins(value: str | None = None) -> list[str]:
    configured = os.getenv("COPILOT_ALLOWED_ORIGINS") if value is None else value
    if configured is None or not configured.strip():
        return list(DEFAULT_LOCAL_ORIGINS)

    origins = [item.strip() for item in configured.split(",") if item.strip()]
    if not origins:
        raise CorsConfigError("COPILOT_ALLOWED_ORIGINS no contiene origenes validos.")

    return list(dict.fromkeys(_validate_origin(origin) for origin in origins))
