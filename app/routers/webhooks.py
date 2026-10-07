from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import settings
from app.database import get_db
from app.schemas import MessageCreate, MessageDB
from app.services.reply import send_reply

router = APIRouter()


@router.post('/messages', response_model=MessageDB)
async def post_message(
    message: MessageCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_webhook_secret: Annotated[str | None, Header()] = None,
):
    """
    Обработка сообщений из мессенджера.

    Если по чату нет активной заявки, функция создаёт заявку в БД и привязывает её к чату.
    После создания заявки выполняется шаблонный ответ пользователю.
    """
    # Проверка заголовка X-Webhook-Secret
    if x_webhook_secret is None or x_webhook_secret != settings.webhook_secret.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or missing X-Webhook-Secret header',
        )

    db_message = models.Message(
        bot_id=message.bot_id,
        message_id=message.message_id,
        chat_id=message.chat_id,
        user_id=message.user_id,
        text=message.text,
        ts=message.ts,
    )
    db.add(db_message)
    try:
        await db.commit()
        await db.refresh(db_message)
    except IntegrityError:
        await db.rollback()

        result = await db.execute(
            select(models.Message).where(
                models.Message.message_id == message.message_id,
            ),
        )
        db_message = result.scalar_one()

    response = MessageDB.model_validate(db_message)

    # Проверяем, есть ли открытая заявка по чату. Если нет - создаём её
    result = await db.execute(
        select(models.ChatApplication).where(
            models.ChatApplication.chat_id == message.chat_id,
            models.ChatApplication.status != 'closed',
        ),
    )
    created_application = False
    if result.scalars().first() is None:
        db.add(
            models.ChatApplication(
                chat_id=message.chat_id,
                user_id=message.user_id,
                operator_id=None,
                status='new',
                status_ts=datetime.now(timezone.utc),
            ),
        )
        try:
            await db.commit()
            created_application = True
        except IntegrityError:
            # Race Condition: по чату найдена активная заявка (проверка на стороне БД)
            await db.rollback()

    # Если делать проверку не на стороне БД, а на стороне Python:
    #
    # import asyncio  # Вынести на глобальный уровень
    # chat_locks: dict[int, asyncio.Lock] = {}  # Вынести на глобальный уровень (можно подключить Redis)
    # chat_locks_dict_lock = asyncio.Lock()  # Вынести на глобальный уровень
    #
    # async with chat_locks_dict_lock:
    #     chat_lock = chat_locks.setdefault(message.chat_id, asyncio.Lock())
    # async with chat_lock:
    #     result = await db.execute(
    #         select(models.ChatApplication).where(
    #             models.ChatApplication.chat_id == message.chat_id,
    #             models.ChatApplication.status != 'closed',
    #         ),
    #     )
    #     created_application = False
    #     if result.scalars().first() is None:
    #         db.add(
    #             models.ChatApplication(
    #                 chat_id=message.chat_id,
    #                 user_id=message.user_id,
    #                 operator_id=None,
    #                 status='new',
    #                 status_ts=datetime.now(timezone.utc),
    #             ),
    #         )
    #         await db.commit()
    #         created_application = True

    if created_application:
        background_tasks.add_task(send_reply, chat_id=message.chat_id)

    return response
