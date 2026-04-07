# Telegram Keyword Monitor

Скрипт на `Telethon`, который отслеживает новые сообщения в выбранных Telegram-чатах и отправляет уведомление в другой чат, если видит релевантный запрос.

## Что делает проект

- слушает новые сообщения в заданном чате;
- проверяет сообщение по двум слоям: слова намерения и предметные слова;
- отбрасывает интро, вакансии, ботов и автоудаляющийся спам;
- отправляет уведомление в отдельный чат;
- защищает от повторных срабатываний задержкой, дедупликацией и cooldown.

## Когда это подходит

Проект подходит, если вы хотите:

- отслеживать сообщения в группе, канале или другом чате, к которому имеет доступ авторизованный Telegram-аккаунт;
- получать отдельные уведомления только по важным словам;
- держать решение на своем сервере без сложной инфраструктуры.

## Ограничения

- Скрипт работает от имени Telegram-аккаунта, авторизованного через `Telethon`.
- Аккаунт должен иметь доступ к исходному чату.
- Для круглосуточной работы нужен сервер или VPS.
- Нельзя публиковать `API_HASH`, `.env` и session-файлы в публичный доступ.

## Структура проекта

```text
telegram-keyword-monitor/
├── monitor.py
├── source_chats.txt
├── intent_keywords.txt
├── product_keywords.txt
├── negative_keywords.txt
├── sender_blacklist.txt
├── keywords.txt
├── .env.example
├── requirements.txt
├── .gitignore
├── telegram-keyword-monitor.service
└── README.md
```

## Требования

- Ubuntu или другой Linux-сервер
- Python 3.10+
- Telegram-аккаунт
- `api_id` и `api_hash` с [my.telegram.org](https://my.telegram.org)

## Быстрый старт

### 1. Подготовить сервер

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
mkdir -p ~/telegram-keyword-monitor
cd ~/telegram-keyword-monitor
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Склонировать или загрузить проект

Если используете Git:

```bash
git clone <YOUR_REPOSITORY_URL>
cd telegram-keyword-monitor
```

Если переносите файлы вручную, просто разместите содержимое репозитория в папке `~/telegram-keyword-monitor`.

### 3. Установить зависимости

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

Создайте рабочий `.env` на основе шаблона:

```bash
cp .env.example .env
```

Заполните `.env`:

```env
API_ID=12345678
API_HASH=your_api_hash
DEST_CHAT_ID=-5202871265
SESSION_NAME=server_monitor_session
COOLDOWN=10
SOURCE_CHATS_FILE=source_chats.txt
INTENT_KEYWORDS_FILE=intent_keywords.txt
PRODUCT_KEYWORDS_FILE=product_keywords.txt
NEGATIVE_KEYWORDS_FILE=negative_keywords.txt
SENDER_BLACKLIST_FILE=sender_blacklist.txt
MESSAGE_DELAY_SECONDS=60
DEDUP_TTL_SECONDS=43200
IGNORE_BOT_SENDERS=true
```

Описание параметров:

- `API_ID` и `API_HASH` - данные приложения Telegram API.
- `DEST_CHAT_ID` - ID чата, куда уходят уведомления.
- `SESSION_NAME` - имя session-файла Telethon.
- `COOLDOWN` - минимальная пауза между алертами в одном чате.
- `SOURCE_CHATS_FILE` - путь к файлу со списком source-чатов.
- `INTENT_KEYWORDS_FILE` - файл со словами намерения: ищу, нужен, куплю, в аренду.
- `PRODUCT_KEYWORDS_FILE` - файл с предметными словами: гирлянды, буквы, стойки и т.д.
- `NEGATIVE_KEYWORDS_FILE` - файл со стоп-словами для вакансий, интро и рекламы.
- `SENDER_BLACKLIST_FILE` - usernames отправителей, которых надо игнорировать.
- `MESSAGE_DELAY_SECONDS` - задержка перед проверкой сообщения.
- `DEDUP_TTL_SECONDS` - время, в течение которого одинаковый текст повторно не пересылается.
- `IGNORE_BOT_SENDERS` - игнорировать ли bot-аккаунты.

### 5. Заполнить словари

Основные файлы:

- `intent_keywords.txt` - намерение купить, арендовать, заказать, запросить смету
- `product_keywords.txt` - предметные слова по вашей номенклатуре
- `negative_keywords.txt` - стоп-слова для интро, вакансий и спама
- `sender_blacklist.txt` - отправители, которых нужно игнорировать

### 6. Первый запуск

```bash
source .venv/bin/activate
python monitor.py
```

При первом запуске Telegram попросит:

- номер телефона;
- код подтверждения;
- при необходимости пароль двухфакторной аутентификации.

После успешного входа рядом со скриптом появится session-файл. Его нельзя публиковать.

## Логика работы

1. Скрипт подключается к Telegram через `Telethon`.
2. Ждет новые сообщения через обработчик `events.NewMessage`.
3. Ставит новое сообщение в очередь на обработку с задержкой `MESSAGE_DELAY_SECONDS`.
4. Повторно читает сообщение и отбрасывает автоудаляющийся спам.
5. Игнорирует bot-отправителей и usernames из `sender_blacklist.txt`.
6. Ищет совпадения по словарям намерения и предмета.
7. Отбрасывает сообщения со стоп-словами из `negative_keywords.txt`.
8. Применяет дедупликацию и cooldown по чату.
9. Если фильтр пройден, отправляет уведомление в `DEST_CHAT_ID`.

## Автозапуск через systemd

В репозитории есть пример unit-файла: `telegram-keyword-monitor.service`.

Скопируйте его в systemd:

```bash
sudo cp telegram-keyword-monitor.service /etc/systemd/system/telegram-keyword-monitor.service
```

Проверьте пути внутри файла. По умолчанию используется домашняя директория вида `/home/<user>/telegram-keyword-monitor`.

После этого выполните:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-keyword-monitor
sudo systemctl start telegram-keyword-monitor
sudo systemctl status telegram-keyword-monitor
```

Если нужно, поправьте `User`, `WorkingDirectory`, `EnvironmentFile` и `ExecStart` под своего пользователя и путь.

## Как менять настройки

### Изменить фильтрацию

Отредактируйте:

- `intent_keywords.txt`
- `product_keywords.txt`
- `negative_keywords.txt`
- `sender_blacklist.txt`

### Изменить чаты

Отредактируйте `.env` или `source_chats.txt`:

- `source_chats.txt` - список чатов-источников, по одному ID на строку
- `DEST_CHAT_ID` - ID чата, куда уходят уведомления
- `COOLDOWN`, `SESSION_NAME`, `SOURCE_CHATS_FILE` - дополнительные настройки запуска
- `MESSAGE_DELAY_SECONDS`, `DEDUP_TTL_SECONDS`, `IGNORE_BOT_SENDERS` - антиспам и поведение фильтра

После изменения настроек при работе через `systemd` перезапустите сервис:

```bash
sudo systemctl restart telegram-keyword-monitor
```

## Безопасность

- не коммитьте `.env`;
- не коммитьте `*.session`;
- не передавайте `API_HASH` третьим лицам;
- используйте отдельный Telegram-аккаунт для мониторинга, если задача чувствительная.

## Публикация на GitHub

### Инициализация локального репозитория

```bash
git init
git add .
git commit -m "Initial commit"
```

### Привязка удаленного репозитория

```bash
git remote add origin https://github.com/<username>/telegram-keyword-monitor.git
git branch -M main
git push -u origin main
```

## Что можно улучшить дальше

- добавить логирование в файл;
- хранить ключевые слова в базе данных;
- добавить whitelist или blacklist чатов;
- отправлять уведомления сразу нескольким получателям;
- добавить веб-панель или Telegram-команды для управления словами.
