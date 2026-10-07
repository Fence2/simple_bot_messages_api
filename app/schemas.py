from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    bot_id: int
    message_id: int
    chat_id: int
    user_id: int
    text: str
    ts: datetime


class MessageDB(MessageCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TakeChat(BaseModel):
    operator_id: int = Field(gt=0)


class ChatApplicationBase(BaseModel):
    operator_id: int | None


class ChatApplicationDB(ChatApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    user_id: int
    status: str | Literal['new', 'in_progress', 'closed'] = Field(min_length=1, max_length=32)
    status_ts: datetime
