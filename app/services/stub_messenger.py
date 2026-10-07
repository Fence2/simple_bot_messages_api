"""Фейковый внешний мессенджер.

Имитирует медленный HTTP-запрос и периодические 429 / 5xx.
"""

from __future__ import annotations

import asyncio
import logging
import random

log = logging.getLogger('stub_messenger')
log.setLevel(logging.INFO)

MIN_DELAY_SECONDS = 0.5
MAX_DELAY_SECONDS = 3.0
RATE_LIMIT_PROBABILITY = 0.10
SERVER_ERROR_PROBABILITY = 0.10
SERVER_ERROR_CODES = (500, 502, 503)


class StubMessengerError(Exception):
    """Ошибка ответа фейкового мессенджера."""

    def __init__(self, status_code: int, description: str) -> None:
        self.status_code = status_code
        self.description = description
        super().__init__(f'{status_code}: {description}')


class StubMessengerRateLimitError(StubMessengerError):
    """HTTP 429 Too Many Requests."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(
            429,
            f'Too Many Requests: retry after {retry_after}',
        )


class StubMessengerServerError(StubMessengerError):
    """HTTP 5xx со стороны фейкового мессенджера."""

    def __init__(self, status_code: int) -> None:
        super().__init__(status_code, 'Internal Server Error')


async def reply(chat_id: int, text: str) -> None:
    """Фейковый запрос reply(chat_id, text) во внешний мессенджер."""
    if not text:
        raise StubMessengerError(400, 'Bad Request: message text is empty')

    delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
    log.info('chat_id=%s задержка=%.2fs', chat_id, delay)
    await asyncio.sleep(delay)

    roll = random.random()
    if roll < RATE_LIMIT_PROBABILITY:
        retry_after = random.randint(1, 5)
        log.warning(
            'chat_id=%s статус=429 повтор_через=%s',
            chat_id,
            retry_after,
        )
        raise StubMessengerRateLimitError(retry_after)

    if roll < RATE_LIMIT_PROBABILITY + SERVER_ERROR_PROBABILITY:
        status_code = random.choice(SERVER_ERROR_CODES)
        log.error('chat_id=%s статус=%s', chat_id, status_code)
        raise StubMessengerServerError(status_code)

    log.info('chat_id=%s статус=200', chat_id)
