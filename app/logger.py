import fcntl
import logging
import re
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from queue import Queue
from typing import TextIO
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_LOG_FORMAT = (
    '{asctime}.{msecs:03.0f} | '
    '{levelname:<8} | '
    '{name}:{funcName}:{lineno} | '
    '[{request_id}] {message}'
)

_request_id: ContextVar[str] = ContextVar(
    'request_id',
    default='-',
)

_REQUEST_ID_RE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')


class RequestIdFilter(logging.Filter):
    """Добавляет request ID в запись логирования."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Добавляет request ID в запись логирования."""
        record.request_id = _request_id.get()
        return True


class DailyFileHandler(logging.Handler):
    """Записывает логи в отдельный файл для каждого дня."""

    def __init__(
        self,
        base_dir: Path,
        encoding: str = 'utf-8',
    ) -> None:
        """Инициализирует обработчик.

        Args:
            base_dir: Корневая директория логов.
            encoding: Кодировка файлов.
        """
        super().__init__()

        self.base_dir = base_dir
        self.encoding = encoding
        self.stream: TextIO | None = None
        self.current_date: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        """Записывает лог в файл соответствующей даты.

        Args:
            record: Запись логирования.
        """
        try:
            record_datetime = datetime.fromtimestamp(record.created)
            log_date = record_datetime.date().isoformat()

            if log_date != self.current_date:
                if self.stream is not None:
                    self.stream.close()

                directory = (
                    self.base_dir
                    / f'{record_datetime.year:04d}'
                    / f'{record_datetime.month:02d}'
                )
                directory.mkdir(parents=True, exist_ok=True)

                self.stream = (
                    directory / f'{log_date}.log'
                ).open(
                    mode='a',
                    encoding=self.encoding,
                    buffering=1,
                )

                self.current_date = log_date

            if self.stream is None:
                raise RuntimeError('Log file is not opened')

            message = self.format(record)

            fcntl.flock(
                self.stream.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                self.stream.write(f'{message}\n')
                self.stream.flush()
            finally:
                fcntl.flock(
                    self.stream.fileno(),
                    fcntl.LOCK_UN,
                )

        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Закрывает текущий файл логов."""
        if self.stream is not None:
            self.stream.close()
            self.stream = None

        super().close()


class RequestIdMiddleware:
    """Добавляет request ID в контекст HTTP-запроса."""

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = 'X-Request-ID',
    ) -> None:
        """Инициализирует middleware.

        Args:
            app: ASGI-приложение.
            header_name: Имя HTTP-заголовка с request ID.
        """
        self.app = app
        self.header_name = header_name.lower().encode('ascii')

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Обрабатывает HTTP-запрос.

        Args:
            scope: ASGI scope.
            receive: Функция получения ASGI-сообщений.
            send: Функция отправки ASGI-сообщений.
        """
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request_id = None

        for name, value in scope.get('headers', []):
            if name.lower() != self.header_name:
                continue

            try:
                candidate = value.decode('ascii').strip()
            except UnicodeDecodeError:
                break

            if _REQUEST_ID_RE.fullmatch(candidate):
                request_id = candidate

            break

        request_id = request_id or uuid4().hex
        token = _request_id.set(request_id)

        async def send_with_request_id(
            message: Message,
        ) -> None:
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.append(
                    (
                        self.header_name,
                        request_id.encode('ascii'),
                    )
                )
                message['headers'] = headers

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )
        finally:
            _request_id.reset(token)


def configure_logging(
    *,
    level: int | str = logging.INFO,
    logs_dir: Path = Path('logs'),
    log_format: str = DEFAULT_LOG_FORMAT,
) -> QueueListener:
    """Настраивает логирование приложения.

    Args:
        level: Уровень логирования.
        logs_dir: Корневая директория файлов логов.
        log_format: Формат записей логирования.

    Returns:
        Запущенный listener очереди логирования.
    """
    formatter = logging.Formatter(
        fmt=log_format,
        datefmt='%H:%M:%S',
        style='{',
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = DailyFileHandler(logs_dir)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    log_queue: Queue[logging.LogRecord] = Queue()

    queue_handler = QueueHandler(log_queue)
    queue_handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.addHandler(queue_handler)

    for logger_name in (
            'uvicorn',
            'uvicorn.error',
            'uvicorn.access',
            'fastapi',
    ):
        logger = logging.getLogger(logger_name)

        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    listener = QueueListener(
        log_queue,
        console_handler,
        file_handler,
        respect_handler_level=True,
    )
    listener.start()

    return listener


def shutdown_logging(listener: QueueListener) -> None:
    """Останавливает логирование.

    Args:
        listener: Запущенный listener логирования.
    """
    listener.stop()

    for handler in listener.handlers:
        handler.close()
