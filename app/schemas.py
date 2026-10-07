from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
