"""Optional Sentry error tracking integration.

Lazy-initialized only when SENTRY_DSN environment variable is set
and sentry-sdk is installed (via `pip install tunacode-cli[observability]`).
"""

from __future__ import annotations

import os

SENTRY_DSN_ENV = "SENTRY_DSN"
SENTRY_ENVIRONMENT_ENV = "SENTRY_ENVIRONMENT"
DEFAULT_ENVIRONMENT = "production"

TRACES_SAMPLE_RATE_DISABLED: float = 0.0

_sentry_initialized: bool = False


def init_sentry() -> bool:
    """Initialize Sentry if DSN is configured and SDK is available.

    Returns True if Sentry was successfully initialized, False otherwise.
    """
    global _sentry_initialized

    if _sentry_initialized:
        return True

    dsn = os.environ.get(SENTRY_DSN_ENV)
    if not dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        return False

    from tunacode.constants import APP_VERSION

    environment = os.environ.get(SENTRY_ENVIRONMENT_ENV, DEFAULT_ENVIRONMENT)

    try:
        sentry_sdk.init(
            dsn=dsn,
            release=APP_VERSION,
            environment=environment,
            traces_sample_rate=TRACES_SAMPLE_RATE_DISABLED,
            attach_stacktrace=True,
        )
    except Exception:
        return False

    _sentry_initialized = True
    return True


def _reset_sentry() -> None:
    """Reset Sentry initialization state (for test teardown)."""
    global _sentry_initialized
    _sentry_initialized = False


def capture_exception(error: BaseException) -> None:
    """Send exception to Sentry. No-op if Sentry is not initialized."""
    if not _sentry_initialized:
        return

    import sentry_sdk

    sentry_sdk.capture_exception(error)
