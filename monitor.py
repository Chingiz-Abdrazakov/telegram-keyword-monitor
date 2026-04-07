import os
import re
import time
import asyncio
import hashlib
from typing import Pattern, Set

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
DEST_CHAT_ID = int(os.environ["DEST_CHAT_ID"])
SESSION_NAME = os.environ.get("SESSION_NAME", "server_monitor_session")
COOLDOWN = int(os.environ.get("COOLDOWN", "10"))
SOURCE_CHATS_FILE = os.environ.get("SOURCE_CHATS_FILE", "source_chats.txt")
INTENT_KEYWORDS_FILE = os.environ.get("INTENT_KEYWORDS_FILE", "intent_keywords.txt")
PRODUCT_KEYWORDS_FILE = os.environ.get("PRODUCT_KEYWORDS_FILE", "product_keywords.txt")
NEGATIVE_KEYWORDS_FILE = os.environ.get("NEGATIVE_KEYWORDS_FILE", "negative_keywords.txt")
SENDER_BLACKLIST_FILE = os.environ.get("SENDER_BLACKLIST_FILE", "sender_blacklist.txt")
MESSAGE_DELAY_SECONDS = int(os.environ.get("MESSAGE_DELAY_SECONDS", "60"))
DEDUP_TTL_SECONDS = int(os.environ.get("DEDUP_TTL_SECONDS", "43200"))
IGNORE_BOT_SENDERS = os.environ.get("IGNORE_BOT_SENDERS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
chat_last_trigger_time: dict[int, float] = {}
recent_alert_fingerprints: dict[str, float] = {}
pending_tasks: set[asyncio.Task] = set()


def load_keywords(path: str) -> list[str]:
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


def load_sender_blacklist(path: str = SENDER_BLACKLIST_FILE) -> set[str]:
    """
    Загружает usernames отправителей, которых нужно игнорировать.
    """
    with open(path, "r", encoding="utf-8") as file:
        return {line.strip().lstrip("@").lower() for line in file if line.strip()}


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


def normalize_text(text: str) -> str:
    """
    Нормализует текст для дедупликации и phrase matching.
    """
    return " ".join(text.casefold().split())


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    """
    Ищет совпадения по корням слов и по фразам.
    """
    normalized_text = normalize_text(text)
    root_keywords = [keyword for keyword in keywords if " " not in keyword]
    phrase_keywords = [normalize_text(keyword) for keyword in keywords if " " in keyword]

    matches: dict[str, str] = {}
    if root_keywords:
        for match in build_pattern(root_keywords).findall(text):
            matches[match.casefold()] = match

    for phrase in phrase_keywords:
        if phrase in normalized_text:
            matches[phrase] = phrase

    return sorted(matches.values(), key=str.lower)


def build_alert_fingerprint(chat_id: int, text: str) -> str:
    """
    Строит отпечаток сообщения для дедупликации.
    """
    payload = f"{chat_id}:{normalize_text(text)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def prune_recent_alerts(now: float) -> None:
    """
    Удаляет устаревшие записи из кэша дедупликации.
    """
    expired = [
        fingerprint
        for fingerprint, created_at in recent_alert_fingerprints.items()
        if now - created_at > DEDUP_TTL_SECONDS
    ]
    for fingerprint in expired:
        recent_alert_fingerprints.pop(fingerprint, None)


def should_skip_sender(sender, blacklist: set[str]) -> bool:
    """
    Определяет, нужно ли игнорировать отправителя.
    """
    username = (getattr(sender, "username", None) or "").lower()
    if username and username in blacklist:
        return True

    if IGNORE_BOT_SENDERS and getattr(sender, "bot", False):
        return True

    return False


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
    intent_matches: list[str],
    product_matches: list[str],
    message_link: str,
) -> str:
    """
    Формирует итоговое уведомление для отправки в Telegram.

    Сообщение включает чат, отправителя, текст, триггеры и ссылку.

    Args:
        chat_title (str): Название чата.
        sender_display (str): Отображаемое имя отправителя.
        text (str): Оригинальный текст сообщения.
        intent_matches (list[str]): Найденные сигналы намерения.
        product_matches (list[str]): Найденные предметные слова.
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
        f"🎯 Намерение: {', '.join(intent_matches)}\n"
        f"🧩 Предмет: {', '.join(product_matches)}\n\n"
        f"🔗 {message_link}"
    )


def track_background_task(task: asyncio.Task) -> None:
    """
    Следит за lifecycle отложенных задач.
    """
    pending_tasks.add(task)

    def _cleanup(done_task: asyncio.Task) -> None:
        pending_tasks.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            pass
        except Exception as error:
            print(f"Background task failed: {error}")

    task.add_done_callback(_cleanup)


async def process_message_later(chat_id: int, message_id: int) -> None:
    """
    Обрабатывает сообщение после задержки, чтобы отсекать автоудаляющийся спам.
    """
    await asyncio.sleep(MESSAGE_DELAY_SECONDS)

    source_chat_ids = load_source_chat_ids()
    if chat_id not in source_chat_ids:
        return

    message = await client.get_messages(chat_id, ids=message_id)
    if not message:
        return

    text = message.raw_text or ""
    if not text:
        return

    intent_keywords = load_keywords(INTENT_KEYWORDS_FILE)
    product_keywords = load_keywords(PRODUCT_KEYWORDS_FILE)
    negative_keywords = load_keywords(NEGATIVE_KEYWORDS_FILE)
    sender_blacklist = load_sender_blacklist()

    if not intent_keywords or not product_keywords:
        return

    sender = await message.get_sender()
    if should_skip_sender(sender, sender_blacklist):
        return

    negative_matches = match_keywords(text, negative_keywords)
    if negative_matches:
        return

    intent_matches = match_keywords(text, intent_keywords)
    if not intent_matches:
        return

    product_matches = match_keywords(text, product_keywords)
    if not product_matches:
        return

    now = time.time()
    prune_recent_alerts(now)

    fingerprint = build_alert_fingerprint(chat_id, text)
    if fingerprint in recent_alert_fingerprints:
        return

    last_chat_trigger = chat_last_trigger_time.get(chat_id, 0.0)
    if now - last_chat_trigger < COOLDOWN:
        return

    recent_alert_fingerprints[fingerprint] = now
    chat_last_trigger_time[chat_id] = now

    chat = await message.get_chat()

    chat_title = getattr(chat, "title", "Личный чат")
    sender_display = build_sender_display(sender)
    message_link = build_message_link(chat, chat_id, message.id)

    alert = build_alert_message(
        chat_title=chat_title,
        sender_display=sender_display,
        text=text,
        intent_matches=intent_matches,
        product_matches=product_matches,
        message_link=message_link,
    )

    await client.send_message(DEST_CHAT_ID, alert)
    print(alert)


@client.on(events.NewMessage)
async def handler(event) -> None:
    """
    Ставит новое сообщение в очередь на отложенную обработку.
    """
    source_chat_ids = load_source_chat_ids()
    if event.chat_id not in source_chat_ids:
        return

    task = asyncio.create_task(process_message_later(event.chat_id, event.id))
    track_background_task(task)


async def main() -> None:
    """
    Запускает Telegram-клиент и переводит его в режим прослушивания.
    """
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
