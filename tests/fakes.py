"""Minimal Telegram test doubles — no network, no token, no event loop tricks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []

    async def send_message(self, chat_id, text, **kwargs):
        record = {"chat_id": chat_id, "text": text, **kwargs}
        self.messages.append(record)
        return FakeMessage(text=text)

    async def send_document(self, chat_id, document, filename=None, caption=None, **kwargs):
        payload = document
        if hasattr(payload, "read"):
            payload = payload.read()
        self.documents.append(
            {"chat_id": chat_id, "filename": filename, "caption": caption, "bytes": payload}
        )
        return FakeMessage(text=caption or "")

    @property
    def texts(self) -> list[str]:
        return [message["text"] for message in self.messages]


@dataclass
class FakeContact:
    phone_number: str
    user_id: int | None = None
    first_name: str = "تست"


@dataclass
class FakeChat:
    id: int = 500
    type: str = "private"


@dataclass
class FakeUser:
    id: int = 500
    first_name: str = "سارا"
    last_name: str | None = None
    username: str | None = "sara"
    is_bot: bool = False


@dataclass
class FakeMessage:
    text: str | None = None
    contact: FakeContact | None = None
    document: Any = None
    chat: FakeChat = field(default_factory=FakeChat)
    reply_to_message: "FakeMessage | None" = None
    caption: str | None = None
    replies: list[dict[str, Any]] = field(default_factory=list)

    async def reply_text(self, text, **kwargs):
        self.replies.append({"text": text, **kwargs})
        return FakeMessage(text=text)


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage = field(default_factory=FakeMessage)
    answers: list[dict[str, Any]] = field(default_factory=list)
    edits: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text=None, show_alert=False, **kwargs):
        self.answers.append({"text": text, "alert": show_alert})

    async def edit_message_text(self, text, **kwargs):
        self.edits.append({"text": text, **kwargs})
        return FakeMessage(text=text)


class FakeUpdate:
    def __init__(
        self,
        *,
        message: FakeMessage | None = None,
        callback_query: FakeCallbackQuery | None = None,
        user: FakeUser | None = None,
        chat: FakeChat | None = None,
    ) -> None:
        self.effective_message = message
        self.callback_query = callback_query
        self.effective_user = user or FakeUser()
        self.effective_chat = chat or (message.chat if message else FakeChat())


class FakeContext:
    def __init__(self, bot: FakeBot | None = None) -> None:
        self.bot = bot or FakeBot()
        self.user_data: dict[str, Any] = {}
        self.chat_data: dict[str, Any] = {}
        self.bot_data: dict[str, Any] = {}
        self.error: BaseException | None = None


def text_update(text: str, user_id: int = 500) -> tuple[FakeUpdate, FakeMessage]:
    message = FakeMessage(text=text, chat=FakeChat(id=user_id))
    update = FakeUpdate(message=message, user=FakeUser(id=user_id))
    return update, message


def contact_update(phone: str, user_id: int = 500, owner: int | None = None):
    contact = FakeContact(phone_number=phone, user_id=user_id if owner is None else owner)
    message = FakeMessage(contact=contact, chat=FakeChat(id=user_id))
    update = FakeUpdate(message=message, user=FakeUser(id=user_id))
    return update, message


def callback_update(data: str, user_id: int = 500):
    query = FakeCallbackQuery(data=data, message=FakeMessage(chat=FakeChat(id=user_id)))
    update = FakeUpdate(
        callback_query=query, user=FakeUser(id=user_id), chat=FakeChat(id=user_id)
    )
    update.effective_message = query.message
    return update, query
