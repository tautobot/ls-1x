from __future__ import annotations

import logging

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict


class SyncSettings(BaseSettings):
    """Trimmed settings for the live-match sync subsystem.

    Ported (and trimmed) from agent.livescore's ``src/config.py`` — DB/redis/betor
    fields dropped. Kept deliberately separate from ``livescore/config.py`` so the sync
    subsystem never entangles with the legacy fetch code (``livescore/apis.py``,
    ``livescore/utils.py``).

    Env var names are prefixed ``SYNC_`` to avoid colliding with ls-1x's *legacy*
    ``X8_BASE_URL`` / ``X8_DOMAIN`` (already defined in ``.env`` and consumed by the
    legacy fetch path). If ``SYNC_*`` is unset, the hardcoded provider defaults below
    are used — the providers need no secrets, only base URLs.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SYNC_",
        extra="ignore",
    )

    # 1xBet provider
    x1_base_url: str = "https://1xbet.mobi"
    x1_domain: str = "1xbet.mobi"

    # 8xBet provider
    x8_base_url: str = "https://api.8xbet.com"
    x8_origin: str = "https://8xbet.com"
    x8_domain: str = "api.8xbet.com"

    # Loop timing (seconds)
    match_finder_interval: int = 30
    match_updater_interval: int = 10

    log_level: str = "INFO"

    # Optional outbound proxy for provider HTTP requests. Bookmakers often block
    # datacenter IP ranges (e.g. Streamlit Community Cloud), so from a blocked host
    # set SYNC_HTTP_PROXY to a proxy in an allowed region, e.g.
    # "http://user:pass@host:port". Empty/unset => direct connection.
    http_proxy: str | None = None


settings = SyncSettings()


def configure_logging() -> None:
    """Configure structlog for the sync subsystem.

    Ported from agent.livescore's ``configure_logging`` — JSON output by default,
    human-readable console output when ``SYNC_LOG_LEVEL=DEBUG``.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            # Render exc_info into the output. Without this, JSONRenderer drops the
            # traceback entirely (logs show only "exc_info": true) — which is why a
            # provider failure on Streamlit Cloud was undiagnosable.
            structlog.processors.format_exc_info,
            (
                structlog.dev.ConsoleRenderer()
                if settings.log_level == "DEBUG"
                else structlog.processors.JSONRenderer()
            ),
        ],
        # NOTE: logging.getLevelNamesMapping() is Python 3.11+ only. ls-1x targets
        # 3.10.11, so resolve the level name -> int via getattr (3.10-safe).
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
