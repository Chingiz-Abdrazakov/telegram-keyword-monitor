import asyncio
import os
import re
import time

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
TARGET_CHAT_ID = int(os.environ["TARGET_CHAT_ID"])
DEST_CHAT_ID = int(os.environ["DEST_CHAT_ID"])
KEYWORDS_FILE = os.environ.get("KEYWORDS_FILE", "keywords.txt")

SESSION_NAME = "server_monitor_session"
COOLDOWN_SECONDS = 60

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
last_trigger_time = 0.0


def load_keywords(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def build_pattern(keywords: list[str]) -> re.Pattern:
    escaped = [re.escape(keyword) for keyword in keywords]
    return re.compile(r"\b(" + "|".join(escaped) + r")\w*\b", re.IGNORECASE)


@client.on(events.NewMessage)
async def handler(event):
    global last_trigger_time

    if event.chat_id != TARGET_CHAT_ID:
        return

    text = event.raw_text or ""
    if not text:
        return

    keywords = load_keywords(KEYWORDS_FILE)
    if not keywords:
        return

    pattern = build_pattern(keywords)
    match = pattern.search(text)
    if not match:
        return

    now = time.time()
    if now - last_trigger_time < COOLDOWN_SECONDS:
        return
    last_trigger_time = now

    chat = await event.get_chat()
    sender = await event.get_sender()

    chat_title = getattr(chat, "title", "Unknown")
    sender_name = (
        getattr(sender, "first_name", None)
        or getattr(sender, "username", None)
        or "Unknown"
    )

    keyword_found = match.group(0)

    alert = (
        f"Found keyword: {keyword_found}\n"
        f"Chat: {chat_title}\n"
        f"From: {sender_name}\n"
        f"Message: {text}"
    )

    await client.send_message(DEST_CHAT_ID, alert)


async def main():
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
