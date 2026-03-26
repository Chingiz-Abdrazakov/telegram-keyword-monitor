import os
import re
import time
import asyncio
from typing import Pattern, Set

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
DEST_CHAT_ID = int(os.environ["DEST_CHAT_ID"])
SESSION_NAME = os.environ.get("SESSION_NAME", "server_monitor_session")
COOLDOWN = int(os.environ.get("COOLDOWN", "10"))
KEYWORDS_FILE = os.environ.get("KEYWORDS_FILE", "keywords.txt")
SOURCE_CHATS_FILE = os.environ.get("SOURCE_CHATS_FILE", "source_chats.txt")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
last_trigger_time = 0.0


def load_keywords(path: str = KEYWORDS_FILE) -> list[str]:
    """
    Загружает список ключевых слов из текстового файла.

    Каждая непустая строка файла считается отдельным ключевым словом.
    Пробелы в начале и конце строки автоматически обрезаются.

    Args:
        path (str): Путь до файла с ключевыми словами.

    Returns:
        list[str]: Список ключевых слов.
    """
    with open(path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def load_source_chat_ids(path: str = SOURCE_CHATS_FILE) -> Set[int]:
    """
    Загружает список ID чатов Telegram, которые необходимо отслеживать.

    Каждая непустая строка файла должна содержать один chat_id.

    Args:
        path (str): Путь до файла со списком chat_id.

    Returns:
        Set[int]: Множество ID чатов.
    """
    with open(path, "r", encoding="utf-8") as file:
        return {int(line.strip()) for line in file if line.strip()}


def build_pattern(keywords: list[str]) -> Pattern[str]:
    """
    Строит регулярное выражение для поиска ключевых слов в тексте.

    Используется поиск по границе слова с учетом возможных окончаний.

    Args:
        keywords (list[str]): Список ключевых слов.

    Returns:
        Pattern[str]: Скомпилированное регулярное выражение.
    """
    escaped_keywords = [re.escape(keyword) for keyword in keywords]
    return re.compile(
        r"\b(" + "|".join(escaped_keywords) + r")\w*\b",
        re.IGNORECASE,
    )


def build_message_link(chat, chat_id: int, message_id: int) -> str:
    """
    Формирует ссылку на сообщение в Telegram.

    Для публичных чатов используется формат через username.
    Для приватных супергрупп используется формат /c/.

    Args:
        chat: Объект чата Telegram.
        chat_id (int): ID чата.
        message_id (int): ID сообщения.

    Returns:
        str: Ссылка на сообщение или сообщение об отсутствии ссылки.
    """
    chat_username = getattr(chat, "username", None)
    if chat_username:
        return f"https://t.me/{chat_username}/{message_id}"

    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        internal_id = chat_id_str[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"

    return "ссылка недоступна"


def build_sender_display(sender) -> str:
    """
    Формирует отображаемое имя отправителя.

    Если у пользователя есть username, он добавляется в формате (@username).

    Args:
        sender: Объект отправителя сообщения.

    Returns:
        str: Строка с именем и username, если он есть.
    """
    name = (
        getattr(sender, "first_name", None)
        or getattr(sender, "title", None)
        or "Unknown"
    )
    username = getattr(sender, "username", None)

    if username:
        return f"{name} (@{username})"

    return name


def build_alert_message(
    chat_title: str,
    sender_display: str,
    text: str,
    triggers: list[str],
    message_link: str,
) -> str:
    """
    Формирует итоговое уведомление для отправки в Telegram.

    Сообщение включает чат, отправителя, текст, триггеры и ссылку.

    Args:
        chat_title (str): Название чата.
        sender_display (str): Отображаемое имя отправителя.
        text (str): Оригинальный текст сообщения.
        triggers (list[str]): Найденные ключевые слова.
        message_link (str): Ссылка на сообщение.

    Returns:
        str: Готовое уведомление.
    """
    short_text = text[:300] + "..." if len(text) > 300 else text

    return (
        f"🚨 СИГНАЛ\n\n"
        f"💬 Чат: {chat_title}\n"
        f"👤 От: {sender_display}\n\n"
        f"📝 Сообщение:\n{short_text}\n\n"
        f"🔑 Триггеры: {', '.join(triggers)}\n\n"
        f"🔗 {message_link}"
    )


@client.on(events.NewMessage)
async def handler(event) -> None:
    """
    Обрабатывает входящие сообщения Telegram и отправляет уведомления.

    Args:
        event: Событие нового сообщения Telethon.
    """
    global last_trigger_time

    source_chat_ids = load_source_chat_ids()
    if event.chat_id not in source_chat_ids:
        return

    text = event.raw_text or ""
    if not text:
        return

    keywords = load_keywords()
    if not keywords:
        return

    pattern = build_pattern(keywords)
    matches = pattern.findall(text)
    if not matches:
        return

    now = time.time()
    if now - last_trigger_time < COOLDOWN:
        return
    last_trigger_time = now

    triggers = sorted(set(matches), key=str.lower)

    chat = await event.get_chat()
    sender = await event.get_sender()

    chat_title = getattr(chat, "title", "Личный чат")
    sender_display = build_sender_display(sender)
    message_link = build_message_link(chat, event.chat_id, event.id)

    alert = build_alert_message(
        chat_title=chat_title,
        sender_display=sender_display,
        text=text,
        triggers=triggers,
        message_link=message_link,
    )

    await client.send_message(DEST_CHAT_ID, alert)
    print(alert)


async def main() -> None:
    """
    Запускает Telegram-клиент и переводит его в режим прослушивания.
    """
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
