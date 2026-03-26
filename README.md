# Telegram Keyword Monitor

Скрипт на `Telethon`, который отслеживает новые сообщения в выбранном Telegram-чате и отправляет уведомление в другой чат, если находит одно из ключевых слов.

## Что делает проект

- слушает новые сообщения в заданном чате;
- проверяет текст на наличие ключевых слов из файла `keywords.txt`;
- отправляет уведомление в отдельный чат;
- защищает от повторных срабатываний коротким cooldown.

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
├── keywords.txt
├── source_chats.txt
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
```

Описание параметров:

- `API_ID` и `API_HASH` - данные приложения Telegram API.

Чат для уведомлений зашит прямо в коде `monitor.py`:

- `DEST_CHAT_ID = -5202871265`

Чаты-источники задаются в `source_chats.txt`, по одному ID на строку.

### 5. Заполнить ключевые слова

Файл `keywords.txt` содержит по одному слову на строку:

```text
заказ
заказы
клиент
смета
декор
оформление
```

Вы можете в любой момент редактировать этот файл и добавлять новые слова.

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
3. Загружает список разрешенных source-чатов из `source_chats.txt`.
4. Загружает список ключевых слов из `keywords.txt`.
5. Ищет все совпадения по регулярному выражению.
6. Если совпадения найдены, отправляет уведомление в `DEST_CHAT_ID`.
7. На повторные уведомления действует cooldown 10 секунд.

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

### Добавить или удалить ключевые слова

Отредактируйте `keywords.txt`.

### Изменить чаты

Отредактируйте `source_chats.txt` или `monitor.py`, если нужно сменить чат для уведомлений:

- `source_chats.txt` - список чатов-источников, по одному ID на строку
- `DEST_CHAT_ID` - ID чата, куда уходят уведомления

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
