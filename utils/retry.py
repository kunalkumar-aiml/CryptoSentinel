"""
Retry utilities using tenacity.
- Exponential backoff with jitter
- Rate-limit aware (429 detection)
- Configurable per call-site
"""
import functools
from typing import Callable, Type, Tuple
from tenacity import (
    retry, stop_after_attempt, wait_exponential, wait_random,
    retry_if_exception_type, before_sleep_log, RetryError
)
import requests, httpx, logging
from utils.logger import get_logger

log = get_logger("retry")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)


def is_retryable_http(exc: Exception) -> bool:
    """Return True if exception should trigger a retry."""
    if isinstance(exc, requests.exceptions.HTTPError):
        return exc.response is not None and exc.response.status_code in RETRYABLE_STATUS
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


def with_retry(
    attempts: int = 4,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    jitter: float = 1.0,
):
    """
    Decorator: retry with exponential backoff + jitter.
    Example:
        @with_retry(attempts=4, max_wait=20)
        def call_api():
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            retryer = retry(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait) + wait_random(0, jitter),
                retry=retry_if_exception_type((*RETRYABLE_EXCEPTIONS, Exception)),
                before_sleep=before_sleep_log(logging.getLogger("retry"), logging.WARNING),
                reraise=True,
            )
            return retryer(fn)(*args, **kwargs)
        return wrapper
    return decorator


def with_retry_async(
    attempts: int = 4,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
):
    """Async version of with_retry."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            from tenacity import AsyncRetrying
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait) + wait_random(0, 1),
                reraise=True,
            ):
                with attempt:
                    return await fn(*args, **kwargs)
        return wrapper
    return decorator
