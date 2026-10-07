from __future__ import annotations

import asyncio
import logging

from app.services import stub_messenger

log = logging.getLogger(__name__)

SERVER_ERROR_BACKOFF_SECONDS = (0.5, 1.0, 2.0, 4.0)
MAX_REPLY_ATTEMPTS = len(SERVER_ERROR_BACKOFF_SECONDS) + 1


async def send_reply(chat_id: int) -> None:
    for attempt in range(MAX_REPLY_ATTEMPTS):
        try:
            await stub_messenger.reply(chat_id, 'Спасибо за обращение! Мы скоро вам ответим, ожидайте пожалуйста.')
            return
        except stub_messenger.StubMessengerRateLimitError as error:
            if attempt == MAX_REPLY_ATTEMPTS - 1:
                log.error(
                    'Не удалось отправить ответ после %s попыток chat_id=%s статус=429',
                    MAX_REPLY_ATTEMPTS,
                    chat_id,
                )
                return
            await asyncio.sleep(error.retry_after + 1)
        except stub_messenger.StubMessengerServerError as error:
            if attempt == MAX_REPLY_ATTEMPTS - 1:
                log.error(
                    'Не удалось отправить ответ после %s попыток chat_id=%s статус=%s',
                    MAX_REPLY_ATTEMPTS,
                    chat_id,
                    error.status_code,
                )
                return
            delay = SERVER_ERROR_BACKOFF_SECONDS[attempt]
            await asyncio.sleep(delay)
        except Exception as error:
            status_code = getattr(error, 'status_code', 'Unknown')
            log.error(
                'Ответ прерван chat_id=%s статус=%s',
                chat_id,
                status_code,
            )
            return
