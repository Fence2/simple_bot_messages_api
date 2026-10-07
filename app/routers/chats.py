from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_db
from app.schemas import ChatApplicationDB, TakeChat

router = APIRouter()


@router.post('/{chat_id}/take', response_model=ChatApplicationDB)
async def take_chat(
    chat_id: int,
    body: TakeChat,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Оператор забирает свободный диалог.

    Если диалог уже был занят, возвращает ошибку 409.
    """
    result = await db.execute(
        select(models.ChatApplication)
        .where(
            models.ChatApplication.chat_id == chat_id,
            models.ChatApplication.status != 'closed',
        )
        .with_for_update(),  # Блокируем объект в БД, чтобы его не изменил другой процесс/поток
    )

    chat_application: models.ChatApplication | None = result.scalar_one_or_none()
    if chat_application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Open chat application not found',
        )

    if chat_application.operator_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Chat is already taken',
        )

    chat_application.operator_id = body.operator_id
    chat_application.status = 'in_progress'
    chat_application.status_ts = datetime.now(timezone.utc)

    await db.commit()
    return chat_application
