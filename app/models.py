from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Identity,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Message(Base):
    __tablename__ = 'message'
    __table_args__ = (
        Index('ix_message_chat_id_user_id', 'chat_id', 'user_id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatApplication(Base):
    __tablename__ = 'chat_application'

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Статус в виде строки со свободным вводом. Позже можно вынести в отдельный PostgreSQL ENUM type.
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
