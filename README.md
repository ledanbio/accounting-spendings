# Accounting Spendings Bot

Telegram-бот для учёта расходов и доходов с мультивалютной поддержкой.

## Стек

- Python 3.12, aiogram 3, SQLAlchemy 2 (async), Alembic
- PostgreSQL 16
- Docker + Docker Compose

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и заполните значения:

```bash
cp .env.example .env
```

2. Укажите `BOT_TOKEN` (получить у [@BotFather](https://t.me/BotFather)) и параметры БД в `.env`.

3. Соберите и запустите:

```bash
make build
make up
```

Миграции применяются автоматически при старте контейнера.

Команды `make` нужно выполнять **из корня репозитория**. Makefile передаёт Docker Compose флаг `--env-file .env`, чтобы значения `POSTGRES_USER` / `POSTGRES_PASSWORD` в сервисе `db` совпадали с `DB_USER` / `DB_PASSWORD`, которые читает бот. Без этого PostgreSQL мог инициализироваться с пользователем по умолчанию (`postgres`), а приложение — подключаться под `DB_USER` из `.env` (ошибка вида `password authentication failed`).

Если вы уже меняли `DB_USER` или `DB_PASSWORD` после первого запуска, данные в volume могли создаться со старыми учётными данными. Тогда остановите стек и удалите том БД: `make down-v`, затем снова `make up` (данные PostgreSQL будут потеряны).

## Команды бота

| Команда       | Описание                          |
|---------------|-----------------------------------|
| `/start`      | Регистрация и приветствие         |
| `/help`       | Список команд                     |
| `/add`        | Добавить доход или расход         |
| `/balance`    | Текущий баланс по валютам         |
| `/history`    | История транзакций с пагинацией   |
| `/categories` | Управление категориями            |
| `/settings`   | Смена валюты по умолчанию         |

## Makefile

```bash
make build      # Собрать образы
make up         # Запустить в фоне
make down       # Остановить
make down-v     # Остановить и удалить volume БД (сброс данных)
make logs       # Логи бота
make restart    # Перезапуск бота
make migrate    # Применить миграции вручную
make revision m="описание"  # Создать новую миграцию
```

## Структура проекта

```
src/
├── config.py           # Настройки из .env
├── main.py             # Точка входа
├── database/           # ORM-модели и сессия
├── bot/                # Telegram-бот (handlers, keyboards, states, middlewares)
└── services/           # Бизнес-логика (переиспользуется для будущего API)
```
