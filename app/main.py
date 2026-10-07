import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, engine, get_db
from app.logger import RequestIdMiddleware, configure_logging, shutdown_logging
from app.routers import webhooks, chats

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    listener = configure_logging(level=settings.log_level)
    log.info('Запуск приложения')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info('Приложение запущено')
        yield
    finally:
        log.info('Приложение завершает работу')
        try:
            await engine.dispose()
        finally:
            shutdown_logging(listener)


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)

app.include_router(webhooks.router, prefix='/webhooks', tags=['webhooks'])
app.include_router(chats.router, prefix='/chats', tags=['chats'])


@app.get('/health')
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text('SELECT 1'))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable',
        ) from exc
    return {'status': 'healthy'}


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
):
    log_request_error = log.error if exception.status_code >= 500 else log.warning
    log_request_error(
        'Ошибка запроса метод=%s путь=%s статус=%s описание=%s',
        request.method,
        request.url.path,
        exception.status_code,
        exception.detail,
    )
    return await http_exception_handler(request, exception)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
):
    log.warning(
        'Ошибка валидации метод=%s путь=%s ошибки=%s',
        request.method,
        request.url.path,
        exception.errors(),
    )
    return await request_validation_exception_handler(request, exception)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
):
    log.exception(
        'Необработанная ошибка метод=%s путь=%s тип=%s',
        request.method,
        request.url.path,
        type(exception).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'detail': 'Internal Server Error'},
    )
