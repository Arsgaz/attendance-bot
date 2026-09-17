# Attendance Bot

DDD-сервис учёта посещаемости с клиентами Telegram и VK и двусторонней
синхронизацией с Google Sheets.

Подробное описание архитектуры, модели данных и процессов находится в
[PROJECT_DOCUMENTATION.md](./PROJECT_DOCUMENTATION.md).

Правила обработки данных и безопасной эксплуатации:

- [PRIVACY_POLICY.md](./PRIVACY_POLICY.md);
- [SECURITY.md](./SECURITY.md).

## Запуск окружения

```bash
cp .env.example .env
poetry install
PYTHONPATH=src poetry run python -m telegram_main
```

VK-клиент запускается отдельным процессом:

```bash
PYTHONPATH=src poetry run python -m vk_main
```

## Запуск через Docker Compose

Docker Compose одновременно запускает миграции, Telegram-бота, VK-бота,
worker синхронизации Google Sheets и сервис резервного копирования. `.env` и
каталог `secrets` подключаются только во время запуска и не копируются в image.

Worker сначала доставляет отметки бота в таблицу, затем раз в 60 секунд читает
явные ручные изменения `✓/+`, `Н`, `Б`, `У` обратно в БД. Очистка ячейки
удаляет существующую отметку с сохранением аудита.

Если нужно сохранить существующую локальную БД, один раз подготовьте runtime:

```bash
mkdir -p runtime
cp attendance.db runtime/attendance.db
```

Запуск всех компонентов:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f telegram-bot vk-bot worker backup
```

После `start_period` в `docker compose ps` все постоянные сервисы должны иметь
статус `healthy`. Healthcheck проверяет доступность БД и актуальную Alembic
revision. Для worker и backup дополнительно проверяется heartbeat рабочего
цикла; доступность Google API на readiness не влияет.

## Резервное копирование

Сервис `backup` раз в сутки создаёт консистентный gzip-снимок SQLite через
SQLite Backup API в каталоге `backups/`. Перед упаковкой выполняется
`PRAGMA integrity_check`. По умолчанию сохраняются семь последних снимков и по
одному снимку за четыре последние ISO-недели. Перезапуск backup-контейнера не
создаёт повторный снимок, пока не истёк `BACKUP_INTERVAL_SECONDS`; ручной запуск
всегда создаёт дополнительный архив.

Создать дополнительный снимок вручную:

```bash
docker compose run --rm backup python -m backup
```

Посмотреть архивы:

```bash
ls -lh backups
```

Восстановление выполняется только при остановленных процессах, работающих с БД:

```bash
docker compose stop telegram-bot vk-bot worker backup
docker compose run --rm backup python -m backup \
  --restore /backups/attendance-YYYYMMDDTHHMMSSZ.sqlite3.gz --yes
docker compose up -d telegram-bot vk-bot worker backup
```

Перед заменой БД команда автоматически создаёт архив `pre-restore-*` с текущим
состоянием. Восстанавливаемый файл также проходит `integrity_check`.

Остановка без удаления БД:

```bash
docker compose down
```

База хранится в `runtime/attendance.db`. Удаление каталога `runtime` удалит
локальные данные приложения. Для обновления структуры Google Sheets выполните:

```bash
docker compose run --rm telegram-bot python -m import_sheet
```

До добавления токена можно запускать доменные тесты:

```bash
poetry run pytest
poetry run ruff check src tests
```

## Миграции

История миграций объединена в одну начальную ревизию `ddb75d1bb7c0`. Она
предназначена для создания новой БД. Базу, созданную старыми ревизиями, нельзя
обновлять этой цепочкой напрямую: сначала сохраните резервную копию и либо
пересоздайте БД, либо отдельно сверяйте схему перед `alembic stamp`.

```bash
poetry run alembic upgrade head
poetry run alembic downgrade -1
poetry run alembic check
```

Новая миграция после изменения SQLAlchemy metadata:

```bash
poetry run alembic revision --autogenerate -m "описание изменения"
```

## Импорт структуры Google Sheets

1. Создайте Google service account и скачайте JSON-файл его credentials.
2. Выдайте email service account доступ на чтение тестовой таблицы.
3. Заполните `GOOGLE_SPREADSHEET_ID` и `GOOGLE_CREDENTIALS_FILE` в `.env`.
4. Примените миграции и запустите импорт:

```bash
poetry run alembic upgrade head
PYTHONPATH=src poetry run python -m import_sheet
```

Импорт создаёт или обновляет студентов, занятия и `sheet_mappings`. Значения
посещаемости из таблицы он не переносит. Повторный запуск идемпотентен, а
удалённые из импортированной структуры записи деактивируются без удаления
истории.

`sequence_number` у импортированного занятия — технический порядок строки
внутри даты. Он не означает номер пары и не должен показываться пользователю как
номер пары. Пустые строки журнала, в том числе выделенные серым, считаются
отсутствием занятия и не импортируются.

Поставить отметку можно в любое время: дата и условное время занятия не
ограничивают доступность операции. Свою отметку студент может изменить или
удалить через раздел «Мои отметки». Каждое изменение сохраняется в аудите и
отправляется в очередь синхронизации.

## Worker синхронизации

Обработать одну пачку очереди и завершиться:

```bash
PYTHONPATH=src poetry run python -m sync_worker --once
```

Запустить постоянный цикл:

```bash
PYTHONPATH=src poetry run python -m sync_worker
```

## Слои

- `domain` — сущности, value objects, policies и доменные события;
- `application` — команды, запросы и оркестрация сценариев;
- `port` — интерфейсы БД, UoW, времени и внешних сервисов;
- `adapter` — реализации портов;
- `presentation` — независимые Telegram- и VK-адаптеры интерфейса;
- `di` — composition root на Dishka.

## Внешние клиенты

Домен и application-слой используют универсальную идентичность
`provider + external_user_id`. Сейчас поддерживаются значения `telegram` и
`vk`. Числовые идентификаторы конкретной платформы преобразуются в строки на
границе presentation-адаптера.

Активные привязки хранятся в `external_accounts`. Один студент может иметь по
одной активной привязке для каждой платформы, то есть одновременно Telegram и
VK. Одна пара `provider + external_user_id` относится только к одному студенту.
Авторство посещаемости и аудит также хранят provider.
