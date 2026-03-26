import asyncio
import os
import re
import time

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

DEST_CHAT_ID = -5202871265

SESSION_NAME = "server_monitor_session"
COOLDOWN = 10
last_trigger_time = 0.0

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


def load_keywords() -> list[str]:
    with open("keywords.txt", "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def load_source_chat_ids() -> set[int]:
    with open("source_chats.txt", "r", encoding="utf-8") as file:
        return {int(line.strip()) for line in file if line.strip()}


def build_pattern(keywords: list[str]) -> re.Pattern:
    return re.compile(
        r"\b(" + "|".join(map(re.escape, keywords)) + r")\w*\b",
        re.IGNORECASE,
    )


@client.on(events.NewMessage)
async def handler(event):
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
    name = (
        getattr(sender, "first_name", None)
        or getattr(sender, "title", None)
        or "Unknown"
    )
    username = getattr(sender, "username", None)

    if username:
        sender_display = f"{name} (@{username})"
    else:
        sender_display = name

    chat_username = getattr(chat, "username", None)
    if chat_username:
        message_link = f"https://t.me/{chat_username}/{event.id}"
    else:
        chat_id_str = str(event.chat_id)
        if chat_id_str.startswith("-100"):
            internal_id = chat_id_str[4:]
            message_link = f"https://t.me/c/{internal_id}/{event.id}"
        else:
            message_link = "ссылка недоступна"

    short_text = text[:300] + "..." if len(text) > 300 else text

    alert = (
        f"🚨 СИГНАЛ\n\n"
        f"💬 Чат: {chat_title}\n"
        f"👤 От: {sender_display}\n\n"
        f"📝 Сообщение:\n{short_text}\n\n"
        f"🔑 Триггеры: {', '.join(triggers)}\n\n"
        f"🔗 {message_link}"
    )

    await client.send_message(DEST_CHAT_ID, alert)
    print(alert)


async def main():
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
