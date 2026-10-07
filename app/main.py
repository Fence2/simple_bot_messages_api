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

from app.database import Base, engine, get_db
from app.routers import webhooks, chats


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)

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
    return await http_exception_handler(request, exception)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
):
    return await request_validation_exception_handler(request, exception)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'detail': 'Internal Server Error'},
    )
